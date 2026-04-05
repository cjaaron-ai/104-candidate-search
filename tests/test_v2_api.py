from unittest.mock import patch, AsyncMock

from app.repositories.analyses import AnalysisRepository


def test_get_analysis_not_found(client):
    resp = client.get("/api/analysis/9999")
    assert resp.status_code == 404


def test_get_analysis_report_not_found(client):
    resp = client.get("/api/analysis/9999/report")
    assert resp.status_code == 404


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
