"""
候選人履歷豐富化服務

爬取候選人完整履歷頁面，填充 V1 未取得的欄位。
"""

import logging
from datetime import datetime

from google.cloud import firestore

from app.config import settings
from app.repositories.candidates import CandidateRepository
from crawler.crawler_104 import Crawler104, CandidateData

logger = logging.getLogger(__name__)


async def enrich_candidate_profile(candidate_id: int, db: firestore.Client):
    """爬取候選人完整履歷並更新 Firestore"""
    cand_repo = CandidateRepository(db)
    candidate = cand_repo.get_candidate(candidate_id)
    if not candidate:
        raise ValueError(f"Candidate ID {candidate_id} not found")

    if not candidate.profile_url:
        raise ValueError(f"Candidate {candidate_id} 沒有 profile_url")

    crawler = Crawler104(
        settings.account_104_username,
        settings.account_104_password,
        cookie_storage_path=settings.cookie_storage_path,
    )
    try:
        await crawler.start()
        logged_in = await crawler.login()
        if not logged_in:
            raise RuntimeError("104 登入失敗")
        profile_data = await crawler.scrape_candidate_profile(candidate.profile_url)
    finally:
        await crawler.close()

    update_data = {
        "industry": profile_data.industry or candidate.industry,
        "expected_salary_min": profile_data.expected_salary_min or candidate.expected_salary_min,
        "expected_salary_max": profile_data.expected_salary_max or candidate.expected_salary_max,
        "education_major": profile_data.education_major or candidate.education_major,
        "skills": profile_data.skills or candidate.skills,
        "certifications": profile_data.certifications or candidate.certifications,
        "languages": profile_data.languages or candidate.languages,
        "work_history": profile_data.work_history or candidate.work_history,
        "autobiography": profile_data.autobiography or candidate.autobiography,
        "profile_scraped": 1,
        "last_scraped_at": datetime.utcnow(),
    }

    updated = cand_repo.update_candidate(candidate_id, update_data)
    logger.info(f"候選人 {candidate.name} 履歷豐富化完成")
    return updated
