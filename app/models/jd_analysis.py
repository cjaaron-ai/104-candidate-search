from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, func

from app.database import Base


class JDAnalysis(Base):
    __tablename__ = "jd_analyses"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_descriptions.id"), index=True)
    analysis_type = Column(String(30))  # "competitive" / "resume_optimization"
    target_url = Column(String(500))
    competitor_count = Column(Integer, default=0)
    summary = Column(JSON)
    recommendations = Column(JSON)
    report_markdown = Column(Text)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)
