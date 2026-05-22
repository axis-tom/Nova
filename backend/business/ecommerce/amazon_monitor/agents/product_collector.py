"""
商品采集 Agent - Amazon 监控场景
对应文章第2步：商品数据采集

职责：
1. 接收扩展后的关键词列表或直接 ASIN 列表
2. 通过 Canopy /search 发现 ASIN（优先，成本低），Rainforest /search 备用
3. L1 采集：Keepa（历史趋势）+ Rainforest（listing+广告+评分）+ Canopy（listing补全）
4. L2 补单：pending_data_requests 队列，补充更多评论页/排名/榜单
5. 三源数据合并、去重、整理
6. 输出结构化商品列表

数据源：
  Keepa — 历史 BSR/价格/销量 CSV 趋势
  Rainforest — listing 详情 + 广告 + 评分分布
  Canopy — ASIN 发现 + listing 补全
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.common.core.agent import Agent
from backend.common.core.state import State
from backend.utils.logger import logger
from backend.business.ecommerce.amazon_monitor.tools.keepa_connector import (
    KeepaError,
    KeepaConfigError,
    KeepaQuotaError,
    KeepaRejectedError,
    KeepaNetworkError,
)
from backend.business.ecommerce.amazon_monitor.tools.rainforest_connector import (
    RainforestError,
    RainforestConfigError,
    RainforestQuotaError,
    RainforestNetworkError,
)
from backend.business.ecommerce.amazon_monitor.tools.canopy_connector import (
    CanopyError,
    CanopyConfigError,
    CanopyQuotaError,
    CanopyNetworkError,
)

# ── 默认 L1 采集范围 ──

DEFAULT_COLLECTION_SCOPE = {
    "keepa": "full",
    "rainforest": {
        "product": True,
        "reviews_first_page": False,  # 503 暂停
    },
    "canopy": {
        "product": True,
    },
}

# Keepa domain → Rainforest domain 映射
_KEEPA_TO_RAINFOREST_DOMAIN = {
    "US": "amazon.com",
    "GB": "amazon.co.uk",
    "DE": "amazon.de",
    "FR": "amazon.fr",
    "JP": "amazon.co.jp",
    "CA": "amazon.ca",
    "IT": "amazon.it",
    "ES": "amazon.es",
    "IN": "amazon.in",
    "MX": "amazon.com.mx",
    "BR": "amazon.com.br",
    "AU": "amazon.com.au",
    "NL": "amazon.nl",
    "SG": "amazon.sg",
    "AE": "amazon.ae",
    "SA": "amazon.sa",
    "TR": "amazon.com.tr",
    "SE": "amazon.se",
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
    """把错误统一写到 state，供 agent_wrapper 暴露给 LLM"""
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


def _append_collection_error(state: State, asin: str, source: str, endpoint: str, error: str) -> None:
    """追加单条采集错误，不影响其他 ASIN"""
    errors = state.get("collection_errors") or []
    errors.append({
        "asin": asin,
        "source": source,
        "endpoint": endpoint,
        "error": error,
    })
    state.set("collection_errors", errors)


def _merge_product(
    keepa_data: Optional[Dict[str, Any]],
    rf_product: Optional[Dict[str, Any]],
    rf_reviews: Optional[Dict[str, Any]],
    canopy_product: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    合并 Keepa + Rainforest + Canopy 三源数据为单一产品 dict。

    优先级：
    - 基础标识: Keepa > Canopy > Rainforest
    - Listing 内容(五点/描述/A+): Rainforest > Canopy > Keepa
    - 规格/变体: Rainforest > Canopy > Keepa
    - 价格/BSR/销量: Keepa 独占（有历史和趋势）
    - 评分分布: Rainforest 独占（rating_breakdown 五星）
    - 广告/sponsor: Rainforest 独占
    - 历史 CSV: Keepa 独占
    """
    k = keepa_data or {}
    r = rf_product or {}
    rv = rf_reviews or {}
    c = canopy_product or {}

    # ── 基础标识 ──
    asin = k.get("asin") or c.get("asin") or r.get("asin", "")
    title = k.get("title") or c.get("title") or r.get("title", "")
    brand = k.get("brand") or c.get("brand") or r.get("brand", "")
    manufacturer = r.get("manufacturer") or c.get("manufacturer") or k.get("manufacturer", "")
    model = k.get("model") or c.get("model_number") or r.get("model_number", "")
    part_number = k.get("part_number") or c.get("part_number") or r.get("part_number", "")
    upc = r.get("upc") or c.get("upc") or k.get("upc", "")
    ean = r.get("ean") or c.get("ean") or k.get("ean", "")
    color = r.get("color") or c.get("color") or k.get("color", "")
    size = r.get("size") or c.get("size") or k.get("size", "")
    weight = k.get("weight") or c.get("weight") or r.get("item_weight", "")
    dimensions = r.get("dimensions") or c.get("dimensions") or ""
    package_quantity = k.get("package_quantity") or r.get("package_quantity")
    product_group = k.get("product_group") or r.get("product_group", "")
    binding = k.get("binding") or r.get("binding", "")
    style = r.get("style") or c.get("color", "")
    material_type = r.get("material") or ""
    country_of_origin = r.get("country_of_origin", "")

    # ── Listing 内容（Rainforest > Canopy > Keepa）──
    feature_bullets = r.get("feature_bullets") or c.get("feature_bullets") or k.get("features") or []
    description = r.get("description") or c.get("description") or k.get("description", "")
    aplus = r.get("aplus_content")
    main_image = r.get("main_image") or c.get("main_image") or ""
    images = r.get("images") or c.get("images") or []
    if not images and k.get("images_csv"):
        images = [u.strip() for u in str(k["images_csv"]).split(",") if u.strip()]
    videos_count = r.get("videos_count", 0)
    specifications = r.get("specifications") or c.get("specifications") or {}

    # ── 价格 ──
    current_price = k.get("current_price") or r.get("current_price")
    list_price = r.get("list_price")
    buybox_price = k.get("buybox_price")
    avg_price_30d = k.get("avg_price_30d")
    avg_price_90d = k.get("avg_price_90d")
    min_price_90d = k.get("min_price_90d")
    max_price_90d = k.get("max_price_90d")
    is_prime = r.get("is_prime", False)
    fulfillment = r.get("fulfillment", "")
    availability = r.get("availability", "")

    # ── BSR ──
    current_bsr = k.get("current_bsr") or r.get("bsr_rank") or c.get("bsr_rank")
    avg_bsr_30d = k.get("avg_bsr_30d")
    avg_bsr_90d = k.get("avg_bsr_90d")
    bsr_trend = k.get("bsr_trend", "unknown")
    category_ranks = k.get("category_ranks")
    bsr_category = r.get("bsr_category") or c.get("bsr_category", "")

    # ── 销量 ──
    monthly_sold = k.get("monthly_sold", 0)
    out_of_stock_pct = k.get("out_of_stock_pct")
    recent_sales = r.get("recent_sales", "")

    # ── 评分 ──
    rating = k.get("rating") or r.get("rating") or c.get("rating")
    review_count = k.get("review_count") or r.get("ratings_total") or c.get("ratings_total", 0)
    rating_breakdown = r.get("rating_breakdown") or {}

    # ── 评论内容 ──
    reviews = rv.get("reviews") or r.get("top_reviews") or c.get("top_reviews") or []
    reviews_total = rv.get("total_reviews") or r.get("ratings_total") or c.get("ratings_total", 0)
    reviews_page_count = 1 if (rv.get("reviews") or r.get("top_reviews") or c.get("top_reviews")) else 0

    # ── 变体（Rainforest > Canopy > Keepa）──
    parent_asin = k.get("parent_asin") or r.get("parent_asin") or c.get("parent_asin", "")
    child_asins = r.get("child_asins") or c.get("child_asins") or []
    variations = r.get("variations") or c.get("variations") or []
    variation_dimensions = r.get("variation_dimensions") or []

    # ── 卖家/竞争 ──
    seller_count = k.get("seller_count", 0)
    buybox_seller = c.get("seller_name") or ""
    buybox_is_fba = k.get("buybox_is_fba")
    stock_level = r.get("stock_level") or ""
    max_order_qty = r.get("max_order_quantity")
    is_prime = c.get("is_prime") or r.get("is_prime", False)
    availability = r.get("availability", "")
    is_in_stock = c.get("is_in_stock")

    # ── 类目（Rainforest > Canopy > Keepa）──
    category_id = k.get("category_id")
    category_name = r.get("category_name") or c.get("category_name", "")
    category_tree = r.get("category_tree") or c.get("category_tree") or k.get("category_tree") or []
    breadcrumbs = r.get("breadcrumbs") or []

    # ── 广告 ──
    sponsored_products = r.get("sponsored_products") or []

    # ── 价格 ──
    current_price = k.get("current_price") or r.get("current_price") or c.get("current_price")
    list_price = r.get("list_price")
    buybox_price = k.get("buybox_price")
    avg_price_30d = k.get("avg_price_30d")
    avg_price_90d = k.get("avg_price_90d")
    min_price_90d = k.get("min_price_90d")
    max_price_90d = k.get("max_price_90d")
    fulfillment = r.get("fulfillment", "")

    # ── 历史时间序列 ──
    price_history = k.get("price_history") or []
    bsr_history = k.get("bsr_history") or []

    return {
        # 标识
        "asin": asin,
        "data_sources": [
            s for s, src in [("keepa", keepa_data), ("rainforest", rf_product), ("canopy", canopy_product)]
            if src
        ],

        # 基础信息
        "title": title,
        "brand": brand,
        "manufacturer": manufacturer,
        "model": model,
        "part_number": part_number,
        "upc": upc,
        "ean": ean,
        "color": color,
        "size": size,
        "style": style,
        "material": material_type,
        "weight": weight,
        "dimensions": dimensions,
        "package_quantity": package_quantity,
        "product_group": product_group,
        "binding": binding,
        "country_of_origin": country_of_origin,

        # Listing 内容
        "feature_bullets": feature_bullets,
        "description": description,
        "aplus_content": aplus,
        "main_image": main_image,
        "images": images,
        "videos_count": videos_count,
        "specifications": specifications,

        # 价格
        "current_price": current_price,
        "list_price": list_price,
        "buybox_price": buybox_price,
        "avg_price_30d": avg_price_30d,
        "avg_price_90d": avg_price_90d,
        "min_price_90d": min_price_90d,
        "max_price_90d": max_price_90d,
        "is_prime": is_prime,
        "is_in_stock": is_in_stock,
        "fulfillment": fulfillment,
        "availability": availability,

        # BSR
        "current_bsr": current_bsr,
        "avg_bsr_30d": avg_bsr_30d,
        "avg_bsr_90d": avg_bsr_90d,
        "bsr_trend": bsr_trend,
        "bsr_category": bsr_category,

        # 销量
        "monthly_sold": monthly_sold,
        "out_of_stock_pct": out_of_stock_pct,
        "recent_sales": recent_sales,

        # 评分
        "rating": rating,
        "review_count": review_count,
        "rating_breakdown": rating_breakdown,

        # 评论内容
        "reviews": reviews,
        "reviews_total": reviews_total,
        "reviews_page_count": reviews_page_count,

        # 变体
        "parent_asin": parent_asin,
        "child_asins": child_asins,
        "variations": variations,
        "variation_dimensions": variation_dimensions,

        # 竞争
        "seller_count": seller_count,
        "buybox_seller": buybox_seller,
        "buybox_is_fba": buybox_is_fba,
        "stock_level": stock_level,
        "max_order_quantity": max_order_qty,

        # 类目
        "category_id": category_id,
        "category_name": category_name,
        "category_tree": category_tree,
        "breadcrumbs": breadcrumbs,

        # 广告
        "sponsored_products": sponsored_products,

        # 历史
        "price_history": price_history,
        "bsr_history": bsr_history,

        # 元数据
        "collected_at": datetime.now().isoformat(),
    }


