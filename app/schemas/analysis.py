from pydantic import BaseModel


class JobImportRequest(BaseModel):
    url: str
    overrides: dict | None = None


class CompetitiveAnalysisRequest(BaseModel):
    max_competitors: int = 10


class JDOptimizeRequest(BaseModel):
    target_resume_url: str


class AnalysisResponse(BaseModel):
    id: int
    job_id: int | None = None
    analysis_type: str
    target_url: str | None = None
    competitor_count: int = 0
    summary: dict | None = None
    recommendations: list | None = None
    report_markdown: str | None = None
    status: str

    model_config = {"from_attributes": True}
