"""
定期排程模組 — 每日自動對所有啟用中的 JD 執行搜尋與評分，並發送 Telegram 通知
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import SessionLocal
from app.models.job import JobDescription
from app.services.search_service import search_and_score
from app.services.notifier import notify_search_results, notify_error

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_search_all():
    """排程任務：對所有啟用中的 JD 執行搜尋，完成後發送 Telegram 通知"""
    logger.info("開始執行排程搜尋...")
    db = SessionLocal()
    all_results = []
    has_error = False

    try:
        jobs = db.query(JobDescription).filter(JobDescription.is_active == 1).all()
        for job in jobs:
            try:
                result = await search_and_score(job.id, db)
                all_results.append(result)
                logger.info(
                    f"職缺 '{job.title}': 找到 {result['total_candidates']} 位候選人，"
                    f"{result['above_threshold']} 位達標"
                )
            except Exception as e:
                has_error = True
                logger.error(f"職缺 '{job.title}' 搜尋失敗: {e}")
                await notify_error(f"職缺「{job.title}」搜尋失敗: {e}")
    finally:
        db.close()

    # 發送搜尋結果通知
    if all_results:
        await notify_search_results(all_results)

    logger.info("排程搜尋完成")


def start_scheduler():
    scheduler.add_job(
        scheduled_search_all,
        "cron",
        hour=8,
        minute=0,
        timezone="Asia/Taipei",
        id="search_all_jobs",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("排程已啟動，每日 08:00 (Asia/Taipei) 執行搜尋")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("排程已停止")
