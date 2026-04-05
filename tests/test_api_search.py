from unittest.mock import patch, AsyncMock


# === trigger_search ===

def test_trigger_search_success(client):
    # First create a job
    r = client.post("/api/jobs/", json={"title": "Test Job"})
    job_id = r.json()["id"]

    mock_result = {"job_id": job_id, "job_title": "Test Job", "total_candidates": 0, "candidates": []}
    with patch("app.routers.search.search_and_score", new_callable=AsyncMock, return_value=mock_result):
        resp = client.post(f"/api/search/{job_id}")
    assert resp.status_code == 200


def test_trigger_search_job_not_found(client):
    with patch("app.routers.search.search_and_score", new_callable=AsyncMock, side_effect=ValueError("not found")):
        resp = client.post("/api/search/9999")
    assert resp.status_code == 404


def test_trigger_search_runtime_error(client):
    r = client.post("/api/jobs/", json={"title": "Test Job"})
    job_id = r.json()["id"]

    with patch("app.routers.search.search_and_score", new_callable=AsyncMock, side_effect=RuntimeError("login failed")):
        resp = client.post(f"/api/search/{job_id}")
    assert resp.status_code == 503


# === get_search_results ===

def test_get_results_empty(client):
    r = client.post("/api/jobs/", json={"title": "Test Job"})
    job_id = r.json()["id"]

    resp = client.get(f"/api/search/{job_id}/results?min_score=0")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_get_results_job_not_found(client):
    resp = client.get("/api/search/9999/results")
    assert resp.status_code == 404


# === update_candidate_status ===

def test_update_candidate_status_invalid(client):
    # Create a fake candidate in Firestore mock via the db
    resp = client.patch("/api/search/candidates/9999/status?status=invalid_status")
    assert resp.status_code == 400


def test_update_candidate_not_found(client):
    resp = client.patch("/api/search/candidates/9999/status?status=contacted")
    assert resp.status_code == 404
