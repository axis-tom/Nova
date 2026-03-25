import re
from typing import List, Dict, Any
from backend.agents.base import Agent, AgentInput, AgentOutput

class PriorityAgent(Agent):
    """
    优先级判断智能体：
    根据输入文本（如邮件、消息）判断紧急程度，输出优先级（高/中/低）。
    支持规则匹配和模型调用两种模式。
    """
    name = "priority_agent"
    description = "判断任务或消息的优先级"

    # 规则关键词映射
    HIGH_KEYWORDS = ["紧急", "立刻", "马上", "urgent", "asap", "重要", "重要通知"]
    MEDIUM_KEYWORDS = ["请尽快", "稍后", "待办", "提醒", "follow up"]
    LOW_KEYWORDS = ["日常", "周报", "参考", "FYI", "仅供参考"]

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        texts = input_data.data.get("texts", [])
        if not texts:
            # 支持单个文本
            if "text" in input_data.data:
                texts = [input_data.data["text"]]
            else:
                return AgentOutput(
                    result=[],
                    metadata={"error": "No text input provided"},
                    error="No text"
                )

        # 是否使用模型（可通过配置启用）
        use_model = input_data.config.get("use_model", False)

        results = []
        for text in texts:
            if use_model:
                priority = await self._get_priority_by_model(text)
            else:
                priority = self._get_priority_by_rules(text)
            results.append({"text": text, "priority": priority})

        return AgentOutput(
            result=results,
            metadata={"method": "model" if use_model else "rules", "count": len(results)}
        )

    def _get_priority_by_rules(self, text: str) -> str:
        """基于关键词的规则匹配"""
        text_lower = text.lower()
        for kw in self.HIGH_KEYWORDS:
            if kw in text_lower:
                return "高"
        for kw in self.MEDIUM_KEYWORDS:
            if kw in text_lower:
                return "中"
        for kw in self.LOW_KEYWORDS:
            if kw in text_lower:
                return "低"
        # 默认中优先级
        return "中"

    async def _get_priority_by_model(self, text: str) -> str:
        """调用模型进行优先级判断"""
        prompt = f"""请判断以下文本的紧急程度，只输出“高”、“中”或“低”三个字之一。

文本：{text}

优先级："""
        try:
            response = await self._call_model(prompt)
            response = response.strip()
            if response in ["高", "中", "低"]:
                return response
            else:
                # 模型输出不规范，回退规则
                return self._get_priority_by_rules(text)
        except Exception as e:
            # 模型调用失败，回退规则
            print(f"Model call failed: {e}")
            return self._get_priority_by_rules(text)