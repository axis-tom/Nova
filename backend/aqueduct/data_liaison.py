"""
DataLiaison — 数据联络员

纯数据层服务，不配 LLM。职责：
1. Phase 0 数据就绪检查（在 Orchestrator ReAct 启动前）
2. 接 Orchestrator/Agent 的数据发现请求 → 查 DB → 按需触发的 ETL（有成本控制）
3. 返回数据可用性报告

与 ProductCollectorAgent 的关键区别：
- 没有 LLM、没有 ReAct 循环
- 不直接调 API，走后端 DataProvider（负责冷启动/刷新/成本控制）
- 永远只回应"DB 有什么"和"能补充什么（有界限的）"
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from backend.core.prompt_engine.engines.intent_classifier import IntentAnalysisSpec
from backend.data.database import AsyncSessionLocal
from backend.data.repositories.postgreSQL.amazon_product_repo import AmazonProductRepository
from backend.aqueduct.data_provider import DataProvider

logger = logging.getLogger(__name__)

# ASIN 正则
_ASIN_PATTERN = re.compile(r'\bB[A-Z0-9]{9}\w?\b')


@dataclass
class DataReadinessReport:
    """数据就绪报告——Phase 0 的输出"""
    available_asins: List[str] = field(default_factory=list)       # DB 已有的 ASIN
    missing_asins: List[str] = field(default_factory=list)         # DB 没有的 ASIN
    category_product_count: int = 0                                # DB 中该品类的产品数
    domain_available: bool = False                                 # 该 domain 是否有数据
    total_products_available: int = 0                              # 会话可用总产品数
    needs_cold_start: bool = False                                 # 是否需要冷启动
    cold_start_asins: List[str] = field(default_factory=list)      # 需要冷启动的 ASIN
    category_hint_raw: str = ""                                    # 原始的 category_hint

    @property
    def is_ready(self) -> bool:
        """是否有足够数据启动分析"""
        return self.total_products_available > 0 or not self.needs_cold_start


class DataLiaison:
    """
    数据联络员——纯数据层服务。

    用法（Phase 0 就绪检查）：
        liaison = DataLiaison()
        report = await liaison.prepare(intent_spec)
        if report.needs_cold_start:
            await liaison.collect_missing(report.cold_start_asins)

    用法（Orchestrator 工具）：
        report = await liaison.discover("蓝牙耳机", domain="US")
        # 返回 DB 中有什么数据
    """

    def __init__(self):
        self._provider = DataProvider()
        self._cold_start_lock: asyncio.Lock = asyncio.Lock()

    # ════════════════════════════════════════════════════════════════
    # Phase 0：从 IntentAnalysisSpec 做数据就绪检查
    # ════════════════════════════════════════════════════════════════

    async def prepare(self, spec: IntentAnalysisSpec, domain: str = "US") -> DataReadinessReport:
        """
        根据 IntentAnalysisSpec 检查数据就绪状态。

        流程：
        1. 从 entities + raw_query 提取 ASIN
        2. 查 DB 检查每个 ASIN 是否存在
        3. 从 category_hint 推断品类范围，查 DB 品类覆盖
        4. 返回就绪报告

        ASIN 级别的缺失 → cold_start（有界限的，不走 ETL 全品类）
        品类级别的缺失 → 只报告不触发（品类级 ETL 由调度器独立负责）
        """
        # 1. 提取所有 ASIN
        all_asins = set(spec.entities or [])
        # 从 raw_query 补充 ASIN
        query_asins = _ASIN_PATTERN.findall(spec.raw_query)
        all_asins.update(a.upper() for a in query_asins)
        # 过滤掉非 ASIN 的实体（品牌名、品类名）
        real_asins = [a for a in all_asins if _ASIN_PATTERN.match(a)]

        # 2. 查 DB
        available = []
        missing = []
        if real_asins:
            async with AsyncSessionLocal() as db:
                repo = AmazonProductRepository(db)
                existing = await repo.get_by_asins(real_asins, domain)
            for asin in real_asins:
                if asin in existing:
                    available.append(asin)
                else:
                    missing.append(asin)

        # 3. 品类覆盖检查
        category_count = 0
        domain_available = False
        try:
            async with AsyncSessionLocal() as db:
                repo = AmazonProductRepository(db)
                products, total = await repo.search_products(
                    domain=domain, limit=1, sort_by="importance_score"
                )
                domain_available = total > 0
                if total > 0:
                    # 粗略估计品类覆盖：取 top 50
                    products50, _ = await repo.search_products(
                        domain=domain, limit=50, sort_by="importance_score"
                    )
                    category_count = len(products50)
        except Exception as e:
            logger.warning(f"[DataLiaison] 品类覆盖检查失败: {e}")

        total_available = len(available) + category_count

        return DataReadinessReport(
            available_asins=available,
            missing_asins=missing,
            category_product_count=category_count,
            domain_available=domain_available,
            total_products_available=total_available,
            needs_cold_start=len(missing) > 0,
            cold_start_asins=missing,
            category_hint_raw=spec.category_hint,
        )

    async def collect_missing(self, asins: List[str], domain: str = "US") -> Dict[str, bool]:
        """
        对缺失的 ASIN 执行冷启动（有界限的采集）。

        只采集 ASIN 级别缺失的数据，不走品类级 ETL。
        DataProvider.get_product_blocking 内部 ETLPipeline.cold_start
        会经过 Keepa 桶水位控制（cost_controller）和采集队列去重。
        """
        if not asins:
            return {}

        async with self._cold_start_lock:
            results = {}
            for asin in asins:
                try:
                    product = await self._provider.get_product_blocking(asin, domain)
                    results[asin] = product is not None
                except Exception as e:
                    logger.warning(f"[DataLiaison] 冷启动 {asin} 失败: {e}")
                    results[asin] = False
            return results

    # ════════════════════════════════════════════════════════════════
    # Orchestrator 工具接口：按需发现数据
    # ════════════════════════════════════════════════════════════════

    async def discover(self, hint: str, domain: str = "US", limit: int = 50) -> str:
        """
        数据发现——查 DB 返回可用数据概览。

        这是给 Orchestrator 的工具的底层方法。
        不触发任何 API 调用。
        """
        discovered_asins = _ASIN_PATTERN.findall(hint.upper())
        async with AsyncSessionLocal() as db:
            repo = AmazonProductRepository(db)

            # 如果有 ASIN，直接查
            asin_data = {}
            if discovered_asins:
                existing = await repo.get_by_asins(discovered_asins, domain)
                for asin, product in existing.items():
                    asin_data[asin] = {
                        "title": product.title,
                        "brand": product.brand,
                        "current_price": product.current_price,
                        "rating": product.rating,
                        "current_bsr": product.current_bsr,
                    }

            # 查品类概览
            products, total = await repo.search_products(
                domain=domain, limit=min(limit, 50), sort_by="importance_score"
            )

        lines = [f"[DataLiaison] 数据库当前状态（{domain}）:", f"  品类产品数: {total}"]
        if asin_data:
            lines.append(f"  指定 ASIN 命中: {len(asin_data)}/{len(discovered_asins)}")
            for asin, info in asin_data.items():
                lines.append(f"    {asin}: {info.get('title', '?')[:50]}")
        if total > 0:
            lines.append(f"  Top 产品样本: {len(products)} 条")
            if products:
                brands = set(p.brand for p in products if p.brand)
                price_range = f"${min(p.current_price for p in products if p.current_price):.0f} ~ ${max(p.current_price for p in products if p.current_price):.0f}"
                lines.append(f"  品牌数: {len(brands)} | 价格区间: {price_range}")

        return "\n".join(lines)