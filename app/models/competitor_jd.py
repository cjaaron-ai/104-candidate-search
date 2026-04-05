from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CompetitorJD:
    id: int = 0
    analysis_id: int = 0
    source_url: str = ""
    source_id: str | None = None
    title: str | None = None
    company: str | None = None
    industry: str | None = None
    required_skills: list[str] | None = field(default_factory=list)
    preferred_skills: list[str] | None = field(default_factory=list)
    min_experience_years: int | None = None
    max_experience_years: int | None = None
    education_level: str | None = None
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_type: str | None = None
    benefits: list[str] | None = field(default_factory=list)
    description: str | None = None
    raw_data: str | None = None
    created_at: datetime | None = None
