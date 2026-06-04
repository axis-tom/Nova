"""
Evaluator — Prompt 效果评估模块

借鉴 Promptfoo 的 YAML 评估配置格式。
评估是开发期功能，不参与运行时行为。
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class EvalCase:
    """评估用例"""
    description: str
    query: str
    expected_dimensions: List[str] = field(default_factory=list)
    expected_intent: str = ""
    expected_entities: List[str] = field(default_factory=list)
    assertions: List[str] = field(default_factory=list)


class Evaluator:
    """Prompt 效果评估模块

    评估是开发期功能，不参与运行时行为。
    设计目标：
    1. 比较不同策略（strategy）的 prompt 在同类 query 上的效果
    2. 用 LLM-as-judge 评估输出质量
    3. 输出 score 供 WeightLearner 使用
    """

    def __init__(self):
        self.cases: List[EvalCase] = []
        self.results: Dict[str, Any] = {}

    def load_case(self, case: EvalCase):
        """注册单个评估用例"""
        self.cases.append(case)

    def load_cases(self, cases: List[EvalCase]):
        """批量注册评估用例"""
        self.cases.extend(cases)

    def evaluate_strategy(self, strategy_name: str, prompt_fn) -> float:
        """评估某个策略的 prompt 质量

        Args:
            strategy_name: 策略名称（如 "pricing_only", "pricing_with_competition"）
            prompt_fn: 接受 query → 返回 prompt 的函数

        Returns:
            score: 0.0 ~ 1.0 的得分
        """
        if not self.cases:
            return 0.0

        total = 0.0
        for case in self.cases:
            # 用 prompt_fn 生成 prompt（评估期模拟）
            try:
                prompt = prompt_fn(case.query)
                score = self._score_prompt(prompt, case)
                total += score
            except Exception:
                total += 0.0

        avg_score = total / len(self.cases)
        self.results[strategy_name] = {
            "score": round(avg_score, 4),
            "case_count": len(self.cases),
        }
        return avg_score

    def _score_prompt(self, prompt: str, case: EvalCase) -> float:
        """单条 prompt 的评分

        检查 prompt 中是否包含预期的维度/实体/意图描述。
        简单的关键词覆盖度评估。
        """
        if not prompt:
            return 0.0

        score = 1.0
        prompt_lower = prompt.lower()

        # 检查预期维度
        if case.expected_dimensions:
            found = sum(1 for d in case.expected_dimensions if d.lower() in prompt_lower)
            score *= found / len(case.expected_dimensions)

        # 检查预期实体
        if case.expected_entities:
            found = sum(1 for e in case.expected_entities if e.lower() in prompt_lower)
            score *= found / len(case.expected_entities)

        return max(0.0, min(1.0, score))

    def get_results(self) -> Dict[str, Any]:
        """获取评估结果"""
        return {
            "strategies": self.results,
            "total_cases": len(self.cases),
        }

    def get_best_strategy(self) -> Optional[str]:
        """获取最高分的策略"""
        if not self.results:
            return None
        return max(self.results, key=lambda s: self.results[s]["score"])