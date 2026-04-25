import json
from typing import Dict, Any, List
from backend.agents.base import Agent, AgentInput, AgentOutput

class GrowthAdvisor(Agent):
    """
    增长顾问智能体：
    提供商业模式创新建议、自动化/外包机会、跨界合作推荐。
    """
    name = "growth_advisor"
    description = "提供增长策略和建议"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        business_data = input_data.data.get("business_data", {})
        if not business_data:
            return AgentOutput(
                result={},
                metadata={"error": "No business data provided"},
                error="No data"
            )

        use_model = input_data.config.get("use_model", True)  # 默认使用模型
        if use_model:
            advice = await self._get_advice_by_model(business_data)
        else:
            advice = self._get_advice_by_rules(business_data)

        return AgentOutput(
            result=advice,
            metadata={"method": "model" if use_model else "rules"}
        )

    def _get_advice_by_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """基于规则的简单增长建议"""
        advice = {}
        # 根据业务类型给出建议
        business_type = data.get("type", "general")
        if business_type == "ecommerce":
            advice["automation"] = "建议自动化订单处理和库存管理。"
            advice["partnership"] = "可与物流平台合作降低配送成本。"
        elif business_type == "saas":
            advice["automation"] = "考虑自动化客户 onboarding 流程。"
            advice["partnership"] = "与咨询公司合作拓展渠道。"
        else:
            advice["automation"] = "分析重复性工作，尝试使用 RPA 工具。"
            advice["partnership"] = "寻找行业互补的合作伙伴。"
        return advice

    async def _get_advice_by_model(self, data: Dict[str, Any]) -> Dict[str, Any]:
        import json
        data_str = json.dumps(data, ensure_ascii=False, indent=2)
        prompt = f"""根据以下业务数据，提供增长策略建议，输出JSON格式，包含 automation（自动化建议）、partnership（合作建议）、innovation（商业模式创新建议）等字段。

数据：
{data_str}

输出（JSON）："""
        try:
            response = await self._call_model(prompt)
            json_str = self._extract_json(response)
            if json_str:
                advice = json.loads(json_str)
                if isinstance(advice, dict):
                    return advice
            return self._get_advice_by_rules(data)
        except Exception as e:
            print(f"Model call failed: {e}")
            return self._get_advice_by_rules(data)

    def _extract_json(self, text: str) -> str:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return ""
