"""
DataLiaison — 数据联络员（精简版）

新定位：只做"食材采购 + 仓库导航"，不做"切菜摆盘"。

职责：
1. 从用户输入提取 ASIN → 检查哪些在本地库 → 触发冷启动采集缺失的
2. 品类跨列探索 → 告诉 LLM "DB 里有 XX 品类/YY 品牌的 Z 个商品"
3. 对"没有明确 ASIN 也没有品类"的查询 → 返回数据库全景

不做的事（已由 5 个数据工具替代）：
- ❌ product_preview 预取数据
- ❌ 字段覆盖检查（asin_fields_coverage）
- ❌ 替代 LLM 判断"数据够不够"
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
_ASIN_PATTERN = re.compile(r'(?<![A-Za-z0-9])B[A-Z0-9]{9}[A-Z0-9]?(?![A-Za-z0-9])')


@dataclass
class DataIntelligenceReport:
    """
    数据情报报告——Phase 0 的输出。

    精简后只报告 3 件事：
    1. DB 中有哪些 ASIN（found）和缺失哪些（missing → can_collect）
    2. 品类探索到了什么（品类名、品牌、商品数）
    3. 数据库全景（什么都不指定时）
    """
    # ── ASIN 级别 ──
    requested_asins: List[str] = field(default_factory=list)
    found_asins: List[str] = field(default_factory=list)
    missing_asins: List[str] = field(default_factory=list)

    # ── 品类级别 ──
    category_hint: str = ""
    exploration: Optional[Dict] = None
    matched_category_names: List[str] = field(default_factory=list)

    # ── 数据库全景 ──
    catalog: Optional[Dict] = None

    # ── 可操作项 ──
    can_collect_asins: List[str] = field(default_factory=list)

    @property
    def total_products_available(self) -> int:
        """DB 中探索到的产品数"""
        if self.exploration:
            return self.exploration.get("total_distinct_asins", 0)
        return 0

    @property
    def domain_has_data(self) -> bool:
        """该 domain 是否有任何数据"""
        if self.catalog:
            return self.catalog.get("total_products", 0) > 0
        return self.total_products_available > 0

    def to_llm_context(self) -> str:
        """
        极简情报摘要——30 字级，只报告 DB 格局。
        LLM 通过 5 个数据工具自主获取数据，不需要看长篇情报。
        """
        parts = []

        # ASIN 状态
        if self.found_asins:
            parts.append(f"✅ DB 中有 {len(self.found_asins)} 个 ASIN: {', '.join(self.found_asins[:8])}")
        if self.missing_asins:
            parts.append(f"❌ 缺失 {len(self.missing_asins)} 个 ASIN: {', '.join(self.missing_asins[:5])}（已采集）")

        # 品类探索（只报告个数，不给具体数据）
        if self.exploration:
            total = self.exploration.get("total_distinct_asins", 0)
            cats = list(self.exploration.get("categories_found", {}).keys())[:4]
            brands = list(self.exploration.get("brands_found", {}).keys())[:6]
            parts.append(f"📊 品类探索: {total} 个商品")
            if cats:
                parts.append(f"   品类: {', '.join(cats)}")
            if brands:
                parts.append(f"   品牌: {', '.join(brands)}")

        # 全景
        if self.catalog:
            parts.append(f"📁 DB 全景: {self.catalog.get('total_products', 0)} 个商品")

        return " | ".join(parts) if parts else "DB 中未找到匹配数据"


class DataLiaison:
    """
    数据联络员——Phase 0 数据预处理（纯读 + 缺失采集）。
    """

    def __init__(self):
        self._provider = DataProvider()
        self._cold_start_lock: asyncio.Lock = asyncio.Lock()

    async def collect_intel(self, spec: IntentAnalysisSpec, domain: str = "US") -> DataIntelligenceReport:
        """
        收集数据情报。

        流程：
        1. 从 entities + raw_query 提取 ASIN
        2. 查 DB 检查每个 ASIN 存在/缺失
        3. 有品类 hint → 跨列探索
        4. 无 hint 无 ASIN → 返回数据库全景
        """
        # 1. ASIN 提取
        all_asins = set(spec.entities or [])
        query_asins = _ASIN_PATTERN.findall(spec.raw_query)
        all_asins.update(a.upper() for a in query_asins)
        real_asins = [a for a in all_asins if _ASIN_PATTERN.match(a)]

        # 2. ASIN 级别查询
        found_asins = []
        missing_asins = []
        if real_asins:
            async with AsyncSessionLocal() as db:
                repo = AmazonProductRepository(db)
                existing = await repo.get_by_asins(real_asins, domain)
            for asin in real_asins:
                if asin in existing:
                    found_asins.append(asin)
                else:
                    missing_asins.append(asin)

        # 3. 品类跨列探索
        exploration = None
        matched_category = []
        category_hint = spec.category_hint.strip() if spec.category_hint else ""
        if category_hint:
            async with AsyncSessionLocal() as db:
                repo = AmazonProductRepository(db)
                exploration = await repo.explore(category_hint, domain=domain)
            if exploration:
                matched_category = list(exploration.get("categories_found", {}).keys())

        # 4. 无 hint 无 ASIN → 数据库全景
        catalog = None
        if not real_asins and not category_hint:
            async with AsyncSessionLocal() as db:
                repo = AmazonProductRepository(db)
                catalog = await repo.get_catalog(domain=domain)

        # 5. 可冷启动的 ASIN
        can_collect = missing_asins if missing_asins else []

        return DataIntelligenceReport(
            requested_asins=real_asins,
            found_asins=found_asins,
            missing_asins=missing_asins,
            category_hint=category_hint,
            exploration=exploration,
            matched_category_names=matched_category,
            catalog=catalog,
            can_collect_asins=can_collect,
        )

    async def collect_missing(self, asins: List[str], domain: str = "US") -> Dict[str, bool]:
        """冷启动采集缺失 ASIN（有界限的采集）"""
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

    async def discover(self, hint: str, domain: str = "US", limit: int = 50) -> str:
        """
        数据发现（给 Orchestrator 工具用，但新 5 个工具已替代此功能）。
        保留以向后兼容。
        """
        discovered_asins = _ASIN_PATTERN.findall(hint.upper())
        async with AsyncSessionLocal() as db:
            repo = AmazonProductRepository(db)
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
            exploration = await repo.explore(hint, domain=domain, limit=limit)

        lines = [f"[DataLiaison] 数据探索报告（{domain}）:"]
        if discovered_asins:
            lines.append(f"  指定 ASIN 命中: {len(asin_data)}/{len(discovered_asins)}")
        total = exploration.get("total_distinct_asins", 0)
        lines.append(f"  品类探索找到: {total} 个商品")
        return "\n".join(lines)