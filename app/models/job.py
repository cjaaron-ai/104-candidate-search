from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON, func

from app.database import Base


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    department = Column(String(100))
    description = Column(Text)
    required_skills = Column(JSON)  # ["Python", "FastAPI", ...]
    preferred_skills = Column(JSON)
    min_experience_years = Column(Integer, default=0)
    max_experience_years = Column(Integer)
    education_level = Column(String(50))  # 學士/碩士/博士
    industry = Column(String(100))
    location = Column(String(100))
    salary_min = Column(Integer)
    salary_max = Column(Integer)

    # Scorecard 權重設定
    weight_skills = Column(Float, default=30.0)
    weight_experience = Column(Float, default=25.0)
    weight_education = Column(Float, default=15.0)
    weight_industry = Column(Float, default=15.0)
    weight_location = Column(Float, default=10.0)
    weight_salary = Column(Float, default=5.0)

    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
