from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.database import Base, get_db
from app.models.job import JobDescription
from app.models.candidate import Candidate


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    from app.main import app

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with patch("app.main.start_scheduler"), \
         patch("app.main.stop_scheduler"), \
         patch("app.main.Base") as mock_base:
        mock_base.metadata.create_all = lambda **kwargs: None
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


def make_job(**overrides) -> JobDescription:
    defaults = dict(
        title="Backend Engineer",
        required_skills=["Python", "FastAPI"],
        preferred_skills=["Docker"],
        min_experience_years=3,
        max_experience_years=8,
        education_level="學士",
        industry="軟體",
        location="台北市",
        salary_min=50000,
        salary_max=80000,
        weight_skills=30.0,
        weight_experience=25.0,
        weight_education=15.0,
        weight_industry=15.0,
        weight_location=10.0,
        weight_salary=5.0,
        is_active=1,
    )
    defaults.update(overrides)
    return JobDescription(**defaults)


def make_candidate(**overrides) -> Candidate:
    defaults = dict(
        source="104",
        source_id="abc123",
        name="王小明",
        title="Senior Engineer",
        company="Test Corp",
        experience_years=5,
        education_level="學士",
        skills=["Python", "SQL"],
        industry="軟體業",
        location="台北市",
        expected_salary_min=60000,
        expected_salary_max=80000,
        status="new",
    )
    defaults.update(overrides)
    return Candidate(**defaults)
