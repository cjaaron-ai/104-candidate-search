from dataclasses import dataclass
from datetime import datetime


@dataclass
class JDAnalysis:
    id: int = 0
    job_id: int | None = None
    analysis_type: str | None = None
    target_url: str | None = None
    competitor_count: int = 0
    summary: dict | None = None
    recommendations: list | None = None
    report_markdown: str | None = None
    status: str = "pending"
    created_at: datetime | None = None
    completed_at: datetime | None = None
