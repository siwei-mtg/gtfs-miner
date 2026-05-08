"""D6 — Reorg detector threshold tuning. Spec §12 v0.2.

Validates the Plan 2 Phase 1 reorg detector against known-reorg and
known-stable GTFS pairs from PAN. Updates ``reorg_thresholds.yaml`` if
FPR > 5% or FNR > 10% (recommendation only — yaml is **not** auto-edited).

Prereq: run ``d1b_dedup_per_network.py`` first to populate the per-network
archives under ``backend/storage/discovery/d1_pan/<network>/``.

Output:
  - ``docs/superpowers/specs/<today>-d6-reorg-detector-discovery.md``
  - Recommendations on threshold revisions

The script gracefully handles the case where fixture ZIPs are absent: it
prints a WARN per missing pair and continues. If no pair runs, an
"awaiting fixtures" stub report is produced — never a crash.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd

# Make ``app.*`` importable when this file is run as a script
# (consistent with d2_insee_coverage.py / d4_kcc_equivalence.py).
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.gtfs_core.gtfs_reader import read_gtfs_zip  # noqa: E402
from app.services.panel_pipeline.diff.feed_diff import feed_diff  # noqa: E402
from app.services.panel_pipeline.diff.reorg_detect import detect_reorg  # noqa: E402


CACHE: Path = BACKEND_ROOT / "storage" / "discovery" / "d1_pan"
REPO_ROOT: Path = Path(__file__).resolve().parents[3]
DEFAULT_REPORT: Path = (
    REPO_ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / f"{datetime.now(timezone.utc):%Y-%m-%d}-d6-reorg-detector-discovery.md"
)


@dataclass(frozen=True, slots=True)
class FeedPair:
    """Two GTFS ZIPs from the same network, with a known reorg label."""

    label: str
    network_dir: str
    """Subdirectory under ``d1_pan/`` (e.g. ``"bordeaux_archive"``)."""
    feed_a_zip: str
    """Filename within ``network_dir``."""
    feed_b_zip: str
    expected_reorg: bool


# Known-reorg + known-stable fixtures. Real ZIPs are downloaded separately
# via ``d1b_dedup_per_network.py --steps fetch resolve dedup download`` for
# each listed network archive.
DEFAULT_PAIRS: Sequence[FeedPair] = (
    FeedPair("bordeaux-2024", "bordeaux_archive", "pre_2024_09.zip", "post_2024_09.zip", True),
    FeedPair("toulouse-2024", "toulouse_archive", "pre_2024.zip", "post_2024.zip", True),
    FeedPair("nantes-2023", "nantes_archive", "pre_2023.zip", "post_2023.zip", True),
    FeedPair("strasbourg-2018-2019", "strasbourg_archive", "2018.zip", "2019.zip", False),
    FeedPair("strasbourg-2019-2020", "strasbourg_archive", "2019.zip", "2020.zip", False),
    FeedPair("strasbourg-2020-2021", "strasbourg_archive", "2020.zip", "2021.zip", False),
    FeedPair("strasbourg-2021-2022", "strasbourg_archive", "2021.zip", "2022.zip", False),
)


def evaluate(pairs: Sequence[FeedPair], cache_dir: Path = CACHE) -> pd.DataFrame:
    """Run the detector on every pair; return a DataFrame with results.

    Input schema:
        pairs: Sequence[FeedPair] — fixture descriptors.
        cache_dir: Path — root containing ``<network_dir>/<zip>`` files.

    Output schema:
        DataFrame with columns:
          pair, expected_reorg (bool), stop_jaccard, route_jaccard,
          min_jaccard, detected (bool), severity (str|None), correct (bool).
        Empty DataFrame if no pair's ZIPs are present.

    Side effects:
        Prints ``WARN: skipping <label> — missing <path>`` for absent ZIPs.
    """
    rows: list[dict] = []
    for fp in pairs:
        zip_a = cache_dir / fp.network_dir / fp.feed_a_zip
        zip_b = cache_dir / fp.network_dir / fp.feed_b_zip
        if not zip_a.exists() or not zip_b.exists():
            missing = zip_a if not zip_a.exists() else zip_b
            print(f"WARN: skipping {fp.label} — missing {missing}")
            continue
        feed_a = read_gtfs_zip(zip_a)
        feed_b = read_gtfs_zip(zip_b)
        diff = feed_diff(feed_a, feed_b)
        verdict = detect_reorg(diff)
        rows.append(
            {
                "pair": fp.label,
                "expected_reorg": fp.expected_reorg,
                "stop_jaccard": diff.stop_jaccard,
                "route_jaccard": diff.route_jaccard,
                "min_jaccard": min(diff.stop_jaccard, diff.route_jaccard),
                "detected": verdict.detected,
                "severity": verdict.severity,
                "correct": verdict.detected == fp.expected_reorg,
            }
        )
    return pd.DataFrame(rows)


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavored markdown table.

    Implemented locally so the script does not need the optional ``tabulate``
    dependency that ``DataFrame.to_markdown`` would require.
    """
    cols = list(df.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body_rows = [
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |"
        for row in df.itertuples(index=False, name=None)
    ]
    return "\n".join([header, sep, *body_rows])


def render_report(df: pd.DataFrame, report_path: Path) -> None:
    """Write a markdown discovery report (idempotent — always overwrites).

    If ``df`` is empty, writes a stub "awaiting fixtures" note instead of
    computing a confusion matrix (avoids ZeroDivisionError).
    """
    report_path.parent.mkdir(parents=True, exist_ok=True)
    today = f"{datetime.now(timezone.utc):%Y-%m-%d}"
    if df.empty:
        report_path.write_text(
            "\n".join(
                [
                    "# D6 — Reorg Detector Threshold Discovery",
                    "",
                    f"**Date**: {today}",
                    "",
                    "_No fixture pairs were available in the d1_pan cache. "
                    "Run `d1b_dedup_per_network.py` for bordeaux / toulouse / "
                    "nantes / strasbourg first._",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return

    tp = int(df.query("expected_reorg & detected").shape[0])
    fp = int(df.query("not expected_reorg & detected").shape[0])
    fn = int(df.query("expected_reorg & not detected").shape[0])
    tn = int(df.query("not expected_reorg & not detected").shape[0])
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (tp + fn) if (tp + fn) > 0 else 0.0

    body = "\n".join(
        [
            "# D6 — Reorg Detector Threshold Discovery",
            "",
            f"**Date**: {today}",
            "",
            "## Confusion matrix",
            f"- TP {tp} · FP {fp} · FN {fn} · TN {tn}",
            f"- FPR {fpr:.1%} (target <5%)",
            f"- FNR {fnr:.1%} (target <10%)",
            "",
            "## Per-pair scores",
            "",
            _df_to_markdown(df),
            "",
            "## Recommendation",
            "",
            "If FPR > 5% or FNR > 10%, adjust thresholds in",
            "`backend/app/services/panel_pipeline/data/reorg_thresholds.yaml`.",
            "Bump `version` to `v1` once values stabilize.",
            "",
        ]
    )
    report_path.write_text(body, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point. Runs ``evaluate`` then ``render_report``."""
    parser = argparse.ArgumentParser(description="D6 reorg detector threshold pilot.")
    parser.add_argument("--cache-dir", type=Path, default=CACHE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    df = evaluate(DEFAULT_PAIRS, cache_dir=args.cache_dir)
    render_report(df, args.report)
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
