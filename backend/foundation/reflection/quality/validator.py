from typing import Dict, Any, List
from backend.common.core import Agent, AgentInput, AgentOutput

class ValidatorAgent(Agent):
    """
    质量验证智能体：
    验证智能体输出是否符合预期格式，是否包含必要字段。
    """
    name = "validator_agent"
    description = "验证输出格式和完整性"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 输入应包含待验证的数据和验证规则
        data = input_data.data.get("data", {})
        rules = input_data.data.get("rules", {})

        if not data:
            return AgentOutput(
                result={"valid": False, "errors": ["No data to validate"]},
                metadata={"error": "No data"}
            )

        errors = self._validate(data, rules)
        valid = len(errors) == 0

        return AgentOutput(
            result={"valid": valid, "errors": errors},
            metadata={"rules_applied": list(rules.keys())}
        )

    def _validate(self, data: Any, rules: Dict[str, Any]) -> List[str]:
        """根据规则验证数据（简单递归实现）"""
        errors = []
        if isinstance(rules, dict) and isinstance(data, dict):
            for field, rule in rules.items():
                if field not in data:
                    errors.append(f"Missing field: {field}")
                else:
                    # 递归验证嵌套字段
                    if isinstance(rule, dict):
                        sub_errors = self._validate(data[field], rule)
                        errors.extend([f"{field}.{e}" for e in sub_errors])
                    else:
                        # 类型检查
                        expected_type = rule.get("type") if isinstance(rule, dict) else rule
                        if expected_type == "list" and not isinstance(data[field], list):
                            errors.append(f"{field} should be list")
                        elif expected_type == "dict" and not isinstance(data[field], dict):
                            errors.append(f"{field} should be dict")
                        elif expected_type == "str" and not isinstance(data[field], str):
                            errors.append(f"{field} should be string")
                        elif expected_type == "int" and not isinstance(data[field], int):
                            errors.append(f"{field} should be integer")
        elif isinstance(rules, list) and isinstance(data, list):
            for idx, item in enumerate(data):
                sub_errors = self._validate(item, rules[0] if rules else {})
                errors.extend([f"[{idx}].{e}" for e in sub_errors])
        else:
            # 简单类型检查
            if rules == "str" and not isinstance(data, str):
                errors.append(f"Expected string, got {type(data).__name__}")
        return errors
