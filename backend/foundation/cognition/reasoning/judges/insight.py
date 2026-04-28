from typing import List, Dict, Any
from backend.common.core import Agent, AgentInput, AgentOutput

class InsightAgent(Agent):
    """
    客户洞察智能体：
    分析客户数据（如对话记录、行为日志），提取有价值的洞察。
    """
    name = "insight_agent"
    description = "从客户数据中提取洞察（偏好、需求、行为模式）"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 输入可能是对话历史、交易记录、用户画像等
        customer_data = input_data.data.get("customer_data", {})
        if not customer_data:
            return AgentOutput(
                result=[],
                metadata={"error": "No customer data provided"},
                error="No data"
            )

        use_model = input_data.config.get("use_model", False)
        if use_model:
            insights = await self._generate_insights_by_model(customer_data)
        else:
            insights = self._generate_insights_by_rules(customer_data)

        return AgentOutput(
            result=insights,
            metadata={"method": "model" if use_model else "rules", "count": len(insights)}
        )

    def _generate_insights_by_rules(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """基于规则的洞察生成（示例）"""
        insights = []
        # 示例：如果对话中提到"价格"次数多，则生成价格敏感洞察
        conversations = data.get("conversations", [])
        if conversations:
            price_mentions = sum(1 for msg in conversations if "价格" in msg.get("content", ""))
            if price_mentions > 3:
                insights.append({
                    "type": "price_sensitivity",
                    "description": "客户对价格关注度高，可能对折扣敏感",
                    "confidence": 0.7
                })
        # 示例：如果交易记录显示高频购买，生成忠诚度洞察
        transactions = data.get("transactions", [])
        if len(transactions) > 10:
            insights.append({
                "type": "loyalty",
                "description": "客户购买频率高，属于高价值客户",
                "confidence": 0.8
            })
        return insights

    async def _generate_insights_by_model(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """调用模型生成洞察"""
        # 将数据转为文本
        import json
        data_str = json.dumps(data, ensure_ascii=False, indent=2)
        prompt = f"""根据以下客户数据，分析并生成洞察（JSON列表），每个洞察包含 type（类型）、description（描述）、confidence（置信度0-1）。

数据：
{data_str}

洞察："""
        try:
            response = await self._call_model(prompt)
            json_str = self._extract_json(response)
            if json_str:
                import json
                insights = json.loads(json_str)
                if isinstance(insights, list):
                    return insights
            return []
        except Exception as e:
            print(f"Model call failed: {e}")
            return self._generate_insights_by_rules(data)

    def _extract_json(self, text: str) -> str:
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return ""
