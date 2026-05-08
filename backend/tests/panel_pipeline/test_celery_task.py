"""Plan 2 Task 7.2 — panel.run Celery task wrapper.

We don't go through a broker; we invoke the underlying ``run`` callable
directly after monkeypatching ``run_panel_pipeline`` to a stub. This
keeps the test independent of Redis and the Windows ``-P solo`` setup.
"""
from __future__ import annotations


def test_panel_run_task_is_registered():
    """The Celery task is importable and registered with the right name."""
    from app.services.worker import panel_run_task

    assert panel_run_task.name == "panel.run"


def test_panel_run_task_calls_orchestrator(monkeypatch):
    """The Celery task delegates to ``run_panel_pipeline``."""
    from app.services.worker import panel_run_task

    called: dict[str, str] = {}

    def fake_run(feed_id: str) -> None:
        called["feed_id"] = feed_id

    monkeypatch.setattr(
        "app.services.panel_pipeline.run.run_panel_pipeline", fake_run
    )

    # Celery's ``Task.run`` is the user-defined function; ``__call__`` would
    # also work but ``run`` is the documented synchronous entry point.
    class _Self:
        # Stand-in for the Celery task ``self`` (bind=True) — we never hit
        # ``self.retry`` because ``fake_run`` doesn't raise.
        pass

    panel_run_task.run.__func__(_Self(), "test-feed-id")  # type: ignore[attr-defined]

    assert called["feed_id"] == "test-feed-id"
