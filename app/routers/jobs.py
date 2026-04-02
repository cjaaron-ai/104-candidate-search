from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.job import JobDescription
from app.schemas.job import JobDescriptionCreate, JobDescriptionResponse

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


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
