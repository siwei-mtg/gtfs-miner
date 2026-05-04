"""D3 validator wrapper smoke test — parser only, no Java/JAR required."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BACKEND_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

CACHED_SEM = (
    BACKEND_ROOT / "storage" / "discovery" / "d3_validator" / "sem_output" / "report.json"
)


def test_wrapper_module_importable() -> None:
    """The discovery script must be importable so Plan 2 can reuse `validate_feed`."""
    from discovery import d3_validator_wrapper as w  # noqa: F401
    assert hasattr(w, "validate_feed")
    assert hasattr(w, "ValidationReport")
    assert hasattr(w, "NoticeCode")


def test_validation_report_dataclass_counts() -> None:
    """ValidationReport.error/warning/info_count derive from notices list."""
    from discovery.d3_validator_wrapper import NoticeCode, ValidationReport
    r = ValidationReport(
        validator_version="7.1.0",
        validated_at="2026-05-05T00:00:00Z",
        country_code="FR",
        feed_input="test.zip",
        output_dir=Path("/tmp/out"),
        validation_time_seconds=1.0,
        notices=[
            NoticeCode("err_a", "ERROR", 5),
            NoticeCode("warn_a", "WARNING", 100),
            NoticeCode("warn_b", "WARNING", 50),
            NoticeCode("info_a", "INFO", 1),
        ],
    )
    assert r.error_count == 5
    assert r.warning_count == 150
    assert r.info_count == 1
    assert r.distinct_error_codes == 1
    assert r.distinct_warning_codes == 2
    summary = r.summary_dict()
    assert summary["error_count"] == 5
    assert summary["warning_count"] == 150
    assert len(summary["notice_codes"]) == 4


@pytest.mark.skipif(
    not CACHED_SEM.exists(),
    reason="Cached SEM validator output missing — run d3_validator_wrapper.py first",
)
def test_parse_real_sem_output() -> None:
    """The parser must handle the real v7.1.0 report.json shape end-to-end."""
    from discovery.d3_validator_wrapper import _parse_outputs
    out_dir = CACHED_SEM.parent
    report = _parse_outputs(out_dir, Path("SEM-GTFS(2).zip"), "FR")
    assert report.validator_version == "7.1.0"
    assert report.error_count == 0  # Spec doc 2026-05-03 baseline
    assert report.warning_count == 166
    assert report.info_count == 1
    assert any(n.code == "expired_calendar" for n in report.notices)
