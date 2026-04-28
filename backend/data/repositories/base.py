from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Dict, Any
from pydantic import BaseModel

# 定义泛型类型，表示数据模型
ModelType = TypeVar("ModelType", bound=BaseModel)
CreateModelType = TypeVar("CreateModelType", bound=BaseModel)
UpdateModelType = TypeVar("UpdateModelType", bound=BaseModel)

class BaseRepository(ABC, Generic[ModelType, CreateModelType, UpdateModelType]):
    """Repository 抽象基类，定义常见 CRUD 操作"""

    @abstractmethod
    async def get(self, id: int, user_id: int) -> Optional[ModelType]:
        """根据 ID 获取单个实体"""
        pass

    @abstractmethod
    async def list(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """列出用户下的实体，支持分页和过滤"""
        pass

    @abstractmethod
    async def create(self, user_id: int, data: CreateModelType) -> ModelType:
        """创建实体"""
        pass

    @abstractmethod
    async def update(
        self,
        id: int,
        user_id: int,
        data: UpdateModelType
    ) -> Optional[ModelType]:
        """更新实体，返回更新后的实体或 None"""
        pass

    @abstractmethod
    async def delete(self, id: int, user_id: int) -> bool:
        """删除实体，返回是否成功"""
        pass

    @abstractmethod
    async def count(self, user_id: int, filters: Optional[Dict[str, Any]] = None) -> int:
        """统计用户下实体数量"""
        pass