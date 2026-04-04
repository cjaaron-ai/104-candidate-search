"""
搜尋服務 — 整合爬蟲與評分引擎

負責：
1. 從 JD 提取搜尋條件
2. 呼叫 104 爬蟲搜尋人選
3. 儲存候選人至資料庫
4. 執行 Scorecard 評分並排序
"""

import json
import logging

from sqlalchemy.orm import Session

from app.models.job import JobDescription
from app.models.candidate import Candidate, CandidateScore
from app.services.scorecard import score_candidate
from app.services.notifier import notify_captcha
from app.config import settings
from crawler.crawler_104 import Crawler104, CandidateData

logger = logging.getLogger(__name__)


async def search_and_score(job_id: int, db: Session) -> dict:
    """對指定 JD 執行搜尋與評分流程"""

    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise ValueError(f"Job ID {job_id} not found")

    # 1. 組合搜尋關鍵字
    keywords = list(job.required_skills or [])
    if job.title:
        keywords.insert(0, job.title)

    # 2. 呼叫爬蟲搜尋（含 CAPTCHA 偵測回呼）
    crawler = Crawler104(
        settings.account_104_username,
        settings.account_104_password,
        cookie_storage_path=settings.cookie_storage_path,
    )
    crawler.on_captcha_detected = notify_captcha

    try:
        await crawler.start()
        logged_in = await crawler.login()
        if not logged_in:
            raise RuntimeError("104 登入失敗")

        raw_candidates = await crawler.search_candidates(
            keywords=keywords,
            location=job.location,
            experience_min=job.min_experience_years,
            experience_max=job.max_experience_years,
            education=job.education_level,
        )
    finally:
        await crawler.close()

    # 3. 儲存候選人並評分
    results = []
    for raw in raw_candidates:
        candidate = _save_candidate(raw, db)

        # 排除已處理的人選
        if candidate.status in ("rejected", "hired"):
            continue

        # 檢查是否已評分過
        existing_score = (
            db.query(CandidateScore)
            .filter(CandidateScore.candidate_id == candidate.id, CandidateScore.job_id == job.id)
            .first()
        )
        if existing_score:
            continue

        # 評分
        scores = score_candidate(job, candidate)

        score_record = CandidateScore(
            candidate_id=candidate.id,
            job_id=job.id,
            **{k: v for k, v in scores.items() if k != "score_details"},
            score_details=scores["score_details"],
        )
        db.add(score_record)
        results.append({"candidate": candidate, "scores": scores})

    db.commit()

    # 4. 依總分排序
    results.sort(key=lambda x: x["scores"]["total_score"], reverse=True)

    return {
        "job_id": job.id,
        "job_title": job.title,
        "total_candidates": len(results),
        "above_threshold": sum(
            1 for r in results if r["scores"]["total_score"] >= settings.scorecard_threshold
        ),
        "candidates": results,
    }


def _save_candidate(raw: CandidateData, db: Session) -> Candidate:
    """儲存或更新候選人資料（跨平台去重）"""

    # 先用 source + source_id 去重
    existing = (
        db.query(Candidate)
        .filter(Candidate.source == raw.source, Candidate.source_id == raw.source_id)
        .first()
    )

    if existing:
        # 更新資料
        existing.title = raw.title or existing.title
        existing.company = raw.company or existing.company
        existing.skills = raw.skills or existing.skills
        existing.experience_years = raw.experience_years or existing.experience_years
        existing.education_level = raw.education_level or existing.education_level
        existing.location = raw.location or existing.location
        existing.raw_data = raw.raw_data or existing.raw_data
        db.flush()
        return existing

    candidate = Candidate(
        source=raw.source,
        source_id=raw.source_id,
        name=raw.name,
        title=raw.title,
        company=raw.company,
        experience_years=raw.experience_years,
        education_level=raw.education_level,
        education_school=raw.education_school,
        education_major=raw.education_major,
        skills=raw.skills,
        industry=raw.industry,
        location=raw.location,
        expected_salary_min=raw.expected_salary_min,
        expected_salary_max=raw.expected_salary_max,
        profile_url=raw.profile_url,
        raw_data=raw.raw_data,
    )
    db.add(candidate)
    db.flush()
    return candidate
