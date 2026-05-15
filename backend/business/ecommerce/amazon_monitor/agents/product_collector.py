"""
商品采集 Agent - Amazon 监控场景
对应文章第2步：商品数据采集

职责：
1. 接收扩展后的关键词列表
2. 通过 Keepa 搜索 ASIN 并获取历史数据（BSR历史、价格历史、销量估算）
3. 去重、过滤、整理商品数据
4. 输出结构化商品列表（含历史趋势数据）

数据源：
  Keepa（唯一数据源）→ 历史BSR、价格历史、销量估算、趋势分析
"""

import asyncio
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.common.core.agent import Agent
from backend.common.core.state import State
from backend.utils.logger import logger

# 无效修饰词列表（这些词加在关键词后面 Keepa 搜不到结果）
_INVALID_SUFFIXES = {
    "review", "reviews", "buy", "cheap", "affordable", "best",
    "top", "good", "great", "cheap", "discount", "sale",
}


def _filter_keywords(keywords: List[str]) -> List[str]:
    """
    过滤掉含无效修饰词的关键词，保留核心搜索词
    例如：'bluetooth earbuds review' → 过滤掉
          'bluetooth earbuds' → 保留
    """
    filtered = []
    seen = set()
    for kw in keywords:
        words = kw.lower().split()
        # 如果最后一个词是无效修饰词，跳过
        if words and words[-1] in _INVALID_SUFFIXES:
            continue
        # 如果第一个词重复（如 'bluetooth bluetooth earbuds'），跳过
        if len(words) >= 2 and words[0] == words[1]:
            continue
        # 去重
        if kw not in seen:
            seen.add(kw)
            filtered.append(kw)
    return filtered


class ProductCollectorAgent(Agent):
    """
    商品采集 Agent
    纯 Keepa 模式：关键词搜索 ASIN + 批量查询历史数据
    """

    name = "product_collector"
    description = "Amazon 商品采集 Agent，基于 Keepa 历史数据"

    async def run(self, state: State) -> State:
        """
        执行商品采集

        输入（从 state 读取）：
          - expanded_keywords: List[str] 扩展后的关键词
          - max_results_per_keyword: int 每个关键词最大结果数（默认10）
          - domain: str 市场（默认 US）

        输出（写入 state）：
          - collected_products: List[dict] 采集到的商品列表（含历史数据）
          - product_map: Dict[str, dict] ASIN → 商品详情映射
          - collection_stats: dict 采集统计信息
        """
        state.add_event("product_collector_start")
        logger.info("[ProductCollector] Starting product collection (Keepa only)")
        return await self._async_run(state)

    async def _async_run(self, state: State) -> State:
        """异步执行商品采集"""
        try:
            # 读取输入参数
            keywords: List[str] = state.get("expanded_keywords", [])
            max_results: int = state.get("max_results_per_keyword", 10)
            domain: str = state.get("domain", "US")

            if not keywords:
                logger.warning("[ProductCollector] No keywords provided")
                state.set("collected_products", [])
                state.set("product_map", {})
                state.set("collection_stats", {"total": 0, "keywords_searched": 0})
                state.add_event("product_collector_no_keywords")
                return state

            # 过滤无效关键词，最多取5个（节省 Keepa Token）
            filtered_keywords = _filter_keywords(keywords)[:5]
            logger.info(
                f"[ProductCollector] Filtered {len(keywords)} → {len(filtered_keywords)} keywords: "
                f"{filtered_keywords}"
            )

            # ── Step 1: Keepa 关键词搜索，串行执行（避免 429）──
            all_asins: List[str] = []
            keyword_asin_map: Dict[str, List[str]] = {}
            failed_keywords: List[str] = []

            keepa = self._get_keepa()
            if keepa:
                for kw in filtered_keywords:
                    try:
                        asins = await keepa.async_search_asins(
                            kw, domain=domain, max_results=max_results
                        )
                        keyword_asin_map[kw] = asins
                        for a in asins:
                            if a not in all_asins:
                                all_asins.append(a)
                        logger.info(f"[ProductCollector] Keepa '{kw}': {len(asins)} ASINs")
                        # 串行间隔 1.5 秒，避免 429
                        await asyncio.sleep(1.5)
                    except Exception as e:
                        logger.error(f"[ProductCollector] Keepa search '{kw}' failed: {e}")
                        failed_keywords.append(kw)
                        keyword_asin_map[kw] = []
            else:
                logger.warning("[ProductCollector] Keepa not configured, no data source available")

            # ── Step 2: Keepa 批量查询历史数据 ──
            keepa_products: Dict[str, Dict] = {}
            if keepa and all_asins:
                logger.info(f"[ProductCollector] Keepa querying {len(all_asins)} ASINs history")
                for i in range(0, len(all_asins), 100):
                    batch = all_asins[i:i + 100]
                    products = await keepa.async_query_products(batch, domain=domain, stats=180)
                    for p in products:
                        keepa_products[p["asin"]] = p
                logger.info(f"[ProductCollector] Keepa returned {len(keepa_products)} products with history")

            # ── Step 3: 整理商品列表 ──
            products_list = []
            product_map = {}

            for asin in all_asins:
                product = keepa_products.get(asin)
                if product:
                    product["collected_at"] = datetime.now().isoformat()
                    products_list.append(product)
                    product_map[asin] = product

            # 按 BSR 排序（BSR 越小越好）
            products_list.sort(
                key=lambda p: p.get("current_bsr") or 999999
            )

            # 统计信息
            collection_stats = {
                "total": len(products_list),
                "unique_asins": len(all_asins),
                "keywords_searched": len(filtered_keywords),
                "keywords_failed": len(failed_keywords),
                "failed_keywords": failed_keywords,
                "keepa_products": len(keepa_products),
                "keyword_asin_map": {k: len(v) for k, v in keyword_asin_map.items()},
                "collected_at": datetime.now().isoformat(),
                "data_sources": ["keepa"],
            }

            state.set("collected_products", products_list)
            state.set("product_map", product_map)
            state.set("collection_stats", collection_stats)
            state.set_meta("products_collected", len(products_list))

            logger.info(
                f"[ProductCollector] Collected {len(products_list)} products "
                f"(Keepa: {len(keepa_products)})"
            )
            state.add_event(f"product_collector_success: {len(products_list)} products")

        except Exception as e:
            logger.error(f"[ProductCollector] Error: {e}")
            state.set("error", str(e))
            state.set("collected_products", [])
            state.set("product_map", {})
            state.set("collection_stats", {"total": 0, "error": str(e)})
            state.add_event(f"product_collector_error: {e}")

        return state

    # ── 内部辅助方法 ──

    def _get_keepa(self):
        """获取 Keepa 连接器（如果未配置则返回 None）"""
        try:
            from backend.business.ecommerce.amazon_monitor.tools.keepa_connector import KeepaConnector
            return KeepaConnector()
        except ValueError as e:
            logger.warning(f"[ProductCollector] Keepa not configured: {e}")
            return None
        except Exception as e:
            logger.warning(f"[ProductCollector] Keepa init failed: {e}")
            return None
