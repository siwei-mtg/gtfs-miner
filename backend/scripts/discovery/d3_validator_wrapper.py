"""
D3 — MobilityData GTFS Validator wrapper (Plan 1 Task 3).

Provides a reusable `validate_feed()` function for Plan 2 (`dq_validator_errors`,
`dq_validator_warnings` indicators). When run as a script, validates the 3
panel-pipeline fixtures (sem, solea, ginko) and writes a markdown report at:

    docs/superpowers/specs/2026-05-03-validator-integration-discovery.md

Java/JAR resolution order:
    1. Env var `GTFS_VALIDATOR_JAVA` (full path to java.exe or `java` if in PATH)
    2. Env var `JAVA_HOME` → $JAVA_HOME/bin/java(.exe)
    3. Hardcoded Adoptium JDK 17 path on Windows
    4. `java` from PATH (will fail if version <11)

    Validator JAR: env `GTFS_VALIDATOR_JAR` or `backend/storage/discovery/d3_validator/gtfs-validator-cli.jar`.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("d3_validator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JAR = BACKEND_ROOT / "storage" / "discovery" / "d3_validator" / "gtfs-validator-cli.jar"
ADOPTIUM_WIN = Path(r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot\bin\java.exe")

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


@dataclass(frozen=True)
class NoticeCode:
    """A distinct validator notice rule."""
    code: str
    severity: str  # "ERROR" | "WARNING" | "INFO"
    total: int  # occurrence count across the feed


@dataclass
class ValidationReport:
    """Parsed output of one validator invocation."""
    validator_version: str
    validated_at: str
    country_code: str
    feed_input: str
    output_dir: Path
    validation_time_seconds: float
    feed_files: list[str] = field(default_factory=list)
    notices: list[NoticeCode] = field(default_factory=list)
    system_errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(n.total for n in self.notices if n.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(n.total for n in self.notices if n.severity == "WARNING")

    @property
    def info_count(self) -> int:
        return sum(n.total for n in self.notices if n.severity == "INFO")

    @property
    def distinct_error_codes(self) -> int:
        return sum(1 for n in self.notices if n.severity == "ERROR")

    @property
    def distinct_warning_codes(self) -> int:
        return sum(1 for n in self.notices if n.severity == "WARNING")

    def summary_dict(self) -> dict[str, Any]:
        return {
            "validator_version": self.validator_version,
            "validated_at": self.validated_at,
            "feed_input": self.feed_input,
            "validation_time_seconds": self.validation_time_seconds,
            "files": self.feed_files,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "distinct_error_codes": self.distinct_error_codes,
            "distinct_warning_codes": self.distinct_warning_codes,
            "notice_codes": [
                {"code": n.code, "severity": n.severity, "total": n.total}
                for n in self.notices
            ],
            "system_error_count": len(self.system_errors),
        }


def resolve_java() -> str:
    """Return the path to a Java 11+ executable. Raises if none found."""
    explicit = os.environ.get("GTFS_VALIDATOR_JAVA")
    if explicit:
        return explicit
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if candidate.exists():
            return str(candidate)
    if os.name == "nt" and ADOPTIUM_WIN.exists():
        return str(ADOPTIUM_WIN)
    found = shutil.which("java")
    if found:
        return found
    raise FileNotFoundError(
        "No Java executable found. Install OpenJDK 17 from https://adoptium.net/ "
        "or set GTFS_VALIDATOR_JAVA / JAVA_HOME."
    )


def resolve_jar() -> Path:
    """Return path to the validator CLI JAR. Raises if missing."""
    explicit = os.environ.get("GTFS_VALIDATOR_JAR")
    jar = Path(explicit) if explicit else DEFAULT_JAR
    if not jar.exists():
        raise FileNotFoundError(
            f"Validator JAR not found at {jar}. Download from "
            "https://github.com/MobilityData/gtfs-validator/releases (CLI jar) "
            "or set GTFS_VALIDATOR_JAR."
        )
    return jar


def validate_feed(
    feed_zip: Path,
    output_dir: Path,
    *,
    country_code: str = "FR",
    threads: int = 4,
    java_path: str | None = None,
    jar_path: Path | None = None,
    timeout_seconds: int = 600,
) -> ValidationReport:
    """Run the MobilityData GTFS Validator on a feed and parse the report.

    Args:
        feed_zip: Path to the GTFS .zip file.
        output_dir: Directory where the validator will write report.json + report.html.
        country_code: ISO 3166-1 alpha-2 (FR for French feeds → enables FR-specific rules).
        threads: Validator thread count (CLI -t).
        java_path: Override java executable (default: auto-resolved).
        jar_path: Override JAR path (default: auto-resolved).
        timeout_seconds: Subprocess timeout — abort if validation hangs.

    Returns:
        ValidationReport with parsed counts. Raises CalledProcessError on validator failure.
    """
    feed_zip = feed_zip.resolve()
    if not feed_zip.exists():
        raise FileNotFoundError(f"Feed not found: {feed_zip}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve()

    java_exe = java_path or resolve_java()
    jar = jar_path or resolve_jar()

    cmd = [
        java_exe, "-jar", str(jar),
        "--input", str(feed_zip),
        "--output_base", str(output_dir),
        "--country_code", country_code,
        "--threads", str(threads),
        "--pretty",
        "--skip_validator_update",
    ]
    logger.info("Running validator: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if result.returncode != 0:
        logger.error("Validator stderr:\n%s", result.stderr[-2000:])
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr,
        )

    return _parse_outputs(output_dir, feed_zip, country_code)


def _parse_outputs(output_dir: Path, feed_zip: Path, country_code: str) -> ValidationReport:
    report_json = output_dir / "report.json"
    if not report_json.exists():
        raise FileNotFoundError(f"Validator did not produce {report_json}")
    data = json.loads(report_json.read_text(encoding="utf-8"))

    summary = data.get("summary", {})
    notices = [
        NoticeCode(
            code=n["code"],
            severity=n["severity"],
            total=int(n["totalNotices"]),
        )
        for n in data.get("notices", [])
    ]

    sys_err_path = output_dir / "system_errors.json"
    system_errors: list[dict[str, Any]] = []
    if sys_err_path.exists() and sys_err_path.stat().st_size > 0:
        try:
            sys_data = json.loads(sys_err_path.read_text(encoding="utf-8"))
            system_errors = sys_data.get("notices", []) if isinstance(sys_data, dict) else []
        except json.JSONDecodeError:
            logger.warning("system_errors.json present but unparseable")

    return ValidationReport(
        validator_version=summary.get("validatorVersion", "unknown"),
        validated_at=summary.get("validatedAt", ""),
        country_code=country_code,
        feed_input=str(feed_zip),
        output_dir=output_dir,
        validation_time_seconds=float(summary.get("validationTimeSeconds", 0.0)),
        feed_files=list(summary.get("files", [])),
        notices=notices,
        system_errors=system_errors,
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
        "Reusable function: `backend/scripts/discovery/d3_validator_wrapper.py:validate_feed`",
        "",
        "```python",
        "from scripts.discovery.d3_validator_wrapper import validate_feed",
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
        "- `GTFS_VALIDATOR_JAVA` env var → `JAVA_HOME` → Windows Adoptium fallback → `java` in PATH",
        "- `GTFS_VALIDATOR_JAR` env var → `backend/storage/discovery/d3_validator/gtfs-validator-cli.jar`",
        "",
        "## Plan 2 integration",
        "",
        "- `panel_pipeline/quality.py` will import `validate_feed`, persist the JSON output to",
        "  `panel_quality.validator_report_json` (compressed) and emit:",
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
