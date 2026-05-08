"""Spec §5.1 B. Density indicators (4 items).

dens_stops_km2     = prod_stops_count / area_km2
dens_lines_100k_pop = prod_lines_count / population × 100_000
dens_kcc_capita    = prod_kcc_year / population
dens_kcc_km2       = prod_kcc_year / area_km2

Pure ratios on Task 2.1 productivity outputs + AomMeta. Called from
`compute._try("density", lambda: density.compute_all(raw_values, meta))`
where `raw_values` already contains the productivity numerators.
"""
from __future__ import annotations

from typing import Mapping


def compute_all(
    prior_values: Mapping[str, float | None],
    meta,                               # AomMeta — no annotation to dodge circular import
) -> dict[str, float | None]:
    """Compute all 4 density indicators.

    Args:
        prior_values: Indicators already computed (productivity, structure, etc.).
                      MUST contain prod_kcc_year, prod_lines_count, prod_stops_count
                      for the corresponding outputs to populate; missing keys → None.
        meta: AomMeta with population (int) and area_km2 (float).
              Zero/negative population or area degrades the dependent indicators
              to None instead of raising ZeroDivisionError.

    Returns:
        {indicator_id: value} with all 4 keys present. Value is None if any
        required input is missing or the denominator is non-positive.
    """
    out: dict[str, float | None] = {}
    pop = meta.population
    area = meta.area_km2
    kcc = prior_values.get("prod_kcc_year")
    lines = prior_values.get("prod_lines_count")
    stops = prior_values.get("prod_stops_count")

    out["dens_stops_km2"] = (stops / area) if (stops is not None and area > 0) else None
    out["dens_lines_100k_pop"] = (
        (lines / pop * 100_000) if (lines is not None and pop > 0) else None
    )
    out["dens_kcc_capita"] = (kcc / pop) if (kcc is not None and pop > 0) else None
    out["dens_kcc_km2"] = (kcc / area) if (kcc is not None and area > 0) else None
    return out
