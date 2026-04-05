from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Candidate:
    id: int = 0
    source: str = "104"
    source_id: str | None = None
    name: str | None = None
    title: str | None = None
    company: str | None = None
    experience_years: int | None = None
    education_level: str | None = None
    education_school: str | None = None
    education_major: str | None = None
    skills: list[str] | None = field(default_factory=list)
    industry: str | None = None
    location: str | None = None
    expected_salary_min: int | None = None
    expected_salary_max: int | None = None
    profile_url: str | None = None
    raw_data: str | None = None

    # V2: 完整履歷爬取欄位
    certifications: list | None = None
    languages: list | None = None
    work_history: list | None = None
    autobiography: str | None = None
    profile_scraped: int = 0
    last_scraped_at: datetime | None = None

    # 狀態追蹤
    status: str = "new"
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class CandidateScore:
    id: int = 0
    candidate_id: int = 0
    job_id: int = 0
    score_skills: float = 0.0
    score_experience: float = 0.0
    score_education: float = 0.0
    score_industry: float = 0.0
    score_location: float = 0.0
    score_salary: float = 0.0
    total_score: float = 0.0
    score_details: dict | None = None
    created_at: datetime | None = None
