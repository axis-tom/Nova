"""
定时任务管理器 - 负责调度数据采集任务

功能：
1. 使用 APScheduler 管理定时任务
2. 支持 cron 表达式配置
3. 集成 CollectorScheduler 进行数据采集
4. 提供任务管理 API
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors.scheduler import CollectorScheduler
from backend.data.database import AsyncSessionLocal
from backend.utils.logger import logger

class SchedulerManager:
    """定时任务管理器"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.collector_scheduler: Optional[CollectorScheduler] = None
        self.db_session: Optional[AsyncSession] = None
        
        # 默认的采集任务配置
        self.default_jobs = {
            "hourly_collection": {
                "trigger": CronTrigger(minute="0"),  # 每小时执行
                "func": self._run_hourly_collection,
                "name": "hourly_data_collection",
                "description": "每小时数据采集任务"
            },
            "daily_collection": {
                "trigger": CronTrigger(hour="2", minute="0"),  # 每天凌晨2点执行
                "func": self._run_daily_collection,
                "name": "daily_data_collection",
                "description": "每日数据采集任务"
            },
            "test_collection": {
                "trigger": CronTrigger(minute="*/5"),  # 每5分钟执行（测试用）
                "func": self._run_test_collection,
                "name": "test_data_collection",
                "description": "测试数据采集任务"
            }
        }
        
    async def initialize(self):
        """初始化调度管理器"""
        logger.info("[SchedulerManager] Initializing...")
        
        # 创建数据库会话
        self.db_session = AsyncSessionLocal()
        
        # 初始化 CollectorScheduler
        self.collector_scheduler = CollectorScheduler(self.db_session)
        
        # 配置调度器
        self.scheduler.configure({
            'timezone': 'Asia/Shanghai',
            'job_defaults': {
                'coalesce': True,  # 合并错过的任务
                'max_instances': 3,  # 最大并发实例数
                'misfire_grace_time': 300  # 错过执行的宽限时间（秒）
            }
        })
        
        logger.info("[SchedulerManager] Initialized successfully")
    
    async def start(self):
        """启动调度器"""
        if not self.collector_scheduler:
            await self.initialize()
        
        logger.info("[SchedulerManager] Starting scheduler...")
        
        # 添加默认任务
        for job_id, job_config in self.default_jobs.items():
            self.add_job(
                job_id=job_id,
                trigger=job_config["trigger"],
                func=job_config["func"],
                name=job_config["name"],
                description=job_config["description"]
            )
        
        # 启动调度器
        self.scheduler.start()
        logger.info(f"[SchedulerManager] Scheduler started with {len(self.scheduler.get_jobs())} jobs")
    
    async def stop(self):
        """停止调度器"""
        logger.info("[SchedulerManager] Stopping scheduler...")
        
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
        except Exception as e:
            logger.warning(f"[SchedulerManager] Error shutting down scheduler: {e}")
        
        # 关闭数据库会话
        if self.db_session:
            try:
                await self.db_session.close()
            except Exception as e:
                logger.warning(f"[SchedulerManager] Error closing database session: {e}")
        
        logger.info("[SchedulerManager] Scheduler stopped")
    
    def add_job(self, job_id: str, trigger, func, name: str, description: str = "", **kwargs):
        """添加定时任务"""
        job = self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            name=name,
            kwargs=kwargs
        )
        
        logger.info(f"[SchedulerManager] Added job: {name} (id: {job_id})")
        logger.info(f"  Next run: {job.next_run_time}")
        logger.info(f"  Trigger: {trigger}")
        
        return job
    
    def remove_job(self, job_id: str):
        """移除定时任务"""
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"[SchedulerManager] Removed job: {job_id}")
            return True
        return False
    
    def get_jobs(self) -> list:
        """获取所有任务"""
        return self.scheduler.get_jobs()
    
    def get_job(self, job_id: str):
        """获取指定任务"""
        return self.scheduler.get_job(job_id)
    
    async def _run_hourly_collection(self):
        """执行每小时数据采集"""
        logger.info("[SchedulerManager] Starting hourly data collection...")
        
        try:
            if not self.collector_scheduler:
                logger.error("[SchedulerManager] Collector scheduler not initialized")
                return
            
            # 执行数据采集
            result = await self.collector_scheduler.collect_all_sources()
            
            logger.info(f"[SchedulerManager] Hourly collection completed: {result['total_collected']} collected, {result['total_failed']} failed")
            
        except Exception as e:
            logger.error(f"[SchedulerManager] Hourly collection failed: {e}")
    
    async def _run_daily_collection(self):
        """执行每日数据采集"""
        logger.info("[SchedulerManager] Starting daily data collection...")
        
        try:
            if not self.collector_scheduler:
                logger.error("[SchedulerManager] Collector scheduler not initialized")
                return
            
            # 执行数据采集
            result = await self.collector_scheduler.collect_all_sources()
            
            logger.info(f"[SchedulerManager] Daily collection completed: {result['total_collected']} collected, {result['total_failed']} failed")
            
            # 可以在这里添加额外的每日清理或统计任务
            
        except Exception as e:
            logger.error(f"[SchedulerManager] Daily collection failed: {e}")
    
    async def _run_test_collection(self):
        """执行测试数据采集（用于调试）"""
        logger.info("[SchedulerManager] Starting test data collection...")
        
        try:
            if not self.collector_scheduler:
                logger.error("[SchedulerManager] Collector scheduler not initialized")
                return
            
            # 只采集前10个数据源进行测试
            # 这里简化实现，实际可能需要更复杂的逻辑
            result = await self.collector_scheduler.collect_all_sources()
            
            logger.info(f"[SchedulerManager] Test collection completed: {result['total_collected']} collected, {result['total_failed']} failed")
            
        except Exception as e:
            logger.error(f"[SchedulerManager] Test collection failed: {e}")
    
    async def trigger_manual_collection(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """手动触发数据采集"""
        logger.info(f"[SchedulerManager] Manual collection triggered for {'all users' if user_id is None else f'user {user_id}'}")
        
        try:
            if not self.collector_scheduler:
                await self.initialize()
            
            if user_id:
                result = await self.collector_scheduler.collect_for_user(user_id)
            else:
                result = await self.collector_scheduler.collect_all_sources()
            
            logger.info(f"[SchedulerManager] Manual collection completed: {result['total_collected']} collected, {result['total_failed']} failed")
            
            return {
                "success": True,
                "message": "Manual collection completed",
                "result": result
            }
            
        except Exception as e:
            error_msg = f"Manual collection failed: {e}"
            logger.error(f"[SchedulerManager] {error_msg}")
            
            return {
                "success": False,
                "error": error_msg
            }

# 全局调度管理器实例
scheduler_manager = SchedulerManager()