from unittest.mock import patch, AsyncMock

import pytest

from tests.conftest import make_job, make_candidate, MockFirestoreClient
from app.services.search_service import search_and_score
from app.repositories.jobs import JobRepository
from app.repositories.candidates import CandidateRepository, CandidateScoreRepository
from crawler.crawler_104 import CandidateData


def _make_candidate_data(**overrides) -> CandidateData:
    defaults = dict(
        source="104",
        source_id="test001",
        name="張三",
        title="Engineer",
        company="TestCo",
        experience_years=5,
        education_level="學士",
        skills=["Python"],
        industry="軟體業",
        location="台北市",
        expected_salary_min=60000,
    )
    defaults.update(overrides)
    return CandidateData(**defaults)


@pytest.fixture()
def firestore_db():
    """Create a mock Firestore client with patched firestore module"""
    db = MockFirestoreClient()
    with patch("app.repositories.base.firestore") as mock_fs:
        from tests.conftest import MockFieldFilter
        mock_fs.FieldFilter = MockFieldFilter
        mock_fs.Query.DESCENDING = "DESCENDING"
        mock_fs.Query.ASCENDING = "ASCENDING"
        mock_fs.transactional = lambda fn: fn
        yield db


@pytest.mark.asyncio
async def test_search_and_score_job_not_found(firestore_db):
    with pytest.raises(ValueError, match="not found"):
        await search_and_score(9999, firestore_db)


@pytest.mark.asyncio
async def test_search_and_score_login_failure(firestore_db):
    job_repo = JobRepository(firestore_db)
    job = job_repo.create_job({"title": "Test", "required_skills": ["Python"], "is_active": 1})

    with patch("app.services.search_service.Crawler104") as MockCrawler:
        instance = AsyncMock()
        instance.login.return_value = False
        MockCrawler.return_value = instance

        with pytest.raises(RuntimeError, match="登入失敗"):
            await search_and_score(job.id, firestore_db)


@pytest.mark.asyncio
async def test_search_and_score_success(firestore_db):
    job_repo = JobRepository(firestore_db)
    job = job_repo.create_job({
        "title": "Backend Engineer",
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Docker"],
        "min_experience_years": 3,
        "max_experience_years": 8,
        "education_level": "學士",
        "industry": "軟體",
        "location": "台北市",
        "salary_min": 50000,
        "salary_max": 80000,
        "weight_skills": 30.0,
        "weight_experience": 25.0,
        "weight_education": 15.0,
        "weight_industry": 15.0,
        "weight_location": 10.0,
        "weight_salary": 5.0,
        "is_active": 1,
    })

    raw = _make_candidate_data()

    with patch("app.services.search_service.Crawler104") as MockCrawler, \
         patch("app.services.search_service.settings") as mock_settings:
        instance = AsyncMock()
        instance.login.return_value = True
        instance.search_candidates.return_value = [raw]
        MockCrawler.return_value = instance
        mock_settings.account_104_username = "user"
        mock_settings.account_104_password = "pass"
        mock_settings.cookie_storage_path = "/tmp/test"
        mock_settings.scorecard_threshold = 70.0

        result = await search_and_score(job.id, firestore_db)

    assert result["total_candidates"] >= 1
    assert result["job_title"] == job.title
