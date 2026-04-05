"""
搜尋服務 — 整合爬蟲與評分引擎

負責：
1. 從 JD 提取搜尋條件
2. 呼叫 104 爬蟲搜尋人選
3. 儲存候選人至 Firestore
4. 執行 Scorecard 評分並排序
"""

import logging
from dataclasses import asdict

from google.cloud import firestore

from app.repositories.jobs import JobRepository
from app.repositories.candidates import CandidateRepository, CandidateScoreRepository
from app.services.scorecard import score_candidate
from app.services.notifier import notify_captcha
from app.config import settings
from crawler.crawler_104 import Crawler104, CandidateData

logger = logging.getLogger(__name__)


async def search_and_score(job_id: int, db: firestore.Client) -> dict:
    """對指定 JD 執行搜尋與評分流程"""
    job_repo = JobRepository(db)
    cand_repo = CandidateRepository(db)
    score_repo = CandidateScoreRepository(db)

    job = job_repo.get_job(job_id)
    if not job:
        raise ValueError(f"Job ID {job_id} not found")

    # 1. 組合搜尋關鍵字
    keywords = list(job.required_skills or [])
    if job.title:
        keywords.insert(0, job.title)

    # 2. 呼叫爬蟲搜尋
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
        candidate = _save_candidate(raw, cand_repo)

        if candidate.status in ("rejected", "hired"):
            continue

        existing_score = score_repo.find_score(candidate.id, job.id)
        if existing_score:
            continue

        scores = score_candidate(job, candidate)

        score_data = {
            "candidate_id": candidate.id,
            "job_id": job.id,
            **{k: v for k, v in scores.items() if k != "score_details"},
            "score_details": scores["score_details"],
        }
        score_repo.create_score(score_data)
        results.append({"candidate": candidate, "scores": scores})

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


def _save_candidate(raw: CandidateData, cand_repo: CandidateRepository):
    """儲存或更新候選人資料"""
    existing = cand_repo.find_by_source(raw.source, raw.source_id)

    if existing:
        update_data = {}
        if raw.title:
            update_data["title"] = raw.title
        if raw.company:
            update_data["company"] = raw.company
        if raw.skills:
            update_data["skills"] = raw.skills
        if raw.experience_years:
            update_data["experience_years"] = raw.experience_years
        if raw.education_level:
            update_data["education_level"] = raw.education_level
        if raw.location:
            update_data["location"] = raw.location
        if raw.raw_data:
            update_data["raw_data"] = raw.raw_data
        if update_data:
            return cand_repo.update_candidate(existing.id, update_data)
        return existing

    data = {
        "source": raw.source,
        "source_id": raw.source_id,
        "name": raw.name,
        "title": raw.title,
        "company": raw.company,
        "experience_years": raw.experience_years,
        "education_level": raw.education_level,
        "education_school": raw.education_school,
        "education_major": raw.education_major,
        "skills": raw.skills,
        "industry": raw.industry,
        "location": raw.location,
        "expected_salary_min": raw.expected_salary_min,
        "expected_salary_max": raw.expected_salary_max,
        "profile_url": raw.profile_url,
        "raw_data": raw.raw_data,
    }
    return cand_repo.create_candidate(data)
