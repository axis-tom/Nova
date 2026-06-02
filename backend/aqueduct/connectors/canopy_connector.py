"""
Canopy 数据连接器
调用 Canopy REST API，提供亚马逊商品详情、评论、搜索等数据

功能：
  - 关键词搜索 ASIN（/search 端点）
  - 商品详情 + 评论预览（/product 端点，内置 topReviews）
  - 评论查询（/product/reviews 端点）

使用前提：
  - 在 .env 中配置 CANOPY_API_KEY
  - requests（已在 requirements.txt）
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_CANOPY_BASE_URL = "https://rest.canopyapi.co/api/amazon"
_CANOPY_TIMEOUT = 60

# 503/超时重试配置
_RETRY_MAX_ATTEMPTS = 4
_RETRY_BASE_DELAY_SECONDS = 15


# ── 域名映射：Rainforest 格式 → Canopy 格式 ──────────────────────────

_DOMAIN_MAP: Dict[str, str] = {
    "amazon.com": "US",
    "amazon.de": "DE",
    "amazon.co.uk": "UK",
    "amazon.fr": "FR",
    "amazon.it": "IT",
    "amazon.es": "ES",
    "amazon.ca": "CA",
    "amazon.in": "IN",
    "amazon.co.jp": "JP",
    "amazon.com.mx": "MX",
    "amazon.com.br": "BR",
    "amazon.com.au": "AU",
    "amazon.nl": "NL",
}


def _to_canopy_domain(domain: str) -> str:
    """将 amazon.com 格式转为 Canopy 的 US 格式"""
    return _DOMAIN_MAP.get(domain, domain)


# ── 异常体系 ─────────────────────────────────────────────────────────


class CanopyError(Exception):
    """Canopy 调用的基类异常"""


class CanopyConfigError(CanopyError):
    """API key 缺失 / 不合法"""


class CanopyQuotaError(CanopyError):
    """Credit 配额耗尽 (HTTP 429)"""

    def __init__(self, message: str, retry_after_seconds: Optional[float] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class CanopyRejectedError(CanopyError):
    """请求被拒绝 — HTTP 400/403"""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class CanopyNetworkError(CanopyError):
    """网络层错误 — 超时 / DNS / 连接拒绝"""


class CanopyTemporaryError(CanopyError):
    """临时性服务故障 (HTTP 503 / 解析失败)，可自动重试"""


# ── 数据解析 ─────────────────────────────────────────────────────────


def _parse_product(raw: Dict[str, Any]) -> Dict[str, Any]:
    """将 Canopy /product 响应解析为标准化格式"""
    product = raw.get("data", {}).get("amazonProduct", raw)

    asin = product.get("asin", "")
    title = product.get("title", "") or ""
    brand = product.get("brand", "") or ""

    # 价格
    price_obj = product.get("price") or {}
    current_price = price_obj.get("value") if isinstance(price_obj, dict) else None

    # 类目
    categories = product.get("categories") or []
    category_tree = []
    category_name = ""
    for cat in categories:
        if isinstance(cat, dict):
            category_tree.append({
                "id": cat.get("id", ""),
                "name": cat.get("name", ""),
                "url": cat.get("url", ""),
            })
            if not category_name:
                category_name = cat.get("name", "")

    # Listing 内容
    feature_bullets = product.get("featureBullets") or []
    # description / aplus — Canopy product 端点不返回这些字段
    description = product.get("description", "") or ""

    # 媒体
    main_image = product.get("mainImageUrl") or ""
    images = product.get("imageUrls") or []

    # 规格
    specs = product.get("technicalSpecifications") or []
    spec_dict = {}
    for spec in specs:
        if isinstance(spec, dict):
            spec_dict[spec.get("name", "")] = spec.get("value", "")

    manufacturer = spec_dict.get("Manufacturer", "") or brand
    model_number = spec_dict.get("Model Number", "") or ""
    part_number = spec_dict.get("Part Number", "") or ""
    color = spec_dict.get("Color", "") or ""
    size = spec_dict.get("Size", "") or ""
    dimensions = spec_dict.get("Product Dimensions", "") or ""
    weight = spec_dict.get("Item Weight", "") or ""
    upc = spec_dict.get("UPC", "") or ""
    ean = spec_dict.get("EAN", "") or ""

    # 评分
    rating = product.get("rating")
    ratings_total = product.get("ratingsTotal", 0)

    # Seller
    seller = product.get("seller") or {}
    seller_name = seller.get("name", "") if isinstance(seller, dict) else ""
    seller_id = seller.get("id", "") if isinstance(seller, dict) else ""

    # 销量相关
    monthly_sold = product.get("monthlySalesEstimate", 0)
    weekly_sold = product.get("weeklySalesEstimate", 0)
    annual_sold = product.get("annualSalesEstimate", 0)
    stock_obj = product.get("stock") or {}
    stock_level = product.get("stockLevel", 0) or (stock_obj.get("level", 0) if isinstance(stock_obj, dict) else 0)
    review_velocity_30d = product.get("reviewVelocity", 0)
    material = spec_dict.get("Material", "") or product.get("material", "")
    style = spec_dict.get("Style", "") or product.get("style", "")
    package_quantity = spec_dict.get("Package Quantity") or product.get("packageQuantity")
    binding = spec_dict.get("Binding", "")
    product_group = spec_dict.get("Product Group", "")
    frequently_bought_together = product.get("frequentlyBoughtTogether", [])

    # 内嵌的 top reviews（Canopy 不提供单独的分页 reviews 端点）
    top_reviews = []
    for rv in (product.get("topReviews") or []):
        if isinstance(rv, dict):
            reviewer = rv.get("reviewer") or {}
            top_reviews.append({
                "id": rv.get("id", ""),
                "title": rv.get("title", ""),
                "body": rv.get("body", ""),
                "rating": rv.get("rating"),
                "helpful_votes": rv.get("helpfulVotes", 0),
                "verified": rv.get("verifiedPurchase", False),
                "reviewer": reviewer.get("name", "") if isinstance(reviewer, dict) else "",
            })

    return {
        "asin": asin,
        "title": title,
        "brand": brand,
        "category_name": category_name,
        "category_tree": category_tree,
        "feature_bullets": feature_bullets,
        "description": description,
        "specifications": spec_dict,
        "main_image": main_image,
        "images": images,
        "current_price": current_price,
        "is_prime": product.get("isPrime", False),
        "is_in_stock": product.get("isInStock"),
        "rating": rating,
        "ratings_total": ratings_total,
        "top_reviews": top_reviews,
        "seller_name": seller_name,
        "seller_id": seller_id,
        "manufacturer": manufacturer,
        "model_number": model_number,
        "part_number": part_number,
        "upc": upc,
        "ean": ean,
        "color": color,
        "size": size,
        "weight": weight,
        "dimensions": dimensions,
        "url": product.get("url", ""),

        # 新增字段
        "monthly_sold": monthly_sold,
        "weekly_sold": weekly_sold,
        "annual_sold": annual_sold,
        "stock_level": stock_level,
        "review_velocity_30d": review_velocity_30d,
        "material": material,
        "style": style,
        "package_quantity": package_quantity,
        "binding": binding,
        "product_group": product_group,
        "frequently_bought_together": frequently_bought_together,
    }


def _parse_reviews(raw: Dict[str, Any]) -> Dict[str, Any]:
    """解析 Canopy /product/reviews 响应（结构与 /product 内嵌 topReviews 相同）"""
    product = raw.get("data", {}).get("amazonProduct", raw)
    review_list = product.get("topReviews") or []

    parsed = []
    for rv in review_list:
        if not isinstance(rv, dict):
            continue
        reviewer = rv.get("reviewer") or {}
        parsed.append({
            "id": rv.get("id", ""),
            "title": rv.get("title", ""),
            "body": rv.get("body", ""),
            "rating": rv.get("rating"),
            "helpful_votes": rv.get("helpfulVotes", 0),
            "verified": rv.get("verifiedPurchase", False),
            "reviewer": reviewer.get("name", "") if isinstance(reviewer, dict) else "",
        })

    return {
        "total_reviews": product.get("ratingsTotal", 0),
        "reviews": parsed,
        "page": 1,
    }


def _parse_search(raw: Dict[str, Any]) -> Dict[str, Any]:
    """解析 Canopy /search 响应"""
    sr = raw.get("data", {}).get("amazonProductSearchResults", raw)
    product_results = sr.get("productResults", {})
    results = product_results.get("results", []) if isinstance(product_results, dict) else []

    asins = []
    items = []
    for item in results:
        if not isinstance(item, dict):
            continue
        a = item.get("asin", "")
        if a:
            asins.append(a)
        price_obj = item.get("price") or {}
        items.append({
            "asin": a,
            "title": item.get("title", ""),
            "price": price_obj.get("value") if isinstance(price_obj, dict) else None,
            "rating": item.get("rating"),
            "ratings_total": item.get("ratingsTotal"),
            "is_prime": item.get("isPrime", False),
            "sponsored": item.get("sponsored", False),
        })

    page_info = product_results.get("pageInfo", {}) if isinstance(product_results, dict) else {}
    total = page_info.get("totalPages", 1) * len(results)

    return {
        "total_results": total,
        "asins": asins,
        "items": items,
        "page_info": page_info,
    }


# ── 连接器 ───────────────────────────────────────────────────────────


class CanopyConnector:
    """Canopy REST API 连接器"""

    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            from backend.config.config import settings
            api_key = settings.CANOPY_API_KEY

        if not api_key or api_key == "your_canopy_api_key_here":
            raise CanopyConfigError(
                "CANOPY_API_KEY 未配置。请在 backend/config/.env 中设置 CANOPY_API_KEY=your_key\n"
                "获取 API Key: https://app.canopyapi.com/"
            )
        self.api_key = api_key

    # ── 内部：REST 调用 ──

    def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET 调用 Canopy REST API。
        内置 503/超时/连接失败 指数退避重试：15s → 30s → 60s → 120s（最多 4 次）。
        """

        headers = {
            "API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                resp = requests.get(
                    f"{_CANOPY_BASE_URL}{endpoint}",
                    params=params,
                    headers=headers,
                    timeout=_CANOPY_TIMEOUT,
                )
                status = resp.status_code
                resp_body = resp.text or ""

                if status == 200:
                    try:
                        return resp.json()
                    except ValueError as e:
                        raise CanopyTemporaryError(
                            f"Canopy 响应 JSON 解析失败: {e}; body[:200]={resp_body[:200]}"
                        ) from e

                if status == 503:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[Canopy] HTTP 503 (attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS}), "
                        f"{delay}s 后重试..."
                    )
                    if attempt < _RETRY_MAX_ATTEMPTS - 1:
                        time.sleep(delay)
                    continue

                if status == 429:
                    retry_after = resp.headers.get("Retry-After")
                    retry_sec = float(retry_after) if retry_after else None
                    raise CanopyQuotaError(
                        f"Canopy credit 配额耗尽 (HTTP 429)"
                        f"{' — Retry-After: ' + str(retry_sec) + 's' if retry_sec else ''}",
                        retry_after_seconds=retry_sec,
                    )

                if status in (400, 403, 404):
                    raise CanopyRejectedError(
                        f"Canopy 拒绝请求 (HTTP {status}): {resp_body[:300]}",
                        status_code=status,
                        body=resp_body,
                    )

                raise CanopyError(f"Canopy 返回非预期状态 HTTP {status}: {resp_body[:200]}")

            except (CanopyTemporaryError,):
                if attempt < _RETRY_MAX_ATTEMPTS - 1:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[Canopy] 解析失败，{delay}s 后重试 "
                        f"(attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS})"
                    )
                    time.sleep(delay)
                continue

            except (CanopyQuotaError, CanopyRejectedError, CanopyError):
                raise

            except requests.Timeout as e:
                if attempt < _RETRY_MAX_ATTEMPTS - 1:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[Canopy] 超时 (attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS}), "
                        f"{delay}s 后重试..."
                    )
                    time.sleep(delay)
                    continue
                raise CanopyNetworkError(f"Canopy 请求超时（{_CANOPY_TIMEOUT}s）: {e}") from e

            except requests.ConnectionError as e:
                if attempt < _RETRY_MAX_ATTEMPTS - 1:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[Canopy] 连接失败 (attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS}), "
                        f"{delay}s 后重试..."
                    )
                    time.sleep(delay)
                    continue
                raise CanopyNetworkError(f"Canopy 连接失败: {e}") from e

            except requests.RequestException as e:
                raise CanopyNetworkError(f"Canopy 请求异常: {e}") from e

        raise CanopyTemporaryError(
            f"Canopy 重试 {_RETRY_MAX_ATTEMPTS} 次后仍失败 (503 / 解析 / 超时)"
        )

    # ── 商品详情 ──

    def get_product(self, asin: str, domain: str = "amazon.com") -> Dict[str, Any]:
        """获取商品详情（含内嵌 topReviews）"""
        cdomain = _to_canopy_domain(domain)
        logger.info(f"[Canopy] /product: {asin} domain={cdomain}")
        raw = self._request("/product", {"asin": asin, "domain": cdomain})
        result = _parse_product(raw)
        logger.info(f"[Canopy] /product parsed: {asin} — {result.get('title', '')[:60]}")
        return result

    async def async_get_product(self, asin: str, domain: str = "amazon.com") -> Dict[str, Any]:
        return await asyncio.to_thread(self.get_product, asin, domain)

    async def async_get_products(
        self, asins: List[str], domain: str = "amazon.com",
    ) -> Dict[str, Dict[str, Any]]:
        result = {}
        for asin in asins:
            try:
                result[asin] = await self.async_get_product(asin, domain)
            except CanopyError as e:
                logger.warning(f"[Canopy] get_product failed for {asin}: {e}")
                result[asin] = {"asin": asin, "_error": str(e)}
        return result

    # ── 评论 ──

    def get_reviews(
        self,
        asin: str,
        domain: str = "amazon.com",
        page: int = 1,
    ) -> Dict[str, Any]:
        """获取商品评论（Canopy /product/reviews 端点）"""
        cdomain = _to_canopy_domain(domain)
        logger.info(f"[Canopy] /product/reviews: {asin} page={page}")
        raw = self._request("/product/reviews", {
            "asin": asin,
            "domain": cdomain,
            "page": page,
        })
        result = _parse_reviews(raw)
        logger.info(
            f"[Canopy] /product/reviews parsed: {asin} — "
            f"{len(result['reviews'])} reviews (total={result['total_reviews']})"
        )
        return result

    async def async_get_reviews(
        self, asin: str, domain: str = "amazon.com", page: int = 1,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(self.get_reviews, asin, domain, page)

    async def async_get_reviews_multi_page(
        self, asin: str, domain: str = "amazon.com",
        start_page: int = 1, num_pages: int = 1,
    ) -> Dict[str, Any]:
        all_reviews = []
        total = 0
        for p in range(start_page, start_page + num_pages):
            try:
                result = await self.async_get_reviews(asin, domain, p)
                all_reviews.extend(result.get("reviews", []))
                total = result.get("total_reviews", total)
            except CanopyError as e:
                logger.warning(f"[Canopy] reviews page {p} failed for {asin}: {e}")
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
    ) -> Dict[str, Any]:
        """关键词搜索 ASIN（Canopy /search 端点）"""
        cdomain = _to_canopy_domain(domain)
        logger.info(f"[Canopy] /search: '{keyword}' domain={cdomain}")
        raw = self._request("/search", {
            "searchTerm": keyword,
            "domain": cdomain,
        })
        result = _parse_search(raw)
        logger.info(
            f"[Canopy] /search: '{keyword}' → {len(result['asins'])} ASINs"
        )
        return result

    async def async_search(
        self, keyword: str, domain: str = "amazon.com", max_results: int = 20,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(self.search, keyword, domain, max_results)


# ── 便捷函数 ──


def get_canopy_connector(api_key: Optional[str] = None) -> CanopyConnector:
    """获取 CanopyConnector 实例"""
    return CanopyConnector(api_key)