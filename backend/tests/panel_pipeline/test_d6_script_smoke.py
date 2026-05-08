"""Smoke tests for the D6 script — no real PAN data required.

Real-data validation happens at human-run time when the human invokes the
script after running ``d1b_dedup_per_network.py`` for the listed networks.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Match the convention of test_d3_validator_wrapper.py: expose
# ``backend/scripts`` on sys.path so ``from discovery import …`` works.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BACKEND_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_d6_script_imports() -> None:
    """Script must import without side effects."""
    from discovery import d6_reorg_thresholds
    assert hasattr(d6_reorg_thresholds, "main")
    assert hasattr(d6_reorg_thresholds, "evaluate")
    assert hasattr(d6_reorg_thresholds, "render_report")
    assert hasattr(d6_reorg_thresholds, "DEFAULT_PAIRS")


def test_default_pairs_has_3_known_reorgs_and_4_known_stable() -> None:
    from discovery.d6_reorg_thresholds import DEFAULT_PAIRS

    reorg_count = sum(1 for fp in DEFAULT_PAIRS if fp.expected_reorg)
    stable_count = sum(1 for fp in DEFAULT_PAIRS if not fp.expected_reorg)
    assert reorg_count == 3, (
        f"Expected 3 known-reorg fixtures (Bordeaux/Toulouse/Nantes), got {reorg_count}"
    )
    assert stable_count == 4, (
        f"Expected 4 known-stable Strasbourg pairs, got {stable_count}"
    )


def test_evaluate_skips_missing_pairs(tmp_path: Path) -> None:
    """When the cache dir doesn't contain the ZIPs, ``evaluate`` returns an empty
    DataFrame without crashing.
    """
    from discovery.d6_reorg_thresholds import DEFAULT_PAIRS, evaluate

    df = evaluate(DEFAULT_PAIRS, cache_dir=tmp_path)
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_render_report_handles_empty_df(tmp_path: Path) -> None:
    """Empty results produce a "no fixtures available" report (no crash)."""
    from discovery.d6_reorg_thresholds import render_report

    out = tmp_path / "report.md"
    render_report(pd.DataFrame(), out)
    assert out.exists()
    assert "No fixture pairs were available" in out.read_text(encoding="utf-8")


def test_render_report_renders_confusion_matrix(tmp_path: Path) -> None:
    """Synthetic results produce a report containing TP/FP/FN/TN and target rates."""
    from discovery.d6_reorg_thresholds import render_report

    df = pd.DataFrame(
        [
            {
                "pair": "p1",
                "expected_reorg": True,
                "stop_jaccard": 0.4,
                "route_jaccard": 0.3,
                "min_jaccard": 0.3,
                "detected": True,
                "severity": "massive",
                "correct": True,
            },
            {
                "pair": "p2",
                "expected_reorg": False,
                "stop_jaccard": 0.95,
                "route_jaccard": 0.95,
                "min_jaccard": 0.95,
                "detected": False,
                "severity": None,
                "correct": True,
            },
        ]
    )
    out = tmp_path / "report.md"
    render_report(df, out)
    txt = out.read_text(encoding="utf-8")
    assert "TP 1" in txt and "TN 1" in txt
    assert "FPR 0.0%" in txt
    assert "FNR 0.0%" in txt
