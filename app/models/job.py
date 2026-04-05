from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobDescription:
    id: int = 0
    title: str = ""
    department: str | None = None
    description: str | None = None
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    min_experience_years: int = 0
    max_experience_years: int | None = None
    education_level: str | None = None
    industry: str | None = None
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None

    # V2: URL 匯入相關欄位
    source_url: str | None = None
    source_id: str | None = None
    company: str | None = None
    benefits: list[str] | None = None
    salary_type: str | None = None
    full_description: str | None = None
    import_method: str = "manual"

    # Scorecard 權重設定
    weight_skills: float = 30.0
    weight_experience: float = 25.0
    weight_education: float = 15.0
    weight_industry: float = 15.0
    weight_location: float = 10.0
    weight_salary: float = 5.0

    is_active: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None
