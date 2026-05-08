"""D3 — MobilityData GTFS Validator wrapper (Plan 1 Task 3).

Plan 2 Task 5.2 promoted the core (`validate_feed`, `ValidationReport`, etc.)
to `app.services.panel_pipeline.quality` so the panel pipeline can import
without `sys.path` hackery. This module remains a CLI entry point for the
discovery report and re-exports the public API for backward compatibility.

When run as a script, validates the 3 panel-pipeline fixtures (sem, solea,
ginko) and writes a markdown report at:

    docs/superpowers/specs/2026-05-03-validator-integration-discovery.md

Java/JAR resolution order:
    1. Env var `GTFS_VALIDATOR_JAVA` (full path to java.exe or `java` if in PATH)
    2. Env var `JAVA_HOME` -> $JAVA_HOME/bin/java(.exe)
    3. Hardcoded Adoptium JDK 17 path on Windows
    4. `java` from PATH (will fail if version <11)

    Validator JAR: env `GTFS_VALIDATOR_JAR` or
    `backend/storage/discovery/d3_validator/gtfs-validator-cli.jar`.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Make `app...` importable when this script is launched standalone.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Re-export public API for backward compatibility.
from app.services.panel_pipeline.quality import (  # noqa: E402, F401
    ADOPTIUM_WIN,
    DEFAULT_JAR,
    NoticeCode,
    ValidationReport,
    ValidatorUnavailable,
    _parse_outputs,
    is_validator_available,
    resolve_java,
    resolve_jar,
    validate_feed,
)

logger = logging.getLogger("d3_validator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


FIXTURES_ROOT = BACKEND_ROOT / "tests" / "Resources" / "raw"
FIXTURES = {
    "sem":   FIXTURES_ROOT / "SEM-GTFS(2).zip",
    "solea": FIXTURES_ROOT / "SOLEA.GTFS_current.zip",
    "ginko": FIXTURES_ROOT / "gtfs-20240704-090655.zip",
}

REPORT_PATH = (
    BACKEND_ROOT.parent
    / "docs" / "superpowers" / "specs"
    / "2026-05-03-validator-integration-discovery.md"
)


# ---------- Discovery script entrypoint ----------


def _format_spec_markdown(results: dict[str, ValidationReport | dict]) -> str:
    java_used = resolve_java()
    jar_used = resolve_jar()

    lines = [
        "# D3 — MobilityData GTFS Validator Integration (Plan 1 Task 3)",
        "",
        "**Status**: ✅ Completed",
        "",
        f"**Date**: 2026-05-05",
        f"**Validator**: gtfs-validator v7.1.0 (CLI)",
        f"**Java**: OpenJDK 17 (Adoptium Temurin)",
        f"**Country code**: FR",
        "",
        "## Setup",
        "",
        f"- Java executable: `{java_used}`",
        f"- Validator JAR: `{jar_used.relative_to(BACKEND_ROOT.parent)}` (~38 MB)",
        f"- JAR source: `https://github.com/MobilityData/gtfs-validator/releases/tag/v7.1.0`",
        "",
        "## Fixture results",
        "",
        "| Fixture | Files | Validation (s) | Errors | Warnings | Infos | Distinct codes (E/W) | System errors |",
        "|---------|-------|----------------|--------|----------|-------|----------------------|---------------|",
    ]
    for name, r in results.items():
        if isinstance(r, dict):  # error case
            lines.append(f"| {name} | ERROR | — | — | — | — | — | {r['error'][:60]} |")
            continue
        lines.append(
            f"| {name} | {len(r.feed_files)} | "
            f"{r.validation_time_seconds:.2f} | "
            f"{r.error_count} | {r.warning_count} | {r.info_count} | "
            f"{r.distinct_error_codes}/{r.distinct_warning_codes} | "
            f"{len(r.system_errors)} |"
        )

    lines += ["", "## Per-fixture notice breakdown", ""]
    for name, r in results.items():
        if isinstance(r, dict):
            continue
        lines += [f"### {name}", ""]
        if not r.notices:
            lines += ["_No notices._", ""]
            continue
        lines += ["| Severity | Code | Total |", "|----------|------|-------|"]
        sev_order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
        sorted_n = sorted(r.notices, key=lambda n: (sev_order.get(n.severity, 99), -n.total))
        for n in sorted_n:
            lines.append(f"| {n.severity} | `{n.code}` | {n.total:,} |")
        lines.append("")

    lines += [
        "## Wrapper API (for Plan 2)",
        "",
        "Reusable function: `app.services.panel_pipeline.quality.validate_feed`",
        "(re-exported from `backend/scripts/discovery/d3_validator_wrapper.py` for back-compat).",
        "",
        "```python",
        "from app.services.panel_pipeline.quality import validate_feed",
        "",
        "report = validate_feed(",
        "    feed_zip=Path('feed.zip'),",
        "    output_dir=Path('out/'),",
        "    country_code='FR',",
        ")",
        "report.error_count       # int — for dq_validator_errors indicator",
        "report.warning_count     # int — for dq_validator_warnings indicator",
        "report.notices           # list[NoticeCode] — full breakdown",
        "report.summary_dict()    # JSON-friendly dict for panel_quality storage",
        "```",
        "",
        "Resolution order for Java/JAR:",
        "- `GTFS_VALIDATOR_JAVA` env var -> `JAVA_HOME` -> Windows Adoptium fallback -> `java` in PATH",
        "- `GTFS_VALIDATOR_JAR` env var -> `backend/storage/discovery/d3_validator/gtfs-validator-cli.jar`",
        "",
        "## Plan 2 integration",
        "",
        "- `panel_pipeline/quality.py` owns `validate_feed`. `panel_pipeline/indicators/quality_indicators.py`",
        "  consumes it and emits:",
        "    - `dq_validator_errors` = `report.error_count`",
        "    - `dq_validator_warnings` = `report.warning_count`",
        "- CI requirement: OpenJDK 17 must be available on the build machine (document in `backend/README.md`).",
        "- Per-feed validation budget: ~3-10s on the dev fixtures; budget 60s/feed in production for safety.",
        "",
        "_Generated by `backend/scripts/discovery/d3_validator_wrapper.py`._",
    ]
    return "\n".join(lines)


def main() -> None:
    cache_root = BACKEND_ROOT / "storage" / "discovery" / "d3_validator"
    cache_root.mkdir(parents=True, exist_ok=True)

    java_exe = resolve_java()
    jar = resolve_jar()
    logger.info("Java: %s", java_exe)
    logger.info("JAR:  %s", jar)

    results: dict[str, ValidationReport | dict] = {}
    summaries: dict[str, dict] = {}
    for name, path in FIXTURES.items():
        if not path.exists():
            logger.warning("Fixture missing: %s", path)
            results[name] = {"error": f"fixture missing: {path.name}"}
            summaries[name] = {"error": f"fixture missing: {path.name}"}
            continue
        out = cache_root / f"{name}_output"
        logger.info("Validating %s ...", name)
        try:
            r = validate_feed(path, out, country_code="FR", threads=4,
                              java_path=java_exe, jar_path=jar)
            results[name] = r
            summaries[name] = r.summary_dict()
            logger.info("%s: errors=%d warnings=%d infos=%d (%.2fs)",
                        name, r.error_count, r.warning_count, r.info_count,
                        r.validation_time_seconds)
        except Exception as e:
            logger.exception("%s validation failed", name)
            results[name] = {"error": str(e)}
            summaries[name] = {"error": str(e)}

    # Cache aggregated summary (plain JSON for Plan 2 contract tests)
    summary_path = cache_root / "summaries.json"
    summary_path.write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Wrote %s", summary_path)

    REPORT_PATH.write_text(_format_spec_markdown(results), encoding="utf-8")
    logger.info("Wrote %s", REPORT_PATH)


if __name__ == "__main__":
    sys.exit(main())
