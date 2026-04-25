"""
calendar_task.py — Celery 定时任务：每周同步法国官方假期日历

注册任务名称：gtfs_miner.sync_calendar
Beat 调度：每周一 03:00（见 celery_app.py beat_schedule）

调用 calendar_seeder.sync_from_api() 从 api.gouv.fr 拉取最新
学区假期与法定节假日数据并 upsert 至 calendar_dates 表。
"""
import logging

from app.celery_app import celery
from app.db.database import SessionLocal
from app.services.calendar_seeder import sync_from_api

logger = logging.getLogger(__name__)


@celery.task(name="gtfs_miner.sync_calendar")
def sync_calendar_task() -> int:
    """
    定期同步法国官方假期日历。

    Returns:
        更新/插入的行数。
    """
    db = SessionLocal()
    try:
        n = sync_from_api(db)
        logger.info("sync_calendar_task: %d lignes mises à jour", n)
        return n
    finally:
        db.close()
