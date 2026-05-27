"""
Amazon Product Advertising API 5.0 客户端
使用 AWS Signature V4 进行请求签名认证
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

import httpx
from backend.utils.logger import logger

# 默认配置
DEFAULT_MARKETPLACE = "www.amazon.com"
PAAPI_ENDPOINTS = {
    "www.amazon.com": "webservices.amazon.com",
    "www.amazon.co.jp": "webservices.amazon.co.jp",
    "www.amazon.de": "webservices.amazon.de",
    "www.amazon.co.uk": "webservices.amazon.co.uk",
    "www.amazon.fr": "webservices.amazon.fr",
    "www.amazon.ca": "webservices.amazon.ca",
    "www.amazon.it": "webservices.amazon.it",
    "www.amazon.es": "webservices.amazon.es",
    "www.amazon.in": "webservices.amazon.in",
    "www.amazon.com.br": "webservices.amazon.com.br",
    "www.amazon.com.mx": "webservices.amazon.com.mx",
    "www.amazon.com.au": "webservices.amazon.com.au",
    "www.amazon.sg": "webservices.amazon.sg",
    "www.amazon.ae": "webservices.amazon.ae",
    "www.amazon.sa": "webservices.amazon.sa",
    "www.amazon.nl": "webservices.amazon.nl",
    "www.amazon.se": "webservices.amazon.se",
    "www.amazon.pl": "webservices.amazon.pl",
    "www.amazon.eg": "webservices.amazon.eg",
    "www.amazon.com.tr": "webservices.amazon.com.tr",
}

SERVICE_NAME = "ProductAdvertisingAPI"
REGION_MAP = {
    "www.amazon.com": "us-east-1",
    "www.amazon.co.jp": "us-west-2",
    "www.amazon.de": "eu-west-1",
    "www.amazon.co.uk": "eu-west-1",
    "www.amazon.fr": "eu-west-1",
    "www.amazon.ca": "us-east-1",
    "www.amazon.it": "eu-west-1",
    "www.amazon.es": "eu-west-1",
    "www.amazon.in": "eu-west-1",
    "www.amazon.com.br": "us-east-1",
    "www.amazon.com.mx": "us-east-1",
    "www.amazon.com.au": "us-west-2",
    "www.amazon.sg": "us-west-2",
    "www.amazon.ae": "eu-west-1",
    "www.amazon.sa": "eu-west-1",
    "www.amazon.nl": "eu-west-1",
    "www.amazon.se": "eu-west-1",
    "www.amazon.pl": "eu-west-1",
    "www.amazon.eg": "eu-west-1",
    "www.amazon.com.tr": "eu-west-1",
}


class AmazonPAAPIClient:
    """
    Amazon Product Advertising API 5.0 客户端
    支持 AWS Signature V4 签名认证
    """

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        associate_tag: str,
        partner_type: str = "Associates",
        marketplace: str = DEFAULT_MARKETPLACE,
        max_retry: int = 3,
        cache_ttl_hours: int = 24,
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.associate_tag = associate_tag
        self.partner_type = partner_type
        self.marketplace = marketplace
        self.max_retry = max_retry
        self.cache_ttl_hours = cache_ttl_hours

        self.endpoint = PAAPI_ENDPOINTS.get(marketplace, "webservices.amazon.com")
        self.region = REGION_MAP.get(marketplace, "us-east-1")
        self.base_url = f"https://{self.endpoint}/paapi5"

        # 简单的内存缓存
        self._cache: Dict[str, Any] = {}

        logger.info(f"[AmazonPAAPI] Initialized for marketplace: {marketplace}, region: {self.region}")

    # ---- AWS Signature V4 签名 ----

    def _sign(self, key: bytes, msg: str) -> bytes:
        return hmac.HMAC(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _get_signature_key(self, date_stamp: str) -> bytes:
        """Derive the signing key using AWS Signature V4"""
        k_date = self._sign(f"AWS4{self.secret_key}".encode("utf-8"), date_stamp)
        k_region = self._sign(k_date, self.region)
        k_service = self._sign(k_region, SERVICE_NAME)
        k_signing = self._sign(k_service, "aws4_request")
        return k_signing

    def _build_signed_request(self, operation: str, payload: dict) -> Dict[str, str]:
        """
        构建 AWS Signature V4 签名的请求头
        """
        now = datetime.utcnow()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        # 1. 规范请求
        body = json.dumps(payload, separators=(",", ":"))
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

        canonical_uri = f"/paapi5/{operation.lower()}"
        canonical_querystring = ""
        canonical_headers = (
            f"content-encoding:amz-1.0\n"
            f"host:{self.endpoint}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:com.amazon.paapi5.{operation}ApiRequest\n"
        )
        signed_headers = "content-encoding;host;x-amz-date;x-amz-target"

        canonical_request = (
            f"POST\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{body_hash}"
        )

        # 2. 待签字符串
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/{SERVICE_NAME}/aws4_request"
        canonical_request_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

        string_to_sign = (
            f"{algorithm}\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{canonical_request_hash}"
        )

        # 3. 签名
        signing_key = self._get_signature_key(date_stamp)
        signature = hmac.HMAC(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        # 4. 构建 Authorization 头
        authorization_header = (
            f"{algorithm} "
            f"Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        headers = {
            "Content-Encoding": "amz-1.0",
            "Content-Type": "application/json; charset=utf-8",
            "Host": self.endpoint,
            "X-Amz-Date": amz_date,
            "X-Amz-Target": f"com.amazon.paapi5.{operation}ApiRequest",
            "Authorization": authorization_header,
        }

        return headers, body

    # ---- API 调用 ----

    async def _call_api(self, operation: str, payload: dict) -> Optional[Dict[str, Any]]:
        """
        调用 PAAPI 接口
        """
        headers, body = self._build_signed_request(operation, payload)

        url = f"{self.base_url}/{operation.lower()}"

        for attempt in range(self.max_retry):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, headers=headers, content=body)

                if response.status_code == 200:
                    return response.json()

                elif response.status_code == 429:
                    logger.warning(f"[AmazonPAAPI] Rate limited (attempt {attempt + 1}/{self.max_retry})")
                    if attempt < self.max_retry - 1:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)  # 指数退避
                    continue

                else:
                    error_body = response.text[:500]
                    logger.error(f"[AmazonPAAPI] API error {response.status_code}: {error_body}")
                    return None

            except Exception as e:
                logger.error(f"[AmazonPAAPI] Request failed (attempt {attempt + 1}/{self.max_retry}): {e}")
                if attempt < self.max_retry - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                continue

        logger.error(f"[AmazonPAAPI] All {self.max_retry} attempts failed for {operation}")
        return None

    # ---- 缓存 ----

    def _get_cache_key(self, operation: str, params: dict) -> str:
        return f"{operation}:{json.dumps(params, sort_keys=True)}"

    def _get_from_cache(self, key: str) -> Optional[Any]:
        if key in self._cache:
            entry = self._cache[key]
            # 检查是否过期
            from datetime import timedelta
            if datetime.now() - entry["time"] < timedelta(hours=self.cache_ttl_hours):
                return entry["data"]
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any):
        self._cache[key] = {
            "data": data,
            "time": datetime.now()
        }

    # ---- 公开 API 方法 ----

    async def search_items(
        self,
        keywords: str,
        category: str = "All",
        max_results: int = 10,
        sort_by: str = "Relevance",
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        condition: str = "New",
        min_reviews: Optional[int] = None,
        min_rating: Optional[float] = None,
        browse_node: Optional[str] = None,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        搜索商品
        """
        params = {
            "Keywords": keywords,
            "SearchIndex": category,
            "ItemCount": max_results,
            "SortBy": sort_by,
            "Resources": [
                "Images.Primary.Medium",
                "Images.Primary.Large",
                "ItemInfo.Title",
                "ItemInfo.Features",
                "ItemInfo.ProductInfo",
                "ItemInfo.ByLineInfo",
                "ItemInfo.Classifications",
                "ItemInfo.ManufactureInfo",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
                "Offers.Listings.Availability",
                "Offers.Listings.IsPrimeExclusive",
                "Offers.Summaries.HighestPrice",
                "Offers.Summaries.LowestPrice",
                "ParentASIN",
                "BrowseNodeInfo.BrowseNodes",
                "BrowseNodeInfo.WebsiteSalesRank",
            ],
            "PartnerTag": self.associate_tag,
            "PartnerType": self.partner_type,
            "Marketplace": self.marketplace,
        }

        if browse_node:
            params["BrowseNodeId"] = browse_node
        if condition and condition != "All":
            params["ItemCondition"] = condition
        if min_price is not None:
            params["MinPrice"] = min_price
        if max_price is not None:
            params["MaxPrice"] = max_price
        if min_rating is not None:
            params["MinReviewsRating"] = min_rating
        if min_reviews is not None:
            params["MinReviewsCount"] = min_reviews

        cache_key = self._get_cache_key("searchitems", params)
        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.info(f"[AmazonPAAPI] Cache hit for search: {keywords}")
                return cached

        result = await self._call_api("searchitems", params)
        if result and use_cache:
            self._set_cache(cache_key, result)

        return result

    async def get_items(
        self,
        asins: List[str],
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        获取商品详情（最多 10 个 ASIN）
        """
        if len(asins) > 10:
            asins = asins[:10]

        params = {
            "ItemIds": asins,
            "Resources": [
                "Images.Primary.Medium",
                "Images.Primary.Large",
                "ItemInfo.Title",
                "ItemInfo.Features",
                "ItemInfo.ProductInfo",
                "ItemInfo.ByLineInfo",
                "ItemInfo.Classifications",
                "ItemInfo.ManufactureInfo",
                "ItemInfo.TradeInInfo",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
                "Offers.Listings.Availability",
                "Offers.Listings.IsPrimeExclusive",
                "Offers.Listings.MerchantInfo",
                "Offers.Summaries.HighestPrice",
                "Offers.Summaries.LowestPrice",
                "Offers.Summaries.OfferCount",
                "ParentASIN",
                "BrowseNodeInfo.BrowseNodes",
                "BrowseNodeInfo.WebsiteSalesRank",
                "CustomerReviews.Count",
                "CustomerReviews.StarRating",
            ],
            "PartnerTag": self.associate_tag,
            "PartnerType": self.partner_type,
            "Marketplace": self.marketplace,
        }

        cache_key = self._get_cache_key("getitems", params)
        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.info(f"[AmazonPAAPI] Cache hit for items: {asins}")
                return cached

        result = await self._call_api("getitems", params)
        if result and use_cache:
            self._set_cache(cache_key, result)

        return result

    async def get_variations(
        self,
        asin: str,
        max_results: int = 10,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        获取商品变体
        """
        params = {
            "ASIN": asin,
            "VariationCount": max_results,
            "Resources": [
                "Images.Primary.Medium",
                "Images.Primary.Large",
                "ItemInfo.Title",
                "ItemInfo.Features",
                "ItemInfo.ProductInfo",
                "Offers.Listings.Price",
                "Offers.Listings.Availability",
                "BrowseNodeInfo.BrowseNodes",
                "BrowseNodeInfo.WebsiteSalesRank",
                "VariationSummary.Price.HighestPrice",
                "VariationSummary.Price.LowestPrice",
                "VariationSummary.VariationDimension",
            ],
            "PartnerTag": self.associate_tag,
            "PartnerType": self.partner_type,
            "Marketplace": self.marketplace,
        }

        cache_key = self._get_cache_key("getvariations", params)
        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.info(f"[AmazonPAAPI] Cache hit for variations: {asin}")
                return cached

        result = await self._call_api("getvariations", params)
        if result and use_cache:
            self._set_cache(cache_key, result)

        return result

    async def browse_node_lookup(
        self,
        browse_node_id: str,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        浏览节点查询（获取分类信息）
        """
        params = {
            "BrowseNodeIds": [browse_node_id],
            "LanguagesOfPreference": ["en_US"],
            "Resources": [
                "BrowseNodes.Ancestor",
                "BrowseNodes.Children",
                "BrowseNodes.SalesRank",
            ],
            "PartnerTag": self.associate_tag,
            "PartnerType": self.partner_type,
            "Marketplace": self.marketplace,
        }

        cache_key = self._get_cache_key("browsenodelookup", params)
        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.info(f"[AmazonPAAPI] Cache hit for browse node: {browse_node_id}")
                return cached

        result = await self._call_api("browsenodelookup", params)
        if result and use_cache:
            self._set_cache(cache_key, result)

        return result

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("[AmazonPAAPI] Cache cleared")