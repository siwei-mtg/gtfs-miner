"""
worker.py — GTFS Miner 后台处理引擎包装器 (Phase 0)

将 gtfs_core.pipeline 的 7 个步骤逐一调用，同时通过 WebSocket 向客户端实时推送进度。
运行在 FastAPI BackgroundTasks 的后台线程中（非异步）。
"""
import asyncio
import time
import zipfile
import traceback
import shutil
from pathlib import Path
from sqlalchemy.orm import Session

import numpy as np
import pandas as pd

from ..core.config import settings, PROJECT_DIR, TEMP_DIR
from ..db.database import SessionLocal, engine as _db_engine
from ..db.models import Project
from ..db import result_models as _r  # noqa: F401 — registers result tables with Base.metadata
from ..api.websockets.progress import manager

# Import individual pipeline functions (not main, to allow step-by-step progress)
from .gtfs_core.pipeline import build_dates_table, DEFAULT_TYPE_VAC, CSV_OPTS
from .gtfs_core.calendar_provider import LocalXlsCalendarProvider
from .gtfs_core.gtfs_norm import gtfs_normalize, ligne_generate
from .gtfs_core.gtfs_reader import read_gtfs_zip
from .gtfs_core.gtfs_spatial import ag_ap_generate_reshape
from .gtfs_core.gtfs_generator import (
    itineraire_generate, itiarc_generate, course_generate,
    sl_generate, service_date_generate, service_jour_type_generate,
    nb_passage_ag, nb_course_ligne, caract_par_sl,
    kcc_course_ligne, kcc_course_sl, passage_arc,
)
from .gtfs_core.gtfs_export import (
    MEF_course, MEF_iti, MEF_iti_arc,
    MEF_ligne, MEF_serdate, MEF_servjour,
)

# HPM/HPS as time fractions — overridable from project parameters
def _parse_time_frac(hhmm: str) -> float:
    """'07:30' -> 7.5/24"""
    h, m = hhmm.split(":")
    return (int(h) + int(m) / 60) / 24


# ── CSV → DB mapping ──────────────────────────────────────────────────────────
# (csv_filename, id_vars_for_melt_or_None, value_column_name_or_None)
_CSV_TO_TABLE: dict[str, tuple] = {
    "A_1_Arrets_Generiques.csv":     ("result_a1_arrets_generiques",     None, None),
    "A_2_Arrets_Physiques.csv":      ("result_a2_arrets_physiques",      None, None),
    "B_1_Lignes.csv":                ("result_b1_lignes",                None, None),
    "B_2_Sous_Lignes.csv":           ("result_b2_sous_lignes",           None, None),
    "C_1_Courses.csv":               ("result_c1_courses",               None, None),
    "C_2_Itineraire.csv":            ("result_c2_itineraire",            None, None),
    "C_3_Itineraire_Arc.csv":        ("result_c3_itineraire_arc",        None, None),
    "D_1_Service_Dates.csv":         ("result_d1_service_dates",         None, None),
    "D_2_Service_Jourtype.csv":      ("result_d2_service_jourtype",      None, None),
    # pivot tables: wide columns "1"–"7" → long (type_jour, metric)
    "E_1_Nombre_Passage_AG.csv":     ("result_e1_passage_ag",
                                      ["id_ag_num", "stop_name", "stop_lat", "stop_lon"], "nb_passage"),
    "E_4_Nombre_Passage_Arc.csv":    ("result_e4_passage_arc",
                                      ["id_ag_num_a", "id_ag_num_b"], "nb_passage"),
    "F_1_Nombre_Courses_Lignes.csv": ("result_f1_nb_courses_lignes",
                                      ["id_ligne_num", "route_short_name", "route_long_name"], "nb_course"),
    "F_2_Caract_SousLignes.csv":     ("result_f2_caract_sous_lignes",    None, None),
    "F_3_KCC_Lignes.csv":            ("result_f3_kcc_lignes",
                                      ["id_ligne_num", "route_short_name", "route_long_name"], "kcc"),
    "F_4_KCC_Sous_Ligne.csv":        ("result_f4_kcc_sous_lignes",
                                      ["sous_ligne", "id_ligne_num", "route_short_name", "route_long_name"], "kcc"),
}


