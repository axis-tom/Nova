"""
Amazon 商品搜索模块
封装 PAAPI SearchItems 操作，返回结构化搜索结果
"""
import logging
from typing import Optional, List, Dict, Any

from backend.connectors.amazon.client import AmazonPAAPIClient
from backend.connectors.amazon.models import (
    AmazonProduct, AmazonSearchResult, AmazonPrice, AmazonRating, AmazonBSR
)
from backend.utils.logger import logger


class AmazonProductSearch:
    """亚马逊商品搜索"""

    def __init__(self, client: AmazonPAAPIClient):
        self.client = client

    async def search(
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
    ) -> AmazonSearchResult:
        """
        搜索商品并返回结构化结果
        """
        logger.info(f"[AmazonProductSearch] Searching: '{keywords}' in '{category}'")

        raw_result = await self.client.search_items(
            keywords=keywords,
            category=category,
            max_results=max_results,
            sort_by=sort_by,
            min_price=min_price,
            max_price=max_price,
            condition=condition,
            min_reviews=min_reviews,
            min_rating=min_rating,
            browse_node=browse_node,
            use_cache=use_cache,
        )

        if not raw_result:
            logger.warning(f"[AmazonProductSearch] No results for '{keywords}'")
            return AmazonSearchResult()

        return self._parse_search_result(raw_result, keywords)

    def _parse_search_result(self, raw: Dict[str, Any], keywords: str) -> AmazonSearchResult:
        """解析 PAAPI 搜索结果"""
        result = AmazonSearchResult(search_url=f"https://{self.client.marketplace}/s?k={keywords}")

        # 解析总数
        search_info = raw.get("SearchResult", {})
        result.total_results = search_info.get("TotalResultCount", 0)
        result.total_pages = search_info.get("TotalPages", 0)

        # 解析商品列表
        items = search_info.get("Items", [])
        for item in items:
            product = self._parse_item(item)
            if product:
                result.products.append(product)

        logger.info(f"[AmazonProductSearch] Found {len(result.products)} products for '{keywords}'")
        return result

    def _parse_item(self, item: Dict[str, Any]) -> Optional[AmazonProduct]:
        """解析单个商品项"""
        try:
            asin = item.get("ASIN", "")
            if not asin:
                return None

            item_info = item.get("ItemInfo", {})
            offers = item.get("Offers", {})
            images = item.get("Images", {})
            browse_info = item.get("BrowseNodeInfo", {})
            customer_reviews = item.get("CustomerReviews", {})

            # 标题
            title = ""
            title_info = item_info.get("Title", {})
            if title_info:
                title = title_info.get("Value", "")

            # 价格
            price = None
            listings = offers.get("Listings", [])
            if listings:
                price_info = listings[0].get("Price", {})
                if price_info:
                    price = AmazonPrice(
                        amount=price_info.get("Amount", 0),
                        currency=price_info.get("Currency", "USD"),
                        display_amount=price_info.get("DisplayAmount", ""),
                        is_prime=listings[0].get("IsPrimeExclusive", False),
                    )
                    # 优惠信息
                    saving = listings[0].get("SavingBasis", {})
                    if saving:
                        price.savings = saving.get("Amount", 0)
                        price.savings_percent = saving.get("Percentage", 0)

            # 评分
            rating = None
            star_rating = customer_reviews.get("StarRating", {})
            review_count = customer_reviews.get("Count", 0)
            if star_rating:
                rating = AmazonRating(
                    overall_rating=star_rating.get("Value", 0) if isinstance(star_rating, dict) else 0,
                    total_reviews=review_count if isinstance(review_count, (int, float)) else 0,
                )

            # BSR
            bsr = None
            sales_rank = browse_info.get("WebsiteSalesRank", {})
            if sales_rank:
                bsr = AmazonBSR(
                    rank=sales_rank.get("Value", 0) if isinstance(sales_rank, dict) else 0,
                    category=sales_rank.get("DisplayName", "") if isinstance(sales_rank, dict) else "",
                )

            # 图片
            image_url = ""
            image_url_large = ""
            primary_image = images.get("Primary", {})
            if primary_image:
                medium = primary_image.get("Medium", {})
                large = primary_image.get("Large", {})
                if medium:
                    image_url = medium.get("URL", "")
                if large:
                    image_url_large = large.get("URL", "")

            # 分类
            category = ""
            category_tree = []
            browse_nodes = browse_info.get("BrowseNodes", [])
            if browse_nodes:
                first_node = browse_nodes[0]
                category = first_node.get("DisplayName", "")
                # 构建分类树
                ancestor = first_node.get("Ancestor")
                while ancestor:
                    category_tree.append({
                        "id": ancestor.get("Id", ""),
                        "name": ancestor.get("DisplayName", ""),
                    })
                    ancestor = ancestor.get("Ancestor")

            # 品牌和制造商
            by_line = item_info.get("ByLineInfo", {})
            brand = by_line.get("Brand", {}).get("Value", "") if isinstance(by_line.get("Brand"), dict) else ""
            manufacturer = by_line.get("Manufacturer", {}).get("Value", "") if isinstance(by_line.get("Manufacturer"), dict) else ""

            # 产品信息
            product_info = item_info.get("ProductInfo", {})
            dimensions = ""
            weight = ""
            if product_info:
                dims = product_info.get("Dimensions", {})
                if dims:
                    dimensions = f"{dims.get('Height', '')}x{dims.get('Width', '')}x{dims.get('Length', '')} {dims.get('Unit', '')}"
                wt = product_info.get("ItemWeight", {})
                if wt:
                    weight = f"{wt.get('Value', '')} {wt.get('Unit', '')}"

            # 特性
            features = item_info.get("Features", {})
            feature_bullets = features.get("DisplayValues", []) if isinstance(features, dict) else []

            # 分类信息
            classifications = item_info.get("Classifications", {})
            binding = classifications.get("Binding", {}).get("Value", "") if isinstance(classifications.get("Binding"), dict) else ""

            product = AmazonProduct(
                asin=asin,
                title=title,
                url=f"https://{self.client.marketplace}/dp/{asin}",
                image_url=image_url,
                image_url_large=image_url_large,
                feature_bullets=feature_bullets,
                price=price,
                rating=rating,
                bsr=bsr,
                brand=brand,
                manufacturer=manufacturer,
                category=category or binding,
                category_tree=category_tree,
                dimensions=dimensions,
                weight=weight,
                availability=listings[0].get("Availability", {}).get("Message", "") if listings else "",
            )

            return product

        except Exception as e:
            logger.error(f"[AmazonProductSearch] Error parsing item: {e}")
            return None

    async def search_by_category(
        self,
        browse_node_id: str,
        max_results: int = 10,
        sort_by: str = "Relevance",
        use_cache: bool = True,
    ) -> AmazonSearchResult:
        """按分类浏览节点搜索"""
        logger.info(f"[AmazonProductSearch] Browsing category node: {browse_node_id}")

        # 先获取分类信息
        node_info = await self.client.browse_node_lookup(browse_node_id, use_cache=use_cache)

        # 搜索该分类下的商品
        raw_result = await self.client.search_items(
            keywords="",
            browse_node=browse_node_id,
            max_results=max_results,
            sort_by=sort_by,
            use_cache=use_cache,
        )

        if not raw_result:
            return AmazonSearchResult()

        return self._parse_search_result(raw_result, f"category:{browse_node_id}")