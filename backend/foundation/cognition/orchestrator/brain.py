
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import uuid

from backend.config.config import settings
from backend.common.exceptions import SOPNotFoundError, StepExecutionError
from backend.foundation.communication.audit import audit_logger
from backend.common.core import Agent, AgentInput, AgentOutput
from backend.common.collectors.base import BaseCollector
from backend.foundation.action.external_calls.outreach import OutboundAgent
from backend.foundation.action.executors.formatter import Formatter
from backend.foundation.action.external_calls.payment import PaymentAgent
from backend.foundation.perception.collectors.competitor import CompetitorAgent
from backend.foundation.perception.collectors.social import SocialAgent
from backend.foundation.perception.collectors.finance import FinancialAgent
from backend.foundation.perception.collectors.news import NewsAgent
from backend.foundation.perception.collectors.email import EmailAgent   # 实际导入各个智能体类
from backend.foundation.cognition.reasoning.judges import PriorityAgent, RiskAgent, InsightAgent
from backend.foundation.action.executors.contextual_ai_analyzer import ContextualAIAnalyzer
from backend.foundation.action.executors.followup_agent import FollowupAgent
from backend.foundation.action.executors.project_agent import ProjectAgent
from backend.foundation.cognition.reasoning.strategists import FinancialAdvisor, GrowthAdvisor, KnowledgeAdvisor
from backend.business.conversation import EmotionAgent, IntentAgent, DialogManager
from backend.foundation.reflection.quality import AuditorAgent, ComplianceAgent, EfficiencyAgent, ValidatorAgent
from backend.foundation.reflection.learning import ImplicitLearner, OutcomeLearner, WeightUpdater, RuleGenerator
from backend.foundation.action.executors.briefing_generator import BriefingGeneratorAgent

# 智能体注册表（实际可根据配置动态导入）
AGENT_REGISTRY = {
    # collector
    "email_agent": EmailAgent,
    "competitor_agent": CompetitorAgent,
    "social_agent": SocialAgent,
    "financial_agent": FinancialAgent,
    "news_agent": NewsAgent,
    # judge
    "priority_agent": PriorityAgent,
    "risk_agent": RiskAgent,
    "insight_agent": InsightAgent,
    # executor
    "payment_agent": PaymentAgent,
    "followup_agent": FollowupAgent,
    "project_agent": ProjectAgent,
    "outbound_agent": OutboundAgent,
    "briefing_generator_agent": BriefingGeneratorAgent,
    "formatter": Formatter,
    # strategist
    "financial_advisor": FinancialAdvisor,
    "growth_advisor": GrowthAdvisor,
    "knowledge_advisor": KnowledgeAdvisor,
    # conversation
    "intent_agent": IntentAgent,
    "dialog_manager": DialogManager,
    "emotion_agent": EmotionAgent,
    # quality
    "validator_agent": ValidatorAgent,
    "auditor_agent": AuditorAgent,
    "efficiency_agent": EfficiencyAgent,
    "compliance_agent": ComplianceAgent,
    # learning
    "implicit_learner": ImplicitLearner,
    "outcome_learner": OutcomeLearner,
    "weight_updater": WeightUpdater,
    "rule_generator": RuleGenerator,
}

