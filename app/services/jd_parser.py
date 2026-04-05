"""
JD URL 解析服務 — 三個 V2 Feature 的共用基礎

從 104 職缺 URL 自動解析 JD 欄位，建立 JobDescription。
"""

import logging

from google.cloud import firestore

from app.config import settings
from app.models.job import JobDescription
from app.repositories.jobs import JobRepository
from crawler.crawler_104 import Crawler104, JobPostingData

logger = logging.getLogger(__name__)


async def parse_jd_from_url(url: str) -> JobPostingData:
    """從 104 職缺 URL 爬取並回傳結構化 JD 資料"""
    crawler = Crawler104(
        settings.account_104_username,
        settings.account_104_password,
        cookie_storage_path=settings.cookie_storage_path,
    )
    try:
        await crawler._ensure_browser()
        return await crawler.scrape_job_posting(url)
    finally:
        await crawler.close()


async def create_job_from_url(
    url: str,
    db: firestore.Client,
    overrides: dict | None = None,
) -> JobDescription:
    """解析 URL 建立 JD，支援覆蓋特定欄位"""
    data = await parse_jd_from_url(url)
    fields = _map_posting_to_jd(data)

    if overrides:
        fields.update({k: v for k, v in overrides.items() if v is not None})

    repo = JobRepository(db)
    job = repo.create_job(fields)
    logger.info(f"已從 URL 建立 JD: {job.title} (id={job.id})")
    return job


def _map_posting_to_jd(data: JobPostingData) -> dict:
    """將 JobPostingData 映射到 JobDescription 欄位"""
    return {
        "title": data.title,
        "description": data.description,
        "required_skills": data.required_skills,
        "preferred_skills": data.preferred_skills,
        "min_experience_years": data.min_experience_years,
        "max_experience_years": data.max_experience_years,
        "education_level": data.education_level,
        "industry": data.industry,
        "location": data.location,
        "salary_min": data.salary_min or None,
        "salary_max": data.salary_max or None,
        "source_url": data.source_url,
        "source_id": data.source_id,
        "company": data.company,
        "benefits": data.benefits,
        "salary_type": data.salary_type,
        "full_description": data.full_description,
        "import_method": "url",
    }
