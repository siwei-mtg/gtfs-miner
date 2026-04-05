"""
test_websocket.py — Task 7: WebSocket integration test.

Strategy:
  1. Create project (real DB via `client` fixture — worker needs the same DB).
  2. Open WebSocket in the main thread.
  3. Trigger upload in a daemon thread (0.3 s delay so WS is accepted first).
  4. Collect JSON messages in the main thread until status == "completed"/"failed".

Threading note: TestClient's ASGI server runs in a separate thread and handles
both HTTP and WS concurrently.  The upload thread calls client.post() while the
main thread blocks on ws.receive_json() — both are independent operations on the
same TestClient and are safe to interleave.

If the test hangs in CI, the @pytest.mark.slow marker lets it run in isolation.
"""
import threading
import time
from pathlib import Path

import pytest

from .conftest import EXPECTED_CSVS

# 55 KB sample dataset — fast enough for a unit-style WS test
GTFS_ZIP_SMALL = Path(__file__).parent / "Resources" / "raw" / "gtfs-20240704-090655.zip"

PROJECT_PARAMS = {
    "hpm_debut": "07:00",
    "hpm_fin": "09:00",
    "hps_debut": "17:00",
    "hps_fin": "19:30",
    "vacances": "A",
    "pays": "法国",
}

# ──────────────────────────────────────────────────────────────────
# Task 7
# ──────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_websocket_receives_progress_messages(client):
    """WebSocket receives ≥7 step messages ending with status=completed."""
    assert GTFS_ZIP_SMALL.exists(), f"Small test dataset missing: {GTFS_ZIP_SMALL}"

    # 1. Create project
    resp = client.post("/api/v1/projects/", json=PROJECT_PARAMS)
    assert resp.status_code == 200, resp.text
    project_id = resp.json()["id"]

    messages = []
    errors = []

    def upload_after_delay():
        """POST upload 0.3 s after start so the WS is accepted before processing begins."""
        time.sleep(0.3)
        with open(GTFS_ZIP_SMALL, "rb") as f:
            r = client.post(
                f"/api/v1/projects/{project_id}/upload",
                files={"file": ("gtfs.zip", f, "application/zip")},
            )
        if r.status_code != 200:
            errors.append(f"Upload failed: {r.status_code} — {r.text}")

    upload_thread = threading.Thread(target=upload_after_delay, daemon=True)
    upload_thread.start()

    # 2. Collect messages via WebSocket
    deadline = time.time() + 300
    with client.websocket_connect(f"/api/v1/projects/{project_id}/ws") as ws:
        while time.time() < deadline:
            try:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("status") in ("completed", "failed"):
                    break
            except Exception as exc:
                errors.append(str(exc))
                break

    upload_thread.join(timeout=15)

    # 3. Assertions
    assert not errors, f"Errors during test: {errors}"
    assert len(messages) >= 7, (
        f"Expected ≥7 step messages, got {len(messages)}:\n"
        + "\n".join(str(m) for m in messages)
    )
    assert messages[-1]["status"] == "completed", (
        f"Pipeline did not complete. Last message: {messages[-1]}"
    )
    for msg in messages:
        assert "project_id" in msg, f"Missing project_id in: {msg}"
        assert "step" in msg,       f"Missing step in: {msg}"
        assert "time_elapsed" in msg, f"Missing time_elapsed in: {msg}"