class Orchestrator:
    """调度引擎：加载SOP，执行智能体链"""
    def __init__(self):
        self.sop_dir = Path(__file__).parent.parent.parent / "planner" / "sop_blueprints"

    async def run_sop(
        self,
        sop_name: str,
        context: Dict[str, Any],
        user_id: int,
        db: AsyncSession,  # 新增
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行指定SOP
        :param sop_name: SOP文件名（不含.yaml）
        :param context: 初始上下文（如用户输入、会话状态）
        :param user_id: 用户ID（用于审计）
        :param trace_id: 链路追踪ID（可选）
        :return: 最终执行结果
        """
        # 在加载 SOP 后，打印步骤名称
        
        if not trace_id:
            trace_id = str(uuid.uuid4())

        # 1. 加载SOP定义
        sop_path = self.sop_dir / f"{sop_name}.yaml"
        if not sop_path.exists():
            raise SOPNotFoundError(f"SOP {sop_name} not found at {sop_path}")

        with open(sop_path, "r", encoding="utf-8") as f:
            sop_definition = yaml.safe_load(f)

        steps = sop_definition.get("steps", [])
        print(f"[Orchestrator] Loaded SOP {sop_name}, steps: {[step.get('name') for step in steps]}")
        final_output = {}

        # 2. 执行每一步
        for step in steps:
            step_name = step.get("name", "unnamed")
            agent_names = step.get("agents", [])
            step_type = step.get("type", "sequential")  # sequential, parallel
            timeout = step.get("timeout", settings.AGENT_TIMEOUT_SECONDS)
            retry = step.get("retry", settings.AGENT_RETRY_LIMIT)

            # 准备步骤输入（整个上下文或特定字段）
            step_input = context  # 可根据 step["input_from"] 进行数据提取

            if step_type == "sequential":
                # 依次执行
                for agent_name in agent_names:
                    result = await self._execute_agent_with_retry(
                        agent_name, step_input, user_id, trace_id, timeout, retry, db
                    )
                    # 将结果合并到上下文
                    context[agent_name] = result
                    step_input = context  # 后续智能体可获取之前结果
            elif step_type == "parallel":
                # 并行执行
                tasks = []
                for agent_name in agent_names:
                    tasks.append(self._execute_agent_with_retry(
                        agent_name, step_input, user_id, trace_id, timeout, retry, db
                    ))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                # 处理异常
                for agent_name, res in zip(agent_names, results):
                    if isinstance(res, Exception):
                        # 记录异常但继续？根据策略决定
                        await audit_logger.log(
                            user_id, f"agent.{agent_name}.parallel_failure",
                            {"error": str(res)}, status="failure",
                            error_msg=str(res), trace_id=trace_id
                        )
                        context[agent_name] = None
                    else:
                        context[agent_name] = res

            # 记录步骤完成
            await audit_logger.log(
                user_id, f"sop.{sop_name}.step.{step_name}",
                {"step_type": step_type, "agents": agent_names},
                status="success", trace_id=trace_id
            )

            final_output = context  # 最后步骤的输出作为最终结果

        return final_output

    async def _execute_agent_with_retry(
        self,
        agent_name: str,
        input_data: Dict[str, Any],
        user_id: int,
        trace_id: str,
        timeout: int,
        retry_limit: int,
        db: AsyncSession,  # 新增
    ) -> Any:
        """带重试的智能体执行"""
        last_exception = None
        for attempt in range(retry_limit + 1):
            try:
                result = await asyncio.wait_for(
                    self._execute_agent(agent_name, input_data, user_id, trace_id, db),
                    timeout=timeout
                )
                return result
            except asyncio.TimeoutError as e:
                last_exception = e
                await audit_logger.log(
                    user_id, f"agent.{agent_name}.timeout",
                    {"attempt": attempt+1}, status="failure",
                    error_msg=f"Timeout after {timeout}s", trace_id=trace_id
                )
            except Exception as e:
                last_exception = e
                await audit_logger.log(
                    user_id, f"agent.{agent_name}.error",
                    {"attempt": attempt+1}, status="failure",
                    error_msg=str(e), trace_id=trace_id
                )
        raise StepExecutionError("unknown", agent_name, str(last_exception))


    async def _execute_agent(
        self,
        agent_name: str,
        input_data: Dict[str, Any],
        user_id: int,
        trace_id: str,
        db: AsyncSession,  # 新增
    ) -> Any:
        """实例化并执行单个智能体"""
        print(f"[Orchestrator] Executing agent: {agent_name}")
        try:
            agent_cls = AGENT_REGISTRY.get(agent_name)
            if not agent_cls:
                raise ValueError(f"Agent {agent_name} not registered")
            agent = agent_cls(db)   # 传入 db
            agent_input = AgentInput(data=input_data, user_id=user_id, trace_id=trace_id)
            output = await agent.execute(agent_input)
            if hasattr(output, "result"):
                return output.result
            return output
        except Exception as e:
            print(f"[Orchestrator] Agent {agent_name} failed: {e}")
            raise

# 全局调度引擎实例
orchestrator = Orchestrator()
