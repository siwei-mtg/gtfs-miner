"""Spec §6.2 v0.2 hard rule: indicators.compute() is a pure function.

Pre-Phase-5, individual indicator categories raise NotImplementedError; compute()
catches those and fills the bundle's `errors` map so the purity contract can be
verified before the implementation phases close.

Contract:
    1. Returns IndicatorBundle with all 38 keys present in `values` dict.
    2. Does not open a DB session.
    3. Same input → same numeric output (computed_at field excluded from compare).
    4. methodology_commit from AomMeta passes through to every IndicatorValue.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from shapely.geometry import box

from app.services.panel_pipeline.compute import AomMeta, IndicatorBundle, compute


FIXTURES = Path(__file__).resolve().parents[1] / "Resources" / "raw"
SEM_ZIP = FIXTURES / "SEM-GTFS(2).zip"


@pytest.fixture()
def sem_meta() -> AomMeta:
    # Real Grenoble polygon comes from D2 cache; for purity test, a coarse Lambert-93
    # bbox covering Grenoble metropolitan suffices — coverage indicators will be None
    # because the carroyage GeoPackage is not bundled with the fixtures.
    return AomMeta(
        slug="grenoble-sem",
        population=445_000,
        area_km2=541.0,
        polygon_l93=box(910_000, 6_440_000, 950_000, 6_490_000),
        methodology_commit="test-deadbeef",
    )


def test_compute_returns_indicator_bundle(sem_meta):
    bundle = compute(SEM_ZIP, sem_meta)
    assert isinstance(bundle, IndicatorBundle)


def test_compute_returns_38_indicators(sem_meta):
    bundle = compute(SEM_ZIP, sem_meta)
    assert len(bundle.values) == 38


def test_compute_no_db_access(sem_meta):
    """Pure-function rule: compute() must not open a DB session."""
    with patch("app.db.database.SessionLocal") as session_factory:
        compute(SEM_ZIP, sem_meta)
        session_factory.assert_not_called()


def test_compute_methodology_commit_passes_through(sem_meta):
    bundle = compute(SEM_ZIP, sem_meta)
    for ind_id, v in bundle.values.items():
        assert v["methodology_commit"] == "test-deadbeef", (
            f"{ind_id} did not propagate methodology_commit"
        )


def test_compute_source_feed_id_none_during_what_if(sem_meta):
    """source_feed_id stays None in what-if; run.py fills it during persistence."""
    bundle = compute(SEM_ZIP, sem_meta)
    for ind_id, v in bundle.values.items():
        assert v["source_feed_id"] is None


def test_compute_unit_set_for_every_indicator(sem_meta):
    bundle = compute(SEM_ZIP, sem_meta)
    for ind_id, v in bundle.values.items():
        assert v["unit"], f"{ind_id} missing unit"


def test_compute_missing_zip_raises(sem_meta):
    with pytest.raises(FileNotFoundError):
        compute(Path("/tmp/does-not-exist.zip"), sem_meta)
