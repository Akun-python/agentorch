from __future__ import annotations

from ...api.models import CapsuleDetailResponse
from ...storage.base import GraphStore


class DetailQueryService:
    """胶囊详情查询服务。"""

    def __init__(self, *, store: GraphStore) -> None:
        self.store = store

    def fetch_capsule_details(self, capsule_ids: list[str]) -> CapsuleDetailResponse:
        """按输入顺序返回能查到的详情，并报告缺失 ID。"""

        details = self.store.fetch_capsules(capsule_ids)
        detail_ids = {item.capsule_id for item in details}
        missing = [capsule_id for capsule_id in capsule_ids if capsule_id not in detail_ids]
        return CapsuleDetailResponse(details=details, missing_capsule_ids=missing)
