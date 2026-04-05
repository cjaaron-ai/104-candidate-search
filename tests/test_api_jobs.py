def test_create_job(client):
    resp = client.post("/api/jobs/", json={"title": "Backend Engineer"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Backend Engineer"
    assert data["weight_skills"] == 30.0
    assert data["is_active"] == 1


def test_create_job_with_full_data(client):
    resp = client.post("/api/jobs/", json={
        "title": "Frontend Dev",
        "required_skills": ["React", "TypeScript"],
        "preferred_skills": ["Next.js"],
        "min_experience_years": 2,
        "max_experience_years": 5,
        "education_level": "學士",
        "location": "台北市",
        "salary_min": 50000,
        "salary_max": 80000,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["required_skills"] == ["React", "TypeScript"]
    assert data["salary_max"] == 80000


def test_list_jobs_empty(client):
    resp = client.get("/api/jobs/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_jobs(client):
    client.post("/api/jobs/", json={"title": "Job A"})
    client.post("/api/jobs/", json={"title": "Job B"})
    resp = client.get("/api/jobs/")
    assert len(resp.json()) == 2


def test_get_job(client):
    r = client.post("/api/jobs/", json={"title": "My Job"})
    job_id = r.json()["id"]
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "My Job"


def test_get_job_not_found(client):
    resp = client.get("/api/jobs/9999")
    assert resp.status_code == 404


def test_update_job(client):
    r = client.post("/api/jobs/", json={"title": "Old Title"})
    job_id = r.json()["id"]
    resp = client.put(f"/api/jobs/{job_id}", json={"title": "New Title"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


def test_update_job_not_found(client):
    resp = client.put("/api/jobs/9999", json={"title": "X"})
    assert resp.status_code == 404


def test_delete_job(client):
    r = client.post("/api/jobs/", json={"title": "To Delete"})
    job_id = r.json()["id"]
    resp = client.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 200

    get_resp = client.get(f"/api/jobs/{job_id}")
    assert get_resp.json()["is_active"] == 0
