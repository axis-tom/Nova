import re
from typing import List, Dict, Any
from backend.agents.base import Agent, AgentInput, AgentOutput

class RiskAgent(Agent):
    """
    风险预警智能体：
    分析文本或数据中的风险点，返回风险列表（类型、描述、严重程度）。
    支持规则和模型两种模式。
    """
    name = "risk_agent"
    description = "识别文本中的潜在风险（财务、法律、声誉等）"

    # 风险关键词映射
    RISK_PATTERNS = {
        "财务风险": ["亏损", "现金流", "坏账", "逾期", "成本上升"],
        "法律风险": ["合同", "违约", "诉讼", "合规", "侵权"],
        "声誉风险": ["负面", "投诉", "曝光", "差评", "公关危机"],
        "运营风险": ["故障", "中断", "延迟", "供应链", "人员流失"],
        "市场风险": ["竞争", "政策变化", "需求下滑", "价格战"],
    }

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        texts = input_data.data.get("texts", [])
        if not texts and "text" in input_data.data:
            texts = [input_data.data["text"]]

        if not texts:
            return AgentOutput(
                result=[],
                metadata={"error": "No text input provided"},
                error="No text"
            )

        use_model = input_data.config.get("use_model", False)
        risks = []

        for text in texts:
            if use_model:
                risks_text = await self._get_risks_by_model(text)
                risks.extend(risks_text)
            else:
                risks_text = self._get_risks_by_rules(text)
                risks.extend(risks_text)

        # 去重（基于描述）
        unique_risks = []
        seen = set()
        for r in risks:
            key = (r["type"], r["description"])
            if key not in seen:
                seen.add(key)
                unique_risks.append(r)

        return AgentOutput(
            result=unique_risks,
            metadata={"method": "model" if use_model else "rules", "count": len(unique_risks)}
        )

    def _get_risks_by_rules(self, text: str) -> List[Dict[str, Any]]:
        """基于关键词匹配识别风险"""
        risks = []
        text_lower = text.lower()
        for risk_type, keywords in self.RISK_PATTERNS.items():
            for kw in keywords:
                if kw in text_lower:
                    # 避免重复添加同一类型
                    if not any(r["type"] == risk_type for r in risks):
                        risks.append({
                            "type": risk_type,
                            "description": f"检测到关键词「{kw}」，可能存在{risk_type}风险",
                            "severity": "中"  # 可进一步细化
                        })
                    break
        return risks

    async def _get_risks_by_model(self, text: str) -> List[Dict[str, Any]]:
        """调用模型识别风险"""
        prompt = f"""分析以下文本中的潜在风险，返回JSON格式列表，每个元素包含 type（风险类型）、description（描述）、severity（严重程度：高/中/低）。如果无风险，返回空列表。

文本：{text}

输出（JSON）："""
        try:
            response = await self._call_model(prompt)
            # 假设模型返回合法JSON
            import json
            # 提取JSON部分（可能包含其他文字）
            json_str = self._extract_json(response)
            if json_str:
                risks = json.loads(json_str)
                if isinstance(risks, list):
                    return risks
            return []
        except Exception as e:
            print(f"Model call failed: {e}")
            return self._get_risks_by_rules(text)

    def _extract_json(self, text: str) -> str:
        """从模型响应中提取JSON字符串"""
        # 简单实现：找到第一个[和最后一个]
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return ""