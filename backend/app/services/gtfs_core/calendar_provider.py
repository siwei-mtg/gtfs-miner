"""
calendar_provider.py — CalendarProvider 协议及 Phase 0 本地实现

定义日历数据的抽象接口（DIP）：
  - pipeline / worker 依赖 CalendarProvider 协议，不依赖具体数据源。
  - LocalXlsCalendarProvider：Phase 0，从 resources/Calendrier.xls 读取。
  - NullCalendarProvider：不添加假期列，用于测试或没有外部日历时的降级。

Phase 1 迁移路径：实现 DBCalendarProvider(session)，从 SQLite/Supabase 查询，
替换 worker.py 中的 LocalXlsCalendarProvider，pipeline 逻辑无需任何修改。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

import pandas as pd

# 资源文件路径（仅 LocalXlsCalendarProvider 知晓此路径）
_DEFAULT_XLS = Path(__file__).parent / "resources" / "Calendrier.xls"

_VAC_COLS = ["Type_Jour_Vacances_A", "Type_Jour_Vacances_B", "Type_Jour_Vacances_C"]


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
                未匹配的日期对应列为 NaN（下游已有容错处理）。
        """
        ...


class LocalXlsCalendarProvider:
    """
    Phase 0 实现：从 resources/Calendrier.xls 读取法国假期分类。

    - 文件不存在时静默降级（返回原 dates，不添加假期列）。
    - 数据范围不覆盖目标日期时，对应行保留 NaN（下游 type_vac fallback 处理）。
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
        self._cache = ref.dropna(subset=["Date_GTFS"])
        return self._cache

    def enrich(self, dates: pd.DataFrame) -> pd.DataFrame:
        ref = self._load()
        if ref is None:
            return dates  # 降级：无假期列，下游 type_vac fallback 保护
        enriched = dates.merge(ref, on="Date_GTFS", how="left")
        return enriched


class NullCalendarProvider:
    """
    空实现：不添加任何假期列。
    用于单元测试或明确不需要假期分类的场景。
    """

    def enrich(self, dates: pd.DataFrame) -> pd.DataFrame:
        return dates
