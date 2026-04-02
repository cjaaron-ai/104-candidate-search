from pydantic import BaseModel


class JobDescriptionCreate(BaseModel):
    title: str
    department: str | None = None
    description: str | None = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    min_experience_years: int = 0
    max_experience_years: int | None = None
    education_level: str | None = None
    industry: str | None = None
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    weight_skills: float = 30.0
    weight_experience: float = 25.0
    weight_education: float = 15.0
    weight_industry: float = 15.0
    weight_location: float = 10.0
    weight_salary: float = 5.0


class JobDescriptionResponse(JobDescriptionCreate):
    id: int
    is_active: int

    model_config = {"from_attributes": True}
