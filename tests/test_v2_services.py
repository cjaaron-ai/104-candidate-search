from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from tests.conftest import make_job, make_candidate
from app.services.competitive_analysis import (
    _generate_comparison,
    _generate_recommendations,
    _generate_markdown_report,
)
from app.services.jd_optimizer import _rule_based_analysis
from app.services.jd_parser import _map_posting_to_jd
from app.models.competitor_jd import CompetitorJD
from crawler.crawler_104 import JobPostingData, CandidateData


# === jd_parser ===

def test_map_posting_to_jd():
    data = JobPostingData(
        title="Backend Dev",
        company="TestCo",
        source_url="https://www.104.com.tw/job/abc",
        source_id="abc",
        required_skills=["Python"],
        location="台北市",
        salary_min=50000,
        salary_max=80000,
        salary_type="monthly",
        benefits=["彈性上班"],
        description="A great job",
    )
    result = _map_posting_to_jd(data)
    assert result["title"] == "Backend Dev"
    assert result["import_method"] == "url"
    assert result["source_url"] == "https://www.104.com.tw/job/abc"
    assert result["salary_min"] == 50000
    assert result["benefits"] == ["彈性上班"]


# === competitive_analysis ===

def _make_competitor(**overrides) -> CompetitorJD:
    defaults = dict(
        analysis_id=1,
        source_url="https://www.104.com.tw/job/test",
        title="Engineer",
        company="TestCo",
        required_skills=["Python", "Docker"],
        salary_min=50000,
        salary_max=80000,
        benefits=["彈性上班"],
        min_experience_years=3,
    )
    defaults.update(overrides)
    return CompetitorJD(**defaults)


def test_generate_comparison():
    job = make_job(salary_min=40000, salary_max=60000, required_skills=["Python"])
    competitors = [
        _make_competitor(salary_min=50000, salary_max=80000, required_skills=["Python", "Docker"]),
        _make_competitor(salary_min=60000, salary_max=90000, required_skills=["Python", "Kubernetes"]),
    ]
    result = _generate_comparison(job, competitors)
    assert result["competitor_count"] == 2
    assert result["salary"]["market_max_median"] == 85000
    assert "docker" in [s.lower() for s in result["skills"]["skills_you_lack"]]


def test_generate_comparison_empty():
    job = make_job()
    result = _generate_comparison(job, [])
    assert result["competitor_count"] == 0


def test_generate_recommendations_salary_gap():
    job = make_job(salary_min=30000, salary_max=50000)
    comparison = {
        "salary": {"market_max_median": 80000},
        "skills": {"skills_you_lack": ["Docker"]},
        "benefits": {"common_benefits_you_lack": []},
    }
    recs = _generate_recommendations(job, comparison)
    salary_recs = [r for r in recs if r["dimension"] == "salary"]
    assert len(salary_recs) == 1
    assert "high" == salary_recs[0]["priority"]


def test_generate_markdown_report():
    job = make_job()
    competitors = [_make_competitor()]
    comparison = _generate_comparison(job, competitors)
    recs = _generate_recommendations(job, comparison)
    report = _generate_markdown_report(job, competitors, comparison, recs)
    assert "# 競爭 JD 分析報告" in report
    assert "薪資比較" in report


# === jd_optimizer: rule_based_analysis ===

def test_rule_based_analysis_skills_diff():
    job = make_job(required_skills=["Python", "Java"])
    resume = CandidateData(
        skills=["Python", "Docker", "Kubernetes"],
        experience_years=5,
        education_level="學士",
    )
    result = _rule_based_analysis(job, resume)
    diffs = result["differences"]
    skill_diffs = [d for d in diffs if d["field"] == "skills"]
    assert len(skill_diffs) >= 1


def test_rule_based_analysis_experience_gap():
    job = make_job(min_experience_years=10, max_experience_years=15)
    resume = CandidateData(experience_years=5)
    result = _rule_based_analysis(job, resume)
    exp_diffs = [d for d in result["differences"] if d["field"] == "experience"]
    assert len(exp_diffs) == 1
    assert "降低" in exp_diffs[0]["suggestion"]


def test_rule_based_analysis_education_gap():
    job = make_job(education_level="碩士")
    resume = CandidateData(education_level="學士")
    result = _rule_based_analysis(job, resume)
    edu_diffs = [d for d in result["differences"] if d["field"] == "education"]
    assert len(edu_diffs) == 1


def test_rule_based_analysis_salary_gap():
    job = make_job(salary_max=60000)
    resume = CandidateData(expected_salary_min=80000)
    result = _rule_based_analysis(job, resume)
    sal_diffs = [d for d in result["differences"] if d["field"] == "salary"]
    assert len(sal_diffs) == 1
