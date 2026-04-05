"""
Firestore BaseRepository — 通用 CRUD 操作

提供 create, get_by_id, query, update, delete 及自動遞增 ID。
"""

from datetime import datetime

from google.cloud import firestore


class BaseRepository:
    collection_name: str = ""

    def __init__(self, db: firestore.Client):
        self.db = db
        self.collection = db.collection(self.collection_name)

    def _get_next_id(self) -> int:
        """使用 Firestore transaction 原子遞增 ID"""
        counter_ref = self.db.collection("counters").document("global")

        @firestore.transactional
        def increment(transaction, ref):
            snapshot = ref.get(transaction=transaction)
            data = snapshot.to_dict() or {}
            current = data.get(self.collection_name, 0)
            new_id = current + 1
            transaction.update(ref, {self.collection_name: new_id})
            return new_id

        transaction = self.db.transaction()
        # 確保 counter 文件存在
        if not counter_ref.get().exists:
            counter_ref.set({self.collection_name: 0})
        return increment(transaction, counter_ref)

    def create(self, data: dict) -> dict:
        """建立文件，自動產生整數 ID"""
        doc_id = self._get_next_id()
        now = datetime.utcnow()
        data["id"] = doc_id
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        # 清除 None 值
        clean = {k: v for k, v in data.items() if v is not None}
        self.collection.document(str(doc_id)).set(clean)
        return {**data, "id": doc_id}

    def get_by_id(self, doc_id: int) -> dict | None:
        """根據整數 ID 取得文件"""
        doc = self.collection.document(str(doc_id)).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = int(doc.id)
        return data

    def query(
        self,
        filters: list[tuple] | None = None,
        order_by: str | None = None,
        descending: bool = False,
        limit: int | None = None,
    ) -> list[dict]:
        """查詢文件"""
        ref = self.collection
        for field, op, value in (filters or []):
            ref = ref.where(filter=firestore.FieldFilter(field, op, value))
        if order_by:
            direction = firestore.Query.DESCENDING if descending else firestore.Query.ASCENDING
            ref = ref.order_by(order_by, direction=direction)
        if limit:
            ref = ref.limit(limit)
        results = []
        for doc in ref.stream():
            data = doc.to_dict()
            data["id"] = int(doc.id)
            results.append(data)
        return results

    def update(self, doc_id: int, data: dict) -> dict | None:
        """更新文件"""
        ref = self.collection.document(str(doc_id))
        if not ref.get().exists:
            return None
        data["updated_at"] = datetime.utcnow()
        ref.update(data)
        return self.get_by_id(doc_id)

    def delete(self, doc_id: int) -> bool:
        """刪除文件"""
        ref = self.collection.document(str(doc_id))
        if not ref.get().exists:
            return False
        ref.delete()
        return True
