"""Aggregate D1 inventory + history outputs into the spec markdown report.

Reads cached CSVs/parquets from `backend/storage/discovery/d1_pan/`,
writes a summary markdown to `docs/superpowers/specs/`.

Usage:
    python d1_report.py
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "storage" / "discovery" / "d1_pan"
REPORT = (
    Path(__file__).resolve().parents[3]
    / "docs" / "superpowers" / "specs"
    / "2026-05-03-pan-history-discovery.md"
)


def main() -> None:
    inv_path = CACHE_DIR / "datasets_gtfs_inventory.csv"
    depth_path = CACHE_DIR / "history_depth_by_dataset.csv"
    if not inv_path.exists():
        raise SystemExit(f"Missing {inv_path}. Run d1a_pan_inventory.py a first.")
    if not depth_path.exists():
        raise SystemExit(f"Missing {depth_path}. Run d1a_pan_inventory.py b first.")

    inv = pd.read_csv(inv_path)
    depth = pd.read_csv(depth_path)

    nonempty = depth[depth["n_rows"] > 0].copy()
    nonempty["oldest_dt"] = pd.to_datetime(nonempty["oldest"], utc=True, errors="coerce")
    earliest_year = nonempty["oldest_dt"].dt.year.value_counts().sort_index()

    # Scan all *_archive subdirs for dedup validation runs
    dedup_runs: list[dict] = []
    for archive_dir in sorted(CACHE_DIR.glob("*_archive")):
        raw_p = archive_dir / "manifest_raw.parquet"
        dedup_p = archive_dir / "manifest_dedup.parquet"
        if not (raw_p.exists() and dedup_p.exists()):
            continue
        raw = pd.read_parquet(raw_p)
        dedup = pd.read_parquet(dedup_p)
        # GTFS-only rows (sig_sha not null)
        gtfs_rows = int(raw["sig_sha"].notna().sum())
        non_gtfs_rows = int(raw["sig_sha"].isna().sum())
        unique_fsd = len(dedup)
        ratio_raw = (len(raw) / unique_fsd) if unique_fsd else None
        ratio_gtfs_only = (gtfs_rows / unique_fsd) if unique_fsd else None
        dedup_runs.append({
            "name": archive_dir.name.replace("_archive", ""),
            "raw_rows": len(raw),
            "gtfs_rows": gtfs_rows,
            "non_gtfs_rows": non_gtfs_rows,
            "unique_fsd": unique_fsd,
            "ratio_raw": ratio_raw,
            "ratio_gtfs_only": ratio_gtfs_only,
        })

    lines = [
        "# D1 — PAN History Discovery Report",
        "",
        f"**Date**: {datetime.now(timezone.utc):%Y-%m-%d}",
        "**Source**: transport.data.gouv.fr `/api/datasets` + `resources_history_csv`",
        "",
        "## Summary",
        "",
        f"- Total GTFS datasets (PAN type=public-transit): **{len(inv)}**",
        f"- Datasets with non-empty history: **{len(nonempty)}**",
        f"- Total raw history rows: **{int(depth['n_rows'].sum())}**",
        f"- Estimated dedup'd feed count (raw / 7): **~{int(depth['n_rows'].sum() / 7)}**",
        "",
        "## Raw history rows distribution (datasets with non-empty history)",
        "",
        f"| p10 | p50 | p90 | p99 | max |",
        f"|-----|-----|-----|-----|-----|",
        f"| {int(nonempty['n_rows'].quantile(0.1))} "
        f"| {int(nonempty['n_rows'].quantile(0.5))} "
        f"| {int(nonempty['n_rows'].quantile(0.9))} "
        f"| {int(nonempty['n_rows'].quantile(0.99))} "
        f"| {int(nonempty['n_rows'].max())} |",
        "",
        "## Earliest publication year",
        "",
        "| Year | Datasets |",
        "|------|----------|",
    ]
    for y, n in earliest_year.items():
        lines.append(f"| {int(y)} | {int(n)} |")

    lines += ["", "## Dedup validation per sample network"]
    if dedup_runs:
        lines += [
            "",
            "| Network | Raw rows | GTFS rows | Non-GTFS | Unique `feed_start_date` | Dedup (raw) | Dedup (GTFS-only) |",
            "|---------|----------|-----------|----------|------|------|------|",
        ]
        for r in dedup_runs:
            ratio_raw = f"{r['ratio_raw']:.2f}×" if r['ratio_raw'] else "—"
            ratio_gtfs = f"{r['ratio_gtfs_only']:.2f}×" if r['ratio_gtfs_only'] else "—"
            lines.append(
                f"| {r['name']} | {r['raw_rows']} | {r['gtfs_rows']} | "
                f"{r['non_gtfs_rows']} | {r['unique_fsd']} | {ratio_raw} | {ratio_gtfs} |"
            )

        # Aggregated statistics
        if len(dedup_runs) >= 2:
            avg_ratio_raw = sum(r['ratio_raw'] for r in dedup_runs if r['ratio_raw']) / len(dedup_runs)
            avg_ratio_gtfs = sum(r['ratio_gtfs_only'] for r in dedup_runs if r['ratio_gtfs_only']) / len(dedup_runs)
            lines += [
                "",
                f"**Average dedup ratio (raw): {avg_ratio_raw:.2f}×**",
                f"**Average dedup ratio (GTFS-only): {avg_ratio_gtfs:.2f}×**",
                "",
                "**⚠️ Spec §6.1 assumed ~7× dedup ratio. Real data shows much lower:**",
                "- Networks falling back to calendar.txt have low dedup (1–3×)",
                "- Even networks with feed_info.txt — wait, neither sample has feed_info.txt",
                "- Many datasets are mixed format (GTFS + NeTEx + other) — non-GTFS rows must be filtered first",
                "",
                "**Updated backfill estimate (this is iterating; final = whole-PAN scan):**",
                f"- Total raw rows: {int(depth['n_rows'].sum())}",
                f"- After non-GTFS filter (~50% from samples): ~{int(depth['n_rows'].sum() * 0.5)} rows",
                f"- After dedup (avg ~2×): ~{int(depth['n_rows'].sum() * 0.25)} distinct feeds",
                f"- Storage estimate: ~{int(depth['n_rows'].sum() * 0.25 * 0.93 / 1024)} GB compressed (mean 0.93 MB/feed)",
                f"- Backfill compute: ~{int(depth['n_rows'].sum() * 0.25 * 30 / 3600)} CPU hours single-thread; "
                f"~{int(depth['n_rows'].sum() * 0.25 * 30 / 3600 / 4)} hours on 4 cores",
            ]
    else:
        lines += [
            "",
            "_No dedup runs found. Execute `d1b_dedup_per_network.py --short-id <id> --name <slug> "
            "--steps fetch resolve dedup` to populate._",
        ]

    lines += [
        "",
        "## Recommendations",
        "",
        "### Cron cadence",
        "- Weekly cron (mid-week 03:00 UTC) covers most networks. PAN publication intervals "
        "are heterogeneous: some networks publish daily (high churn but high non-GTFS noise), "
        "others quarterly. Weekly catches all in time for monthly indicator updates.",
        "",
        "### Backfill batch order",
        "- Process in **tier order** (T5 smallest first → T1 largest last) for fastest "
        "user-visible coverage growth.",
        "- Pre-filter non-GTFS rows (no `routes.txt` in `zip_metadata`) before queueing "
        "to avoid wasting download bandwidth — Transilien's 7,145 rows contain 3,598 NeTEx/other "
        "(~50%).",
        "",
        "### AOMs without history",
        "- Process current resource only; mark `history_depth_months=0` in `panel_networks`. "
        "Show a 'Données récentes' badge in UI to distinguish from time-series-rich networks.",
        "",
        "### Mixed-format datasets caution",
        "- Many PAN datasets (especially régional / IDFM-adjacent) bundle GTFS + NeTEx + GTFS-RT "
        "in the same dataset. The dedup pipeline correctly filters for `routes.txt` presence, "
        "but storage allocation must account for the **GTFS-only** subset, not raw row count.",
        "",
        "### feed_info.txt is rare",
        "- Both validation samples (Strasbourg, Transilien) fall back to `calendar.txt` "
        "fingerprinting. `feed_info.txt` is optional in GTFS spec and rarely included by "
        "French operators. The dedup pipeline must use the calendar fallback as the **default** "
        "behavior, not an edge case.",
        "",
        "_Generated by `backend/scripts/discovery/d1_report.py` from cached CSVs._",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