def _persist_results_to_db(project_id: str, out_dir: Path, db: Session) -> None:
    """Read each output CSV and bulk-insert into the corresponding result table.

    Idempotent: previous rows for *project_id* are deleted before insertion.
    Only columns present in the target table are written (extra CSV columns are dropped).
    Pivot tables (E_1, E_4, F_1, F_3, F_4) are melted to long format first.
    """
    from sqlalchemy import text, inspect as sa_inspect

    # Use the engine the session is bound to so tests can redirect to an in-memory DB.
    _engine = getattr(db, "bind", None) or _db_engine

    for csv_name, (table_name, id_cols, val_col) in _CSV_TO_TABLE.items():
        csv_path = out_dir / csv_name
        if not csv_path.exists():
            continue

        df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig")

        # Melt pivot tables (wide Type_Jour columns → long)
        if id_cols is not None:
            pivot_cols = [c for c in df.columns if str(c).isdigit()]
            keep = [c for c in id_cols if c in df.columns]
            if keep and pivot_cols:
                df = df[keep + pivot_cols].melt(
                    id_vars=keep, var_name="type_jour", value_name=val_col
                )
                df["type_jour"] = df["type_jour"].astype(int)

        # Idempotency: clear previous results for this project
        db.execute(text(f"DELETE FROM {table_name} WHERE project_id = :pid"),
                   {"pid": project_id})
        db.commit()

        df["project_id"] = project_id

        # Drop columns not present in the target table (robustness against CSV extras)
        table_cols = {c["name"] for c in sa_inspect(_engine).get_columns(table_name)}
        df = df[[c for c in df.columns if c in table_cols]]

        df.to_sql(table_name, _engine, if_exists="append", index=False)


