"""Provisional v0 error-margin propagation (Plan 2 Assumption A1).

Formula:
    margin = sqrt(Σ w_i · (1 − dq_i/100)²) × scale_factor[indicator]

Weights from spec §5.1 G overall_score formula. scale_factor in
data/error_margin_scale.yaml. Canonical replacement lands in
methodology/error_propagation.md before W16 launch (Plan 4).
"""
from __future__ import annotations

import math
from pathlib import Path

import yaml

from app.services.panel_pipeline._registry import INDICATOR_REGISTRY


SCALE_PATH = Path(__file__).resolve().parent / "data" / "error_margin_scale.yaml"


# Weights per dq_* — must match §5.1 G overall_score formula.
DQ_WEIGHTS: dict[str, float] = {
    "dq_validator_errors": 0.25,
    "dq_field_completeness": 0.20,
    "dq_coord_quality": 0.15,
    "dq_route_type_completeness": 0.15,
    "dq_freshness": 0.15,
    "dq_validator_warnings": 0.10,
}


_SCALE_CACHE: dict | None = None


def _scale_factor(indicator_id: str) -> float:
    """Read the scale_factor from data/error_margin_scale.yaml (cached after first read)."""
    global _SCALE_CACHE
    if _SCALE_CACHE is None:
        _SCALE_CACHE = yaml.safe_load(SCALE_PATH.read_text(encoding="utf-8"))
    return float(_SCALE_CACHE["overrides"].get(indicator_id, _SCALE_CACHE["default"]))


def propagate(indicator_id: str, raw_values: dict[str, float | None]) -> float:
    """Compute provisional v0 error-margin (% of value) for an indicator.

    Args:
        indicator_id: target indicator key in INDICATOR_REGISTRY.
        raw_values: dict containing dq_* values (0-100). Missing → treated as 100.

    Returns:
        Error margin as percentage of indicator value, in [0, ~100].
    """
    if indicator_id not in INDICATOR_REGISTRY:
        return 0.0
    deps = INDICATOR_REGISTRY[indicator_id].dq_dependencies
    if not deps:
        return 0.0
    sum_sq = 0.0
    for dq in deps:
        weight = DQ_WEIGHTS.get(dq, 0.0)
        value = raw_values.get(dq)
        if value is None:
            value = 100.0
        deviation = max(0.0, 1.0 - float(value) / 100.0)
        sum_sq += weight * deviation ** 2
    return math.sqrt(sum_sq) * _scale_factor(indicator_id)
