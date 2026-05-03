"""
KCC equivalence contract test — spec §11.
Activates in Plan 2 once panel_pipeline.run computes prod_kcc_year.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

BASELINES_PATH = (
    Path(__file__).resolve().parents[2]
    / "storage" / "discovery" / "d4_kcc" / "baselines.json"
)


@pytest.mark.skip(reason="Activated in Plan 2 once prod_kcc_year is implemented")
@pytest.mark.parametrize("fixture", ["sem", "solea", "ginko"])
def test_kcc_equivalence(fixture: str) -> None:
    """Spec §11 contract: panel KCC and full pipeline KCC must be within 0.1%."""
    baselines = json.loads(BASELINES_PATH.read_text(encoding="utf-8"))
    expected = baselines[fixture]
    # Plan 2 will replace this stub:
    from app.services.panel_pipeline.run import run_panel_pipeline_for_fixture
    panel = run_panel_pipeline_for_fixture(fixture)
    actual = panel["prod_kcc_year"]
    # expected = first KCC column total — actual reconciliation logic in Plan 2
    expected_kcc = next(iter(expected["kcc_total_per_column"].values()))
    assert abs(actual - expected_kcc) / expected_kcc < 0.001, (
        f"{fixture}: panel={actual:.2f} vs full={expected_kcc:.2f}"
    )
