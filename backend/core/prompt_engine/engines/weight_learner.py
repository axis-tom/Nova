"""
WeightLearner — 权重学习模块

借鉴 AutoPrompt 的迭代优化循环理念。
在运行时记录每个策略的 score，用于下次选择最优策略。
简化版实现：30 行 Python 完成核心逻辑。
"""

from typing import Dict, Any, Optional


class WeightLearner:
    """权重学习器——记录每个策略的得分，用于下次选择最优策略

    优化循环：
    1. 策略 A（pricing 为主线）score=0.7
    2. 策略 B（competition 为主线）score=0.85
    3. 下次同类 query → B 被选中的概率更高
    4. 执行后更新 score
    5. 连续 N 次无提升 → 停止尝试某策略
    """

    # 默认策略权重
    DEFAULT_WEIGHTS = {
        "pricing_first": 1.0,
        "competition_first": 1.0,
        "review_first": 1.0,
        "balanced": 1.0,
    }

    def __init__(self):
        self.weights: Dict[str, float] = dict(self.DEFAULT_WEIGHTS)
        self.scores: Dict[str, list] = {k: [] for k in self.DEFAULT_WEIGHTS}
        self._consecutive_no_improvement: Dict[str, int] = {k: 0 for k in self.DEFAULT_WEIGHTS}
        self.MAX_NO_IMPROVEMENT = 5  # 连续 N 次无提升 → 停止尝试

    def select_strategy(self, context: str, available_strategies: Optional[list] = None) -> str:
        """根据当前权重选择最优策略

        Args:
            context: 上下文描述（用于后续区分场景）
            available_strategies: 可选策略列表，None = 全部

        Returns:
            选中策略的名称
        """
        candidates = available_strategies or list(self.weights.keys())

        # 剔除已停止尝试的策略
        active = [s for s in candidates
                  if self._consecutive_no_improvement.get(s, 0) < self.MAX_NO_IMPROVEMENT]
        if not active:
            active = candidates  # 所有策略都停用过，重置

        # 按权重采样（加权随机）
        import random
        weights = [self.weights.get(s, 1.0) for s in active]
        total = sum(weights)
        if total <= 0:
            return active[0]

        r = random.uniform(0, total)
        cumulative = 0.0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return active[i]
        return active[-1]

    def update_score(self, strategy: str, score: float):
        """更新策略得分

        Args:
            strategy: 策略名称
            score: 0.0 ~ 1.0 的得分（1.0 = 最满意）
        """
        if strategy not in self.scores:
            self.scores[strategy] = []
        self.scores[strategy].append(score)

        # 计算加权平均（最近 N 次权重更高）
        recent = self.scores[strategy][-10:]  # 最多保留 10 次
        weights = [1.0 + i * 0.5 for i in range(len(recent))]  # 越近权重越高
        weighted_avg = sum(s * w for s, w in zip(recent, weights)) / sum(weights)

        self.weights[strategy] = weighted_avg

        # 无提升检测
        if len(recent) >= 2:
            if recent[-1] <= recent[-2]:
                self._consecutive_no_improvement[strategy] = \
                    self._consecutive_no_improvement.get(strategy, 0) + 1
            else:
                self._consecutive_no_improvement[strategy] = 0

    def get_best_strategy(self, context: Optional[str] = None) -> Optional[str]:
        """获取当前最优策略"""
        if not self.weights:
            return None
        return max(self.weights, key=self.weights.get)

    def get_weight_summary(self) -> Dict[str, Any]:
        """获取权重摘要"""
        return {
            "weights": dict(self.weights),
            "scores": {k: v[-5:] if v else [] for k, v in self.scores.items()},
            "active": [k for k, v in self._consecutive_no_improvement.items()
                      if v < self.MAX_NO_IMPROVEMENT],
            "stopped": [k for k, v in self._consecutive_no_improvement.items()
                       if v >= self.MAX_NO_IMPROVEMENT],
        }

    def reset(self):
        """重置所有权重"""
        self.weights = dict(self.DEFAULT_WEIGHTS)
        self.scores = {k: [] for k in self.DEFAULT_WEIGHTS}
        self._consecutive_no_improvement = {k: 0 for k in self.DEFAULT_WEIGHTS}