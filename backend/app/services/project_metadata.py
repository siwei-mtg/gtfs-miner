"""Extract per-project metadata from normalized GTFS DataFrames.

Pure helpers — no I/O, no DB access — so the worker can call them
without broadening the pipeline core's responsibilities (SOLID P1).
"""
from typing import Optional, Tuple

import pandas as pd


def extract_reseau(agency_df: Optional[pd.DataFrame], max_len: int = 200) -> Optional[str]:
    """Return distinct agency_names joined by ' / ', truncated to max_len."""
    if agency_df is None or "agency_name" not in agency_df.columns:
        return None
    names = (
        agency_df["agency_name"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .drop_duplicates()
        .tolist()
    )
    if not names:
        return None
    joined = " / ".join(names)
    return joined if len(joined) <= max_len else joined[: max_len - 1] + "…"


def extract_validite(dates_df: Optional[pd.DataFrame]) -> Tuple[Optional[int], Optional[int]]:
    """Return (min, max) YYYYMMDD ints from the pipeline Dates table."""
    if dates_df is None or len(dates_df) == 0 or "Date_GTFS" not in dates_df.columns:
        return (None, None)
    col = pd.to_numeric(dates_df["Date_GTFS"], errors="coerce").dropna()
    if col.empty:
        return (None, None)
    return (int(col.min()), int(col.max()))
