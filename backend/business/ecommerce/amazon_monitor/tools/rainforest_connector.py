"""
Rainforest 数据连接器
直接调用 Rainforest REST API，提供亚马逊商品详情、评论、搜索等数据

功能：
  - 关键词搜索 ASIN（/search 端点）
  - 商品详情查询（/product 端点）：listing 内容、变体、图片、A+、广告、类目
  - 评论查询（/reviews 端点）：评论文本、星级分布、分页
  - L2 补单端点：offers、category、best_sellers

使用前提：
  - 在 .env 中配置 RAINFOREST_API_KEY
  - requests（已在 requirements.txt）

注：Rainforest 按端点独立计费（credit 制），每次请求消耗不等。
    免费试用 100 次 request，订阅后按量计费。
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Rainforest REST 基础 URL
_RAINFOREST_BASE_URL = "https://api.rainforestapi.com/request"
_RAINFOREST_TIMEOUT = 60

# 503 重试配置
_RETRY_MAX_ATTEMPTS = 4          # 最多重试次数
_RETRY_BASE_DELAY_SECONDS = 15   # 初始等待秒数


# ── 异常体系 ─────────────────────────────────────────────────────────


class RainforestError(Exception):
    """Rainforest 调用的基类异常"""


class RainforestConfigError(RainforestError):
    """API key 缺失 / 不合法"""


class RainforestQuotaError(RainforestError):
    """Credit 配额耗尽 (HTTP 429)"""

    def __init__(self, message: str, retry_after_seconds: Optional[float] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RainforestRejectedError(RainforestError):
    """请求被拒绝 — HTTP 400/403"""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class RainforestNetworkError(RainforestError):
    """网络层错误 — 超时 / DNS / 连接拒绝"""


class RainforestTemporaryError(RainforestError):
    """临时性服务故障 (HTTP 503 / 解析失败)，可自动重试"""


# ── 数据解析 ─────────────────────────────────────────────────────────


def _parse_product(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 Rainforest /product 响应解析为标准化格式。
    提取选品分析需要的所有字段。
    """
    product = raw.get("product", raw)

    # ── 基础信息 ──
    asin = product.get("asin", "")
    title = product.get("title", "") or ""
    brand = product.get("brand", "") or ""
    parent_asin = product.get("parent_asin", "") or ""

    # ── 类目 ──
    categories = product.get("categories") or []
    category_name = categories[0].get("name", "") if categories else ""
    category_tree = []
    for cat in categories:
        category_tree.append({
            "id": cat.get("category_id", ""),
            "name": cat.get("name", ""),
            "link": cat.get("link", ""),
        })

    # ── Listing 内容 ──
    feature_bullets = product.get("feature_bullets") or []
    if isinstance(feature_bullets, str):
        feature_bullets = feature_bullets.split("\n")
    description = ""
    spec_flat = product.get("specifications_flat", "") or ""
    specifications = product.get("specifications") or []
    aplus = product.get("a_plus_content") or {}

    # ── 媒体 ──
    main_image = ""
    main_img_obj = product.get("main_image") or {}
    if isinstance(main_img_obj, dict):
        main_image = main_img_obj.get("link", "")
    images = []
    for img in (product.get("images") or []):
        if isinstance(img, dict) and img.get("link"):
            images.append(img["link"])
    images_flat = product.get("images_flat", "") or ""
    videos_count = product.get("videos_count", 0)

    # ── 价格 ──
    buybox = product.get("buybox_winner") or {}
    current_price = None
    if isinstance(buybox, dict):
        price_obj = buybox.get("price") or {}
        if isinstance(price_obj, dict):
            current_price = price_obj.get("value")
    list_price = None
    # list_price 有时在 buybox 里或独立字段
    if isinstance(buybox, dict):
        lp = buybox.get("list_price") or buybox.get("rrp")
        if isinstance(lp, dict):
            list_price = lp.get("value")
    is_prime = False
    if isinstance(buybox, dict):
        is_prime = buybox.get("is_prime", False)
    fulfillment = ""
    if isinstance(buybox, dict):
        fulfillment_data = buybox.get("fulfillment") or {}
        if isinstance(fulfillment_data, dict):
            fulfillment = fulfillment_data.get("type", "")
    availability = ""
    if isinstance(buybox, dict):
        availability_data = buybox.get("availability") or {}
        if isinstance(availability_data, dict):
            availability = availability_data.get("raw", "") or availability_data.get("type", "")

    # ── BSR ──
    bsr_rank = None
    bsr_category = ""
    bestseller_list = product.get("bestsellers_rank") or []
    if bestseller_list:
        first_bsr = bestseller_list[0] if isinstance(bestseller_list[0], dict) else {}
        bsr_rank = first_bsr.get("rank")
        bsr_category = first_bsr.get("category", "")

    # ── 评分 ──
    rating = product.get("rating")
    ratings_total = product.get("ratings_total", 0)
    rating_breakdown = product.get("rating_breakdown") or {}
    if isinstance(rating_breakdown, dict):
        rating_breakdown = {
            5: rating_breakdown.get("five_star", 0),
            4: rating_breakdown.get("four_star", 0),
            3: rating_breakdown.get("three_star", 0),
            2: rating_breakdown.get("two_star", 0),
            1: rating_breakdown.get("one_star", 0),
        }

    # ── 变体 ──
    variations = []
    child_asins = []
    for var in (product.get("variants") or []):
        if isinstance(var, dict):
            var_asin = var.get("asin", "")
            var_dimensions = var.get("dimensions") or []
            var_dim_flat = ", ".join(
                f"{d.get('name', '')}: {d.get('value', '')}"
                for d in var_dimensions if isinstance(d, dict)
            ) if var_dimensions else ""
            variations.append({
                "asin": var_asin,
                "title": var.get("title", ""),
                "link": var.get("link", ""),
                "is_current": var.get("is_current_product", False),
                "dimensions": var_dim_flat,
                "image": (var.get("main_image") or {}).get("link", "") if isinstance(var.get("main_image"), dict) else "",
            })
            if var_asin and var_asin != asin:
                child_asins.append(var_asin)

    # ── 评论预览 ──
    top_reviews = []
    for rv in (product.get("top_reviews") or []):
        if isinstance(rv, dict):
            profile = rv.get("profile") or {}
            date_info = rv.get("date") or {}
            top_reviews.append({
                "id": rv.get("id", ""),
                "title": rv.get("title", ""),
                "body": rv.get("body", ""),
                "rating": rv.get("rating"),
                "date": date_info.get("raw", "") if isinstance(date_info, dict) else str(date_info),
                "reviewer": profile.get("name", "") if isinstance(profile, dict) else "",
                "verified": rv.get("verified_purchase", False),
            })

    # ── 规格信息 ──
    spec_dict = {}
    for spec in specifications:
        if isinstance(spec, dict):
            spec_dict[spec.get("name", "")] = spec.get("value", "")

    manufacturer = spec_dict.get("Manufacturer", "") or spec_dict.get("Brand", "") or brand
    model_number = spec_dict.get("Model Number", "") or product.get("model_number", "") or ""
    part_number = spec_dict.get("Part Number", "") or ""
    upc = spec_dict.get("UPC", "") or ""
    ean = spec_dict.get("EAN", "") or ""
    item_weight = spec_dict.get("Item Weight", "") or ""
    package_quantity_raw = spec_dict.get("Package Quantity", "")
    package_quantity = int(package_quantity_raw) if package_quantity_raw and str(package_quantity_raw).isdigit() else None
    color = product.get("color", "") or spec_dict.get("Color", "") or ""
    size = spec_dict.get("Size", "") or ""
    style = spec_dict.get("Style", "") or ""
    material_type = product.get("material", "") or spec_dict.get("Material", "") or ""
    dimensions = product.get("dimensions", "") or spec_dict.get("Product Dimensions", "") or ""
    binding = spec_dict.get("Binding", "") or ""
    product_group = spec_dict.get("Product Group", "") or ""
    country_of_origin = spec_dict.get("Country of Origin", "") or ""

    # ── 库存 ──
    stock_level = ""
    if isinstance(buybox, dict):
        availability_data = buybox.get("availability") or {}
        if isinstance(availability_data, dict):
            stock_level = availability_data.get("raw", "") or availability_data.get("type", "")
    max_order_qty = None
    if isinstance(buybox, dict):
        max_order_qty = buybox.get("maximum_order_quantity")

    # ── 广告数据 ──
    sponsored_products = product.get("sponsored_products") or []

    # ── 最近销量 ──
    recent_sales = product.get("recent_sales", "") or ""

    return {
        "asin": asin,
        "title": title,
        "brand": brand,
        "parent_asin": parent_asin,
        "child_asins": child_asins,

        # 类目
        "category_name": category_name,
        "category_tree": category_tree,

        # Listing
        "feature_bullets": feature_bullets,
        "specifications": spec_dict,
        "description": spec_flat,
        "aplus_content": aplus,

        # 媒体
        "main_image": main_image,
        "images": images,
        "images_flat": images_flat,
        "videos_count": videos_count,

        # 价格
        "current_price": current_price,
        "list_price": list_price,
        "is_prime": is_prime,
        "fulfillment": fulfillment,
        "availability": availability,

        # BSR
        "bsr_rank": bsr_rank,
        "bsr_category": bsr_category,

        # 评分
        "rating": rating,
        "ratings_total": ratings_total,
        "rating_breakdown": rating_breakdown,

        # 变体
        "variations": variations,

        # 评论预览
        "top_reviews": top_reviews,

        # 规格
        "manufacturer": manufacturer,
        "model_number": model_number,
        "part_number": part_number,
        "upc": upc,
        "ean": ean,
        "item_weight": item_weight,
        "package_quantity": package_quantity,
        "color": color,
        "size": size,
        "style": style,
        "material": material_type,
        "dimensions": dimensions,
        "binding": binding,
        "product_group": product_group,
        "country_of_origin": country_of_origin,

        # 库存
        "stock_level": stock_level,
        "max_order_quantity": max_order_qty,

        # 广告
        "sponsored_products": sponsored_products,

        # 销量
        "recent_sales": recent_sales,
    }