class ProductCollectorAgent(Agent):
    """
    商品采集 Agent
    三数据源模式：Keepa（历史趋势）+ Rainforest（listing + 广告 + 评分分布）+ Canopy（搜索 + listing 补全）
    """

    name = "product_collector"
    description = "Amazon 商品采集 Agent，基于 Keepa + Rainforest + Canopy 三数据源"

    async def run(self, state: State) -> State:
        """
        执行商品采集

        输入（从 state 读取）：
          - watchlist_asins: List[str]  推荐：直接传 ASIN 列表
          - expanded_keywords: List[str]  关键词列表 → Canopy/Rainforest /search 发现 ASIN
          - allow_keyword_search: bool  显式允许走搜索路径，默认 True
          - domain: str  市场（默认 US）
          - collection_scope: dict  L1/L2 行为控制（不传用默认值）
          - pending_data_requests: List[dict]  L2 补单队列

        输出（写入 state）：
          - collected_products: List[dict]  采集到的商品列表（三源合并）
          - product_map: Dict[str, dict]  ASIN → 商品详情
          - collection_stats: dict  采集统计
          - collection_errors: List[dict]  单 ASIN 错误日志
          - error / error_type / error_details: 整体失败时填充
        """
        state.add_event("product_collector_start")
        logger.info("[ProductCollector] Starting (Keepa + Rainforest + Canopy three-source)")
        return await self._async_run(state)

    async def _async_run(self, state: State) -> State:
        """异步执行商品采集"""
        try:
            # ── 读取输入 ──
            watchlist_asins: List[str] = state.get("watchlist_asins", []) or []
            keywords: List[str] = state.get("expanded_keywords", []) or []
            allow_keyword_search: bool = bool(
                state.get("allow_keyword_search", True)
            )
            domain: str = state.get("domain", "US")
            scope: Dict = state.get("collection_scope") or DEFAULT_COLLECTION_SCOPE
            pending: List[Dict] = state.get("pending_data_requests") or []

            # ── 初始化连接器 ──
            keepa = self._get_keepa()
            rainforest = self._get_rainforest()
            canopy = self._get_canopy()

            if not keepa and not rainforest and not canopy:
                _set_error(
                    state, "config",
                    "Keepa、Rainforest、Canopy 均未配置。请在 backend/config/.env 中设置至少一个 API Key",
                )
                return state

            # ── 路由：L2 补单优先 → L1 发现 → 错误 ──

            if pending:
                logger.info(f"[ProductCollector] L2 mode: {len(pending)} pending requests")
                return await self._collect_l2(state, pending, domain, keepa, rainforest)

            if watchlist_asins:
                # 模式 A: 直接 ASIN — L1 收集
                all_asins = [a.strip() for a in watchlist_asins if a and a.strip()]
                asin_source = "watchlist"
                logger.info(f"[ProductCollector] Mode A: {len(all_asins)} watchlist ASINs")

            elif allow_keyword_search and keywords:
                # 模式 B: 关键词搜索 → Canopy 优先, Rainforest 备用
                asin_source = ""
                all_asins = []

                if canopy:
                    logger.info(f"[ProductCollector] Mode B: {len(keywords)} keywords → Canopy search")
                    search_results = await self._search_asins_by_canopy(
                        canopy, keywords, domain,
                    )
                    all_asins = search_results["all_asins"]
                    asin_source = "canopy_search"
                    state.set("search_results", search_results)

                if not all_asins and rainforest:
                    logger.info(f"[ProductCollector] Canopy search returned empty, falling back to Rainforest")
                    search_results = await self._search_asins_by_rainforest(
                        rainforest, keywords, domain,
                    )
                    all_asins = search_results["all_asins"]
                    asin_source = "rainforest_search"
                    state.set("search_results", search_results)

                if not all_asins:
                    _set_error(
                        state, "no_search_source",
                        "关键词搜索需要 Canopy 或 Rainforest API。"
                        "请在 backend/config/.env 中配置 CANOPY_API_KEY 或 RAINFOREST_API_KEY。",
                    )
                    return state

            else:
                _set_error(
                    state, "no_input",
                    "ProductCollector 需要输入：\n"
                    "  - watchlist_asins=['B0XXX', ...] 直接查指定商品\n"
                    "  - expanded_keywords=['...'] 通过 Canopy/Rainforest 搜索发现 ASIN\n"
                    "  - pending_data_requests=[...] L2 补单",
                )
                return state

            if not all_asins:
                _set_error(state, "no_asins", "未找到任何 ASIN，请检查输入")
                return state

            # ── L1 收集 ──
            return await self._collect_l1(state, all_asins, asin_source, domain, scope, keepa, rainforest, canopy)

        except KeepaConfigError as e:
            logger.warning(f"[ProductCollector] Keepa config: {e}")
            _set_error(state, "keepa_config", str(e))
        except KeepaQuotaError as e:
            logger.warning(f"[ProductCollector] Keepa quota: {e}")
            _set_error(state, "keepa_quota", str(e), {"retry_after_minutes": e.retry_after_minutes})
        except RainforestConfigError as e:
            logger.warning(f"[ProductCollector] Rainforest config: {e}")
            _set_error(state, "rainforest_config", str(e))
        except RainforestQuotaError as e:
            logger.warning(f"[ProductCollector] Rainforest quota: {e}")
            _set_error(state, "rainforest_quota", str(e))
        except CanopyConfigError as e:
            logger.warning(f"[ProductCollector] Canopy config: {e}")
            _set_error(state, "canopy_config", str(e))
        except CanopyQuotaError as e:
            logger.warning(f"[ProductCollector] Canopy quota: {e}")
            _set_error(state, "canopy_quota", str(e))
        except (KeepaError, RainforestError, CanopyError) as e:
            logger.error(f"[ProductCollector] API error: {type(e).__name__}: {e}")
            _set_error(state, "api_error", str(e))
        except Exception as e:
            logger.error(f"[ProductCollector] Unexpected: {e}")
            _set_error(state, "unexpected", str(e))

        return state

    # ── L1 核心收集 ──────────────────────────────────────────────────

    async def _collect_l1(
        self,
        state: State,
        all_asins: List[str],
        asin_source: str,
        domain: str,
        scope: Dict,
        keepa,
        rainforest,
        canopy,
    ) -> State:
        """
        L1 收集：对每个 ASIN 并发获取
          Keepa（历史趋势）
          + Rainforest product（listing + 广告 + 评分分布）
          + Canopy product（listing 补全）
        单 ASIN 失败不阻塞整体。
        """
        rf_domain = _keepa_domain_to_rainforest(domain)
        rf_scope = scope.get("rainforest", {})
        canopy_scope = scope.get("canopy", {})
        do_rf_product = rf_scope.get("product", True) and rainforest is not None
        do_rf_reviews = rf_scope.get("reviews_first_page", False) and rainforest is not None  # 503 暂停
        do_canopy_product = canopy_scope.get("product", True) and canopy is not None

        logger.info(
            f"[ProductCollector] L1 collecting {len(all_asins)} ASINs "
            f"(Keepa={'yes' if keepa else 'no'}, "
            f"Rainforest_product={do_rf_product}, Rainforest_reviews={do_rf_reviews}, "
            f"Canopy_product={do_canopy_product})"
        )

        # 1. Keepa 批量查询（一次调 /product 覆盖所有 ASIN）
        keepa_products: Dict[str, Dict] = {}
        if keepa and all_asins:
            try:
                for i in range(0, len(all_asins), 100):
                    batch = all_asins[i:i + 100]
                    products = await keepa.async_query_products(batch, domain=domain, stats=180)
                    for p in products:
                        keepa_products[p["asin"]] = p
                logger.info(f"[ProductCollector] Keepa: {len(keepa_products)}/{len(all_asins)}")
            except KeepaError as e:
                logger.warning(f"[ProductCollector] Keepa L1 failed: {e}")
                _append_collection_error(state, "batch", "keepa", "/product", str(e))

        # 2. Rainforest product + reviews（逐 ASIN）
        rf_products: Dict[str, Optional[Dict]] = {}
        rf_reviews_data: Dict[str, Optional[Dict]] = {}

        async def _fetch_rf(asin: str):
            if do_rf_product:
                try:
                    rf_products[asin] = await rainforest.async_get_product(asin, rf_domain)
                except RainforestError as e:
                    logger.warning(f"[ProductCollector] RF product {asin}: {e}")
                    _append_collection_error(state, asin, "rainforest", "/product", str(e))
                    rf_products[asin] = None

            if do_rf_reviews:
                try:
                    rf_reviews_data[asin] = await rainforest.async_get_reviews(
                        asin, rf_domain, page=1, max_page=1, sort_by="most_recent",
                    )
                except RainforestError as e:
                    logger.warning(f"[ProductCollector] RF reviews {asin}: {e}")
                    _append_collection_error(state, asin, "rainforest", "/reviews", str(e))
                    rf_reviews_data[asin] = None

        # 3. Canopy product（逐 ASIN）
        canopy_products: Dict[str, Optional[Dict]] = {}

        async def _fetch_canopy(asin: str):
            if do_canopy_product:
                try:
                    canopy_products[asin] = await canopy.async_get_product(asin, domain)
                except CanopyError as e:
                    logger.warning(f"[ProductCollector] Canopy product {asin}: {e}")
                    _append_collection_error(state, asin, "canopy", "/product", str(e))
                    canopy_products[asin] = None

        # 串行拉取（避免过频）
        for asin in all_asins:
            await _fetch_rf(asin)
            await _fetch_canopy(asin)

        logger.info(
            f"[ProductCollector] Rainforest: {len([v for v in rf_products.values() if v])} products, "
            f"{len([v for v in rf_reviews_data.values() if v])} reviews sets; "
            f"Canopy: {len([v for v in canopy_products.values() if v])} products"
        )

        # 4. 合并数据（三源）
        products_list = []
        product_map = {}
        for asin in all_asins:
            k_data = keepa_products.get(asin)
            r_data = rf_products.get(asin)
            rv_data = rf_reviews_data.get(asin)
            c_data = canopy_products.get(asin)

            if not k_data and not r_data and not c_data:
                continue

            merged = _merge_product(k_data, r_data, rv_data, c_data)
            products_list.append(merged)
            product_map[asin] = merged

        # 5. 排序（BSR 越小越好）
        products_list.sort(key=lambda p: p.get("current_bsr") or 999999)

        # 6. 统计
        active_sources = [
            s for s, src in [("keepa", keepa), ("rainforest", rainforest), ("canopy", canopy)]
            if src
        ]
        collection_stats = {
            "total": len(products_list),
            "unique_asins": len(all_asins),
            "asin_source": asin_source,
            "keepa_products": len(keepa_products),
            "rainforest_products": len([v for v in rf_products.values() if v]),
            "rainforest_reviews": len([v for v in rf_reviews_data.values() if v]),
            "canopy_products": len([v for v in canopy_products.values() if v]),
            "data_sources": active_sources,
            "collected_at": datetime.now().isoformat(),
            "collection_errors": len(state.get("collection_errors") or []),
        }

        state.set("collected_products", products_list)
        state.set("product_map", product_map)
        state.set("collection_stats", collection_stats)
        state.set_meta("products_collected", len(products_list))

        logger.info(
            f"[ProductCollector] L1 done: {len(products_list)} products "
            f"(source={asin_source}, K={len(keepa_products)}, RF={len([v for v in rf_products.values() if v])}, "
            f"C={len([v for v in canopy_products.values() if v])})"
        )
        state.add_event(f"product_collector_success: {len(products_list)} products from {asin_source}")
        return state

    # ── L2 补单收集 ──────────────────────────────────────────────────

    async def _collect_l2(
        self,
        state: State,
        pending: List[Dict],
        domain: str,
        keepa,
        rainforest,
    ) -> State:
        """
        L2 补单收集：根据 pending_data_requests 按需补充数据。

        pending 格式: [{"asin": "B0XXX", "field": "reviews_page_2", "reason": "..."}, ...]
        支持 field:
          - reviews_page_N: 拉取第 N 页评论
          - reviews_all: 拉取所有可用页（最多 3 页）
          - offers: 拉取卖家报价
          - best_sellers: 拉取类目榜单
        """
        if not rainforest:
            _set_error(state, "no_rainforest", "L2 补单需要 Rainforest API")
            return state

        rf_domain = _keepa_domain_to_rainforest(domain)
        products = state.get("product_map") or {}
        new_reviews: Dict[str, List[Dict]] = {}
        collection_errors = state.get("collection_errors") or []

        for req in pending:
            asin = req.get("asin", "")
            field = req.get("field", "")

            try:
                if field.startswith("reviews_page_"):
                    page = int(field.split("_")[-1])
                    result = await rainforest.async_get_reviews(
                        asin, rf_domain, page=page, max_page=1,
                    )
                    revs = result.get("reviews", [])
                    if asin not in new_reviews:
                        new_reviews[asin] = []
                    new_reviews[asin].extend(revs)
                    logger.info(f"[ProductCollector] L2: {asin} reviews p{page} → {len(revs)} reviews")

                elif field == "reviews_all":
                    result = await rainforest.async_get_reviews_multi_page(
                        asin, rf_domain, start_page=1, num_pages=3,
                    )
                    revs = result.get("reviews", [])
                    if asin not in new_reviews:
                        new_reviews[asin] = []
                    new_reviews[asin].extend(revs)
                    logger.info(f"[ProductCollector] L2: {asin} reviews_all → {len(revs)} reviews")

                elif field == "offers":
                    offers = await rainforest.async_get_offers(asin, rf_domain)
                    if asin in products:
                        products[asin]["offers"] = offers
                    logger.info(f"[ProductCollector] L2: {asin} offers → {len(offers)} offers")

                elif field == "best_sellers":
                    category_id = req.get("category_id", "")
                    if category_id:
                        best = await rainforest.async_get_best_sellers(category_id, rf_domain)
                        state.set("best_sellers_data", best)
                        logger.info(f"[ProductCollector] L2: best_sellers {category_id} → {len(best)} items")

            except RainforestError as e:
                logger.warning(f"[ProductCollector] L2 {asin}/{field}: {e}")
                collection_errors.append({
                    "asin": asin, "source": "rainforest",
                    "endpoint": field, "error": str(e),
                })

        # ── 合并新评论到 collected_products ──
        if new_reviews:
            for p in (state.get("collected_products") or []):
                asin = p.get("asin", "")
                if asin in new_reviews:
                    existing = list(p.get("reviews") or [])
                    seen_ids = {r.get("id") for r in existing}
                    for r in new_reviews[asin]:
                        if r.get("id") not in seen_ids:
                            existing.append(r)
                            seen_ids.add(r.get("id"))
                    p["reviews"] = existing
                    p["reviews_page_count"] = p.get("reviews_page_count", 0) + 1

        # 清空已处理的请求
        state.set("pending_data_requests", [])
        state.set("collection_errors", collection_errors)
        state.add_event(f"product_collector_l2: processed {len(pending)} requests")
        logger.info(f"[ProductCollector] L2 done: {len(pending)} requests processed")
        return state

    # ── 关键词搜索（Rainforest） ─────────────────────────────────────

    async def _search_asins_by_rainforest(
        self,
        rainforest,
        keywords: List[str],
        domain: str,
    ) -> Dict[str, Any]:
        """
        通过 Rainforest /search 获取 ASIN 列表。

        Returns:
            {all_asins, keyword_results: [{keyword, total, asins, items}, ...]}
        """
        rf_domain = _keepa_domain_to_rainforest(domain)
        from backend.config.config import settings
        max_kw = getattr(settings, 'RAINFOREST_SEARCH_MAX_KEYWORDS', 5)
        max_results = getattr(settings, 'RAINFOREST_SEARCH_MAX_RESULTS', 20)

        keywords = keywords[:max_kw]
        all_asins: List[str] = []
        keyword_results = []

        for kw in keywords:
            logger.info(f"[ProductCollector] Rainforest search: '{kw}'")
            try:
                result = await rainforest.async_search(kw, rf_domain, max_results)
                keyword_results.append({"keyword": kw, **result})
                for asin in result.get("asins", []):
                    if asin not in all_asins:
                        all_asins.append(asin)
                logger.info(
                    f"[ProductCollector] '{kw}' → {len(result.get('asins', []))} ASINs "
                    f"(total results: {result.get('total_results', 0)})"
                )
            except RainforestError as e:
                logger.warning(f"[ProductCollector] RF search '{kw}' failed: {e}")
                keyword_results.append({"keyword": kw, "total_results": 0, "asins": [], "items": [], "_error": str(e)})

        return {
            "all_asins": all_asins,
            "keyword_results": keyword_results,
        }

    # ── 关键词搜索（Canopy） ─────────────────────────────────────────

    async def _search_asins_by_canopy(
        self,
        canopy,
        keywords: List[str],
        domain: str,
    ) -> Dict[str, Any]:
        """通过 Canopy /search 获取 ASIN 列表（优先搜索源，成本低）"""
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
                logger.info(
                    f"[ProductCollector] Canopy '{kw}' → {len(result.get('asins', []))} ASINs "
                    f"(total results: {result.get('total_results', 0)})"
                )
            except CanopyError as e:
                logger.warning(f"[ProductCollector] Canopy search '{kw}' failed: {e}")
                keyword_results.append({"keyword": kw, "total_results": 0, "asins": [], "items": [], "_error": str(e)})

        return {
            "all_asins": all_asins,
            "keyword_results": keyword_results,
        }

    # ── 连接器工厂 ───────────────────────────────────────────────────

    def _get_keepa(self):
        """获取 Keepa 连接器"""
        try:
            from backend.business.ecommerce.amazon_monitor.tools.keepa_connector import KeepaConnector
            return KeepaConnector()
        except KeepaConfigError as e:
            logger.warning(f"[ProductCollector] Keepa not configured: {e}")
            return None
        except Exception as e:
            logger.warning(f"[ProductCollector] Keepa init failed: {e}")
            return None

    def _get_rainforest(self):
        """获取 Rainforest 连接器"""
        try:
            from backend.business.ecommerce.amazon_monitor.tools.rainforest_connector import RainforestConnector
            return RainforestConnector()
        except RainforestConfigError as e:
            logger.warning(f"[ProductCollector] Rainforest not configured: {e}")
            return None
        except Exception as e:
            logger.warning(f"[ProductCollector] Rainforest init failed: {e}")
            return None

    def _get_canopy(self):
        """获取 Canopy 连接器"""
        try:
            from backend.business.ecommerce.amazon_monitor.tools.canopy_connector import CanopyConnector
            return CanopyConnector()
        except CanopyConfigError as e:
            logger.warning(f"[ProductCollector] Canopy not configured: {e}")
            return None
        except Exception as e:
            logger.warning(f"[ProductCollector] Canopy init failed: {e}")
            return None