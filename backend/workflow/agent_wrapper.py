"""
Agent Registry 初始化 - 轻量接入实现

用于初始化AgentRegistry，注册现有的智能体。
遵循任务要求：不改email_agent，不重构briefing_agent，只是"包一层调用"。
"""

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.collector.email_agent import EmailAgent
from backend.agents.executor.briefing_generator_agent import BriefingGeneratorAgent
from backend.agents.executor.ai_analyzer import AIAnalyzer
from backend.agents.registry import AgentRegistry
from backend.utils.llm_client import llm_client


def create_email_agent_factory(db: AsyncSession) -> Any:
    """创建EmailAgent工厂函数"""
    return EmailAgent(db)


def create_briefing_agent_factory(db: AsyncSession) -> Any:
    """创建BriefingAgent工厂函数"""
    return BriefingGeneratorAgent(db)


def create_ai_analyzer_factory(db: AsyncSession) -> Any:
    """创建AIAnalyzer工厂函数"""
    return AIAnalyzer(llm_client)


def init_agent_registry(db: AsyncSession = None):
    """
    初始化AgentRegistry
    
    Args:
        db: 数据库会话（如果为None，则注册需要db参数的工厂函数）
    """
    # 清除现有的注册
    AgentRegistry.clear()
    
    if db is not None:
        # 如果有db会话，直接创建agent实例并注册
        # 但AgentRegistry.get()需要返回实例，所以我们需要注册工厂函数
        def email_factory():
            return EmailAgent(db)
        
        def briefing_factory():
            return BriefingGeneratorAgent(db)
        
        def ai_analyzer_factory():
            return AIAnalyzer(llm_client)
        
        AgentRegistry.register("email_agent", email_factory)
        AgentRegistry.register("briefing_agent", briefing_factory)
        AgentRegistry.register("ai_analyzer", ai_analyzer_factory)
    else:
        # 如果没有db会话，注册需要db参数的工厂函数
        # 这样调用者需要提供db参数
        AgentRegistry.register("email_agent", lambda db: EmailAgent(db))
        AgentRegistry.register("briefing_agent", lambda db: BriefingGeneratorAgent(db))
        AgentRegistry.register("ai_analyzer", lambda: AIAnalyzer(llm_client))
    
    print(f"AgentRegistry initialized with agents: {list(AgentRegistry.list_agents().keys())}")
