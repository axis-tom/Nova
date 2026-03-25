from typing import Dict, Any, List
from backend.agents.base import Agent, AgentInput, AgentOutput

class RuleGenerator(Agent):
    """
    规则生成智能体：
    根据用户历史行为，自动生成 IF-THEN 规则。
    """
    name = "rule_generator"
    description = "从用户行为生成自动化规则"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 输入应包含用户行为序列
        behaviors = input_data.data.get("behaviors", [])
        if not behaviors:
            return AgentOutput(
                result={"generated_rules": []},
                metadata={"error": "No behaviors"},
                error="No behaviors"
            )

        use_model = input_data.config.get("use_model", True)
        if use_model:
            rules = await self._generate_rules_by_model(behaviors)
        else:
            rules = self._generate_rules_by_pattern(behaviors)

        return AgentOutput(
            result={"generated_rules": rules},
            metadata={"method": "model" if use_model else "patterns"}
        )

    def _generate_rules_by_pattern(self, behaviors: List[Dict]) -> List[Dict]:
        """基于简单模式生成规则"""
        rules = []
        # 示例：如果用户经常忽略某种类型的通知，生成忽略规则
        ignore_counts = {}
        for b in behaviors:
            if b.get("action") == "ignore":
                item_type = b.get("item_type")
                ignore_counts[item_type] = ignore_counts.get(item_type, 0) + 1

        for item_type, count in ignore_counts.items():
            if count >= 3:  # 忽略三次以上
                rules.append({
                    "condition": f"item_type == '{item_type}'",
                    "action": "auto_ignore",
                    "confidence": min(0.8, count / 10)
                })

        return rules

    async def _generate_rules_by_model(self, behaviors: List[Dict]) -> List[Dict]:
        """调用模型生成规则"""
        import json
        behavior_str = json.dumps(behaviors[-20:], ensure_ascii=False)  # 最近20条
        prompt = f"""根据以下用户行为序列，生成可能的自动化规则（IF-THEN 格式），输出JSON列表，每个规则包含 condition、action、confidence。

行为序列：
{behavior_str}

输出（JSON列表）："""
        try:
            response = await self._call_model(prompt)
            json_str = self._extract_json(response)
            if json_str:
                rules = json.loads(json_str)
                if isinstance(rules, list):
                    return rules
            return self._generate_rules_by_pattern(behaviors)
        except Exception as e:
            print(f"Model call failed: {e}")
            return self._generate_rules_by_pattern(behaviors)

    def _extract_json(self, text: str) -> str:
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return ""