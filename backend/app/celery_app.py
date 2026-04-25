from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Fall back to in-memory broker so the app can be imported in tests without Redis
_broker = settings.REDIS_URL or "memory://"
_backend = settings.REDIS_URL or "cache+memory://"

celery = Celery(
    "gtfs_miner",
    broker=_broker,
    backend=_backend,
    include=[
        "app.services.worker",
        "app.services.calendar_task",
    ],
)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    beat_schedule={
        # 每周一 03:00 从 api.gouv.fr 拉取最新假期排期
        # 确保新学年数据（Vacances_A/B/C + Ferie）及时更新
        "sync-calendar-weekly": {
            "task": "gtfs_miner.sync_calendar",
            "schedule": crontab(hour=3, minute=0, day_of_week=1),
        },
    },
)
