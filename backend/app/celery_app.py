from celery import Celery
from app.core.config import settings

# Fall back to in-memory broker so the app can be imported in tests without Redis
_broker = settings.REDIS_URL or "memory://"
_backend = settings.REDIS_URL or "cache+memory://"

celery = Celery(
    "gtfs_miner",
    broker=_broker,
    backend=_backend,
    include=["app.services.worker"],
)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
)
