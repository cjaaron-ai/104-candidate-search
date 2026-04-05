"""
定期排程模組 — 可透過環境變數設定排程時間，或停用排程改用外部觸發
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.firestore import get_firestore_client
from app.repositories.jobs import JobRepository
from app.services.search_service import search_and_score
from app.services.notifier import notify_search_results, notify_error

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_search_all():
    """排程任務：對所有啟用中的 JD 執行搜尋，完成後發送 Telegram 通知"""
    logger.info("開始執行排程搜尋...")
    db = get_firestore_client()
    job_repo = JobRepository(db)
    all_results = []

    try:
        jobs = job_repo.list_jobs(active_only=True)
        for job in jobs:
            try:
                result = await search_and_score(job.id, db)
                all_results.append(result)
                logger.info(
                    f"職缺 '{job.title}': 找到 {result['total_candidates']} 位候選人，"
                    f"{result['above_threshold']} 位達標"
                )
            except Exception as e:
                logger.error(f"職缺 '{job.title}' 搜尋失敗: {e}")
                await notify_error(f"職缺「{job.title}」搜尋失敗: {e}")
    except Exception as e:
        logger.error(f"排程搜尋失敗: {e}")

    if all_results:
        await notify_search_results(all_results)

    logger.info("排程搜尋完成")


def start_scheduler():
    if not settings.schedule_cron_hour:
        logger.info("排程未設定（SCHEDULE_CRON_HOUR 為空），跳過排程啟動。")
        return

    scheduler.add_job(
        scheduled_search_all,
        "cron",
        hour=settings.schedule_cron_hour,
        minute=settings.schedule_cron_minute,
        timezone=settings.schedule_timezone,
        id="search_all_jobs",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"排程已啟動，每日 {settings.schedule_cron_hour}:{settings.schedule_cron_minute} "
        f"({settings.schedule_timezone}) 執行搜尋"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("排程已停止")
