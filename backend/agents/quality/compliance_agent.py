import re
from typing import Dict, Any, List
from backend.agents.base import Agent, AgentInput, AgentOutput

class ComplianceAgent(Agent):
    """
    合规检查智能体：
    检查合同、税务等内容的合规性，提醒潜在风险。
    """
    name = "compliance_agent"
    description = "检查文本合规性（合同、税务等）"

    # 简单规则示例：需要检查的关键词
    RISK_KEYWORDS = {
        "合同风险": ["违约金", "违约责任", "争议解决", "管辖", "不可抗力"],
        "税务风险": ["增值税", "个税", "发票", "抵扣"],
        "数据隐私": ["个人信息", "数据保护", "授权"],
    }

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        text = input_data.data.get("text", "")
        if not text:
            return AgentOutput(
                result={"risks": []},
                metadata={"error": "No text provided"},
                error="No text"
            )

        use_model = input_data.config.get("use_model", False)
        if use_model:
            risks = await self._check_by_model(text)
        else:
            risks = self._check_by_rules(text)

        return AgentOutput(
            result={"risks": risks},
            metadata={"method": "model" if use_model else "rules"}
        )

    def _check_by_rules(self, text: str) -> List[Dict[str, Any]]:
        """基于关键词规则检查"""
        risks = []
        text_lower = text.lower()
        for risk_type, keywords in self.RISK_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    risks.append({
                        "type": risk_type,
                        "description": f"检测到关键词「{kw}」，建议审查相关条款。",
                        "severity": "中"
                    })
                    break  # 每种类型只报一次
        return risks

    async def _check_by_model(self, text: str) -> List[Dict[str, Any]]:
        """调用模型进行合规检查"""
        prompt = f"""请检查以下文本是否存在合规风险，输出JSON列表，每个元素包含 type（风险类型）、description（描述）、severity（高/中/低）。如果无风险，返回空列表。

文本：{text}

输出（JSON）："""
        try:
            response = await self._call_model(prompt)
            json_str = self._extract_json(response)
            if json_str:
                import json
                risks = json.loads(json_str)
                if isinstance(risks, list):
                    return risks
            return self._check_by_rules(text)
        except Exception as e:
            print(f"Model call failed: {e}")
            return self._check_by_rules(text)

    def _extract_json(self, text: str) -> str:
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return ""