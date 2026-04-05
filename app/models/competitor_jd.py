from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, func

from app.database import Base


class CompetitorJD(Base):
    __tablename__ = "competitor_jds"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("jd_analyses.id"), index=True)
    source_url = Column(String(500), nullable=False)
    source_id = Column(String(100))
    title = Column(String(200))
    company = Column(String(200))
    industry = Column(String(100))
    required_skills = Column(JSON)
    preferred_skills = Column(JSON)
    min_experience_years = Column(Integer)
    max_experience_years = Column(Integer)
    education_level = Column(String(50))
    location = Column(String(100))
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    salary_type = Column(String(20))
    benefits = Column(JSON)
    description = Column(Text)
    raw_data = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
