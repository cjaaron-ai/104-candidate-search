"""
測試用 conftest — 使用 Firestore mock（in-memory dict 模擬）

無需 Firestore emulator，所有資料存在 dict 中。
"""

from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest
from starlette.testclient import TestClient

from app.models.job import JobDescription
from app.models.candidate import Candidate


class MockDocumentSnapshot:
    def __init__(self, doc_id, data, exists=True):
        self.id = doc_id
        self._data = data
        self.exists = exists

    def to_dict(self):
        return dict(self._data) if self._data else None


class MockDocumentReference:
    def __init__(self, collection, doc_id):
        self._collection = collection
        self._id = doc_id

    def get(self, transaction=None):
        data = self._collection._docs.get(self._id)
        return MockDocumentSnapshot(self._id, data, exists=data is not None)

    def set(self, data):
        self._collection._docs[self._id] = dict(data)

    def update(self, data):
        if self._id in self._collection._docs:
            self._collection._docs[self._id].update(data)

    def delete(self):
        self._collection._docs.pop(self._id, None)


class MockQuery:
    def __init__(self, docs):
        self._docs = list(docs)

    def where(self, filter=None, **kwargs):
        if filter:
            field = filter.field_path
            op = filter.op_string
            value = filter.value
        else:
            return self
        filtered = []
        for doc_id, data in self._docs:
            if op == "==" and data.get(field) == value:
                filtered.append((doc_id, data))
        return MockQuery(filtered)

    def order_by(self, field, direction=None):
        reverse = direction == "DESCENDING" if direction else False
        sorted_docs = sorted(self._docs, key=lambda x: x[1].get(field, 0), reverse=reverse)
        return MockQuery(sorted_docs)

    def limit(self, n):
        return MockQuery(self._docs[:n])

    def stream(self):
        for doc_id, data in self._docs:
            yield MockDocumentSnapshot(doc_id, data)


class MockCollectionReference:
    def __init__(self):
        self._docs = {}

    def document(self, doc_id):
        return MockDocumentReference(self, doc_id)

    def where(self, filter=None, **kwargs):
        items = list(self._docs.items())
        q = MockQuery(items)
        if filter:
            return q.where(filter=filter)
        return q

    def order_by(self, field, direction=None):
        items = list(self._docs.items())
        return MockQuery(items).order_by(field, direction)

    def limit(self, n):
        items = list(self._docs.items())
        return MockQuery(items).limit(n)

    def stream(self):
        for doc_id, data in self._docs.items():
            yield MockDocumentSnapshot(doc_id, data)

    def list_documents(self):
        return [MockDocumentReference(self, did) for did in self._docs]


class MockFieldFilter:
    def __init__(self, field_path, op_string, value):
        self.field_path = field_path
        self.op_string = op_string
        self.value = value


class MockTransaction:
    def __init__(self):
        self._ops = []

    def update(self, ref, data):
        ref.update(data)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockFirestoreClient:
    def __init__(self):
        self._collections = {}

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollectionReference()
        return self._collections[name]

    def transaction(self):
        return MockTransaction()


@pytest.fixture()
def db():
    return MockFirestoreClient()


@pytest.fixture()
def client(db):
    from app.main import app
    from app.firestore import get_db

    app.dependency_overrides[get_db] = lambda: db

    with patch("app.main.start_scheduler"), \
         patch("app.main.stop_scheduler"):
        # Patch firestore.FieldFilter to use our mock
        with patch("app.repositories.base.firestore") as mock_fs:
            mock_fs.FieldFilter = MockFieldFilter
            mock_fs.Query.DESCENDING = "DESCENDING"
            mock_fs.Query.ASCENDING = "ASCENDING"
            mock_fs.transactional = lambda fn: fn
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
