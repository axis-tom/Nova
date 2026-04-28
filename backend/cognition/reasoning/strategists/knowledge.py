import json
from typing import Dict, Any, List
from backend.common.core import Agent, AgentInput, AgentOutput

class KnowledgeAdvisor(Agent):
    """
    知识顾问智能体：
    主动向用户推送相关知识库内容，并学习用户决策结果。
    """
    name = "knowledge_advisor"
    description = "主动推送知识库内容，并学习用户反馈"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 输入可能包含用户上下文和最近决策
        user_context = input_data.data.get("user_context", {})
        decision_history = input_data.data.get("decision_history", [])

        use_model = input_data.config.get("use_model", True)

        if use_model:
            knowledge = await self._get_recommendations_by_model(user_context, decision_history)
        else:
            knowledge = self._get_recommendations_by_rules(user_context, decision_history)

        return AgentOutput(
            result=knowledge,
            metadata={"method": "model" if use_model else "rules", "count": len(knowledge)}
        )

    def _get_recommendations_by_rules(self, context: Dict, history: List) -> List[Dict[str, Any]]:
        """基于规则的推荐"""
        # 示例：根据最近决策主题推荐知识库文章
        recommendations = []
        # 假设历史中有决策主题
        if history:
            last_topic = history[-1].get("topic", "")
            if "营销" in last_topic:
                recommendations.append({
                    "title": "营销自动化最佳实践",
                    "url": "https://docs.nova.ai/knowledge/marketing-auto",
                    "reason": "您最近在处理营销相关决策"
                })
            elif "财务" in last_topic:
                recommendations.append({
                    "title": "小企业现金流管理指南",
                    "url": "https://docs.nova.ai/knowledge/cashflow",
                    "reason": "您近期关注财务话题"
                })
        return recommendations

    async def _get_recommendations_by_model(self, context: Dict, history: List) -> List[Dict[str, Any]]:
        """调用模型推荐知识库内容"""
        import json
        context_str = json.dumps(context, ensure_ascii=False)
        history_str = json.dumps(history[-5:], ensure_ascii=False)  # 最近5条
        prompt = f"""根据用户上下文和决策历史，推荐3条相关的知识库内容，输出JSON列表，每个包含 title（标题）、url（链接）、reason（推荐理由）。

用户上下文：{context_str}
最近决策历史：{history_str}

输出（JSON列表）："""
        try:
            response = await self._call_model(prompt)
            json_str = self._extract_json(response)
            if json_str:
                recs = json.loads(json_str)
                if isinstance(recs, list):
                    return recs
            return self._get_recommendations_by_rules(context, history)
        except Exception as e:
            print(f"Model call failed: {e}")
            return self._get_recommendations_by_rules(context, history)

    def _extract_json(self, text: str) -> str:
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return ""
