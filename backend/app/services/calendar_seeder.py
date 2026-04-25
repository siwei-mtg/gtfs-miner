"""
calendar_seeder.py — 日历数据播种与同步

两个数据源：
  1. Calendrier.xls（本地文件，Phase 0 历史数据，2015-2050）
  2. api.gouv.fr（官方 API，学区假期 + 法定节假日，优先级最高）

入口函数：
  - seed_from_xls(db)   : 从本地 XLS 初始播种
  - sync_from_api(db)   : 从官方 API 拉取最新数据并 upsert
  - ensure_calendar(db) : 若 calendar_dates 为空，自动执行播种 + 同步

实现说明：所有写入走 ORM 而非 raw SQL，以保持 SQLite / PostgreSQL 双向兼容
（之前用 `INSERT OR REPLACE` / `datetime('now')` 是 SQLite 专属，Postgres 不接受）。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import urllib.request
import json

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

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

    依赖 `ensure_calendar` 的空表前置检查 — 此函数仅做纯 INSERT，不 upsert，
    所以 dialect-agnostic 且适合大批量（XLS 含约 12 000 行 / 35 年覆盖）。
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

    now = datetime.utcnow()
    rows = [
        CalendarDate(
            date_gtfs=row["Date_GTFS"],
            is_holiday=bool(row["Ferie"]),
            zone_a=bool(row["Vacances_A"]),
            zone_b=bool(row["Vacances_B"]),
            zone_c=bool(row["Vacances_C"]),
            updated_at=now,
        )
        for _, row in df.iterrows()
    ]
    db.bulk_save_objects(rows)
    db.commit()
    logger.info("seed_from_xls : %d lignes écrites", len(rows))
    return len(rows)


def _get_or_create(db: Session, date_gtfs: str) -> CalendarDate:
    obj = db.get(CalendarDate, date_gtfs)
    if obj is None:
        obj = CalendarDate(date_gtfs=date_gtfs)
        db.add(obj)
    return obj


def sync_from_api(db: Session) -> int:
    """
    从 api.gouv.fr 拉取最新的法定节假日和学区假期数据并 upsert。

    API 数据优先级最高（覆盖 XLS 播种数据）。每条记录走 ORM read-modify-write，
    总写入量有限（一年 ~50 fériés + 学区假期几十天），性能可接受。
    返回更新行数。
    """
    count = 0
    now = datetime.utcnow()

    # ── 1. Jours fériés ───────────────────────────────────────────────────
    try:
        feries_raw = _fetch_json(_API_FERIES)
        # Format: {"YYYY-MM-DD": "Nom du jour", ...}
        for date_str, name in feries_raw.items():
            date_gtfs = date_str.replace("-", "")
            obj = _get_or_create(db, date_gtfs)
            obj.is_holiday = True
            obj.holiday_name = name
            obj.updated_at = now
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
                obj = _get_or_create(db, date_gtfs)
                # OR with existing flag — preserves any zone already set by
                # previous API entries or XLS seed.
                setattr(obj, zone_col, True)
                obj.updated_at = now
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
