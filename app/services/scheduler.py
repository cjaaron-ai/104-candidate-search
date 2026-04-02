"""
定期排程模組 — 自動對所有啟用中的 JD 執行搜尋與評分
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import SessionLocal
from app.models.job import JobDescription
from app.services.search_service import search_and_score
from app.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_search_all():
    """排程任務：對所有啟用中的 JD 執行搜尋"""
    logger.info("Starting scheduled search for all active jobs...")
    db = SessionLocal()
    try:
        jobs = db.query(JobDescription).filter(JobDescription.is_active == 1).all()
        for job in jobs:
            try:
                result = await search_and_score(job.id, db)
                logger.info(
                    f"Job '{job.title}': found {result['total_candidates']} candidates, "
                    f"{result['above_threshold']} above threshold"
                )
            except Exception as e:
                logger.error(f"Search failed for job '{job.title}': {e}")
    finally:
        db.close()
    logger.info("Scheduled search completed")


def start_scheduler():
    scheduler.add_job(
        scheduled_search_all,
        "interval",
        minutes=settings.search_interval_minutes,
        id="search_all_jobs",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started, interval: {settings.search_interval_minutes} minutes")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("Scheduler stopped")
