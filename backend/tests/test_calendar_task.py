"""
test_calendar_task.py — Tests pour la tâche Celery de synchronisation du calendrier (TD-004).

Vérifie :
  1. La tâche est bien enregistrée dans le registre Celery.
  2. Le planning Beat hebdomadaire est configuré.
  3. La tâche s'exécute sans erreur en mode eager (sans Redis).
  4. La tâche retourne un entier (nombre de lignes mises à jour).
"""
import pytest
from unittest.mock import patch

from app.celery_app import celery
import app.services.calendar_task  # noqa: F401 — déclenche l'enregistrement @celery.task


def test_sync_calendar_task_registered():
    """gtfs_miner.sync_calendar doit être présent dans le registre Celery."""
    assert "gtfs_miner.sync_calendar" in celery.tasks


def test_beat_schedule_configured():
    """Le planning Beat hebdomadaire doit être configuré."""
    schedule = celery.conf.beat_schedule
    assert "sync-calendar-weekly" in schedule
    entry = schedule["sync-calendar-weekly"]
    assert entry["task"] == "gtfs_miner.sync_calendar"


def test_sync_calendar_task_eager():
    """
    La tâche s'exécute en mode eager (CELERY_TASK_ALWAYS_EAGER).
    On mock sync_from_api pour éviter les appels réseau en CI.
    """
    celery.conf.update(task_always_eager=True, task_eager_propagates=True)
    try:
        with patch("app.services.calendar_task.sync_from_api", return_value=42) as mock_sync:
            from app.services.calendar_task import sync_calendar_task
            result = sync_calendar_task.delay()
            assert result.get() == 42
            assert mock_sync.called
    finally:
        celery.conf.update(task_always_eager=False)


def test_sync_calendar_task_returns_int():
    """La tâche retourne toujours un entier, même si l'API retourne 0 mise à jour."""
    celery.conf.update(task_always_eager=True, task_eager_propagates=True)
    try:
        with patch("app.services.calendar_task.sync_from_api", return_value=0):
            from app.services.calendar_task import sync_calendar_task
            result = sync_calendar_task.delay()
            assert isinstance(result.get(), int)
    finally:
        celery.conf.update(task_always_eager=False)
