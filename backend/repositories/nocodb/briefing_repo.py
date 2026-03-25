import httpx
from typing import Optional, List, Dict, Any
from backend.models.briefing import BriefingCreate, BriefingUpdate, BriefingInDB
from backend.repositories.base import BaseRepository
from backend.core.config import settings

class BriefingRepository(BaseRepository[BriefingInDB, BriefingCreate, BriefingUpdate]):
    """NocoDB 实现的简报仓库"""

    def __init__(self):
        self.base_url = settings.NOCODB_URL
        self.api_key = settings.NOCODB_API_KEY
        self.table_name = "briefings"
        self.endpoint = f"{self.base_url}/api/v2/tables/{self.table_name}/records"

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        headers = {
            "xc-token": self.api_key,
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                endpoint,
                json=json,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()

    async def get(self, id: int, user_id: int) -> Optional[BriefingInDB]:
        try:
            result = await self._request("GET", f"{self.endpoint}/{id}")
            if result.get("user_id") != user_id:
                return None
            return BriefingInDB(**result)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def list(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[BriefingInDB]:
        params = {"offset": skip, "limit": limit}
        where_parts = [f"(user_id,eq,{user_id})"]
        if filters:
            where_parts.append(self._build_where(filters))
        params["where"] = "~and".join(where_parts) if where_parts else ""
        # 按创建时间倒序
        params["sort"] = "-created_at"
        result = await self._request("GET", self.endpoint, params=params)
        briefings = [BriefingInDB(**item) for item in result.get("list", [])]
        return briefings

    async def create(self, user_id: int, data: BriefingCreate) -> BriefingInDB:
        payload = data.dict()
        payload["user_id"] = user_id
        result = await self._request("POST", self.endpoint, json=payload)
        return BriefingInDB(**result)

    async def update(
        self,
        id: int,
        user_id: int,
        data: BriefingUpdate
    ) -> Optional[BriefingInDB]:
        existing = await self.get(id, user_id)
        if not existing:
            return None
        payload = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
        if not payload:
            return existing
        try:
            result = await self._request("PATCH", f"{self.endpoint}/{id}", json=payload)
            return BriefingInDB(**result)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def delete(self, id: int, user_id: int) -> bool:
        existing = await self.get(id, user_id)
        if not existing:
            return False
        try:
            await self._request("DELETE", f"{self.endpoint}/{id}")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise

    async def count(self, user_id: int, filters: Optional[Dict[str, Any]] = None) -> int:
        params = {}
        where_parts = [f"(user_id,eq,{user_id})"]
        if filters:
            where_parts.append(self._build_where(filters))
        params["where"] = "~and".join(where_parts) if where_parts else ""
        result = await self._request("GET", self.endpoint, params=params)
        return len(result.get("list", []))

    def _build_where(self, filters: Dict[str, Any]) -> str:
        parts = []
        for key, value in filters.items():
            parts.append(f"({key},eq,{value})")
        return "~and".join(parts) if parts else ""