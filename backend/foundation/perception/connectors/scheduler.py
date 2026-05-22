"""
统一数据采集调度层 - CollectorScheduler

职责：
1. 定时触发数据采集（cron / background task）
2. 读取所有启用的 data_sources
3. 根据 type 分发到对应的 Agent
4. 确保所有 collector 输出统一格式
5. 写入 raw_emails / raw_data
6. 更新 last_collected_at

设计原则：
- 所有 collector 必须通过 scheduler 调用
- 禁止 collector 直接被业务逻辑调用
- 禁止 collector 绕过 scheduler 执行
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from backend.data.models.data_source import DataSourceInDB, DataSourceType
from backend.data.repositories.postgreSQL.data_source_repo import DataSourceRepository
from backend.common.core import AgentInput, AgentOutput
from backend.foundation.perception.collectors.competitor import CompetitorAgent
from backend.foundation.perception.collectors.social import SocialAgent
from backend.foundation.perception.collectors.finance import FinancialAgent
from backend.foundation.perception.collectors.news import NewsAgent
from backend.foundation.perception.collectors.email import EmailAgent

from backend.foundation.communication.audit import audit_logger
from backend.utils.logger import logger

class CollectorScheduler:
    """统一数据采集调度器"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.data_source_repo = DataSourceRepository(db)
        
        # Agent 映射表：type -> Agent class
        self.agent_registry: Dict[str, Any] = {
            DataSourceType.EMAIL.value: EmailAgent,
            DataSourceType.RSS.value: CompetitorAgent,  # 暂时用 CompetitorAgent 替代
            DataSourceType.SOCIAL.value: SocialAgent,
            DataSourceType.FINANCIAL.value: FinancialAgent,
            DataSourceType.NEWS.value: NewsAgent,
        }
        
        # Agent 实例缓存
        self.agent_instances: Dict[str, Any] = {}
        
    async def get_agent_for_type(self, source_type: str):
        """获取对应类型的 Agent 实例"""
        if source_type not in self.agent_instances:
            agent_cls = self.agent_registry.get(source_type)
            if not agent_cls:
                raise ValueError(f"No agent registered for type: {source_type}")
            self.agent_instances[source_type] = agent_cls(self.db)
        return self.agent_instances[source_type]
    
    async def collect_all_sources(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        采集所有用户的所有数据源
        
        Args:
            user_id: 如果指定，只采集该用户的数据源；否则采集所有用户的数据源
            
        Returns:
            采集结果统计
        """
        logger.info(f"[CollectorScheduler] Starting collection for {'all users' if user_id is None else f'user {user_id}'}")
        
        # 获取所有启用的数据源
        filters = {"enabled": True}
        if user_id:
            # 获取指定用户的数据源
            data_sources = await self.data_source_repo.list(user_id, filters=filters)
            user_sources = {user_id: data_sources}
        else:
            # 获取所有用户的数据源（需要按用户分组）
            # 这里简化实现：先获取所有数据源，然后按用户分组
            # 实际项目中可能需要更高效的查询
            all_sources = []
            # 假设我们有一个获取所有数据源的方法
            # 这里暂时简化，实际需要实现
            user_sources = await self._get_all_user_sources(filters)
        
        total_collected = 0
        total_failed = 0
        results = {}
        
        for uid, sources in user_sources.items():
            if not sources:
                continue
                
            logger.info(f"[CollectorScheduler] Processing {len(sources)} sources for user {uid}")
            
            # 按类型分组
            sources_by_type = {}
            for source in sources:
                source_type = source.type.value
                if source_type not in sources_by_type:
                    sources_by_type[source_type] = []
                sources_by_type[source_type].append(source)
            
            # 按类型批量采集
            for source_type, type_sources in sources_by_type.items():
                try:
                    agent = await self.get_agent_for_type(source_type)
                    collected_count = await self._collect_sources_for_user(
                        uid, type_sources, agent, source_type
                    )
                    total_collected += collected_count
                    results.setdefault(uid, {})[source_type] = collected_count
                    
                except Exception as e:
                    logger.error(f"[CollectorScheduler] Failed to collect {source_type} for user {uid}: {e}")
                    total_failed += len(type_sources)
                    await audit_logger.log(
                        uid, f"collector.{source_type}.batch_failure",
                        {"error": str(e), "source_count": len(type_sources)},
                        status="failure", error_msg=str(e)
                    )
        
        logger.info(f"[CollectorScheduler] Collection completed: {total_collected} collected, {total_failed} failed")
        return {
            "total_collected": total_collected,
            "total_failed": total_failed,
            "results": results
        }
    
    async def _collect_sources_for_user(
        self, 
        user_id: int, 
        sources: List[DataSourceInDB], 
        agent: Any,
        source_type: str
    ) -> int:
        """
        为指定用户采集特定类型的数据源
        
        Returns:
            成功采集的数据源数量
        """
        collected_count = 0
        
        for source in sources:
            try:
                # 准备输入数据
                input_data = AgentInput(
                    data={
                        "data_source_id": source.id,
                        "data_source_name": source.name,
                        "config": source.config,
                        "last_collected_at": source.last_collected_at.isoformat() if source.last_collected_at else None
                    },
                    user_id=user_id,
                    trace_id=f"collector_{source.id}_{datetime.now().timestamp()}"
                )
                
                # 执行采集
                output = await agent.execute(input_data)
                
                if output.error:
                    logger.warning(f"[CollectorScheduler] Agent returned error for source {source.id}: {output.error}")
                    await audit_logger.log(
                        user_id, f"collector.{source_type}.error",
                        {"data_source_id": source.id, "error": output.error},
                        status="failure", error_msg=output.error
                    )
                else:
                    collected_count += 1
                    logger.info(f"[CollectorScheduler] Successfully collected source {source.id} ({source.name})")
                    
                    # 记录成功日志
                    await audit_logger.log(
                        user_id, f"collector.{source_type}.success",
                        {
                            "data_source_id": source.id,
                            "collected_count": output.metadata.get("count", 0),
                            "metadata": output.metadata
                        },
                        status="success"
                    )
                    
            except Exception as e:
                logger.error(f"[CollectorScheduler] Failed to collect source {source.id}: {e}")
                await audit_logger.log(
                    user_id, f"collector.{source_type}.failure",
                    {"data_source_id": source.id, "error": str(e)},
                    status="failure", error_msg=str(e)
                )
        
        return collected_count
    
    async def _get_all_user_sources(self, filters: Dict[str, Any]) -> Dict[int, List[DataSourceInDB]]:
        """
        获取所有用户的数据源（按用户分组）
        
        注意：这是一个简化实现，实际项目中可能需要更高效的查询方式
        """
        try:
            # 获取所有启用的数据源
            from backend.data.repositories.postgreSQL.user_repo import UserRepository
            
            user_repo = UserRepository(self.db)
            
            # 获取所有用户
            users = await user_repo.list_all()
            
            user_sources = {}
            
            for user in users:
                # 获取用户的所有启用的数据源
                data_sources = await self.data_source_repo.list(
                    user.id,
                    filters=filters
                )
                
                if data_sources:
                    user_sources[user.id] = data_sources
            
            logger.info(f"[CollectorScheduler] Found data sources for {len(user_sources)} users")
            return user_sources
            
        except Exception as e:
            logger.error(f"[CollectorScheduler] Failed to get user sources: {e}")
            return {}
    
    async def collect_for_user(self, user_id: int) -> Dict[str, Any]:
        """为指定用户采集所有数据源"""
        return await self.collect_all_sources(user_id)
    
    async def collect_single_source(self, user_id: int, data_source_id: int) -> Dict[str, Any]:
        """采集单个数据源"""
        source = await self.data_source_repo.get(data_source_id, user_id)
        if not source:
            return {"success": False, "error": "Data source not found"}
        
        if not source.enabled:
            return {"success": False, "error": "Data source is disabled"}
        
        try:
            agent = await self.get_agent_for_type(source.type.value)
            input_data = AgentInput(
                data={
                    "data_source_id": source.id,
                    "data_source_name": source.name,
                    "config": source.config,
                    "last_collected_at": source.last_collected_at.isoformat() if source.last_collected_at else None
                },
                user_id=user_id,
                trace_id=f"collector_single_{source.id}_{datetime.now().timestamp()}"
            )
            
            output = await agent.execute(input_data)
            
            result = {
                "success": True,
                "data_source_id": source.id,
                "collected_count": output.metadata.get("count", 0),
                "metadata": output.metadata
            }
            
            if output.error:
                result["warning"] = output.error
                
            await audit_logger.log(
                user_id, f"collector.{source.type.value}.single_success",
                result, status="success"
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[CollectorScheduler] Failed to collect single source {data_source_id}: {error_msg}")
            
            await audit_logger.log(
                user_id, f"collector.{source.type.value}.single_failure",
                {"data_source_id": source.id, "error": error_msg},
                status="failure", error_msg=error_msg
            )
            
            return {
                "success": False,
                "error": error_msg,
                "data_source_id": source.id
            }