def _parse_reviews(raw: Dict[str, Any]) -> Dict[str, Any]:
    """解析 Rainforest /reviews 响应"""
    reviews_data = raw.get("reviews", raw)
    total = reviews_data.get("total_reviews", 0)
    review_list = reviews_data.get("reviews", []) or []

    parsed = []
    for rv in review_list:
        if not isinstance(rv, dict):
            continue
        profile = rv.get("profile") or {}
        date_info = rv.get("date") or {}
        parsed.append({
            "id": rv.get("id", ""),
            "title": rv.get("title", ""),
            "body": rv.get("body", ""),
            "rating": rv.get("rating"),
            "date": date_info.get("raw", "") if isinstance(date_info, dict) else str(date_info),
            "reviewer": profile.get("name", "") if isinstance(profile, dict) else "",
            "verified": rv.get("verified_purchase", False),
            "helpful_votes": rv.get("helpful_votes", 0),
            "vine_voice": rv.get("vine_voice", False),
        })

    return {
        "total_reviews": total,
        "reviews": parsed,
        "page": reviews_data.get("page", 1),
    }


def _parse_search(raw: Dict[str, Any]) -> Dict[str, Any]:
    """解析 Rainforest /search 响应，提取 ASIN 列表和基础信息"""
    sr = raw.get("search_results", raw)
    results = sr if isinstance(sr, list) else sr.get("results", []) or []

    asins = []
    items = []
    for item in results:
        if not isinstance(item, dict):
            continue
        asin = item.get("asin", "")
        if asin:
            asins.append(asin)
        items.append({
            "asin": asin,
            "title": item.get("title", ""),
            "price": item.get("price"),
            "rating": item.get("rating"),
            "ratings_total": item.get("ratings_total"),
            "is_prime": item.get("is_prime", False),
            "position": item.get("position"),
            "sponsored": item.get("sponsored", False),
        })

    total = sr.get("total_results", len(results)) if isinstance(sr, dict) else len(results)

    return {
        "total_results": total,
        "asins": asins,
        "items": items,
    }


