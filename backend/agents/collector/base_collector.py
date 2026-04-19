"""
统一数据采集器基类（支持数据语义层）

所有数据采集器必须继承此类，确保：
1. 统一的输入输出格式（使用ContextualData）
2. 统一的数据存储方式
3. 统一的错误处理
4. 统一的状态更新
5. 自动注入环境上下文，防止sandbox/production数据污染
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import Agent, AgentInput, AgentOutput
from backend.core.state import State
from backend.core.contextual_data import ContextWrapper, Environment, DataSource
from backend.repositories.postgres.data_source_repo import DataSourceRepository
from backend.utils.logger import logger

class BaseCollector(Agent, ABC):
    """统一数据采集器基类"""
    
    def __init__(self, db: AsyncSession):
        super().__init__()
        self.db = db
        self.data_source_repo = DataSourceRepository(db)
    
    def run(self, state: State) -> State:
        """
        实现Agent基类的run方法（新规范）
        
        将State转换为AgentInput，调用execute方法，然后将结果转换回State
        """
        try:
            # 从state中提取数据
            user_id = state.meta.get("user_id", 0)
            trace_id = state.meta.get("trace_id")
            config = state.meta.get("config", {})
            
            # 创建AgentInput
            input_data = AgentInput(
                data=state.data,
                user_id=user_id,
                trace_id=trace_id,
                config=config
            )
            
            # 执行采集
            import asyncio
            output = asyncio.run(self.execute(input_data))
            
            # 将结果设置回state
            if output.result:
                state.set("result", output.result)
            
            if output.metadata:
                for key, value in output.metadata.items():
                    state.set_meta(key, value)
            
            if output.error:
                state.set("error", output.error)
            
            return state
            
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] run method failed: {e}")
            state.set("error", str(e))
            return state
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """
        统一的数据采集执行方法
        
        处理流程：
        1. 验证输入数据
        2. 获取数据源配置
        3. 执行数据采集
        4. 存储采集结果
        5. 更新数据源状态
        6. 返回统一格式结果
        """
        try:
            # 1. 验证输入数据
            data_source_id = input_data.data.get("data_source_id")
            if not data_source_id:
                return AgentOutput(
                    result=[],
                    metadata={"error": "Missing data_source_id"},
                    error="data_source_id is required"
                )
            
            user_id = input_data.user_id
            
            # 2. 获取数据源配置
            data_source = await self.data_source_repo.get(data_source_id, user_id)
            if not data_source:
                return AgentOutput(
                    result=[],
                    metadata={"error": f"Data source {data_source_id} not found"},
                    error="Data source not found"
                )
            
            if not data_source.enabled:
                return AgentOutput(
                    result=[],
                    metadata={"error": f"Data source {data_source_id} is disabled"},
                    error="Data source is disabled"
                )
            
            # 3. 执行数据采集
            logger.info(f"[{self.__class__.__name__}] Collecting data from source {data_source_id} ({data_source.name})")
            
            collection_result = await self._collect_data(
                data_source.config,
                data_source.last_collected_at,
                input_data
            )
            
            # 4. 存储采集结果
            stored_count = 0
            if collection_result.get("data"):
                stored_count = await self._store_collected_data(
                    user_id,
                    data_source_id,
                    collection_result["data"]
                )
            
            # 5. 更新数据源状态
            if collection_result.get("success", False):
                await self.data_source_repo.update_last_collected(
                    data_source_id,
                    user_id,
                    datetime.now()
                )
            
            # 6. 返回统一格式结果（使用ContextualData包装）
            # 获取环境信息（从数据源配置或输入数据中）
            env = input_data.config.get("env", "production")
            if isinstance(env, str):
                env = env.lower()
                if env not in ["sandbox", "production"]:
                    env = "production"  # 默认生产环境
            
            # 获取数据源类型
            source_type = data_source.type if hasattr(data_source, 'type') else "unknown"
            
            # 使用ContextWrapper包装数据
            contextual_data = ContextWrapper.wrap_collector_output(
                collector_name=self.__class__.__name__,
                data=collection_result.get("data", []),
                env=env,
                source=source_type,
                trace_id=input_data.trace_id,
                metadata={
                    "data_source_id": data_source_id,
                    "data_source_name": data_source.name,
                    "collected_count": len(collection_result.get("data", [])),
                    "stored_count": stored_count,
                    "success": collection_result.get("success", False),
                    "error": collection_result.get("error"),
                    **collection_result.get("metadata", {})
                }
            )
            
            return AgentOutput(
                result=contextual_data.to_dict(),
                metadata={
                    "data_source_id": data_source_id,
                    "data_source_name": data_source.name,
                    "contextual_data_format": True,
                    "env": env,
                    "source": source_type
                },
                error=collection_result.get("error")
            )
            
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Collection failed: {e}")
            return AgentOutput(
                result=[],
                metadata={"error": str(e), "exception": e.__class__.__name__},
                error=f"Collection failed: {str(e)}"
            )
    
    @abstractmethod
    async def _collect_data(
        self, 
        config: Dict[str, Any],
        last_collected_at: Optional[datetime],
        input_data: AgentInput
    ) -> Dict[str, Any]:
        """
        具体的数据采集逻辑，由子类实现
        
        Args:
            config: 数据源配置
            last_collected_at: 上次采集时间（用于增量采集）
            input_data: 原始输入数据
            
        Returns:
            {
                "success": bool,  # 是否成功
                "data": List[Dict],  # 采集到的数据
                "error": Optional[str],  # 错误信息
                "metadata": Dict[str, Any]  # 附加元数据
            }
        """
        pass
    
    async def _store_collected_data(
        self,
        user_id: int,
        data_source_id: int,
        data: List[Dict[str, Any]]
    ) -> int:
        """
        存储采集到的数据
        
        子类可以重写此方法以实现特定的存储逻辑
        默认实现：记录日志但不存储
        
        Returns:
            成功存储的数据条数
        """
        if not data:
            return 0
        
        logger.info(f"[{self.__class__.__name__}] Would store {len(data)} items for user {user_id}, source {data_source_id}")
        
        # 这里应该调用具体的存储仓库
        # 例如：raw_email_repo, raw_data_repo 等
        
        return 0  # 默认返回0，子类需要实现具体存储逻辑
    
    def _get_incremental_params(self, last_collected_at: Optional[datetime]) -> Dict[str, Any]:
        """
        获取增量采集参数
        
        根据上次采集时间生成增量采集所需的参数
        """
        params = {}
        
        if last_collected_at:
            # 转换为适合API调用的格式
            params["since"] = last_collected_at.isoformat()
            params["incremental"] = True
        else:
            # 首次采集，可以设置默认时间范围
            params["incremental"] = False
        
        return params