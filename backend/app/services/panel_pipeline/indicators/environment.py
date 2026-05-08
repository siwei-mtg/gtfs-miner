"""Spec §5.1 H. Environment indicators (1 item). Plan 2 Task 5.5.

env_co2_year_estimated — KCC × ADEME Base Carbone v23+ emission factors,
grouped by GTFS route_type. Disclosure: order-of-magnitude estimate,
±30% (diesel-dominant) or ±50% (mixed-electric). Spec §5.1 H mandates UI
labeling as "Estimation order-of-magnitude — not for legal GHG reporting".

Formula:
    env_co2_year_estimated [tCO2/year]
        = Σ_{route_type} (kcc_km × factor_kgCO2_per_km) / 1000

The KCC-by-route-type breakdown is supplied by `productivity.compute_all`
through the `_kcc_by_route_type` sentinel key in `raw_values`. This module
does not re-read GTFS or recompute spatial chains — it is a pure scalar
combinator over prior indicators + a static factor table.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import yaml


_FACTORS_PATH = Path(__file__).resolve().parents[1] / "data" / "ademe_factors.yaml"
_FACTORS_CACHE: dict | None = None


def _load_factors() -> dict:
    """Load ADEME factors YAML (cached after first read).

    The cache is module-level and process-local — safe under the Plan 2
    Assumption A3 read-only static-data exemption from purity rules
    (the YAML is a versioned methodology constant, not state).
    """
    global _FACTORS_CACHE
    if _FACTORS_CACHE is None:
        _FACTORS_CACHE = yaml.safe_load(_FACTORS_PATH.read_text(encoding="utf-8"))
    return _FACTORS_CACHE


def compute_all(prior_values: Mapping) -> dict[str, float | None]:
    """Compute env_co2_year_estimated.

    Input Schema:
        prior_values: indicators-so-far dict produced by `compute()`. MUST
            contain `_kcc_by_route_type` (dict[int, float] of KCC km per
            route_type) populated by `productivity.compute_all` as a
            sentinel side-output. If the sentinel is absent (productivity
            failed earlier in the pipeline), returns None.

    Output Schema:
        {"env_co2_year_estimated": tCO2_per_year} — float or None.
        Unit alignment with KCC: KCC is window-total km (the spec name
        "kcc_year" treats the analysis window as the year proxy), so
        env_co2 is "tCO2 over the same window labeled per-year".

    Rules:
        - Unknown route_types fall back to `default` factor in YAML
          (currently 110 kgCO2/km — diesel bus assumption).
        - kcc=0 for all route_types → returns 0.0 (a valid value, not None).
        - Missing sentinel key → None.
    """
    kcc_by_type = prior_values.get("_kcc_by_route_type")
    if kcc_by_type is None:
        return {"env_co2_year_estimated": None}

    cfg = _load_factors()
    factors = cfg["factors_kg_co2_per_km"]
    default_factor = float(cfg.get("default", 110.0))

    total_kg = 0.0
    for route_type, kcc_km in kcc_by_type.items():
        factor = float(factors.get(route_type, default_factor))
        total_kg += float(kcc_km) * factor

    return {"env_co2_year_estimated": total_kg / 1000.0}
