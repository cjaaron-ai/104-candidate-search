"""
Firestore 客戶端初始化

取代 app/database.py，提供 Firestore 客戶端與 FastAPI 依賴注入。
"""

import os

from google.cloud import firestore

from app.config import settings


def _get_client() -> firestore.Client:
    """建立 Firestore 客戶端"""
    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        return firestore.Client(project="test-project")
    return firestore.Client(project=settings.gcp_project_id or None)


_client: firestore.Client | None = None


def get_firestore_client() -> firestore.Client:
    global _client
    if _client is None:
        _client = _get_client()
    return _client


def get_db():
    """FastAPI 依賴注入 — 回傳 Firestore 客戶端"""
    return get_firestore_client()
