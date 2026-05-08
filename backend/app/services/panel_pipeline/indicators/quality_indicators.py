"""Spec §5.1 G. Data quality indicators (6 items).

Two come from the MobilityData GTFS Validator (Java) — gracefully degrade to None
when the validator is unavailable (no Java / no JAR in CI). The other 4 are
computed directly from the raw GTFS dict, no external tools.

Indicators:
    - dq_validator_errors          — validator severity=ERROR notice count
    - dq_validator_warnings        — validator severity=WARNING notice count
    - dq_field_completeness        — weighted % of required fields populated (0-100)
    - dq_coord_quality             — % of stops within metropolitan France bbox
    - dq_route_type_completeness   — % of routes with route_type populated (raw, before
                                     gtfs_norm defaults missing values to 3)
    - dq_freshness                 — days since feed_info.feed_end_date (or None)
"""
from __future__ import annotations

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd

logger = logging.getLogger("panel_pipeline.quality_indicators")


# Required-field weights for dq_field_completeness. Drawn from spec §5.1 G:
# weight reflects "how often this field is consulted".
_REQUIRED_FIELDS: dict[str, dict[str, float]] = {
    "stops":      {"stop_id": 1.0, "stop_name": 1.0, "stop_lat": 1.0, "stop_lon": 1.0},
    "routes":     {"route_id": 1.0, "route_type": 1.0, "route_short_name": 0.5,
                   "route_long_name": 0.5},
    "trips":      {"trip_id": 1.0, "route_id": 1.0, "service_id": 1.0},
    "stop_times": {"trip_id": 1.0, "stop_id": 1.0, "stop_sequence": 1.0,
                   "arrival_time": 0.5, "departure_time": 0.5},
}

# Metropolitan France bounding box (approx, includes Corsica).
_LAT_MIN, _LAT_MAX = 41.0, 52.0
_LON_MIN, _LON_MAX = -5.0, 10.0


def compute_all(
    zip_path: Path,
    raw: Mapping[str, pd.DataFrame],
) -> dict[str, float | None]:
    """Compute all 6 dq_* indicators.

    Args:
        zip_path: Path to the GTFS ZIP — only used by the validator subprocess.
        raw: Output of `read_gtfs_zip` (table_name -> DataFrame).

    Returns:
        Flat {indicator_id: value | None} for the 6 dq_* indicators. Validator-
        sourced values are None when Java/JAR is unavailable; the other 4 are
        always populated (may be 0.0 if data is empty).
    """
    out: dict[str, float | None] = {}
    out.update(_validator_indicators(zip_path))
    out["dq_field_completeness"] = _field_completeness(raw)
    out["dq_coord_quality"] = _coord_quality(raw)
    out["dq_route_type_completeness"] = _route_type_completeness(raw)
    out["dq_freshness"] = _freshness_days(raw)
    return out


def _validator_indicators(zip_path: Path) -> dict[str, float | None]:
    """Run the GTFS Validator. Returns None for both keys if unavailable."""
    # Lazy import — keeps top-level light and lets tests monkey-patch.
    from app.services.panel_pipeline.quality import (
        ValidatorUnavailable,
        is_validator_available,
        validate_feed,
    )

    if not is_validator_available():
        logger.info("GTFS Validator unavailable (Java/JAR missing) — dq_validator_* = None")
        return {"dq_validator_errors": None, "dq_validator_warnings": None}

    try:
        with tempfile.TemporaryDirectory(prefix="gtfs_validator_") as tmp:
            report = validate_feed(Path(zip_path), Path(tmp))
        return {
            "dq_validator_errors": float(report.error_count),
            "dq_validator_warnings": float(report.warning_count),
        }
    except (ValidatorUnavailable, RuntimeError, FileNotFoundError) as e:
        logger.warning("GTFS Validator failed (%s: %s) — dq_validator_* = None",
                       type(e).__name__, e)
        return {"dq_validator_errors": None, "dq_validator_warnings": None}
    except Exception as e:  # noqa: BLE001 — never let validator errors poison the pipeline
        logger.warning("GTFS Validator unexpected error (%s: %s) — dq_validator_* = None",
                       type(e).__name__, e)
        return {"dq_validator_errors": None, "dq_validator_warnings": None}


def _field_completeness(raw: Mapping[str, pd.DataFrame]) -> float:
    """Spec §5.1 G: weighted % of required fields populated across required tables."""
    total_weight = 0.0
    completion = 0.0
    for table_name, fields in _REQUIRED_FIELDS.items():
        df = raw.get(table_name)
        if df is None or len(df) == 0:
            for _f, w in fields.items():
                total_weight += w
                # Missing table -> field counts as 0% complete.
            continue
        for field_name, weight in fields.items():
            total_weight += weight
            if field_name not in df.columns:
                continue
            non_null_pct = float(df[field_name].notna().sum()) / len(df) * 100.0
            completion += weight * non_null_pct
    if total_weight <= 0:
        return 0.0
    return completion / total_weight


def _coord_quality(raw: Mapping[str, pd.DataFrame]) -> float:
    """Spec §5.1 G: % of stops within France bbox."""
    stops = raw.get("stops")
    if stops is None or len(stops) == 0:
        return 0.0
    if "stop_lat" not in stops.columns or "stop_lon" not in stops.columns:
        return 0.0
    lat = pd.to_numeric(stops["stop_lat"], errors="coerce")
    lon = pd.to_numeric(stops["stop_lon"], errors="coerce")
    in_bbox = (
        (lat >= _LAT_MIN) & (lat <= _LAT_MAX)
        & (lon >= _LON_MIN) & (lon <= _LON_MAX)
    )
    valid = int(in_bbox.fillna(False).sum())
    return float(valid) / len(stops) * 100.0


def _route_type_completeness(raw: Mapping[str, pd.DataFrame]) -> float:
    """Spec §5.1 G: % of routes with route_type explicitly populated.

    Uses raw routes (before normalization) since `gtfs_norm` defaults missing
    `route_type` to 3 (bus). On the raw frame, NaN means "missing".
    """
    routes = raw.get("routes")
    if routes is None or len(routes) == 0:
        return 0.0
    if "route_type" not in routes.columns:
        return 0.0
    populated = int(routes["route_type"].notna().sum())
    return float(populated) / len(routes) * 100.0


def _freshness_days(raw: Mapping[str, pd.DataFrame]) -> float | None:
    """Spec §5.1 G: days since feed_info.feed_end_date (fallback feed_start_date).

    Returns None if feed_info is missing or the dates can't be parsed.
    Negative deltas (future-dated feeds) are clamped to 0.
    """
    feed_info = raw.get("feed_info")
    if feed_info is None or len(feed_info) == 0:
        return None
    # feed_info has 1 row per GTFS spec; take the first.
    row = feed_info.iloc[0]
    end_date_str: str | None = None
    for col in ("feed_end_date", "feed_start_date"):
        if col in feed_info.columns:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                end_date_str = str(val).strip()
                break
    if not end_date_str:
        return None
    try:
        # GTFS dates are YYYYMMDD.
        end_date = datetime.strptime(end_date_str[:8], "%Y%m%d")
    except ValueError:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    delta_days = (now - end_date).days
    return float(max(delta_days, 0))
