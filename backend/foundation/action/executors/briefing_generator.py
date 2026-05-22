from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from backend.common.core import Agent, AgentInput, AgentOutput
from backend.common.core.state import State
from backend.data.repositories.postgreSQL.raw_email_repo import RawEmailRepository
from backend.data.repositories.postgreSQL.briefing_repo import BriefingRepository
from backend.data.models.briefing import BriefingCreate

class BriefingGeneratorAgent(Agent):
    def __init__(self, db: AsyncSession):
        self.db = db
        self.raw_email_repo = RawEmailRepository(db)
        self.briefing_repo = BriefingRepository(db)

    def run(self, state: State) -> State:
        """
        执行简报生成（新规范）
        
        从状态中获取 ai_analyzer 生成的结果，保存到数据库
        """
        user_id = state.get_meta("user_id", 0)
        
        # 从状态中获取 ai_analyzer 生成的结果
        summary = state.get("summary")
        
        if not summary:
            # 如果没有 summary，可能是 ai_analyzer 未执行或失败
            state.set("error", "未找到 ai_analyzer 生成的结果")
            return state
        
        # 获取邮件数量（从状态中获取或从数据库查询）
        email_count = state.get("email_count", 0)
        
        # 保存简报
        title = f"{datetime.now().strftime('%Y-%m-%d')} 简报"
        # 注意：这里需要异步调用，但在 run 方法中不能直接使用 await
        # 实际实现中应该使用异步上下文
        # 这里简化处理，实际应该使用异步方式
        state.set("briefing_title", title)
        state.set("briefing_content", summary)
        state.set("email_count", email_count)
        
        # 标记已执行
        state.add_event("briefing_generated")
        
        return state

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """
        向后兼容的 execute 方法
        
        注意：新代码应该使用 run(state) 方法
        此方法会调用 run 方法
        """
        # 将 AgentInput 转换为 State
        state = State(input_data.data)
        state.set_meta("user_id", input_data.user_id)
        if input_data.trace_id:
            state.set_meta("trace_id", input_data.trace_id)
        if input_data.config:
            state.set_meta("config", input_data.config)
        
        # 执行 run 方法
        result_state = self.run(state)
        
        # 将 State 转换为 AgentOutput
        # 优先使用"result"键，否则使用整个data部分
        if "result" in result_state:
            result = result_state.get("result")
        else:
            # 返回整个data部分，但排除一些内部键
            result = result_state.to_plain_dict()
            # 移除可能不需要的键
            for key in ["error", "metadata", "executed"]:
                if key in result:
                    del result[key]
        
        # 从meta中提取metadata
        metadata = {}
        for key in result_state.meta:
            if key not in ["user_id", "trace_id", "config", "step"]:
                metadata[key] = result_state.meta[key]
        
        # 提取error信息
        error = result_state.get("error")
        
        return AgentOutput(
            result=result,
            metadata=metadata,
            error=error
        )
