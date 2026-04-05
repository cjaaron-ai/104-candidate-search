from fastapi import APIRouter, Depends, HTTPException
from google.cloud import firestore

from app.firestore import get_db
from app.repositories.jobs import JobRepository
from app.schemas.job import JobDescriptionCreate, JobDescriptionResponse
from app.schemas.analysis import JobImportRequest
from app.services.jd_parser import create_job_from_url

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/import", response_model=JobDescriptionResponse)
async def import_job_from_url(req: JobImportRequest, db: firestore.Client = Depends(get_db)):
    """從 104 職缺 URL 自動解析並建立 JD"""
    try:
        job = await create_job_from_url(req.url, db, req.overrides)
        return job
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/", response_model=JobDescriptionResponse)
def create_job(job_in: JobDescriptionCreate, db: firestore.Client = Depends(get_db)):
    repo = JobRepository(db)
    job = repo.create_job(job_in.model_dump())
    return job


@router.get("/", response_model=list[JobDescriptionResponse])
def list_jobs(active_only: bool = True, db: firestore.Client = Depends(get_db)):
    repo = JobRepository(db)
    return repo.list_jobs(active_only=active_only)


@router.get("/{job_id}", response_model=JobDescriptionResponse)
def get_job(job_id: int, db: firestore.Client = Depends(get_db)):
    repo = JobRepository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/{job_id}", response_model=JobDescriptionResponse)
def update_job(job_id: int, job_in: JobDescriptionCreate, db: firestore.Client = Depends(get_db)):
    repo = JobRepository(db)
    job = repo.update_job(job_id, job_in.model_dump())
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}")
def delete_job(job_id: int, db: firestore.Client = Depends(get_db)):
    repo = JobRepository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    repo.deactivate_job(job_id)
    return {"message": "Job deactivated"}
