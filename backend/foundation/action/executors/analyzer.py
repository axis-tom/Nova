from backend.common.core import Agent
from backend.foundation.cognition.state_machine.state_machine import State


class AIAnalyzer(Agent):

    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def run(self, state):
        """
        执行 AI 分析
        
        从状态中获取邮件，使用 LLM 生成总结
        """
        emails = state.get("emails", [])
        
        if not emails:
            state.set("error", "未找到邮件数据")
            state.add_event("ai_analyzer_skipped")
            return state
        
        # 计算邮件数量
        email_count = len(emails)
        state.set("email_count", email_count)
        
        # 构造消息列表
        messages = []
        for email in emails:
            if isinstance(email, dict):
                content = f"主题：{email.get('subject', '无主题')}\n发件人：{email.get('from', '未知发件人')}\n内容预览：{email.get('body_preview', '无内容预览')}"
                messages.append(content)
            else:
                messages.append(str(email))
        
        try:
            # 调用 LLM 生成简报，添加超时设置
            import asyncio
            summary = await asyncio.wait_for(
                self.llm_client.generate_briefing(messages),
                timeout=10
            )
            state.set("summary", summary)
            state.add_event("ai_analyzer_done")
        except asyncio.TimeoutError:
            state.set("summary", "AI失败")
            state.set("error", "AI调用超时")
            state.add_event("ai_analyzer_timeout")
        except Exception as e:
            state.set("summary", "AI失败")
            state.set("error", f"AI 分析失败: {str(e)}")
            state.add_event("ai_analyzer_failed")
        
        return state
