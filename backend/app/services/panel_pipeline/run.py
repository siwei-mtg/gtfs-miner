"""Pipeline entry point. Plan 2 implements full body."""
from __future__ import annotations

from pathlib import Path


def run_panel_pipeline(feed_id: str) -> None:
    """
    Process one PAN GTFS feed end-to-end.

    Plan 1 stub. Plan 2 implements:
      1. Load feed from R2 (or download from PAN if absent)
      2. Reuse gtfs_core: rawgtfs_from_zip, gtfs_normalize, ligne_generate,
         service_date_generate, service_jour_type_generate
      3. Compute 38 indicators via indicators.* modules
      4. Run quality.compute_quality()
      5. Persist to panel_indicators + panel_quality
      6. Trigger aggregator.recompute_derived(network_id)
    """
    raise NotImplementedError("Implemented in Plan 2 Task 1")


# ──────────────────────────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────────────────────────

_FIXTURES_ROOT = (
    Path(__file__).resolve().parents[3] / "tests" / "Resources" / "raw"
)
_FIXTURE_PATHS: dict[str, Path] = {
    "sem":   _FIXTURES_ROOT / "SEM-GTFS(2).zip",
    "solea": _FIXTURES_ROOT / "SOLEA.GTFS_current.zip",
    "ginko": _FIXTURES_ROOT / "gtfs-20240704-090655.zip",
}


def run_panel_pipeline_for_fixture(fixture: str) -> dict[str, float]:
    """Test helper: run pure compute() on a packaged test fixture with stub AomMeta.

    Used by `test_kcc_equivalence_contract.py` to verify the panel KCC matches
    the full pipeline KCC within 0.1% (spec §11). The AomMeta is stubbed
    because the fixtures don't have AOM polygons available in the test
    environment — coverage indicators will populate as None, which is fine
    for this contract test.

    Args:
        fixture: One of "sem", "solea", "ginko" (matches d4_kcc/baselines.json keys).

    Returns:
        Flat dict {indicator_id: value} for indicators that computed
        (None values dropped).
    """
    from shapely.geometry import box

    from app.services.panel_pipeline.compute import AomMeta, compute

    meta = AomMeta(
        slug=fixture,
        population=1,
        area_km2=1.0,
        polygon_l93=box(0, 0, 1, 1),
        methodology_commit="test",
    )
    bundle = compute(_FIXTURE_PATHS[fixture], meta)
    return {
        k: v["value"]
        for k, v in bundle.values.items()
        if v["value"] is not None
    }