# ── 连接器 ───────────────────────────────────────────────────────────


class RainforestConnector:
    """Rainforest REST API 连接器"""

    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            from backend.config.config import settings
            api_key = settings.RAINFOREST_API_KEY

        if not api_key or api_key == "your_rainforest_api_key_here":
            raise RainforestConfigError(
                "RAINFOREST_API_KEY 未配置。请在 backend/config/.env 中设置 RAINFOREST_API_KEY=your_key\n"
                "获取 API Key: https://app.rainforestapi.com/"
            )
        self.api_key = api_key

    # ── 内部：REST 调用 ──

    def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET 调用 Rainforest REST API。
        所有端点统一走 /request，通过 type 参数区分。

        内置 503 指数退避重试：15s → 30s → 60s → 120s（最多 4 次）。
        skip_on_incident 参数：503 时不抛异常，返回空 dict（优雅跳过故障）。
        """

        for attempt in range(_RETRY_MAX_ATTEMPTS):
            full_params = {
                "api_key": self.api_key,
                "skip_on_incident": "true",
                **params,
            }

            resp_body = ""
            try:
                resp = requests.get(
                    _RAINFOREST_BASE_URL,
                    params=full_params,
                    timeout=_RAINFOREST_TIMEOUT,
                )
                status = resp.status_code
                resp_body = resp.text or ""

                if status == 200:
                    try:
                        return resp.json()
                    except ValueError as e:
                        raise RainforestTemporaryError(
                            f"Rainforest 响应 JSON 解析失败: {e}; body[:200]={resp_body[:200]}"
                        ) from e

                if status == 503:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[Rainforest] HTTP 503 (attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS}), "
                        f"{delay}s 后重试..."
                    )
                    if attempt < _RETRY_MAX_ATTEMPTS - 1:
                        time.sleep(delay)
                    continue

                if status == 429:
                    retry_after = resp.headers.get("Retry-After")
                    retry_sec = float(retry_after) if retry_after else None
                    raise RainforestQuotaError(
                        f"Rainforest credit 配额耗尽 (HTTP 429)"
                        f"{' — Retry-After: ' + str(retry_sec) + 's' if retry_sec else ''}",
                        retry_after_seconds=retry_sec,
                    )

                if status in (400, 403):
                    raise RainforestRejectedError(
                        f"Rainforest 拒绝请求 (HTTP {status}): {resp_body[:300]}",
                        status_code=status,
                        body=resp_body,
                    )

                raise RainforestError(f"Rainforest 返回非预期状态 HTTP {status}: {resp_body[:200]}")

            except (RainforestTemporaryError,):
                if attempt < _RETRY_MAX_ATTEMPTS - 1:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[Rainforest] 解析失败，{delay}s 后重试 "
                        f"(attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS})"
                    )
                    time.sleep(delay)
                continue

            except (RainforestQuotaError, RainforestRejectedError, RainforestError):
                raise

            except requests.Timeout as e:
                if attempt < _RETRY_MAX_ATTEMPTS - 1:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[Rainforest] 超时 (attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS}), "
                        f"{delay}s 后重试..."
                    )
                    time.sleep(delay)
                    continue
                raise RainforestNetworkError(
                    f"Rainforest 请求超时（{_RAINFOREST_TIMEOUT}s）: {e}"
                ) from e

            except requests.ConnectionError as e:
                if attempt < _RETRY_MAX_ATTEMPTS - 1:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[Rainforest] 连接失败 (attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS}), "
                        f"{delay}s 后重试..."
                    )
                    time.sleep(delay)
                    continue
                raise RainforestNetworkError(f"Rainforest 连接失败: {e}") from e

            except requests.RequestException as e:
                raise RainforestNetworkError(f"Rainforest 请求异常: {e}") from e

        # 所有重试耗尽
        raise RainforestTemporaryError(
            f"Rainforest 重试 {_RETRY_MAX_ATTEMPTS} 次后仍失败 "
            f"(503 / 解析 / 超时)"
        )

    # ── 商品详情 ──

    def get_product(self, asin: str, domain: str = "amazon.com") -> Dict[str, Any]:
        """
        获取单个商品详情（Rainforest /product 端点）

        Returns:
            标准化的商品详情 dict（_parse_product 输出）
        """
        logger.info(f"[Rainforest] /product: {asin} (domain={domain})")
        raw = self._get({
            "type": "product",
            "asin": asin,
            "amazon_domain": domain,
        })
        result = _parse_product(raw)
        logger.info(f"[Rainforest] /product parsed: {asin} — {result.get('title', '')[:60]}")
        return result

    async def async_get_product(self, asin: str, domain: str = "amazon.com") -> Dict[str, Any]:
        """异步版 get_product"""
        return await asyncio.to_thread(self.get_product, asin, domain)

    async def async_get_products(
        self, asins: List[str], domain: str = "amazon.com",
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量获取商品详情。
        Rainforest 没有批量端点，逐个请求（后续可优化为并发）。
        """
        result = {}
        for asin in asins:
            try:
                result[asin] = await self.async_get_product(asin, domain)
            except RainforestError as e:
                logger.warning(f"[Rainforest] get_product failed for {asin}: {e}")
                result[asin] = {"asin": asin, "_error": str(e)}
        return result

    # ── 评论 ──

    def get_reviews(
        self,
        asin: str,
        domain: str = "amazon.com",
        page: int = 1,
        max_page: int = 1,
        sort_by: str = "most_recent",
        verified_only: bool = False,
        rating_filter: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        获取商品评论（Rainforest /reviews 端点）

        Args:
            asin: 商品 ASIN
            domain: 市场域名
            page: 起始页码（1-based）
            max_page: 最大拉取页数（每页约 10 条）
            sort_by: most_recent / most_helpful
            verified_only: 仅已验证购买
            rating_filter: 按星级筛选（1-5），None=全部

        Returns:
            {total_reviews, reviews: [...], page}
        """
        logger.info(
            f"[Rainforest] /reviews: {asin} page={page} "
            f"(sort={sort_by}, verified={verified_only}, rating={rating_filter})"
        )
        params: Dict[str, Any] = {
            "type": "reviews",
            "asin": asin,
            "amazon_domain": domain,
            "page": page,
            "max_page": max_page,
            "sort_by": sort_by,
        }
        if verified_only:
            params["verified_purchase"] = "true"
        if rating_filter and 1 <= rating_filter <= 5:
            params["review_stars"] = str(rating_filter)

        raw = self._get(params)
        result = _parse_reviews(raw)
        logger.info(
            f"[Rainforest] /reviews parsed: {asin} — "
            f"{len(result['reviews'])} reviews (total={result['total_reviews']})"
        )
        return result

    async def async_get_reviews(
        self, asin: str, domain: str = "amazon.com",
        page: int = 1, max_page: int = 1,
        sort_by: str = "most_recent",
        verified_only: bool = False,
        rating_filter: Optional[int] = None,
    ) -> Dict[str, Any]:
        """异步版 get_reviews"""
        return await asyncio.to_thread(
            self.get_reviews, asin, domain, page, max_page, sort_by, verified_only, rating_filter,
        )

    async def async_get_reviews_multi_page(
        self, asin: str, domain: str = "amazon.com",
        start_page: int = 1, num_pages: int = 1,
        page_size: int = 10, sort_by: str = "most_recent",
    ) -> Dict[str, Any]:
        """
        多页评论拉取（用于 L2 补单）。
        依次请求多页并合并结果。
        """
        all_reviews = []
        total = 0
        for p in range(start_page, start_page + num_pages):
            try:
                result = await self.async_get_reviews(
                    asin, domain=domain, page=p, max_page=1, sort_by=sort_by,
                )
                all_reviews.extend(result.get("reviews", []))
                total = result.get("total_reviews", total)
            except RainforestError as e:
                logger.warning(f"[Rainforest] reviews page {p} failed for {asin}: {e}")

        return {
            "total_reviews": total,
            "reviews": all_reviews,
            "start_page": start_page,
            "pages_fetched": num_pages,
        }

    # ── 关键词搜索 ──

    def search(
        self,
        keyword: str,
        domain: str = "amazon.com",
        max_results: int = 20,
        category: str = "aps",
        sort_by: str = "",
    ) -> Dict[str, Any]:
        """
        关键词搜索 ASIN（Rainforest /search 端点）

        Args:
            keyword: 搜索词
            domain: 市场域名
            max_results: 最大返回结果数
            category: 搜索分类（aps=All, 或具体类目 ID）
            sort_by: relevance / price_low_to_high / price_high_to_low / average_review

        Returns:
            {total_results, asins: [...], items: [{asin, title, price, rating, ...}, ...]}
        """
        logger.info(f"[Rainforest] /search: '{keyword}' (domain={domain}, max={max_results})")
        params: Dict[str, Any] = {
            "type": "search",
            "search_term": keyword,
            "amazon_domain": domain,
            "max_page": max(max_results // 10, 1),
            "category": category,
        }
        if sort_by:
            params["sort_by"] = sort_by
        raw = self._get(params)
        result = _parse_search(raw)
        logger.info(
            f"[Rainforest] /search parsed: '{keyword}' → "
            f"{len(result['asins'])} ASINs (total={result['total_results']})"
        )
        return result

    async def async_search(
        self, keyword: str, domain: str = "amazon.com",
        max_results: int = 20, category: str = "aps",
    ) -> Dict[str, Any]:
        """异步版 search"""
        return await asyncio.to_thread(
            self.search, keyword, domain, max_results, category,
        )

    async def async_search_multi(
        self, keywords: List[str], domain: str = "amazon.com",
        max_results_per_kw: int = 20,
    ) -> List[Dict[str, Any]]:
        """批量关键词搜索，每个关键词返回搜索结果"""
        results = []
        for kw in keywords:
            try:
                results.append(await self.async_search(kw, domain, max_results_per_kw))
            except RainforestError as e:
                logger.warning(f"[Rainforest] search failed for '{kw}': {e}")
                results.append({"total_results": 0, "asins": [], "items": [], "_error": str(e)})
        return results

    # ── L2 端点 ──

    def get_offers(self, asin: str, domain: str = "amazon.com") -> List[Dict[str, Any]]:
        """获取卖家报价列表（Rainforest /offers 端点，L2）"""
        logger.info(f"[Rainforest] /offers: {asin}")
        raw = self._get({
            "type": "offers",
            "asin": asin,
            "amazon_domain": domain,
        })
        offers_data = raw.get("offers", raw)
        offers = offers_data if isinstance(offers_data, list) else offers_data.get("offers", []) or []
        return [
            {
                "seller_name": o.get("seller_name", ""),
                "seller_id": o.get("seller_id", ""),
                "price": (o.get("price") or {}).get("value") if isinstance(o.get("price"), dict) else None,
                "shipping": (o.get("shipping") or {}).get("value") if isinstance(o.get("shipping"), dict) else None,
                "condition": o.get("condition", ""),
                "is_fba": o.get("is_fba", False),
                "is_prime": o.get("is_prime", False),
                "buybox_winner": o.get("buybox_winner", False),
            }
            for o in offers if isinstance(o, dict)
        ]

    async def async_get_offers(self, asin: str, domain: str = "amazon.com") -> List[Dict[str, Any]]:
        """异步版 get_offers"""
        return await asyncio.to_thread(self.get_offers, asin, domain)

    def get_best_sellers(
        self, category_id: str, domain: str = "amazon.com", max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取类目热销榜（Rainforest /category 端点，L2）"""
        logger.info(f"[Rainforest] /category best_sellers: {category_id}")
        raw = self._get({
            "type": "category",
            "category_id": category_id,
            "amazon_domain": domain,
            "best_sellers": "true",
            "max_page": max(max_results // 10, 1),
        })
        cat_data = raw.get("category", raw)
        results = cat_data.get("best_sellers", []) if isinstance(cat_data, dict) else []
        return [
            {"asin": r.get("asin", ""), "title": r.get("title", ""), "rank": r.get("rank")}
            for r in results[:max_results] if isinstance(r, dict)
        ]

    async def async_get_best_sellers(
        self, category_id: str, domain: str = "amazon.com", max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """异步版 get_best_sellers"""
        return await asyncio.to_thread(self.get_best_sellers, category_id, domain, max_results)


# ── 便捷函数 ──


def get_rainforest_connector(api_key: Optional[str] = None) -> RainforestConnector:
    """获取 RainforestConnector 实例"""
    return RainforestConnector(api_key)