def run_project_task_sync(project_id: str, zip_path: str, parameters: dict, loop: asyncio.AbstractEventLoop = None):
    """
    Sync function intended to run in a FastAPI BackgroundTask.
    Calls each pipeline step individually so that WebSocket progress can be sent after each one.
    """
    db: Session = SessionLocal()
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        db.close()
        return

    project.status = "processing"
    db.commit()

    start_time = time.time()

    def send_progress(step: str, status: str = "processing", error: str = None):
        elapsed = round(time.time() - start_time, 2)
        message = {
            "project_id": project_id,
            "status": status,
            "step": step,
            "time_elapsed": elapsed,
            "error": error,
        }
        if loop is not None:
            # BackgroundTasks mode (dev/test — no Redis)
            future = asyncio.run_coroutine_threadsafe(
                manager.broadcast_to_project(project_id, message), loop
            )
            try:
                future.result(timeout=5)
            except Exception:
                pass  # Never let a WS failure kill the pipeline
        else:
            # Celery mode: publish to Redis (silent failure when Redis absent)
            try:
                import redis as _redis
                import json as _json
                r = _redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
                r.publish(f"progress:{project_id}", _json.dumps(message))
                r.close()
            except Exception:
                pass

    # Resolve processing parameters
    hpm = (_parse_time_frac(parameters.get("hpm_debut", "07:00")),
           _parse_time_frac(parameters.get("hpm_fin", "09:00")))
    hps = (_parse_time_frac(parameters.get("hps_debut", "17:00")),
           _parse_time_frac(parameters.get("hps_fin", "19:30")))
    vacances = parameters.get("vacances", "A")
    type_vac_map = {
        "A": "Type_Jour_Vacances_A",
        "B": "Type_Jour_Vacances_B",
        "C": "Type_Jour_Vacances_C",
        "全部": "Type_Jour",
    }
    type_vac = type_vac_map.get(vacances, DEFAULT_TYPE_VAC)

    out_dir = PROJECT_DIR / project.tenant_id / project_id / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    send_progress("[1/7] 读取与解压 GTFS 文件")

    try:
        # ── 1. Load raw GTFS ──────────────────────────────────────────────
        zip_path_obj = Path(zip_path)
        raw_dict = read_gtfs_zip(zip_path_obj)
        if not raw_dict:
            raise ValueError("No GTFS .txt tables found in the uploaded ZIP.")
        tables_found = list(raw_dict.keys())

        send_progress(f"[2/7] 标准化 GTFS 表（已加载：{', '.join(tables_found)}）")

        # ── 2. Normalize ──────────────────────────────────────────────────
        normed = gtfs_normalize(raw_dict)
        n_stops  = len(normed['stops'])
        n_routes = len(normed['routes'])
        n_trips  = len(normed['trips'])

        send_progress(f"[3/7] 空间聚类生成站点映射（{n_stops} 停靠站，{n_routes} 线路，{n_trips} 班次）")

        # ── 3. Spatial clustering (A_1 / A_2) ────────────────────────────
        AP, AG, marker = ag_ap_generate_reshape(normed['stops'])
        AG.to_csv(out_dir / "A_1_Arrets_Generiques.csv", **CSV_OPTS)
        AP.to_csv(out_dir / "A_2_Arrets_Physiques.csv",  **CSV_OPTS)

        send_progress(f"[4/7] 生成行程、弧段与班次数据（聚类方式：{marker}，{len(AG)} AG / {len(AP)} AP）")

        # ── 4. Itinerary, arcs & courses (C_1 / C_2 / C_3) ──────────────
        lignes         = ligne_generate(normed['routes'])
        itineraire     = itineraire_generate(normed['stop_times'], AP, normed['trips'])
        itineraire_arc = itiarc_generate(itineraire, AG)
        courses        = course_generate(itineraire, itineraire_arc)

        courses_export    = MEF_course(courses, normed['trip_id_coor'])
        itineraire_export = MEF_iti(itineraire, courses)
        iti_arc_export    = MEF_iti_arc(itineraire_arc, courses)

        courses_export.to_csv(out_dir    / "C_1_Courses.csv",       **CSV_OPTS)
        itineraire_export.to_csv(out_dir / "C_2_Itineraire.csv",    **CSV_OPTS)
        iti_arc_export.to_csv(out_dir    / "C_3_Itineraire_Arc.csv",**CSV_OPTS)

        send_progress(f"[5/7] 生成线路与子线路（{len(courses)} 班次，{len(itineraire_arc)} 弧段）")

        # ── 5. Lignes & sous-lignes (B_1 / B_2) ─────────────────────────
        sous_ligne    = sl_generate(courses, AG, lignes)
        lignes_export = MEF_ligne(lignes, courses_export, AG)

        lignes_export.to_csv(out_dir / "B_1_Lignes.csv",      **CSV_OPTS)
        sous_ligne.to_csv(out_dir    / "B_2_Sous_Lignes.csv", **CSV_OPTS)

        send_progress(f"[6/7] 生成服务日期与日类型（{len(lignes_export)} 线路，{len(sous_ligne)} 子线路）")

        # ── 6. Service dates (D_1 / D_2) ─────────────────────────────────
        Dates = build_dates_table(normed['calendar'], normed['calendar_dates'])
        Dates = LocalXlsCalendarProvider().enrich(Dates)  # inject Type_Jour_Vacances_*
        service_dates, msg = service_date_generate(
            normed['calendar'], normed['calendar_dates'], Dates
        )

        # Graceful fallback: provider may not cover all dates (e.g. XLS absent).
        if type_vac not in service_dates.columns:
            type_vac = "Type_Jour"
        
        service_jour_type = service_jour_type_generate(service_dates, courses, type_vac)

        MEF_serdate(service_dates, normed['ser_id_coor']).to_csv(
            out_dir / "D_1_Service_Dates.csv", **CSV_OPTS)
        MEF_servjour(service_jour_type, normed['route_id_coor'], normed['ser_id_coor'], type_vac).to_csv(
            out_dir / "D_2_Service_Jourtype.csv", **CSV_OPTS)

        send_progress(f"[7/7] 计算通过次数与 KCC 指标（{msg}）")

        # ── 7. Passage counts & KCC (E_1 / E_4 / F_1–F_4) ───────────────
        pnode = AG[['id_ag_num', 'stop_name', 'stop_lon', 'stop_lat']].rename(
            columns={'id_ag_num': 'NO', 'stop_name': 'NAME', 'stop_lon': 'LON', 'stop_lat': 'LAT'}
        )

        nb_passage_ag(service_jour_type, itineraire_export, AG, type_vac).to_csv(
            out_dir / "E_1_Nombre_Passage_AG.csv", **CSV_OPTS)
        passage_arc(iti_arc_export, service_jour_type, pnode, type_vac).to_csv(
            out_dir / "E_4_Nombre_Passage_Arc.csv", **CSV_OPTS)
        nb_course_ligne(service_jour_type, courses_export, type_vac, lignes_export).to_csv(
            out_dir / "F_1_Nombre_Courses_Lignes.csv", **CSV_OPTS)
        caract_par_sl(service_jour_type, courses_export, hpm, hps, type_vac, sous_ligne).to_csv(
            out_dir / "F_2_Caract_SousLignes.csv", **CSV_OPTS)
        kcc_course_ligne(service_jour_type, courses_export, type_vac, lignes_export, False).to_csv(
            out_dir / "F_3_KCC_Lignes.csv", **CSV_OPTS)
        kcc_course_sl(service_jour_type, courses_export, type_vac, sous_ligne, False).to_csv(
            out_dir / "F_4_KCC_Sous_Ligne.csv", **CSV_OPTS)

        # ── Cleanup temp zip ─────────────────────────────────────────────
        zip_path_obj.unlink(missing_ok=True)

        # ── Step 8: persist CSV results to DB ────────────────────────────
        send_progress("[8/8] 将结果写入数据库")
        _persist_results_to_db(project_id, out_dir, db)

        # ── Mark as completed ─────────────────────────────────────────────
        project.status = "completed"
        db.commit()

        elapsed = round(time.time() - start_time, 2)
        send_progress(f"处理完成（总耗时 {elapsed} 秒）", status="completed")

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        project.status = "failed"
        project.error_message = error_msg[:4000]  # SQLite TEXT column guard
        db.commit()
        send_progress("处理失败", status="failed", error=str(e))

    finally:
        db.close()


# ── Celery task wrapper ────────────────────────────────────────────────────────
from app.celery_app import celery  # noqa: E402 — imported after module-level code


@celery.task(bind=True, name="gtfs_miner.process_project")
def process_project_task(self, project_id: str, zip_path: str, parameters: dict):
    """Celery-dispatched version of the pipeline (no event loop — uses Redis publish)."""
    run_project_task_sync(project_id, zip_path, parameters, loop=None)
