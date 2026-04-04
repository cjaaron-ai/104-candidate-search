from unittest.mock import patch, AsyncMock

from tests.conftest import make_job, make_candidate
from app.models.candidate import CandidateScore


# === trigger_search ===

def test_trigger_search_success(client, db):
    job = make_job()
    db.add(job)
    db.commit()
    db.refresh(job)

    mock_result = {"job_id": job.id, "job_title": job.title, "total_candidates": 0, "candidates": []}
    with patch("app.routers.search.search_and_score", new_callable=AsyncMock, return_value=mock_result):
        resp = client.post(f"/api/search/{job.id}")
    assert resp.status_code == 200
    assert resp.json()["job_id"] == job.id


def test_trigger_search_job_not_found(client):
    with patch("app.routers.search.search_and_score", new_callable=AsyncMock, side_effect=ValueError("not found")):
        resp = client.post("/api/search/9999")
    assert resp.status_code == 404


def test_trigger_search_runtime_error(client, db):
    job = make_job()
    db.add(job)
    db.commit()
    db.refresh(job)

    with patch("app.routers.search.search_and_score", new_callable=AsyncMock, side_effect=RuntimeError("login failed")):
        resp = client.post(f"/api/search/{job.id}")
    assert resp.status_code == 503


# === get_search_results ===

def test_get_results_empty(client, db):
    job = make_job()
    db.add(job)
    db.commit()
    db.refresh(job)

    resp = client.get(f"/api/search/{job.id}/results?min_score=0")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_get_results_with_scores(client, db):
    job = make_job()
    db.add(job)
    db.commit()
    db.refresh(job)

    cand = make_candidate()
    db.add(cand)
    db.commit()
    db.refresh(cand)

    score = CandidateScore(
        candidate_id=cand.id, job_id=job.id,
        score_skills=80, score_experience=90, score_education=100,
        score_industry=70, score_location=100, score_salary=100,
        total_score=85.0, score_details={},
    )
    db.add(score)
    db.commit()

    resp = client.get(f"/api/search/{job.id}/results?min_score=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["candidates"][0]["total_score"] == 85.0


def test_get_results_threshold_filter(client, db):
    job = make_job()
    db.add(job)
    db.commit()
    db.refresh(job)

    c1 = make_candidate(source_id="c1", name="高分")
    c2 = make_candidate(source_id="c2", name="低分")
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)

    db.add(CandidateScore(candidate_id=c1.id, job_id=job.id, total_score=85.0, score_details={}))
    db.add(CandidateScore(candidate_id=c2.id, job_id=job.id, total_score=50.0, score_details={}))
    db.commit()

    resp = client.get(f"/api/search/{job.id}/results?min_score=70")
    assert resp.json()["total"] == 1

    resp = client.get(f"/api/search/{job.id}/results?min_score=0")
    assert resp.json()["total"] == 2


def test_get_results_job_not_found(client):
    resp = client.get("/api/search/9999/results")
    assert resp.status_code == 404


# === update_candidate_status ===

def test_update_candidate_status(client, db):
    cand = make_candidate()
    db.add(cand)
    db.commit()
    db.refresh(cand)

    resp = client.patch(f"/api/search/candidates/{cand.id}/status?status=contacted")
    assert resp.status_code == 200
    assert "contacted" in resp.json()["message"]


def test_update_candidate_status_invalid(client, db):
    cand = make_candidate()
    db.add(cand)
    db.commit()
    db.refresh(cand)

    resp = client.patch(f"/api/search/candidates/{cand.id}/status?status=invalid_status")
    assert resp.status_code == 400


def test_update_candidate_not_found(client):
    resp = client.patch("/api/search/candidates/9999/status?status=contacted")
    assert resp.status_code == 404
