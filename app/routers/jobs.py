from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.job import JobDescription
from app.schemas.job import JobDescriptionCreate, JobDescriptionResponse
from app.schemas.analysis import JobImportRequest
from app.services.jd_parser import create_job_from_url

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/import", response_model=JobDescriptionResponse)
async def import_job_from_url(req: JobImportRequest, db: Session = Depends(get_db)):
    """從 104 職缺 URL 自動解析並建立 JD"""
    try:
        job = await create_job_from_url(req.url, db, req.overrides)
        return job
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/", response_model=JobDescriptionResponse)
def create_job(job_in: JobDescriptionCreate, db: Session = Depends(get_db)):
    job = JobDescription(**job_in.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/", response_model=list[JobDescriptionResponse])
def list_jobs(active_only: bool = True, db: Session = Depends(get_db)):
    query = db.query(JobDescription)
    if active_only:
        query = query.filter(JobDescription.is_active == 1)
    return query.all()


@router.get("/{job_id}", response_model=JobDescriptionResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/{job_id}", response_model=JobDescriptionResponse)
def update_job(job_id: int, job_in: JobDescriptionCreate, db: Session = Depends(get_db)):
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for key, value in job_in.model_dump().items():
        setattr(job, key, value)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = 0
    db.commit()
    return {"message": "Job deactivated"}
