import json
from typing import Dict, Any, List
from backend.agents.base import Agent, AgentInput, AgentOutput

class FinancialAdvisor(Agent):
    """
    财务顾问智能体：
    分析财务数据，提供现金流预测、利润分析、定价建议等。
    """
    name = "financial_advisor"
    description = "提供财务分析和建议"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        financial_data = input_data.data.get("financial_data", {})
        if not financial_data:
            return AgentOutput(
                result={},
                metadata={"error": "No financial data provided"},
                error="No data"
            )

        use_model = input_data.config.get("use_model", False)
        if use_model:
            advice = await self._get_advice_by_model(financial_data)
        else:
            advice = self._get_advice_by_rules(financial_data)

        return AgentOutput(
            result=advice,
            metadata={"method": "model" if use_model else "rules"}
        )

    def _get_advice_by_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """基于规则的财务分析"""
        advice = {}
        # 假设 data 包含收入、成本、利润等
        revenue = data.get("revenue", 0)
        cost = data.get("cost", 0)
        profit = revenue - cost
        if profit > 0:
            advice["profit_analysis"] = f"当前利润为 {profit}，建议保持增长势头。"
            if profit / revenue < 0.2:
                advice["suggestion"] = "利润率较低，建议优化成本或提价。"
            else:
                advice["suggestion"] = "利润率良好，可考虑扩张。"
        else:
            advice["profit_analysis"] = f"当前亏损 {abs(profit)}，请紧急调整策略。"
            advice["suggestion"] = "削减非必要开支，重新定价。"

        # 现金流预测（简单模拟）
        cash_balance = data.get("cash_balance", 0)
        advice["cash_flow_forecast"] = f"当前现金余额 {cash_balance}，预计可支撑 {cash_balance // (cost//12) if cost else '无限'} 个月。"

        return advice

    async def _get_advice_by_model(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """调用模型生成财务建议"""
        import json
        data_str = json.dumps(data, ensure_ascii=False, indent=2)
        prompt = f"""根据以下财务数据，提供财务分析建议，输出JSON格式，包含 profit_analysis、cash_flow_forecast、suggestion 等字段。

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
