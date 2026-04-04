from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from tests.conftest import make_job, make_candidate
from app.models.candidate import CandidateScore
from app.services.search_service import search_and_score, _save_candidate
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


@pytest.mark.asyncio
async def test_search_and_score_job_not_found(db):
    with pytest.raises(ValueError, match="not found"):
        await search_and_score(9999, db)


@pytest.mark.asyncio
async def test_search_and_score_login_failure(db):
    job = make_job()
    db.add(job)
    db.commit()
    db.refresh(job)

    with patch("app.services.search_service.Crawler104") as MockCrawler:
        instance = AsyncMock()
        instance.login.return_value = False
        MockCrawler.return_value = instance

        with pytest.raises(RuntimeError, match="登入失敗"):
            await search_and_score(job.id, db)


@pytest.mark.asyncio
async def test_search_and_score_success(db):
    job = make_job()
    db.add(job)
    db.commit()
    db.refresh(job)

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

        result = await search_and_score(job.id, db)

    assert result["total_candidates"] >= 1
    assert result["job_title"] == job.title


@pytest.mark.asyncio
async def test_search_and_score_skips_rejected(db):
    job = make_job()
    db.add(job)
    db.commit()
    db.refresh(job)

    # Pre-insert a rejected candidate with matching source_id
    cand = make_candidate(source_id="rejected001", status="rejected")
    db.add(cand)
    db.commit()

    raw = _make_candidate_data(source_id="rejected001")

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

        result = await search_and_score(job.id, db)

    assert result["total_candidates"] == 0


@pytest.mark.asyncio
async def test_search_and_score_skips_already_scored(db):
    job = make_job()
    db.add(job)
    db.commit()
    db.refresh(job)

    cand = make_candidate(source_id="scored001")
    db.add(cand)
    db.commit()
    db.refresh(cand)

    # Pre-insert score
    existing_score = CandidateScore(candidate_id=cand.id, job_id=job.id, total_score=80.0, score_details={})
    db.add(existing_score)
    db.commit()

    raw = _make_candidate_data(source_id="scored001")

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

        result = await search_and_score(job.id, db)

    assert result["total_candidates"] == 0


# === _save_candidate ===

def test_save_candidate_new(db):
    raw = _make_candidate_data(source_id="new001")
    candidate = _save_candidate(raw, db)
    assert candidate.id is not None
    assert candidate.name == "張三"


def test_save_candidate_existing_updates(db):
    cand = make_candidate(source_id="exist001", title="Old Title")
    db.add(cand)
    db.commit()

    raw = _make_candidate_data(source_id="exist001", title="New Title")
    updated = _save_candidate(raw, db)
    assert updated.title == "New Title"
    assert updated.id == cand.id
