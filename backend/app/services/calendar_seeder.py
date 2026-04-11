"""
calendar_seeder.py — 日历数据播种与同步

两个数据源：
  1. Calendrier.xls（本地文件，Phase 0 历史数据，2015-2050）
  2. api.gouv.fr（官方 API，学区假期 + 法定节假日，优先级最高）

入口函数：
  - seed_from_xls(db)   : 从本地 XLS 初始播种
  - sync_from_api(db)   : 从官方 API 拉取最新数据并 upsert
  - ensure_calendar(db) : 若 calendar_dates 为空，自动执行播种 + 同步
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
import urllib.request
import json

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..db.models import CalendarDate

logger = logging.getLogger(__name__)

_DEFAULT_XLS = Path(__file__).parent / "gtfs_core" / "resources" / "Calendrier.xls"

# api.gouv.fr endpoints
_API_VACANCES = "https://calendrier.api.gouv.fr/vacances/scolaires/zones.json"
_API_FERIES   = "https://calendrier.api.gouv.fr/jours-feries/metropole.json"


def _fetch_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode())


def seed_from_xls(db: Session, xls_path: Optional[Path] = None) -> int:
    """
    从 Calendrier.xls 初始播种 calendar_dates 表。

    读取 Date_GTFS, Ferie, Vacances_A, Vacances_B, Vacances_C 列，
    upsert 到 calendar_dates（INSERT OR REPLACE，SQLite）。
    返回写入行数。
    """
    path = xls_path or _DEFAULT_XLS
    if not path.exists():
        logger.warning("Calendrier.xls introuvable : %s — seed ignoré", path)
        return 0

    df = pd.read_excel(
        path,
        usecols=["Date_GTFS", "Ferie", "Vacances_A", "Vacances_B", "Vacances_C"],
    )
    df["Date_GTFS"] = df["Date_GTFS"].astype(str).str.strip()

    count = 0
    for _, row in df.iterrows():
        db.execute(
            text(
                "INSERT OR REPLACE INTO calendar_dates "
                "(date_gtfs, is_holiday, zone_a, zone_b, zone_c, updated_at) "
                "VALUES (:d, :h, :a, :b, :c, datetime('now'))"
            ),
            {
                "d": row["Date_GTFS"],
                "h": bool(row["Ferie"]),
                "a": bool(row["Vacances_A"]),
                "b": bool(row["Vacances_B"]),
                "c": bool(row["Vacances_C"]),
            },
        )
        count += 1

    db.commit()
    logger.info("seed_from_xls : %d lignes écrites", count)
    return count


def sync_from_api(db: Session) -> int:
    """
    从 api.gouv.fr 拉取最新的法定节假日和学区假期数据并 upsert。

    API 数据优先级最高（覆盖 XLS 播种数据）。
    返回更新行数。
    """
    count = 0

    # ── 1. Jours fériés ───────────────────────────────────────────────────
    try:
        feries_raw = _fetch_json(_API_FERIES)
        # Format: {"YYYY-MM-DD": "Nom du jour", ...}
        for date_str, name in feries_raw.items():
            date_gtfs = date_str.replace("-", "")
            db.execute(
                text(
                    "INSERT OR REPLACE INTO calendar_dates "
                    "(date_gtfs, is_holiday, holiday_name, zone_a, zone_b, zone_c, updated_at) "
                    "VALUES (:d, 1, :n, "
                    "COALESCE((SELECT zone_a FROM calendar_dates WHERE date_gtfs=:d), 0), "
                    "COALESCE((SELECT zone_b FROM calendar_dates WHERE date_gtfs=:d), 0), "
                    "COALESCE((SELECT zone_c FROM calendar_dates WHERE date_gtfs=:d), 0), "
                    "datetime('now'))"
                ),
                {"d": date_gtfs, "n": name},
            )
            count += 1
    except Exception as exc:
        logger.warning("sync_from_api : échec jours fériés — %s", exc)

    # ── 2. Vacances scolaires ─────────────────────────────────────────────
    try:
        vacances_raw = _fetch_json(_API_VACANCES)
        # Format: list of {"zones": "Zone A", "date_debut": "...", "date_fin": "..."}
        zone_map = {"Zone A": "zone_a", "Zone B": "zone_b", "Zone C": "zone_c"}

        for entry in vacances_raw:
            zone_label = entry.get("zones", "")
            zone_col   = zone_map.get(zone_label)
            if not zone_col:
                continue

            debut = date.fromisoformat(entry["date_debut"][:10])
            fin   = date.fromisoformat(entry["date_fin"][:10])
            cur   = debut
            while cur <= fin:
                date_gtfs = cur.strftime("%Y%m%d")
                db.execute(
                    text(
                        f"INSERT INTO calendar_dates "
                        f"(date_gtfs, is_holiday, zone_a, zone_b, zone_c, updated_at) "
                        f"VALUES (:d, "
                        f"COALESCE((SELECT is_holiday FROM calendar_dates WHERE date_gtfs=:d), 0), "
                        f"CASE WHEN :za THEN 1 ELSE COALESCE((SELECT zone_a FROM calendar_dates WHERE date_gtfs=:d), 0) END, "
                        f"CASE WHEN :zb THEN 1 ELSE COALESCE((SELECT zone_b FROM calendar_dates WHERE date_gtfs=:d), 0) END, "
                        f"CASE WHEN :zc THEN 1 ELSE COALESCE((SELECT zone_c FROM calendar_dates WHERE date_gtfs=:d), 0) END, "
                        f"datetime('now')) "
                        f"ON CONFLICT(date_gtfs) DO UPDATE SET "
                        f"{zone_col}=1, updated_at=datetime('now')"
                    ),
                    {
                        "d":  date_gtfs,
                        "za": zone_col == "zone_a",
                        "zb": zone_col == "zone_b",
                        "zc": zone_col == "zone_c",
                    },
                )
                count += 1
                cur += timedelta(days=1)
    except Exception as exc:
        logger.warning("sync_from_api : échec vacances scolaires — %s", exc)

    db.commit()
    logger.info("sync_from_api : %d lignes mises à jour", count)
    return count


def ensure_calendar(db: Session) -> None:
    """
    Vérifie que calendar_dates contient des données.
    Si la table est vide, déclenche seed_from_xls() puis sync_from_api().
    """
    row = db.execute(text("SELECT COUNT(*) FROM calendar_dates")).scalar()
    if row and row > 0:
        return

    logger.info("calendar_dates vide — démarrage du seeding initial")
    n_xls = seed_from_xls(db)
    logger.info("seed_from_xls terminé : %d lignes", n_xls)

    try:
        n_api = sync_from_api(db)
        logger.info("sync_from_api terminé : %d mises à jour", n_api)
    except Exception as exc:
        logger.warning("sync_from_api échoué (données XLS utilisées) : %s", exc)
