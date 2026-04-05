from fastapi import APIRouter, Depends, HTTPException
from google.cloud import firestore

from app.firestore import get_db
from app.repositories.jobs import JobRepository
from app.repositories.candidates import CandidateRepository, CandidateScoreRepository
from app.services.search_service import search_and_score
from app.services.profile_enrichment import enrich_candidate_profile
from app.config import settings

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.post("/{job_id}")
async def trigger_search(job_id: int, db: firestore.Client = Depends(get_db)):
    """手動觸發對特定 JD 的搜尋與評分"""
    try:
        result = await search_and_score(job_id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{job_id}/results")
def get_search_results(
    job_id: int,
    min_score: float | None = None,
    db: firestore.Client = Depends(get_db),
):
    """取得特定 JD 的搜尋結果（已評分排序）"""
    job_repo = JobRepository(db)
    job = job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    threshold = min_score if min_score is not None else settings.scorecard_threshold

    score_repo = CandidateScoreRepository(db)
    cand_repo = CandidateRepository(db)
    scores = score_repo.get_scores_for_job(job_id)

    results = []
    for score in scores:
        if score.get("total_score", 0) < threshold:
            continue
        candidate = cand_repo.get_candidate(score["candidate_id"])
        if candidate:
            results.append({
                "candidate": {
                    "id": candidate.id,
                    "name": candidate.name,
                    "title": candidate.title,
                    "company": candidate.company,
                    "experience_years": candidate.experience_years,
                    "education_level": candidate.education_level,
                    "skills": candidate.skills,
                    "location": candidate.location,
                    "source": candidate.source,
                    "profile_url": candidate.profile_url,
                    "status": candidate.status,
                },
                "total_score": score.get("total_score", 0),
                "score_skills": score.get("score_skills", 0),
                "score_experience": score.get("score_experience", 0),
                "score_education": score.get("score_education", 0),
                "score_industry": score.get("score_industry", 0),
                "score_location": score.get("score_location", 0),
                "score_salary": score.get("score_salary", 0),
                "score_details": score.get("score_details"),
            })

    return {
        "job_id": job.id,
        "job_title": job.title,
        "threshold": threshold,
        "total": len(results),
        "candidates": results,
    }


@router.patch("/candidates/{candidate_id}/status")
def update_candidate_status(
    candidate_id: int,
    status: str,
    db: firestore.Client = Depends(get_db),
):
    """更新候選人狀態"""
    valid_statuses = {"new", "contacted", "interviewed", "rejected", "hired"}
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    cand_repo = CandidateRepository(db)
    candidate = cand_repo.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    cand_repo.update_candidate(candidate_id, {"status": status})
    return {"message": f"Candidate {candidate_id} status updated to {status}"}


@router.post("/candidates/{candidate_id}/enrich")
async def trigger_enrich_candidate(candidate_id: int, db: firestore.Client = Depends(get_db)):
    """爬取候選人完整履歷以豐富化資料"""
    try:
        candidate = await enrich_candidate_profile(candidate_id, db)
        return {
            "id": candidate.id,
            "name": candidate.name,
            "profile_scraped": candidate.profile_scraped,
            "industry": candidate.industry,
            "skills": candidate.skills,
            "certifications": candidate.certifications,
            "work_history": candidate.work_history,
            "languages": candidate.languages,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
