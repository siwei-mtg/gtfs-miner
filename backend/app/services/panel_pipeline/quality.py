"""GTFS validator integration. Plan 2 Task 5.2.

Promoted from `backend/scripts/discovery/d3_validator_wrapper.py` so the panel
pipeline can import without `sys.path` hackery. The discovery script remains
as a thin re-exporter / CLI entry point.

Provides:
    - NoticeCode, ValidationReport dataclasses
    - validate_feed(zip_path, output_dir, ...) -> ValidationReport
    - resolve_java(), resolve_jar() helpers
    - is_validator_available() — quick check, no subprocess
    - ValidatorUnavailable exception

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
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("panel_pipeline.quality")


# Path layout: this file lives at backend/app/services/panel_pipeline/quality.py
# parents[3] therefore points to backend/.
BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JAR = BACKEND_ROOT / "storage" / "discovery" / "d3_validator" / "gtfs-validator-cli.jar"
ADOPTIUM_WIN = Path(r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot\bin\java.exe")


class ValidatorUnavailable(Exception):
    """Raised when Java + GTFS Validator JAR cannot be resolved."""


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
    """Return the path to a Java 11+ executable. Raises FileNotFoundError if none found."""
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
    """Return path to the validator CLI JAR. Raises FileNotFoundError if missing."""
    explicit = os.environ.get("GTFS_VALIDATOR_JAR")
    jar = Path(explicit) if explicit else DEFAULT_JAR
    if not jar.exists():
        raise FileNotFoundError(
            f"Validator JAR not found at {jar}. Download from "
            "https://github.com/MobilityData/gtfs-validator/releases (CLI jar) "
            "or set GTFS_VALIDATOR_JAR."
        )
    return jar


def is_validator_available() -> bool:
    """Quick check: True iff both Java and the validator JAR can be resolved."""
    try:
        resolve_java()
        resolve_jar()
        return True
    except (FileNotFoundError, RuntimeError):
        return False


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
        country_code: ISO 3166-1 alpha-2 (FR for French feeds -> enables FR-specific rules).
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
