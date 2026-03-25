import httpx
from typing import Optional, List, Dict, Any
from backend.models.user import UserCreate, UserUpdate, UserInDB, UserOut
from backend.repositories.base import BaseRepository
from backend.core.config import settings

class UserRepository(BaseRepository[UserInDB, UserCreate, UserUpdate]):
    """NocoDB 实现的用户仓库"""

    def __init__(self):
        self.base_url = settings.NOCODB_URL  # 假设配置中有
        self.api_key = settings.NOCODB_API_KEY
        self.table_name = "users"
        # 构建表 API 端点
        self.endpoint = f"{self.base_url}/api/v2/tables/{self.table_name}/records"

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """封装 HTTP 请求，处理认证"""
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

    async def get(self, id: int, user_id: int) -> Optional[UserInDB]:
        """获取用户（但 NocoDB 中用户表可能不直接用 user_id 过滤，而是用 id）"""
        # NocoDB 中用户 ID 是主键
        try:
            result = await self._request("GET", f"{self.endpoint}/{id}")
            # 假设返回格式包含字段
            return UserInDB(**result)
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
    ) -> List[UserInDB]:
        """列出所有用户（通常不需要按 user_id 过滤，因为用户表本身存储用户）"""
        params = {"offset": skip, "limit": limit}
        if filters:
            # NocoDB 支持 where 条件
            where_clause = self._build_where(filters)
            params["where"] = where_clause
        result = await self._request("GET", self.endpoint, params=params)
        # 假设返回 {"list": [...]}
        users = [UserInDB(**item) for item in result.get("list", [])]
        return users

    async def create(self, user_id: int, data: UserCreate) -> UserInDB:
        """创建用户，user_id 实际上被忽略，因为新用户还没有 ID"""
        payload = data.dict()
        # 密码需要哈希，但在 controller 层处理，这里直接存储哈希后的密码
        result = await self._request("POST", self.endpoint, json=payload)
        # 返回创建的记录，可能包含自动生成的 ID
        return UserInDB(**result)

    async def update(
        self,
        id: int,
        user_id: int,
        data: UserUpdate
    ) -> Optional[UserInDB]:
        """更新用户"""
        payload = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
        if not payload:
            return await self.get(id, user_id)
        try:
            result = await self._request("PATCH", f"{self.endpoint}/{id}", json=payload)
            return UserInDB(**result)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def delete(self, id: int, user_id: int) -> bool:
        """删除用户"""
        try:
            await self._request("DELETE", f"{self.endpoint}/{id}")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise

    async def count(self, user_id: int, filters: Optional[Dict[str, Any]] = None) -> int:
        """统计用户数量"""
        params = {}
        if filters:
            params["where"] = self._build_where(filters)
        # NocoDB 可能提供 count 端点，这里简单实现：获取所有并计数
        result = await self._request("GET", self.endpoint, params=params)
        return len(result.get("list", []))

    def _build_where(self, filters: Dict[str, Any]) -> str:
        """构建 NocoDB where 条件（简单实现）"""
        parts = []
        for key, value in filters.items():
            parts.append(f"({key},eq,{value})")
        return "~and".join(parts) if parts else ""