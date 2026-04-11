"""
calendar_provider.py — CalendarProvider 协议及实现

定义日历数据的抽象接口（DIP）：
  - pipeline / worker 依赖 CalendarProvider 协议，不依赖具体数据源。
  - LocalXlsCalendarProvider：Phase 0，从 resources/Calendrier.xls 读取并转换为整数编码。
  - DBCalendarProvider：Phase 1，从 SQLite/Supabase 的 calendar_dates 表查询。
  - NullCalendarProvider：不添加假期列，用于测试或没有外部日历时的降级。

Day-type 整数编码（11 种）：
  1–7  = Lundi_Scolaire … Dimanche_Scolaire（学期内，与 Type_Jour 一致）
  8    = Semaine_Vacances（学期假期内的工作日，周一至周五）
  9    = Samedi_Vacances
  10   = Dimanche_Vacances
  11   = Ferie（法定节假日）
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

import pandas as pd

# 资源文件路径（仅 LocalXlsCalendarProvider 知晓此路径）
_DEFAULT_XLS = Path(__file__).parent / "resources" / "Calendrier.xls"

_VAC_COLS = ["Type_Jour_Vacances_A", "Type_Jour_Vacances_B", "Type_Jour_Vacances_C"]

# Mapping des étiquettes string de l'XLS vers l'encodage entier normalisé.
# Doit rester en phase avec la logique de DBCalendarProvider._compute_type_vac().
TYPE_JOUR_VAC_LABELS: dict[str, int] = {
    "Lundi_Scolaire":    1,
    "Mardi_Scolaire":    2,
    "Mercredi_Scolaire": 3,
    "Jeudi_Scolaire":    4,
    "Vendredi_Scolaire": 5,
    "Samedi_Scolaire":   6,
    "Dimanche_Scolaire": 7,
    "Semaine_Vacances":  8,
    "Samedi_Vacances":   9,
    "Dimanche_Vacances": 10,
    "Ferie":             11,
}


@runtime_checkable
class CalendarProvider(Protocol):
    """
    为 Dates DataFrame 注入法国学区假期分类列。

    调用方（run_pipeline / worker）仅依赖此协议，不依赖具体实现。
    实现方可以是本地文件、SQLite、Supabase 或任何数据源。
    """

    def enrich(self, dates: pd.DataFrame) -> pd.DataFrame:
        """
        Input:  dates — [Date_GTFS(int32), Type_Jour, Semaine, Mois, Annee]
        Output: dates + [Type_Jour_Vacances_A, Type_Jour_Vacances_B, Type_Jour_Vacances_C]
                列值为整数（TYPE_JOUR_VAC_LABELS 编码）。
                未匹配的日期对应列为 NaN（下游已有容错处理）。
        """
        ...


class LocalXlsCalendarProvider:
    """
    Phase 0 实现：从 resources/Calendrier.xls 读取法国假期分类。

    - 文件不存在时静默降级（返回原 dates，不添加假期列）。
    - XLS 中的字符串标签（如 "Lundi_Scolaire"）在 enrich() 中映射为整数编码，
      使下游 pivot/melt 逻辑（依赖数字列名）正常工作。
    """

    def __init__(self, xls_path: Optional[Path] = None) -> None:
        self._path = xls_path or _DEFAULT_XLS
        self._cache: Optional[pd.DataFrame] = None  # 延迟加载，避免启动时 I/O

    def _load(self) -> Optional[pd.DataFrame]:
        if self._cache is not None:
            return self._cache
        if not self._path.exists():
            return None
        ref = pd.read_excel(self._path, usecols=["Date_GTFS"] + _VAC_COLS)
        ref["Date_GTFS"] = pd.to_numeric(ref["Date_GTFS"], errors="coerce").astype("Int32")
        ref = ref.dropna(subset=["Date_GTFS"])
        # Convertir les étiquettes string en entiers normalisés
        for col in _VAC_COLS:
            if col in ref.columns:
                ref[col] = ref[col].map(TYPE_JOUR_VAC_LABELS)
        self._cache = ref
        return self._cache

    def enrich(self, dates: pd.DataFrame) -> pd.DataFrame:
        ref = self._load()
        if ref is None:
            return dates  # 降级：无假期列，下游 type_vac fallback 保护
        enriched = dates.merge(ref, on="Date_GTFS", how="left")
        return enriched


class DBCalendarProvider:
    """
    Phase 1 实现：从 SQLite/Supabase 的 calendar_dates 表查询假期分类。

    接受 SQLAlchemy Session，查询 calendar_dates 表，根据 zone_a/b/c 和
    is_holiday 布尔标志计算整数编码的 Type_Jour_Vacances_A/B/C 列。
    """

    def __init__(self, session) -> None:
        self._session = session

    @staticmethod
    def _compute_type_vac(type_jour: int, zone_holiday: bool, is_holiday: bool) -> int:
        """
        根据基础 day-of-week（1–7）、学区假期标志和法定节假日标志计算 vacation type code。
        与 TYPE_JOUR_VAC_LABELS 保持一致。
        """
        if is_holiday:
            return 11  # Ferie
        if zone_holiday:
            if type_jour in (1, 2, 3, 4, 5):
                return 8   # Semaine_Vacances
            elif type_jour == 6:
                return 9   # Samedi_Vacances
            else:
                return 10  # Dimanche_Vacances
        return type_jour  # Lundi_Scolaire … Dimanche_Scolaire

    def enrich(self, dates: pd.DataFrame) -> pd.DataFrame:
        if dates.empty:
            for col in _VAC_COLS:
                dates[col] = pd.NA
            return dates

        date_min = int(dates["Date_GTFS"].min())
        date_max = int(dates["Date_GTFS"].max())

        from sqlalchemy import text
        rows = self._session.execute(
            text(
                "SELECT date_gtfs, is_holiday, zone_a, zone_b, zone_c "
                "FROM calendar_dates "
                "WHERE CAST(date_gtfs AS INTEGER) BETWEEN :dmin AND :dmax"
            ),
            {"dmin": date_min, "dmax": date_max},
        ).fetchall()

        if not rows:
            return dates  # 降级：DB 无数据，下游 fallback 处理

        ref = pd.DataFrame(rows, columns=["Date_GTFS", "is_holiday", "zone_a", "zone_b", "zone_c"])
        ref["Date_GTFS"] = pd.to_numeric(ref["Date_GTFS"], errors="coerce").astype("Int32")

        enriched = dates.merge(ref, on="Date_GTFS", how="left")

        for col, zone_col in zip(_VAC_COLS, ["zone_a", "zone_b", "zone_c"]):
            enriched[col] = enriched.apply(
                lambda r, zc=zone_col: self._compute_type_vac(
                    int(r["Type_Jour"]),
                    bool(r[zc]) if pd.notna(r[zc]) else False,
                    bool(r["is_holiday"]) if pd.notna(r["is_holiday"]) else False,
                ),
                axis=1,
            ).astype("Int8")

        enriched = enriched.drop(columns=["is_holiday", "zone_a", "zone_b", "zone_c"])
        return enriched


class NullCalendarProvider:
    """
    空实现：不添加任何假期列。
    用于单元测试或明确不需要假期分类的场景。
    """

    def enrich(self, dates: pd.DataFrame) -> pd.DataFrame:
        return dates
