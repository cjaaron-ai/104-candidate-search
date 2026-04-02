from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON, func

from app.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(20), nullable=False)  # "104" / "linkedin"
    source_id = Column(String(100))  # 平台上的原始 ID
    name = Column(String(100))
    title = Column(String(200))
    company = Column(String(200))
    experience_years = Column(Integer)
    education_level = Column(String(50))
    education_school = Column(String(200))
    education_major = Column(String(200))
    skills = Column(JSON)  # ["Python", "SQL", ...]
    industry = Column(String(100))
    location = Column(String(100))
    expected_salary_min = Column(Integer)
    expected_salary_max = Column(Integer)
    profile_url = Column(String(500))
    raw_data = Column(Text)  # 完整爬取資料 JSON

    # 狀態追蹤
    status = Column(String(20), default="new")  # new / contacted / interviewed / rejected / hired
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CandidateScore(Base):
    __tablename__ = "candidate_scores"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, nullable=False, index=True)
    job_id = Column(Integer, nullable=False, index=True)

    score_skills = Column(Float, default=0)
    score_experience = Column(Float, default=0)
    score_education = Column(Float, default=0)
    score_industry = Column(Float, default=0)
    score_location = Column(Float, default=0)
    score_salary = Column(Float, default=0)
    total_score = Column(Float, default=0)

    score_details = Column(JSON)  # 評分細節
    created_at = Column(DateTime, server_default=func.now())
