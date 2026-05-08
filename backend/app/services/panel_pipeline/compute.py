"""Pure compute() entrypoint — spec §6.2 v0.2 hard rule.

No DB writes. No global state. Same input → same numeric output.

Used by:
    1. panel_pipeline.run        (production: load feed → compute → persist)
    2. V1 Pro what-if simulator  (user-uploaded ZIP → preview indicators)

Phase 0 ships with NotImplementedError bridges around each indicator category so
the purity contract is verifiable before Phases 2/3/5 land the real impls.
Once Phase 5 closes, the bridges are removed (Task 5.6 in the plan).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from shapely.geometry.base import BaseGeometry

from app.services.panel_pipeline._registry import INDICATOR_REGISTRY
from app.services.panel_pipeline.error_margin import propagate
from app.services.panel_pipeline.types import INDICATOR_IDS


@dataclass(frozen=True, slots=True)
class AomMeta:
    """Caller-supplied AOM metadata. Polygon must already be in Lambert-93 (EPSG:2154)."""
    slug: str
    population: int
    area_km2: float
    polygon_l93: BaseGeometry
    methodology_commit: str


class IndicatorValue(TypedDict):
    value: float | None
    unit: str
    error_margin_pct: float | None
    source_feed_id: str | None      # None during what-if; filled by run.py during persist
    computed_at: str                # ISO 8601 UTC
    methodology_commit: str


@dataclass(frozen=True, slots=True)
class IndicatorBundle:
    """Output of compute(). 38-key `values` dict, plus `errors` for any category that
    failed (e.g., AOM polygon missing → 6 cov_* indicators report `aom_polygon_missing`)."""
    values: dict[str, IndicatorValue]
    errors: dict[str, str] = field(default_factory=dict)


def _none_for_category(category: str) -> list[str]:
    return [k for k, v in INDICATOR_REGISTRY.items() if v.category == category]


def compute(zip_path: Path, meta: AomMeta) -> IndicatorBundle:
    """Run the 38-indicator pipeline on a single GTFS ZIP. Pure function.

    Args:
        zip_path: Path to GTFS ZIP. Must exist.
        meta: AOM metadata frozen dataclass with population, area, polygon_l93, commit.

    Returns:
        IndicatorBundle with 38 IndicatorValue entries (some may have value=None when
        a category cannot compute — see bundle.errors for the reason).

    Raises:
        FileNotFoundError if zip_path does not exist.
    """
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    # Lazy imports — keep top-level light and let test patches target inner modules.
    from app.services.gtfs_core.gtfs_norm import gtfs_normalize
    from app.services.gtfs_core.gtfs_reader import read_gtfs_zip
    from app.services.panel_pipeline.indicators import (
        accessibility, coverage, density, environment, frequency,
        productivity, quality_indicators, structure,
    )

    raw_values: dict[str, float | None] = {}
    errors: dict[str, str] = {}

    # 1. Read + normalize (reuse gtfs_core)
    raw = read_gtfs_zip(zip_path)
    normed = gtfs_normalize(raw)

    # 2. Compute each category. Phase 0 wraps every call so NotImplementedError from
    # stub modules is caught and reported in `errors[]`. Each call also catches
    # FileNotFoundError (e.g., coverage needs the carroyage GeoPackage which may not
    # be present in test environments — see test_compute_purity.py).

    def _try(category: str, fn) -> None:
        try:
            raw_values.update(fn())
        except NotImplementedError:
            for ind_id in _none_for_category(category):
                raw_values.setdefault(ind_id, None)
                errors[ind_id] = "not_implemented_yet"
        except FileNotFoundError as e:
            for ind_id in _none_for_category(category):
                raw_values.setdefault(ind_id, None)
                errors[ind_id] = f"data_file_missing: {e}"
        except Exception as e:
            for ind_id in _none_for_category(category):
                raw_values.setdefault(ind_id, None)
                errors[ind_id] = f"compute_failed: {type(e).__name__}: {e}"

    _try("productivity", lambda: productivity.compute_all(raw, normed, meta))
    _try("density",      lambda: density.compute_all(raw_values, meta))
    _try("structure",    lambda: structure.compute_all(raw, normed))
    _try("coverage",     lambda: coverage.compute_all(raw, normed, meta))
    _try("frequency",    lambda: frequency.compute_all(raw, normed))
    _try("accessibility",lambda: accessibility.compute_all(raw))
    _try("quality",      lambda: quality_indicators.compute_all(zip_path, raw))
    _try("environment",  lambda: environment.compute_all(raw_values))

    # 3. Wrap each indicator in audit-grade IndicatorValue.
    now = datetime.now(timezone.utc).isoformat()
    bundle: dict[str, IndicatorValue] = {}
    for ind_id in INDICATOR_IDS:
        meta_ind = INDICATOR_REGISTRY[ind_id]
        val = raw_values.get(ind_id)
        margin = propagate(ind_id, raw_values) if val is not None else None
        bundle[ind_id] = IndicatorValue(
            value=val,
            unit=meta_ind.unit,
            error_margin_pct=margin,
            source_feed_id=None,                 # filled by run.py during persist
            computed_at=now,
            methodology_commit=meta.methodology_commit,
        )
    return IndicatorBundle(values=bundle, errors=errors)
