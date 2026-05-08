"""Provisional v0 error-margin propagation (Plan 2 Assumption A1).

Formula:
    margin = sqrt(Σ w_i · (1 − dq_i/100)²) × scale_factor[indicator]

Weights from spec §5.1 G overall_score formula. scale_factor in
data/error_margin_scale.yaml. Canonical replacement lands in
methodology/error_propagation.md before W16 launch (Plan 4).

Plan 2 Phase 0: this module ships as a stub that returns 0.0 so compute() can
be tested for purity. Task 5.4 fills in the real formula with TDD.
"""
from __future__ import annotations

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


def propagate(indicator_id: str, raw_values: dict[str, float | None]) -> float:
    """Compute provisional v0 error-margin (% of value) for an indicator.

    Phase 0 stub: returns 0.0. Task 5.4 implements the full formula.

    Args:
        indicator_id: target indicator key in the registry.
        raw_values: dict containing dq_* values (0-100).

    Returns:
        Error margin as percentage of indicator value, in [0, ~100].
    """
    if indicator_id not in INDICATOR_REGISTRY:
        return 0.0
    # Task 5.4 will replace with full formula. Until then, return 0 so that
    # `compute()` produces a deterministic numeric output for the purity tests.
    return 0.0
