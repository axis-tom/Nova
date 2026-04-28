import json
from typing import Dict, Any, Optional
from backend.common.core import Agent, AgentInput, AgentOutput

class EmotionAgent(Agent):
    """
    情绪分析智能体：
    分析用户文本情绪，返回情绪类型和强度。
    """
    name = "emotion_agent"
    description = "分析用户情绪（积极、消极、中性等）"

    # 简单关键词映射
    POSITIVE_KEYWORDS = ["好", "棒", "满意", "开心", "感谢", "赞"]
    NEGATIVE_KEYWORDS = ["差", "坏", "不满", "生气", "失望", "糟糕"]

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        text = input_data.data.get("text", "")
        if not text:
            return AgentOutput(
                result={"emotion": "neutral", "intensity": 0},
                metadata={"error": "No text"},
                error="No text"
            )

        use_model = input_data.config.get("use_model", False)
        if use_model:
            emotion = await self._get_emotion_by_model(text)
        else:
            emotion = self._get_emotion_by_rules(text)

        return AgentOutput(
            result=emotion,
            metadata={"method": "model" if use_model else "rules"}
        )

    def _get_emotion_by_rules(self, text: str) -> Dict[str, Any]:
        """基于关键词简单判断情绪"""
        text_lower = text.lower()
        positive_score = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text_lower)
        negative_score = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text_lower)

        if positive_score > negative_score:
            emotion = "positive"
            intensity = min(positive_score / 5, 1.0)
        elif negative_score > positive_score:
            emotion = "negative"
            intensity = min(negative_score / 5, 1.0)
        else:
            emotion = "neutral"
            intensity = 0.0

        return {"emotion": emotion, "intensity": intensity}

    async def _get_emotion_by_model(self, text: str) -> Dict[str, Any]:
        """调用模型进行情绪分析"""
        prompt = f"""分析以下文本的情绪，输出JSON格式，包含 emotion（positive/negative/neutral）和 intensity（0-1之间的浮点数）。

文本：{text}

输出（JSON）："""
        try:
            response = await self._call_model(prompt)
            json_str = self._extract_json(response)
            if json_str:
                result = json.loads(json_str)
                if isinstance(result, dict):
                    # 确保字段存在
                    return {
                        "emotion": result.get("emotion", "neutral"),
                        "intensity": float(result.get("intensity", 0))
                    }
            return {"emotion": "neutral", "intensity": 0}
        except Exception as e:
            print(f"Model call failed: {e}")
            return self._get_emotion_by_rules(text)

    def _extract_json(self, text: str) -> str:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return ""