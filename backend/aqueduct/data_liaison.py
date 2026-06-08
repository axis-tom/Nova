"""
DataLiaison — 数据联络员

纯数据层服务，不配 LLM。职责：
1. Phase 0 数据就绪检查（在 Orchestrator ReAct 启动前）
2. 接 Orchestrator/Agent 的数据发现请求 → 查 DB → 返回数据
3. 永远只报告"DB 发现了什么"——不做"够不够分析"的判断

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
# ★ P8 修复：不用 \b 边界，改用 lookbehind/lookahead 防误匹配
# \b 在 Python3 中把 CJK 字符视为 \w，中文字符 + ASIN 之间没有 word boundary
_ASIN_PATTERN = re.compile(r'(?<![A-Za-z0-9])B[A-Z0-9]{9}[A-Z0-9]?(?![A-Za-z0-9])')


@dataclass
class DataIntelligenceReport:
    """
    数据情报报告——Phase 0 的输出。

    不再替代 LLM 做"数据够不够"的判断。
    只报告事实，让 LLM 自己决策。
    """
    # ── ASIN 级别的命中情况 ──
    requested_asins: List[str] = field(default_factory=list)       # 用户提到的 ASIN（从 entities + raw_query 提取）
    found_asins: List[str] = field(default_factory=list)            # DB 中存在的 ASIN
    missing_asins: List[str] = field(default_factory=list)          # DB 中没有的 ASIN
    asin_product_count: int = 0                                     # DB 中找到的 ASIN 商品数
    asin_fields_coverage: Dict[str, List[str]] = field(default_factory=dict)  # 每 ASIN 有哪些字段有值

    # ── 品类级别的探索结果 ──
    category_hint: str = ""                                          # 用户原始品类提示
    exploration: Optional[Dict] = None                               # explore() 的完整输出（含各个方面命中数、策略明细）
    matched_category_names: List[str] = field(default_factory=list)  # 探索到的品类名
    matched_product_types: List[str] = field(default_factory=list)   # 探索到的产品类型名

    # ── 数据库全景（无 hint 时用） ──
    catalog: Optional[Dict] = None                                   # get_catalog() 的完整输出

    # ── 可用操作 ──
    can_collect_asins: List[str] = field(default_factory=list)       # 可以冷启动的 ASIN

    # ── 产品预取数据（让 LLM 直接看到真实数值，不再猜疑） ──
    product_preview: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @property
    def total_products_available(self) -> int:
        """DB 中总共能获取到的产品数（不论数据质量）"""
        if self.exploration:
            return self.exploration.get("total_distinct_asins", 0)
        return self.asin_product_count

    @property
    def domain_has_data(self) -> bool:
        """该 domain 是否有任何数据"""
        if self.catalog:
            return self.catalog.get("total_products", 0) > 0
        return self.total_products_available > 0

    def to_llm_context(self) -> str:
        """
        生成供 LLM 阅读的自然语言上下文。
        这个文本是"情报报告"——只描述事实，不做判断。
        """
        parts = []

        # ── ASIN 级别 ──
        if self.requested_asins:
            found = self.found_asins[:10]
            missing = self.missing_asins[:10]
            parts.append(f"用户提及了 {len(self.requested_asins)} 个 ASIN：")
            if found:
                parts.append(f"  ✅ DB 中找到了 {len(found)} 个：{', '.join(found)}")
                if self.asin_fields_coverage:
                    parts.append(f"  这些 ASIN 的数据（180+ 字段）已就绪，直接调 call_nova_agent 分析，不要用 search_web 搜 estos ASIN。")
            if missing:
                parts.append(f"  ❌ {len(missing)} 个 ASIN 不在 DB 中：{', '.join(missing)}（需冷启动采集）")

        # ── 品类探索 ──
        if self.exploration:
            exp = self.exploration
            total = exp.get("total_distinct_asins", 0)
            parts.append(f"\n品类探索（搜索词：{self.category_hint}）：")
            parts.append(f"  共找到 {total} 个相关商品")

            # 各策略命中情况
            strategies = exp.get("strategies_attempted", [])
            active = [s for s in strategies if s.get("matched", 0) > 0]
            if active:
                parts.append(f"  搜索策略命中明细：")
                for s in active:
                    parts.append(f"    - {s['column']}({s['strategy']}): {s['matched']} 条（新增 {s.get('new_asins', 0)} 条）")

            # 发现的品类分布
            cats = exp.get("categories_found", {})
            if cats:
                top_cats = list(cats.keys())[:5]
                parts.append(f"  🏷️ 匹配到的品类名：{', '.join(f'{c}({cats[c]})' for c in top_cats)}")

            ptypes = exp.get("product_types_found", {})
            if ptypes:
                top_pts = list(ptypes.keys())[:5]
                parts.append(f"  📦 匹配到的产品类型：{', '.join(f'{p}({ptypes[p]})' for p in top_pts)}")

            brands = exp.get("brands_found", {})
            if brands:
                top_br = list(brands.keys())[:10]
                parts.append(f"  🏢 涉及品牌（前{len(top_br)}）：{', '.join(f'{b}({brands[b]})' for b in top_br)}")

            # 高价值产品
            products = exp.get("products", [])
            if products:
                top = sorted(products, key=lambda p: p.get("importance_score", 0) or 0, reverse=True)[:5]
                parts.append(f"  ⭐ 高 Importance 产品样本：")
                for p in top:
                    parts.append(f"    {p.get('asin', '')}: {p.get('title', '?')[:50]} | "
                                 f"${p.get('current_price', '?')} | "
                                 f"rating={p.get('rating', '?')} | "
                                 f"BSR={p.get('current_bsr', '?')} | "
                                 f"月销={p.get('monthly_sold', '?')}")

        # ── 数据库全景 ──
        if self.catalog:
            cat = self.catalog
            parts.append(f"\n数据库全景（{cat.get('total_products', 0)} 个商品）：")
            if cat.get("categories"):
                parts.append(f"  📁 品类：{', '.join(c['name'] for c in cat['categories'][:8])}")
            if cat.get("product_types"):
                parts.append(f"  📦 产品类型：{', '.join(p['name'] for p in cat['product_types'][:8])}")
            if cat.get("brands"):
                parts.append(f"  🏢 品牌：{', '.join(b['name'] for b in cat['brands'][:10])}")

            # 字段填充率——帮助 LLM 判断"这些数据质量够不够"
            field_stats = cat.get("field_stats", {})
            if field_stats:
                filled_fields = [f"{k}={v.get('pct', 0)}%" for k, v in sorted(field_stats.items(), key=lambda x: -x[1].get('pct', 0))[:10]]
                parts.append(f"  字段填充率（前10）：{' | '.join(filled_fields)}")

        # ── 可操作项 ──
        if self.can_collect_asins:
            parts.append(f"\n🔧 可以采集的 ASIN：{', '.join(self.can_collect_asins)}（调用 DataProvider 冷启动）")

        return "\n".join(parts)


class DataLiaison:
    """
    数据联络员——纯数据层服务。

    用法（Phase 0 情报收集）：
        liaison = DataLiaison()
        report = await liaison.collect_intel(intent_spec)
        # report.to_llm_context() → 给 LLM 自己判断

    用法（Orchestrator 工具）：
        report = await liaison.discover("蓝牙耳机", domain="US")
        # 返回 DB 中有什么数据
    """

    def __init__(self):
        self._provider = DataProvider()
        self._cold_start_lock: asyncio.Lock = asyncio.Lock()

    # ════════════════════════════════════════════════════════════════
    # Phase 0：情报收集（不再做二元"数据就绪"判断）
    # ════════════════════════════════════════════════════════════════

    async def collect_intel(self, spec: IntentAnalysisSpec, domain: str = "US") -> DataIntelligenceReport:
        """
        根据 IntentAnalysisSpec 收集数据情报。

        返回的 DataIntelligenceReport 包含所有发现的事实，
        但不做"够不够分析"的判断——交给 LLM 自己决定。

        流程：
        1. 从 entities + raw_query 提取 ASIN
        2. 查 DB 检查每个 ASIN 是否存在
        3. 从 category_hint 跨列探索品类
        4. 如果没有 hint 也没有 ASIN，返回数据库全景
        5. ★ 对每个命中 ASIN 预取关键字段预览数据
        """
        # 1. ASIN 提取
        all_asins = set(spec.entities or [])
        query_asins = _ASIN_PATTERN.findall(spec.raw_query)
        all_asins.update(a.upper() for a in query_asins)
        real_asins = [a for a in all_asins if _ASIN_PATTERN.match(a)]

        # 2. ASIN 级别查询
        found_asins = []
        missing_asins = []
        asin_coverage: Dict[str, List[str]] = {}
        product_preview: Dict[str, Dict[str, Any]] = {}
        if real_asins:
            async with AsyncSessionLocal() as db:
                repo = AmazonProductRepository(db)
                existing = await repo.get_by_asins(real_asins, domain)
            for asin in real_asins:
                if asin in existing:
                    found_asins.append(asin)
                    p = existing[asin]
                    # 字段覆盖检查
                    filled = []
                    for f in ("title", "brand", "current_price", "rating", "review_count",
                              "current_bsr", "monthly_sold", "feature_bullets",
                              "main_image", "buybox_price", "offer_count", "fba_fee",
                              "stock_level", "aplus_content", "price_history",
                              "bsr_history", "rating_history", "is_fba"):
                        if getattr(p, f, None) is not None:
                            filled.append(f)
                    asin_coverage[asin] = filled

                    # ★ 产品预取：关键字段的实际数值
                    preview = {}
                    for f in ("title", "brand", "current_price", "buybox_price",
                              "avg_price_30d", "avg_price_90d", "list_price",
                              "rating", "review_count", "current_bsr",
                              "avg_bsr_30d", "avg_bsr_90d", "monthly_sold",
                              "weekly_sold", "annual_sold", "feature_bullets_count",
                              "seller_count", "offer_count_fba", "offer_count_fbm",
                              "is_fba", "is_prime", "has_amazon_selling",
                              "has_coupon", "main_image", "images_count",
                              "fulfillment_type", "availability", "stock_level",
                              "fba_fee", "referral_fee_percent",
                              "color", "size", "style", "material",
                              "brand_store_name", "parent_asin",
                              "out_of_stock_pct_30d"):
                        val = getattr(p, f, None)
                        if val is not None:
                            preview[f] = val
                    product_preview[asin] = preview
                else:
                    missing_asins.append(asin)

        # 3. 品类跨列探索
        exploration = None
        matched_category = []
        matched_type = []
        category_hint = spec.category_hint.strip() if spec.category_hint else ""

        if category_hint:
            async with AsyncSessionLocal() as db:
                repo = AmazonProductRepository(db)
                exploration = await repo.explore(category_hint, domain=domain)

            if exploration:
                # 提取品类名和产品类型
                matched_category = list(exploration.get("categories_found", {}).keys())
                matched_type = list(exploration.get("product_types_found", {}).keys())

        # 4. 没有 hint 也没有 ASIN → 返回数据库全景
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
            asin_product_count=len(found_asins),
            asin_fields_coverage=asin_coverage,
            category_hint=category_hint,
            exploration=exploration,
            matched_category_names=matched_category,
            matched_product_types=matched_type,
            catalog=catalog,
            can_collect_asins=can_collect,
            product_preview=product_preview,
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

            # 跨列探索
            exploration = await repo.explore(hint, domain=domain, limit=limit)

        lines = [f"[DataLiaison] 数据探索报告（{domain}）:"]
        if discovered_asins:
            lines.append(f"  指定 ASIN 命中: {len(asin_data)}/{len(discovered_asins)}")
            for asin, info in asin_data.items():
                lines.append(f"    {asin}: {info.get('title', '?')[:50]}")

        total = exploration.get("total_distinct_asins", 0)
        lines.append(f"  品类探索找到: {total} 个商品")

        strategies = exploration.get("strategies_attempted", [])
        active = [s for s in strategies if s.get("matched", 0) > 0]
        if active:
            lines.append(f"  搜索路径命中:")
            for s in active:
                lines.append(f"    - {s['column']}({s['strategy']}): {s['matched']}条")

        categories = exploration.get("categories_found", {})
        if categories:
            lines.append(f"  品类: {', '.join(list(categories.keys())[:5])}")

        brands = exploration.get("brands_found", {})
        if brands:
            lines.append(f"  品牌: {', '.join(list(brands.keys())[:8])}")

        return "\n".join(lines)