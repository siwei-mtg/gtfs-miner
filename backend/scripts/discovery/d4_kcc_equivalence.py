"""
D4 — KCC Equivalence Contract Test (Plan 1: infrastructure only)

Validates spec §11 engineering contract. In Plan 1, this script:
  1. Runs the existing full pipeline (gtfs_core.pipeline.run_pipeline) on 3 fixtures
  2. Extracts network-level KCC = sum of F_3_KCC_Lignes.kcc
  3. Stores baseline values for Plan 2 to compare against

Output: backend/storage/discovery/d4_kcc/baselines.json
        docs/superpowers/specs/2026-05-03-kcc-equivalence-discovery.md
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd

# Add backend root to sys.path so `app.*` imports work when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.gtfs_core.gtfs_reader import read_gtfs_zip
from app.services.gtfs_core.pipeline import run_pipeline, PipelineConfig

CACHE_DIR = Path(__file__).resolve().parents[2] / "storage" / "discovery" / "d4_kcc"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "tests" / "Resources" / "raw"
FIXTURES = {
    "sem":   FIXTURES_ROOT / "SEM-GTFS(2).zip",
    "solea": FIXTURES_ROOT / "SOLEA.GTFS_current.zip",
    "ginko": FIXTURES_ROOT / "gtfs-20240704-090655.zip",
}

REPORT_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs" / "superpowers" / "specs"
    / "2026-05-03-kcc-equivalence-discovery.md"
)

logger = logging.getLogger("d4_kcc")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def extract_full_pipeline_kcc(zip_path: Path) -> dict:
    """Run full pipeline on the fixture and return network-level KCC summary.

    F_3_KCC_Lignes is in long/pivoted format: identifier columns (id_ligne_num,
    route_short_name, route_long_name) + jour_type columns (1, 2, 3, ...) where
    each cell is the KCC value for that line × day type. Network-level KCC for
    a representative day type = sum of one column across all rows.

    For the contract test, we capture all jour_type column sums + the cross-day
    grand total (which is what panel_pipeline's prod_kcc_year would compute).
    """
    raw = read_gtfs_zip(zip_path)
    config = PipelineConfig()
    outputs = run_pipeline(raw, config=config, on_progress=lambda s: logger.info("  %s", s))

    f3 = outputs["F_3_KCC_Lignes"]
    id_cols = {"id_ligne_num", "route_short_name", "route_long_name"}
    jour_type_cols = [c for c in f3.columns if c not in id_cols]
    # Each column is a jour_type representative day's KCC across all lines
    per_jour_type = {
        str(c): float(pd.to_numeric(f3[c], errors="coerce").sum())
        for c in jour_type_cols
    }
    grand_total_kcc = float(sum(per_jour_type.values()))

    f1 = outputs["F_1_Nombre_Courses_Lignes"]
    f1_jour_type_cols = [c for c in f1.columns if c not in id_cols]
    courses_per_jour_type = {
        str(c): float(pd.to_numeric(f1[c], errors="coerce").sum())
        for c in f1_jour_type_cols
    }

    return {
        "n_lines": int(len(f3)),
        "jour_type_columns": [str(c) for c in jour_type_cols],
        "kcc_per_jour_type": per_jour_type,
        "kcc_grand_total": grand_total_kcc,
        "courses_per_jour_type": courses_per_jour_type,
        "courses_grand_total": float(sum(courses_per_jour_type.values())),
    }


def main() -> None:
    baselines: dict[str, dict] = {}
    for name, path in FIXTURES.items():
        if not path.exists():
            logger.warning("Fixture missing: %s", path)
            continue
        logger.info("Running full pipeline on %s ...", name)
        try:
            data = extract_full_pipeline_kcc(path)
            baselines[name] = data
            logger.info("%s done: %s", name, data)
        except Exception as e:
            logger.exception("%s failed: %s", name, e)
            baselines[name] = {"error": str(e)}

    cache_path = CACHE_DIR / "baselines.json"
    cache_path.write_text(json.dumps(baselines, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote %s", cache_path)

    lines = [
        "# D4 — KCC Equivalence Contract Test (Plan 1 baseline)",
        "",
        f"**Fixtures**: {', '.join(FIXTURES.keys())}",
        f"**Cached baselines**: `backend/storage/discovery/d4_kcc/baselines.json`",
        "",
        "## F_3_KCC_Lignes format note",
        "",
        "The full pipeline outputs `F_3_KCC_Lignes` in **wide format**: identifier",
        "columns (`id_ligne_num`, `route_short_name`, `route_long_name`) + one numeric",
        "column per jour_type (1=Mon, 2=Tue, ..., 7=Sun, sometimes vacances variants).",
        "**Network-level KCC** for the contract test = sum across ALL jour_type columns",
        "and ALL lines (= the grand total below).",
        "",
        "## Baseline results (full pipeline)",
        "",
        "| Fixture | Lines | jour_type cols | KCC grand total | Courses grand total |",
        "|---------|-------|----------------|-----------------|---------------------|",
    ]
    for name, data in baselines.items():
        if "error" in data:
            lines.append(f"| {name} | ERROR | — | — | {data['error'][:60]} |")
            continue
        jc = ", ".join(data["jour_type_columns"])
        lines.append(
            f"| {name} | {data['n_lines']} | `{jc}` | "
            f"{data['kcc_grand_total']:,.2f} | "
            f"{data['courses_grand_total']:,.0f} |"
        )

    lines.append("")
    lines.append("## Per-jour_type KCC breakdown")
    lines.append("")
    for name, data in baselines.items():
        if "error" in data:
            continue
        lines.append(f"### {name}")
        lines.append("")
        lines.append("| jour_type | KCC | Courses |")
        lines.append("|-----------|-----|---------|")
        for jt in data["jour_type_columns"]:
            kcc_v = data["kcc_per_jour_type"].get(jt, 0)
            courses_v = data["courses_per_jour_type"].get(jt, 0)
            lines.append(f"| {jt} | {kcc_v:,.2f} | {courses_v:,.0f} |")
        lines.append("")
    lines += [
        "",
        "## Plan 2 contract",
        "",
        "When `panel_pipeline` implements `prod_kcc_year`, the value computed",
        "on each fixture **must** be within 0.1% of the corresponding baseline above.",
        "",
        "Test: `backend/tests/panel_pipeline/test_kcc_equivalence_contract.py` (currently skipped).",
        "",
        "_Generated by `backend/scripts/discovery/d4_kcc_equivalence.py`._",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %s", REPORT_PATH)


if __name__ == "__main__":
    main()
