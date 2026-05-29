"""
商品采集 Agent - Amazon 监控场景（Aqueduct 改造版）

职责（缩减）：
1. 接收扩展后的关键词列表或直接 ASIN 列表
2. 通过 Canopy /search 发现 ASIN（优先，成本低），Rainforest /search 备用
3. 将发现的/传入的 ASIN 通过 DataProvider 读取（不走直接 API）
4. DataProvider 自动处理冷启动 → 采集 → 返回

数据源：
  搜索：Canopy /search > Rainforest /search（走连接器，搜索不计入覆盖度）
  数据：DataProvider → amazon_products 表（不走直接 API 采集）
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.common.core.agent import Agent
from backend.common.core.state import State
from backend.utils.logger import logger
from backend.aqueduct.data_provider import DataProvider

# ── 默认搜索范围 ──

DEFAULT_SEARCH_SCOPE = {
    "canopy_search": True,      # Canopy /search 优先
    "rainforest_search": True,  # Rainforest /search 备用
}

# Keepa domain → Rainforest domain 映射
_KEEPA_TO_RAINFOREST_DOMAIN = {
    "US": "amazon.com", "GB": "amazon.co.uk", "DE": "amazon.de",
    "FR": "amazon.fr", "JP": "amazon.co.jp", "CA": "amazon.ca",
    "IT": "amazon.it", "ES": "amazon.es", "IN": "amazon.in",
    "MX": "amazon.com.mx", "BR": "amazon.com.br", "AU": "amazon.com.au",
    "NL": "amazon.nl", "SG": "amazon.sg", "AE": "amazon.ae",
    "SA": "amazon.sa", "TR": "amazon.com.tr", "SE": "amazon.se",
    "PL": "amazon.pl",
}


def _keepa_domain_to_rainforest(keepa_domain: str) -> str:
    """将 Keepa 的短域名（US/DE/JP）转成 Rainforest 的全域名"""
    return _KEEPA_TO_RAINFOREST_DOMAIN.get(keepa_domain.upper(), "amazon.com")


def _set_error(
    state: State,
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    state.set("error", message)
    state.set("error_type", error_type)
    state.set("error_details", details or {})
    state.set("collected_products", [])
    state.set("product_map", {})
    state.set("collection_stats", {
        "total": 0,
        "error": message,
        "error_type": error_type,
    })
    state.add_event(f"product_collector_error[{error_type}]: {message}")


class ProductCollectorAgent(Agent):
    """
    商品采集 Agent（Aqueduct 版）

    搜索 + 读表模式：
    - ASIN 搜索用 Canopy/Rainforest /search
    - 商品数据走 DataProvider → amazon_products 表
    - 不再直接调 Keepa/Rainforest/Canopy 产品的 API
    """

    name = "product_collector"
    description = "Amazon 商品采集 Agent，搜索 ASIN + 从 DataProvider 读取数据"

    async def run(self, state: State) -> State:
        state.add_event("product_collector_start")
        logger.info("[ProductCollector] Starting (search + DataProvider mode)")
        return await self._async_run(state)

    async def _async_run(self, state: State) -> State:
        try:
            watchlist_asins: List[str] = state.get("watchlist_asins", []) or []
            keywords: List[str] = state.get("expanded_keywords", []) or []
            allow_keyword_search: bool = bool(state.get("allow_keyword_search", True))
            domain: str = state.get("domain", "US")

            provider = DataProvider()
            all_asins = []

            # ── 模式 A: 直接 ASIN 列表 ──
            if watchlist_asins:
                all_asins = [a.strip() for a in watchlist_asins if a and a.strip()]
                asin_source = "watchlist"
                logger.info(f"[ProductCollector] Mode A: {len(all_asins)} watchlist ASINs")

            # ── 模式 B: 关键词搜索 → Canopy 优先, Rainforest 备用 ──
            elif allow_keyword_search and keywords:
                all_asins, asin_source = await self._search_asins(keywords, domain)
                if not all_asins:
                    _set_error(
                        state, "no_search_results",
                        f"关键词搜索无结果，请检查关键词或 API 状态",
                    )
                    return state
            else:
                _set_error(
                    state, "no_input",
                    "ProductCollector 需要输入 watchlist_asins 或 expanded_keywords",
                )
                return state

            # ── 通过 DataProvider 读取商品数据 ──
            product_map = {}
            products_list = []
            for asin in all_asins:
                product = await provider.get_product(asin, domain)
                if product:
                    product_map[asin] = product
                    products_list.append(product)

            # BSR 排序
            products_list.sort(key=lambda p: p.get("current_bsr") or 999999)

            collection_stats = {
                "total": len(products_list),
                "unique_asins": len(all_asins),
                "asin_source": asin_source,
                "collected_at": datetime.now().isoformat(),
            }

            state.set("collected_products", products_list)
            state.set("product_map", product_map)
            state.set("collection_stats", collection_stats)
            state.set_meta("products_collected", len(products_list))

            logger.info(
                f"[ProductCollector] Done: {len(products_list)} products "
                f"(source={asin_source}, total_asins={len(all_asins)})"
            )
            state.add_event(f"product_collector_success: {len(products_list)} products from {asin_source}")
            return state

        except Exception as e:
            logger.error(f"[ProductCollector] Unexpected: {e}")
            _set_error(state, "unexpected", str(e))
            return state

    async def _search_asins(self, keywords: List[str], domain: str) -> (List[str], str):
        """搜索关键词发现 ASIN — Canopy 优先, Rainforest 备用"""
        canopy = self._get_canopy()
        if canopy:
            logger.info(f"[ProductCollector] Search via Canopy: {keywords}")
            try:
                result = await self._search_asins_by_canopy(canopy, keywords, domain)
                if result.get("all_asins"):
                    return result["all_asins"], "canopy_search"
            except Exception as e:
                logger.warning(f"[ProductCollector] Canopy search failed: {e}")

        rainforest = self._get_rainforest()
        if rainforest:
            logger.info(f"[ProductCollector] Fallback search via Rainforest: {keywords}")
            try:
                rf_domain = _keepa_domain_to_rainforest(domain)
                result = await self._search_asins_by_rainforest(rainforest, keywords, rf_domain)
                if result.get("all_asins"):
                    return result["all_asins"], "rainforest_search"
            except Exception as e:
                logger.warning(f"[ProductCollector] Rainforest search failed: {e}")

        return [], "none"

    async def _search_asins_by_rainforest(
        self, rainforest, keywords: List[str], domain: str,
    ) -> Dict[str, Any]:
        """Rainforest /search 搜索"""
        from backend.config.config import settings
        max_kw = getattr(settings, 'RAINFOREST_SEARCH_MAX_KEYWORDS', 5)
        max_results = getattr(settings, 'RAINFOREST_SEARCH_MAX_RESULTS', 20)

        keywords = keywords[:max_kw]
        all_asins: List[str] = []
        keyword_results = []

        for kw in keywords:
            logger.info(f"[ProductCollector] Rainforest search: '{kw}'")
            try:
                result = await rainforest.async_search(kw, domain, max_results)
                keyword_results.append({"keyword": kw, **result})
                for asin in result.get("asins", []):
                    if asin not in all_asins:
                        all_asins.append(asin)
                logger.info(f"[ProductCollector] '{kw}' → {len(result.get('asins', []))} ASINs")
            except Exception as e:
                logger.warning(f"[ProductCollector] RF search '{kw}' failed: {e}")
                keyword_results.append({"keyword": kw, "total_results": 0, "asins": [], "_error": str(e)})

        return {"all_asins": all_asins, "keyword_results": keyword_results}

    async def _search_asins_by_canopy(
        self, canopy, keywords: List[str], domain: str,
    ) -> Dict[str, Any]:
        """Canopy /search 搜索"""
        from backend.config.config import settings
        max_kw = getattr(settings, 'CANOPY_SEARCH_MAX_KEYWORDS', 5)
        max_results = getattr(settings, 'CANOPY_SEARCH_MAX_RESULTS', 20)

        keywords = keywords[:max_kw]
        all_asins: List[str] = []
        keyword_results = []

        for kw in keywords:
            logger.info(f"[ProductCollector] Canopy search: '{kw}'")
            try:
                result = await canopy.async_search(kw, domain, max_results)
                keyword_results.append({"keyword": kw, **result})
                for asin in result.get("asins", []):
                    if asin not in all_asins:
                        all_asins.append(asin)
                logger.info(f"[ProductCollector] Canopy '{kw}' → {len(result.get('asins', []))} ASINs")
            except Exception as e:
                logger.warning(f"[ProductCollector] Canopy search '{kw}' failed: {e}")
                keyword_results.append({"keyword": kw, "total_results": 0, "asins": [], "_error": str(e)})

        return {"all_asins": all_asins, "keyword_results": keyword_results}

    # ── 连接器工厂（仅用于搜索，不用于采集） ──────────────────────────

    def _get_rainforest(self):
        try:
            from backend.aqueduct.connectors.rainforest_connector import RainforestConnector
            return RainforestConnector()
        except Exception as e:
            logger.warning(f"[ProductCollector] Rainforest not available: {e}")
            return None

    def _get_canopy(self):
        try:
            from backend.aqueduct.connectors.canopy_connector import CanopyConnector
            return CanopyConnector()
        except Exception as e:
            logger.warning(f"[ProductCollector] Canopy not available: {e}")
            return None