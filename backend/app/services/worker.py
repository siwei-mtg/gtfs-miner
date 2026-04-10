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
from ..db.database import SessionLocal
from ..db.models import Project
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


def run_project_task_sync(project_id: str, zip_path: str, parameters: dict, loop: asyncio.AbstractEventLoop):
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
        future = asyncio.run_coroutine_threadsafe(
            manager.broadcast_to_project(project_id, message), loop
        )
        try:
            future.result(timeout=5)
        except Exception:
            pass  # Never let a WS failure kill the pipeline

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
