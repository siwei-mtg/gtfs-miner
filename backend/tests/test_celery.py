"""
test_celery.py — GROUP D: Celery + Redis integration tests (Task 13 & 15).

All tests in this file are marked @pytest.mark.integration:
they require a running Redis instance and a live Celery worker.
Run with: pytest -m integration
"""
import json
import pytest


@pytest.mark.integration
def test_celery_ping():
    """Celery worker responds to ping — requires Redis + running worker."""
    from app.celery_app import celery
    resp = celery.control.ping(timeout=2)
    assert resp, "No Celery worker responded — start Redis and the worker first."


@pytest.mark.integration
def test_ws_progress_via_redis():
    """Worker-side Redis publish reaches subscriber — no WebSocket required."""
    import redis as _redis
    from app.core.config import settings

    r = _redis.from_url(settings.REDIS_URL)
    pubsub = r.pubsub()
    pubsub.subscribe("progress:test-ws-project")
    r.publish(
        "progress:test-ws-project",
        json.dumps({"step": "test", "status": "processing"}),
    )
    for msg in pubsub.listen():
        if msg["type"] == "message":
            data = json.loads(msg["data"])
            assert data["step"] == "test"
            break
    pubsub.unsubscribe()
    r.close()
