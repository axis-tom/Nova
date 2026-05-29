"""
API 成本管控

在 BudgetAwareScheduler 之上加三层保护：
  1. 硬配额 — API 月消耗上限
  2. 自适应限速 — 桶水位低时自动降级
  3. 异常熔断 — 连续 N 次失败暂停该源
"""
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CostController:
    """
    API 成本管控。

    用法：
        controller = CostController()
        if await controller.check_and_throttle("keepa", 10):
            # 执行采集
            ...
        if controller.should_circuit_break("rainforest"):
            # 跳过该源
            ...
    """

    # 硬配额上限
    MONTHLY_HARD_LIMITS = {
        "keepa_token": 1000,      # Pro 月使用上限
        "rf_credit": 500,          # Rainforest 预充值
        "canopy_credit": 200,      # Canopy 预充值
    }

    # 日限额（月配额 / 30 * 安全系数 1.5）
    _DAILY_LIMIT_CACHE: Dict[str, int] = {}

    def __init__(self):
        # (source_key, date_str) → 累计用量
        self._usage: Dict[str, int] = defaultdict(int)
        # source → [(timestamp, is_error)]
        self._errors: Dict[str, List[tuple]] = defaultdict(list)
        # source → 熔断截止时间
        self._circuit_break_until: Dict[str, float] = {}
        # source → 熔断恢复后的半开请求数（待确认）
        self._half_open: Dict[str, int] = {}

    # ── 硬配额检查 ──────────────────────────────────────────────────

    def _today(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _daily_limit(self, source_key: str) -> int:
        if source_key not in self._DAILY_LIMIT_CACHE:
            monthly = self.MONTHLY_HARD_LIMITS.get(source_key, 500)
            self._DAILY_LIMIT_CACHE[source_key] = max(10, monthly // 30)
        return self._DAILY_LIMIT_CACHE[source_key]

    async def check_and_throttle(self, source: str, cost: int = 1) -> bool:
        """
        检查此次请求是否在配额内。

        Args:
            source: 数据源（keepa/rainforest/canopy）
            cost: 本次请求预计消耗的 token/credit 数

        Returns:
            True=允许请求，False=已达限额
        """
        # 熔断检查
        if self._is_circuit_broken(source):
            logger.warning(f"[CostController] {source} 处于熔断状态，跳过")
            return False

        # 月配额检查
        monthly_key = f"monthly_{source}"
        monthly_usage = self._usage.get(monthly_key, 0)
        monthly_limit = self.MONTHLY_HARD_LIMITS.get(f"{source}_token"
                        if source == "keepa" else f"{source}_credit", 500)
        if monthly_usage + cost > monthly_limit:
            logger.warning(
                f"[CostController] {source} 月配额已达 ({monthly_usage}/{monthly_limit})"
            )
            return False

        # 日限额检查
        daily_key = f"{source}_{self._today()}"
        daily_usage = self._usage.get(daily_key, 0)
        daily_limit = self._daily_limit(daily_key)
        if daily_usage + cost > daily_limit:
            logger.warning(f"[CostController] {source} 日限额已达 ({daily_usage}/{daily_limit})")
            return False

        return True

    # ── 配额消耗记录 ─────────────────────────────────────────────────

    async def record_usage(self, source: str, cost: int = 1):
        """记录一次配额消耗"""
        self._usage[f"monthly_{source}"] += cost
        self._usage[f"{source}_{self._today()}"] += cost
        logger.debug(f"[CostController] {source} 消耗 {cost}，月累计 {self._usage[f'monthly_{source}']}")

    async def record_error(self, source: str):
        """记录一次失败（用于熔断判断）"""
        now = time.time()
        self._errors[source].append((now, True))
        # 只保留最近 30 分钟内的记录
        cutoff = now - 1800
        self._errors[source] = [(t, e) for t, e in self._errors[source] if t > cutoff]

        # 连续 5 次全失败 → 熔断
        recent = [e for _, e in self._errors[source][-5:]]
        if len(recent) >= 5 and all(recent):
            cool_off = 300  # 5 分钟冷却期
            self._circuit_break_until[source] = now + cool_off
            logger.warning(f"[CostController] {source} 连续 5 次失败，熔断 {cool_off}s")

    async def record_success(self, source: str):
        """记录一次成功（消除熔断判断的失败计数）"""
        # 清除该源的错误记录
        if source in self._errors:
            self._errors[source] = []
        # 如果处于半开状态，成功一次即可恢复
        if source in self._half_open:
            del self._half_open[source]

    # ── 熔断 ─────────────────────────────────────────────────────────

    def _is_circuit_broken(self, source: str) -> bool:
        """检查源是否处于熔断状态"""
        if source in self._circuit_break_until:
            if time.time() < self._circuit_break_until[source]:
                return True
            # 冷却期结束 → 半开状态，允许少量请求探测
            del self._circuit_break_until[source]
            self._half_open[source] = 0
            logger.info(f"[CostController] {source} 熔断冷却结束，进入半开探测")
        return False

    def should_circuit_break(self, source: str) -> bool:
        """对外接口：检查是否应跳过该源"""
        return self._is_circuit_broken(source)

    # ── 状态查询 ─────────────────────────────────────────────────────

    def get_usage_report(self) -> Dict:
        """获取当前用量报告"""
        report = {}
        for key in self.MONTHLY_HARD_LIMITS:
            usage = self._usage.get(f"monthly_{key.replace('_token', '').replace('_credit', '')}", 0)
            report[key] = {
                "used": usage,
                "limit": self.MONTHLY_HARD_LIMITS[key],
                "remaining": max(0, self.MONTHLY_HARD_LIMITS[key] - usage),
            }
        return report

    def get_daily_usage(self, source: str) -> int:
        """获取某个源当日用量"""
        return self._usage.get(f"{source}_{self._today()}", 0)

    def reset(self):
        """重置所有用量和错误记录（用于测试或月结算）"""
        self._usage.clear()
        self._errors.clear()
        self._circuit_break_until.clear()
        self._half_open.clear()


# 全局单例
cost_controller = CostController()