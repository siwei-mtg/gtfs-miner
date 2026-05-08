"""Error margin propagation v0 (Plan 2 Assumption A1)."""
from __future__ import annotations

import math

import pytest

from app.services.panel_pipeline.error_margin import propagate


_PERFECT_DQ = {
    "dq_validator_errors": 100.0,
    "dq_validator_warnings": 100.0,
    "dq_field_completeness": 100.0,
    "dq_coord_quality": 100.0,
    "dq_route_type_completeness": 100.0,
    "dq_freshness": 100.0,
}

_ZERO_DQ = {k: 0.0 for k in _PERFECT_DQ}


def test_zero_error_when_dq_perfect():
    """All dq_* = 100 → no degradation → margin = 0."""
    raw = {**_PERFECT_DQ, "prod_kcc_year": 1_000_000.0}
    assert propagate("prod_kcc_year", raw) == pytest.approx(0.0)


def test_max_error_when_dq_zero_kcc():
    """All dq_* = 0 (max degradation) → margin = sqrt(Σ w_i) × scale=1 for kcc."""
    raw = {**_ZERO_DQ, "prod_kcc_year": 1.0}
    margin = propagate("prod_kcc_year", raw)
    # All 6 dq deps with weights 0.25, 0.10, 0.20, 0.15, 0.15, 0.15 → sum 1.00
    expected = math.sqrt(1.00) * 1.0
    assert margin == pytest.approx(expected, rel=0.01)


def test_co2_scaled_to_30():
    """env_co2 has scale_factor=30 in YAML → margin scaled accordingly."""
    raw = {**_ZERO_DQ, "env_co2_year_estimated": 1000.0}
    margin = propagate("env_co2_year_estimated", raw)
    expected = math.sqrt(1.00) * 30.0
    assert margin == pytest.approx(expected, rel=0.01)


def test_coverage_scaled_to_5():
    """cov_* has scale_factor=5."""
    raw = {**_ZERO_DQ, "cov_pop_300m": 50.0}
    margin = propagate("cov_pop_300m", raw)
    # cov_pop_300m has dq_dependencies = ("dq_coord_quality",) only → weight 0.15
    expected = math.sqrt(0.15) * 5.0
    assert margin == pytest.approx(expected, rel=0.01)


def test_dq_indicator_self_zero():
    """dq_* indicators (empty dq_dependencies) → margin = 0."""
    raw = {"dq_validator_errors": 5.0}
    assert propagate("dq_validator_errors", raw) == 0.0


def test_unknown_indicator_returns_zero():
    """Indicators not in registry → 0.0 (defensive)."""
    assert propagate("unknown_indicator_id", {}) == 0.0


def test_partial_dq_treats_missing_as_perfect():
    """Missing dq_* in raw_values → treated as 100 (no degradation)."""
    raw = {"prod_kcc_year": 1.0}   # no dq_* present
    margin = propagate("prod_kcc_year", raw)
    assert margin == pytest.approx(0.0)
