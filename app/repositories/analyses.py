import dataclasses

from app.repositories.base import BaseRepository
from app.models.jd_analysis import JDAnalysis
from app.models.competitor_jd import CompetitorJD

_ANALYSIS_FIELDS = {f.name for f in dataclasses.fields(JDAnalysis)}
_COMP_FIELDS = {f.name for f in dataclasses.fields(CompetitorJD)}


class AnalysisRepository(BaseRepository):
    collection_name = "jd_analyses"

    def create_analysis(self, data: dict) -> JDAnalysis:
        doc = self.create(data)
        return self._to_model(doc)

    def get_analysis(self, analysis_id: int) -> JDAnalysis | None:
        doc = self.get_by_id(analysis_id)
        return self._to_model(doc) if doc else None

    def update_analysis(self, analysis_id: int, data: dict) -> JDAnalysis | None:
        doc = self.update(analysis_id, data)
        return self._to_model(doc) if doc else None

    @staticmethod
    def _to_model(data: dict) -> JDAnalysis:
        return JDAnalysis(**{k: v for k, v in data.items() if k in _ANALYSIS_FIELDS})


class CompetitorJDRepository(BaseRepository):
    collection_name = "competitor_jds"

    def create_competitor(self, data: dict) -> CompetitorJD:
        doc = self.create(data)
        return self._to_model(doc)

    def get_by_analysis(self, analysis_id: int) -> list[CompetitorJD]:
        docs = self.query(filters=[("analysis_id", "==", analysis_id)])
        return [self._to_model(d) for d in docs]

    @staticmethod
    def _to_model(data: dict) -> CompetitorJD:
        return CompetitorJD(**{k: v for k, v in data.items() if k in _COMP_FIELDS})
