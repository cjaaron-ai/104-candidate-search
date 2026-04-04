from tests.conftest import make_job, make_candidate
from app.services.scorecard import (
    score_candidate,
    _score_skills,
    _score_experience,
    _score_education,
    _score_industry,
    _score_location,
    _score_salary,
)


# === _score_skills ===

def test_skills_perfect_match():
    job = make_job(required_skills=["Python", "FastAPI"], preferred_skills=["Docker"])
    cand = make_candidate(skills=["Python", "FastAPI", "Docker"])
    score, details = _score_skills(job, cand)
    assert score == 100.0


def test_skills_required_only():
    job = make_job(required_skills=["Python", "FastAPI"], preferred_skills=["Docker"])
    cand = make_candidate(skills=["Python", "FastAPI"])
    score, _ = _score_skills(job, cand)
    assert score == 70.0  # 100*0.7 + 0*0.3


def test_skills_partial_required():
    job = make_job(required_skills=["Python", "FastAPI"], preferred_skills=[])
    cand = make_candidate(skills=["Python"])
    score, _ = _score_skills(job, cand)
    assert score == 35.0  # 50*0.7 + 0*0.3


def test_skills_preferred_only():
    job = make_job(required_skills=["Java"], preferred_skills=["Docker"])
    cand = make_candidate(skills=["Docker"])
    score, _ = _score_skills(job, cand)
    assert score == 30.0  # 0*0.7 + 100*0.3


def test_skills_no_requirements():
    job = make_job(required_skills=[], preferred_skills=[])
    cand = make_candidate(skills=["Python"])
    score, details = _score_skills(job, cand)
    assert score == 100.0
    assert "未定義" in details["reason"]


def test_skills_case_insensitive():
    job = make_job(required_skills=["python", "fastapi"], preferred_skills=[])
    cand = make_candidate(skills=["Python", "FastAPI"])
    score, _ = _score_skills(job, cand)
    assert score == 70.0  # all required matched, no preferred


def test_skills_no_candidate_skills():
    job = make_job(required_skills=["Python"], preferred_skills=["Docker"])
    cand = make_candidate(skills=[])
    score, _ = _score_skills(job, cand)
    assert score == 0.0


# === _score_experience ===

def test_experience_within_range():
    job = make_job(min_experience_years=3, max_experience_years=8)
    cand = make_candidate(experience_years=5)
    score, _ = _score_experience(job, cand)
    assert score == 100.0


def test_experience_below_minimum():
    job = make_job(min_experience_years=5, max_experience_years=10)
    cand = make_candidate(experience_years=3)
    score, _ = _score_experience(job, cand)
    assert score == 60.0  # 100 - 2*20


def test_experience_above_maximum():
    job = make_job(min_experience_years=3, max_experience_years=8)
    cand = make_candidate(experience_years=15)
    score, _ = _score_experience(job, cand)
    # over = 15 - 8 = 7, score = max(60, 100 - 7*5) = max(60, 65) = 65
    assert score == 65.0


def test_experience_no_requirement():
    job = make_job(min_experience_years=0, max_experience_years=None)
    cand = make_candidate(experience_years=10)
    score, details = _score_experience(job, cand)
    assert score == 100.0
    assert "未定義" in details["reason"]


def test_experience_zero_candidate():
    job = make_job(min_experience_years=5, max_experience_years=10)
    cand = make_candidate(experience_years=0)
    score, _ = _score_experience(job, cand)
    assert score == 0.0  # 100 - 5*20 = 0


# === _score_education ===

def test_education_meets_requirement():
    job = make_job(education_level="學士")
    cand = make_candidate(education_level="學士")
    score, _ = _score_education(job, cand)
    assert score == 100.0


def test_education_exceeds():
    job = make_job(education_level="學士")
    cand = make_candidate(education_level="碩士")
    score, _ = _score_education(job, cand)
    assert score == 100.0


def test_education_one_below():
    job = make_job(education_level="碩士")
    cand = make_candidate(education_level="學士")
    score, _ = _score_education(job, cand)
    assert score == 70.0


def test_education_two_below():
    job = make_job(education_level="博士")
    cand = make_candidate(education_level="學士")
    score, _ = _score_education(job, cand)
    # req_rank=5, cand_rank=3, gap=2, score = max(0, 100 - 2*30) = 40
    assert score == 40.0


def test_education_no_requirement():
    job = make_job(education_level=None)
    cand = make_candidate(education_level="碩士")
    score, details = _score_education(job, cand)
    assert score == 100.0
    assert "未定義" in details["reason"]


# === _score_industry ===

def test_industry_match():
    job = make_job(industry="軟體")
    cand = make_candidate(industry="軟體業")
    score, _ = _score_industry(job, cand)
    assert score == 100.0


def test_industry_no_match():
    job = make_job(industry="金融")
    cand = make_candidate(industry="軟體業")
    score, _ = _score_industry(job, cand)
    assert score == 40.0


def test_industry_candidate_missing():
    job = make_job(industry="軟體")
    cand = make_candidate(industry=None)
    score, _ = _score_industry(job, cand)
    assert score == 50.0


# === _score_location ===

def test_location_match():
    job = make_job(location="台北市")
    cand = make_candidate(location="台北市")
    score, _ = _score_location(job, cand)
    assert score == 100.0


def test_location_no_match():
    job = make_job(location="台北市")
    cand = make_candidate(location="高雄市")
    score, _ = _score_location(job, cand)
    assert score == 30.0


def test_location_partial_match():
    job = make_job(location="台北")
    cand = make_candidate(location="台北市信義區")
    score, _ = _score_location(job, cand)
    assert score == 100.0


# === _score_salary ===

def test_salary_within_budget():
    job = make_job(salary_max=80000)
    cand = make_candidate(expected_salary_min=60000)
    score, _ = _score_salary(job, cand)
    assert score == 100.0


def test_salary_over_budget():
    job = make_job(salary_max=80000)
    cand = make_candidate(expected_salary_min=100000)
    score, _ = _score_salary(job, cand)
    # over_pct = (100000-80000)/80000*100 = 25%, score = 100 - 25*2 = 50
    assert score == 50.0


def test_salary_candidate_missing():
    job = make_job(salary_max=80000)
    cand = make_candidate(expected_salary_min=None)
    score, _ = _score_salary(job, cand)
    assert score == 70.0


def test_salary_no_job_max():
    job = make_job(salary_max=None)
    cand = make_candidate(expected_salary_min=100000)
    score, details = _score_salary(job, cand)
    assert score == 100.0


# === score_candidate (integration) ===

def test_score_candidate_weighted_total():
    job = make_job(
        weight_skills=50.0,
        weight_experience=50.0,
        weight_education=0.0,
        weight_industry=0.0,
        weight_location=0.0,
        weight_salary=0.0,
    )
    cand = make_candidate(
        skills=["Python", "FastAPI"],  # all required -> skills=70 (no preferred match)
        experience_years=5,             # within range -> experience=100
    )
    result = score_candidate(job, cand)
    # total = (70*50 + 100*50) / 100 = 85.0
    assert result["total_score"] == 85.0


def test_score_candidate_returns_all_dimensions():
    job = make_job()
    cand = make_candidate()
    result = score_candidate(job, cand)
    assert "score_skills" in result
    assert "score_experience" in result
    assert "score_education" in result
    assert "score_industry" in result
    assert "score_location" in result
    assert "score_salary" in result
    assert "total_score" in result
    assert "score_details" in result
