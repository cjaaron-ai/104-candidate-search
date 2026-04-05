import dataclasses

from google.cloud import firestore as fs

from app.repositories.base import BaseRepository
from app.models.candidate import Candidate, CandidateScore

_CAND_FIELDS = {f.name for f in dataclasses.fields(Candidate)}
_SCORE_FIELDS = {f.name for f in dataclasses.fields(CandidateScore)}


class CandidateRepository(BaseRepository):
    collection_name = "candidates"

    def find_by_source(self, source: str, source_id: str) -> Candidate | None:
        docs = self.query(
            filters=[("source", "==", source), ("source_id", "==", source_id)],
            limit=1,
        )
        return self._to_model(docs[0]) if docs else None

    def create_candidate(self, data: dict) -> Candidate:
        doc = self.create(data)
        return self._to_model(doc)

    def get_candidate(self, cid: int) -> Candidate | None:
        doc = self.get_by_id(cid)
        return self._to_model(doc) if doc else None

    def update_candidate(self, cid: int, data: dict) -> Candidate | None:
        doc = self.update(cid, data)
        return self._to_model(doc) if doc else None

    @staticmethod
    def _to_model(data: dict) -> Candidate:
        return Candidate(**{k: v for k, v in data.items() if k in _CAND_FIELDS})


class CandidateScoreRepository(BaseRepository):
    collection_name = "candidate_scores"

    def find_score(self, candidate_id: int, job_id: int) -> dict | None:
        docs = self.query(
            filters=[("candidate_id", "==", candidate_id), ("job_id", "==", job_id)],
            limit=1,
        )
        return docs[0] if docs else None

    def get_scores_for_job(self, job_id: int) -> list[dict]:
        return self.query(
            filters=[("job_id", "==", job_id)],
            order_by="total_score",
            descending=True,
        )

    def create_score(self, data: dict) -> CandidateScore:
        doc = self.create(data)
        return CandidateScore(**{k: v for k, v in doc.items() if k in _SCORE_FIELDS})
