from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.candidate import Candidate, CandidateScore
from app.models.job import JobDescription
from app.services.search_service import search_and_score
from app.config import settings

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.post("/{job_id}")
async def trigger_search(job_id: int, db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db),
):
    """取得特定 JD 的搜尋結果（已評分排序）"""
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    threshold = min_score if min_score is not None else settings.scorecard_threshold

    scores = (
        db.query(CandidateScore)
        .filter(CandidateScore.job_id == job_id)
        .order_by(CandidateScore.total_score.desc())
        .all()
    )

    results = []
    for score in scores:
        if score.total_score < threshold:
            continue
        candidate = db.query(Candidate).filter(Candidate.id == score.candidate_id).first()
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
                "total_score": score.total_score,
                "score_skills": score.score_skills,
                "score_experience": score.score_experience,
                "score_education": score.score_education,
                "score_industry": score.score_industry,
                "score_location": score.score_location,
                "score_salary": score.score_salary,
                "score_details": score.score_details,
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
    db: Session = Depends(get_db),
):
    """更新候選人狀態（new/contacted/interviewed/rejected/hired）"""
    valid_statuses = {"new", "contacted", "interviewed", "rejected", "hired"}
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.status = status
    db.commit()
    return {"message": f"Candidate {candidate_id} status updated to {status}"}
