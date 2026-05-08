"""DSP events loader (Task 4.2). Plan 2 Assumption A2: hash includes notes."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import PanelDspEvent, PanelNetwork

# Module under test
from scripts.load_dsp_events import compute_row_hash, load_dsp_events


SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "dsp_timeline_sample.csv"


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture()
def lyon_network(session):
    n = PanelNetwork(slug="lyon", pan_dataset_id="pan-lyon", display_name="TCL")
    session.add(n)
    session.commit()
    return n


def test_compute_row_hash_includes_notes():
    """Per Assumption A2: changing `notes` produces a different hash."""
    base = {
        "network_slug": "lyon", "event_type": "contract_started",
        "event_date": "2017-09-01", "operator_before": "",
        "operator_after": "Keolis", "source": "BOAMP",
        "boamp_url": "https://boamp.fr/...", "notes": "v1",
    }
    h1 = compute_row_hash(base)
    h2 = compute_row_hash({**base, "notes": "v2"})
    assert h1 != h2, "edits to notes should produce a different hash"


def test_compute_row_hash_deterministic():
    """Same row -> same hash (no random salt)."""
    row = {
        "network_slug": "lyon", "event_type": "contract_started",
        "event_date": "2017-09-01", "operator_before": "",
        "operator_after": "Keolis", "source": "BOAMP",
        "boamp_url": "https://boamp.fr/...", "notes": "x",
    }
    assert compute_row_hash(row) == compute_row_hash(row)


def test_load_dsp_events_inserts_new_rows(session, lyon_network):
    n_inserted = load_dsp_events(session, SAMPLE)
    assert n_inserted == 2
    assert session.query(PanelDspEvent).count() == 2


def test_load_dsp_events_idempotent_on_replay(session, lyon_network):
    """Re-loading the same CSV -> no new inserts."""
    load_dsp_events(session, SAMPLE)
    n_second = load_dsp_events(session, SAMPLE)
    assert n_second == 0
    assert session.query(PanelDspEvent).count() == 2


def test_load_dsp_events_edit_appends_new_row(session, lyon_network, tmp_path):
    """Mutating `notes` creates a NEW row (audit trail per A2). Old row stays."""
    load_dsp_events(session, SAMPLE)
    initial = session.query(PanelDspEvent).count()
    edited = tmp_path / "edited.csv"
    edited.write_text(
        SAMPLE.read_text(encoding="utf-8").replace("v1-pilot", "v2-revised"),
        encoding="utf-8",
    )
    n_added = load_dsp_events(session, edited)
    assert n_added == 2  # both rows changed notes; both get new hash -> both insert
    assert session.query(PanelDspEvent).count() == initial + 2


def test_load_dsp_events_skips_unknown_slug(session):
    """If a CSV row references an unknown network_slug, skip it (warn, don't crash)."""
    # No network created -> all rows in SAMPLE reference "lyon" -> all skipped
    n_inserted = load_dsp_events(session, SAMPLE)
    assert n_inserted == 0
    assert session.query(PanelDspEvent).count() == 0


def test_load_dsp_events_handles_optional_fields(session, lyon_network, tmp_path):
    """contract_value_eur empty -> None; date parses correctly."""
    load_dsp_events(session, SAMPLE)
    rows = session.query(PanelDspEvent).all()
    for r in rows:
        assert r.contract_value_eur is None  # sample has empty value
        assert r.event_date is not None
        assert r.network_id == lyon_network.network_id
