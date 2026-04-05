from unittest.mock import patch, AsyncMock

from tests.conftest import make_job
from app.models.jd_analysis import JDAnalysis


def test_get_analysis_not_found(client):
    resp = client.get("/api/analysis/9999")
    assert resp.status_code == 404


def test_get_analysis_report_not_found(client):
    resp = client.get("/api/analysis/9999/report")
    assert resp.status_code == 404


def test_get_analysis_found(client, db):
    analysis = JDAnalysis(
        job_id=None,
        analysis_type="competitive",
        status="completed",
        summary={"test": True},
        recommendations=[],
        report_markdown="# Report",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    resp = client.get(f"/api/analysis/{analysis.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_get_analysis_report(client, db):
    analysis = JDAnalysis(
        analysis_type="competitive",
        status="completed",
        report_markdown="# My Report\nContent here",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    resp = client.get(f"/api/analysis/{analysis.id}/report")
    assert resp.status_code == 200
    assert "My Report" in resp.json()["report_markdown"]


def test_trigger_competitive_analysis_job_not_found(client):
    with patch(
        "app.routers.analysis.analyze_competitive_landscape",
        new_callable=AsyncMock,
        side_effect=ValueError("not found"),
    ):
        resp = client.post("/api/analysis/competitive/9999", json={"max_competitors": 5})
    assert resp.status_code == 404


def test_trigger_optimization_job_not_found(client):
    with patch(
        "app.routers.analysis.optimize_jd_for_target",
        new_callable=AsyncMock,
        side_effect=ValueError("not found"),
    ):
        resp = client.post("/api/analysis/optimize/9999", json={"target_resume_url": "https://vip.104.com.tw/resume/abc"})
    assert resp.status_code == 404
