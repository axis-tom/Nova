import json
from typing import Dict, Any, Optional
from backend.common.core import Agent, AgentInput, AgentOutput

class IntentAgent(Agent):
    """
    意图识别智能体：
    将用户自然语言输入转为结构化意图（如生成简报、查询数据、执行操作等）。
    """
    name = "intent_agent"
    description = "识别用户意图，返回意图类型和相关参数"

    # 简单规则意图映射
    INTENT_PATTERNS = {
        "generate_briefing": ["生成简报", "给我简报", "今日简报", "日报"],
        "query_data": ["查询", "数据", "统计", "多少"],
        "execute_task": ["执行", "操作", "催款", "发送"],
        "settings": ["设置", "配置", "偏好"],
        "help": ["帮助", "怎么用", "功能"],
    }

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        user_input = input_data.data.get("text", "")
        if not user_input:
            return AgentOutput(
                result={"intent": "unknown", "params": {}},
                metadata={"error": "No input text"},
                error="No input"
            )

        use_model = input_data.config.get("use_model", False)
        if use_model:
            intent = await self._get_intent_by_model(user_input)
        else:
            intent = self._get_intent_by_rules(user_input)

        return AgentOutput(
            result=intent,
            metadata={"method": "model" if use_model else "rules"}
        )

    def _get_intent_by_rules(self, text: str) -> Dict[str, Any]:
        """基于关键词匹配意图"""
        text_lower = text.lower()
        for intent, keywords in self.INTENT_PATTERNS.items():
            for kw in keywords:
                if kw in text_lower:
                    # 提取参数（简单示例：从文本中提取时间等）
                    params = self._extract_params(text, intent)
                    return {"intent": intent, "params": params}
        return {"intent": "unknown", "params": {}}

    def _extract_params(self, text: str, intent: str) -> Dict[str, Any]:
        """根据意图提取参数（示例）"""
        params = {}
        if intent == "generate_briefing":
            # 尝试提取日期
            import re
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', text)
            if date_match:
                params["date"] = date_match.group()
        return params

    async def _get_intent_by_model(self, text: str) -> Dict[str, Any]:
        """调用模型识别意图"""
        prompt = f"""请识别以下用户输入的意图，输出JSON格式，包含 intent（意图类型）和 params（参数字典）。意图类型可从以下选择：generate_briefing, query_data, execute_task, settings, help, unknown。

用户输入：{text}

输出（JSON）："""
        try:
            response = await self._call_model(prompt)
            json_str = self._extract_json(response)
            if json_str:
                result = json.loads(json_str)
                if isinstance(result, dict):
                    return result
            return {"intent": "unknown", "params": {}}
        except Exception as e:
            print(f"Model call failed: {e}")
            return self._get_intent_by_rules(text)

    def _extract_json(self, text: str) -> str:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return ""