"""
候選人履歷豐富化服務

爬取候選人完整履歷頁面，填充 V1 未取得的欄位。
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models.candidate import Candidate
from crawler.crawler_104 import Crawler104, CandidateData

logger = logging.getLogger(__name__)


async def enrich_candidate_profile(candidate_id: int, db: Session) -> Candidate:
    """爬取候選人完整履歷並更新資料庫"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
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

    _update_candidate(candidate, profile_data)
    candidate.profile_scraped = 1
    candidate.last_scraped_at = datetime.utcnow()
    db.commit()
    db.refresh(candidate)

    logger.info(f"候選人 {candidate.name} 履歷豐富化完成")
    return candidate


async def enrich_candidates_batch(
    candidate_ids: list[int],
    db: Session,
) -> list[Candidate]:
    """批次豐富化候選人履歷"""
    crawler = Crawler104(
        settings.account_104_username,
        settings.account_104_password,
        cookie_storage_path=settings.cookie_storage_path,
    )
    results = []

    try:
        await crawler.start()
        logged_in = await crawler.login()
        if not logged_in:
            raise RuntimeError("104 登入失敗")

        for cid in candidate_ids:
            candidate = db.query(Candidate).filter(Candidate.id == cid).first()
            if not candidate or not candidate.profile_url:
                continue
            if candidate.profile_scraped == 1:
                results.append(candidate)
                continue

            try:
                profile_data = await crawler.scrape_candidate_profile(candidate.profile_url)
                _update_candidate(candidate, profile_data)
                candidate.profile_scraped = 1
                candidate.last_scraped_at = datetime.utcnow()
                results.append(candidate)
                logger.info(f"候選人 {candidate.name} 履歷豐富化完成")
            except Exception as e:
                logger.warning(f"候選人 {cid} 豐富化失敗: {e}")

        db.commit()
    finally:
        await crawler.close()

    return results


def _update_candidate(candidate: Candidate, data: CandidateData):
    """用爬取資料更新候選人欄位（新資料覆蓋空欄位）"""
    candidate.industry = data.industry or candidate.industry
    candidate.expected_salary_min = data.expected_salary_min or candidate.expected_salary_min
    candidate.expected_salary_max = data.expected_salary_max or candidate.expected_salary_max
    candidate.education_major = data.education_major or candidate.education_major
    candidate.skills = data.skills or candidate.skills
    candidate.certifications = data.certifications or candidate.certifications
    candidate.languages = data.languages or candidate.languages
    candidate.work_history = data.work_history or candidate.work_history
    candidate.autobiography = data.autobiography or candidate.autobiography
