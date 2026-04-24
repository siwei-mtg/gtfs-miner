"""
test_progress_replay.py — WebSocket replay of persisted ProgressEvent rows.

Verifies the fix for the "reconnect loses history" bug: a client that opens
the project WebSocket after events were emitted still sees the full timeline,
in stable order, and a second reconnection sees the identical stream.
"""
import uuid

import pytest

from app.db.database import SessionLocal
from app.db.models import ProgressEvent, Project, Tenant


@pytest.fixture
def project_with_events(client_authed):
    """Insert a project plus a deterministic 3-event progress history.

    client_authed is requested only to ensure the app is bootstrapped and
    tables are created against the real engine.
    """
    db = SessionLocal()
    try:
        tenant_id = f"tenant-{uuid.uuid4()}"
        project_id = f"proj-{uuid.uuid4()}"
        db.add(Tenant(id=tenant_id, name="replay-test"))
        db.add(Project(id=project_id, status="completed", tenant_id=tenant_id))
        events = [
            ("processing", "[1/9] reading zip", 0.10, None),
            ("processing", "[2/9] normalising",  0.55, None),
            ("completed",  "done",              1.20, None),
        ]
        for i, (status, step, t, err) in enumerate(events, start=1):
            db.add(ProgressEvent(
                project_id=project_id,
                seq=i,
                status=status,
                step=step,
                time_elapsed=t,
                error=err,
            ))
        db.commit()
        yield project_id, events
    finally:
        # Best-effort cleanup so this fixture doesn't leak rows across the
        # session-scoped real DB used by other tests.
        db.query(ProgressEvent).filter(ProgressEvent.project_id == project_id).delete()
        db.query(Project).filter(Project.id == project_id).delete()
        db.query(Tenant).filter(Tenant.id == tenant_id).delete()
        db.commit()
        db.close()


def _drain_replay(ws, n):
    """Receive n replayed messages from a freshly-opened WS."""
    return [ws.receive_json() for _ in range(n)]


def test_websocket_replays_persisted_history(client_authed, project_with_events):
    project_id, events = project_with_events
    with client_authed.websocket_connect(f"/api/v1/projects/{project_id}/ws") as ws:
        msgs = _drain_replay(ws, len(events))

    assert [m["step"] for m in msgs]   == [e[1] for e in events]
    assert [m["status"] for m in msgs] == [e[0] for e in events]
    assert [m["time_elapsed"] for m in msgs] == [e[2] for e in events]
    for m in msgs:
        assert m["project_id"] == project_id


def test_replay_is_identical_across_reconnects(client_authed, project_with_events):
    project_id, events = project_with_events
    with client_authed.websocket_connect(f"/api/v1/projects/{project_id}/ws") as ws1:
        first = _drain_replay(ws1, len(events))
    with client_authed.websocket_connect(f"/api/v1/projects/{project_id}/ws") as ws2:
        second = _drain_replay(ws2, len(events))

    assert first == second, (
        "Replay should be deterministic across reconnects — "
        "one client must not miss events another client saw."
    )
