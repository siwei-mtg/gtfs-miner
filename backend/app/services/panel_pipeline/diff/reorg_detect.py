"""Reorg detector. Verdict driven by min(stop_jaccard, route_jaccard) per spec §3.1.

Thresholds in data/reorg_thresholds.yaml — overridden per Discovery Task D6 output.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from app.services.panel_pipeline.diff.feed_diff import FeedDiff


THRESHOLDS_PATH = Path(__file__).resolve().parent.parent / "data" / "reorg_thresholds.yaml"


Severity = Literal["minor", "major", "massive"]


@dataclass(frozen=True, slots=True)
class ReorgVerdict:
    detected: bool
    severity: Severity | None
    stop_jaccard: float
    route_jaccard: float
    threshold_version: str


def _load_thresholds() -> dict:
    return yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8"))


def detect_reorg(diff: FeedDiff) -> ReorgVerdict:
    """Decide whether a feed pair represents a network reorganization.

    Args:
        diff: FeedDiff from feed_diff(). Only stop_jaccard / route_jaccard consumed.

    Returns:
        ReorgVerdict with severity bucket. None severity ⇔ detected=False.
    """
    cfg = _load_thresholds()
    j = min(diff.stop_jaccard, diff.route_jaccard)
    if j >= cfg["minor_min"]:
        return ReorgVerdict(False, None, diff.stop_jaccard, diff.route_jaccard, cfg["version"])
    if j >= cfg["major_min"]:
        sev: Severity = "minor"
    elif j >= cfg["massive_min"]:
        sev = "major"
    else:
        sev = "massive"
    return ReorgVerdict(True, sev, diff.stop_jaccard, diff.route_jaccard, cfg["version"])
