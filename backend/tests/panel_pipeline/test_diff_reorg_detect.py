from __future__ import annotations

import pytest

from app.services.panel_pipeline.diff.feed_diff import FeedDiff
from app.services.panel_pipeline.diff.reorg_detect import ReorgVerdict, detect_reorg


def _diff(stop_j: float, route_j: float) -> FeedDiff:
    return FeedDiff([], [], {}, [], [], {}, stop_j, route_j)


def test_no_reorg_at_full_jaccard():
    v = detect_reorg(_diff(1.0, 1.0))
    assert v.detected is False
    assert v.severity is None


def test_minor_reorg():
    v = detect_reorg(_diff(0.95, 0.78))
    assert v.detected is True
    assert v.severity == "minor"


def test_major_reorg():
    v = detect_reorg(_diff(0.80, 0.55))
    assert v.detected is True
    assert v.severity == "major"


def test_massive_reorg():
    v = detect_reorg(_diff(0.50, 0.27))
    assert v.detected is True
    assert v.severity == "massive"


def test_route_jaccard_dominates():
    """If stops are stable but routes are gutted, severity should still escalate."""
    v = detect_reorg(_diff(stop_j=0.99, route_j=0.30))
    assert v.severity == "massive"


def test_verdict_carries_jaccards_and_threshold_version():
    v = detect_reorg(_diff(0.95, 0.78))
    assert v.stop_jaccard == 0.95
    assert v.route_jaccard == 0.78
    assert v.threshold_version  # non-empty string


# ---------------------------------------------------------------------------
# Boundary tests — guard against off-by-one in `>=` vs `>` on threshold cuts.
# Thresholds in data/reorg_thresholds.yaml: minor_min=0.85, major_min=0.70,
# massive_min=0.50. Spec §3.1 uses half-open intervals [lower, upper).
# ---------------------------------------------------------------------------

def test_boundary_at_minor_min_is_no_reorg():
    """j == minor_min → no reorg (lower bound is inclusive)."""
    v = detect_reorg(_diff(0.85, 0.85))
    assert v.detected is False
    assert v.severity is None


def test_boundary_at_major_min_is_minor():
    """j == major_min → minor (lower bound inclusive on the minor bucket)."""
    v = detect_reorg(_diff(0.70, 0.70))
    assert v.detected is True
    assert v.severity == "minor"


def test_boundary_at_massive_min_is_major():
    """j == massive_min → major (lower bound inclusive on the major bucket)."""
    v = detect_reorg(_diff(0.50, 0.50))
    assert v.detected is True
    assert v.severity == "major"


def test_zero_jaccard_is_massive():
    """Total set turnover (no shared stops or routes) → massive."""
    v = detect_reorg(_diff(0.0, 0.0))
    assert v.detected is True
    assert v.severity == "massive"
