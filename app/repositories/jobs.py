import dataclasses

from app.repositories.base import BaseRepository
from app.models.job import JobDescription

_JOB_FIELDS = {f.name for f in dataclasses.fields(JobDescription)}


class JobRepository(BaseRepository):
    collection_name = "job_descriptions"

    def create_job(self, data: dict) -> JobDescription:
        data.setdefault("is_active", 1)
        data.setdefault("import_method", "manual")
        doc = self.create(data)
        return self._to_model(doc)

    def get_job(self, job_id: int) -> JobDescription | None:
        doc = self.get_by_id(job_id)
        return self._to_model(doc) if doc else None

    def list_jobs(self, active_only: bool = True) -> list[JobDescription]:
        filters = [("is_active", "==", 1)] if active_only else None
        docs = self.query(filters=filters)
        return [self._to_model(d) for d in docs]

    def update_job(self, job_id: int, data: dict) -> JobDescription | None:
        doc = self.update(job_id, data)
        return self._to_model(doc) if doc else None

    def deactivate_job(self, job_id: int) -> bool:
        return self.update(job_id, {"is_active": 0}) is not None

    @staticmethod
    def _to_model(data: dict) -> JobDescription:
        return JobDescription(**{k: v for k, v in data.items() if k in _JOB_FIELDS})
