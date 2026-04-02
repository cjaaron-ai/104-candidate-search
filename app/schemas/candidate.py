from pydantic import BaseModel


class CandidateResponse(BaseModel):
    id: int
    source: str
    name: str | None = None
    title: str | None = None
    company: str | None = None
    experience_years: int | None = None
    education_level: str | None = None
    skills: list[str] | None = None
    industry: str | None = None
    location: str | None = None
    profile_url: str | None = None
    status: str

    model_config = {"from_attributes": True}


class CandidateScoreResponse(BaseModel):
    candidate: CandidateResponse
    score_skills: float
    score_experience: float
    score_education: float
    score_industry: float
    score_location: float
    score_salary: float
    total_score: float
    score_details: dict | None = None

    model_config = {"from_attributes": True}


class SearchResult(BaseModel):
    job_id: int
    job_title: str
    total_candidates: int
    above_threshold: int
    candidates: list[CandidateScoreResponse]
