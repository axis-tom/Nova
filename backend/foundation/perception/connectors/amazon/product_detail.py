"""
Amazon 商品详情模块
封装 PAAPI GetItems 操作，返回结构化商品详情
"""
from typing import Optional, List, Dict, Any

from backend.foundation.perception.connectors.amazon.client import AmazonPAAPIClient
from backend.foundation.perception.connectors.amazon.models import (
    AmazonProduct, AmazonPrice, AmazonRating, AmazonBSR
)
from backend.utils.logger import logger


class AmazonProductDetail:
    """亚马逊商品详情查询"""

    def __init__(self, client: AmazonPAAPIClient):
        self.client = client

    async def get_product(self, asin: str, use_cache: bool = True) -> Optional[AmazonProduct]:
        """
        获取单个商品详情
        """
        logger.info(f"[AmazonProductDetail] Fetching product: {asin}")
        return await self.get_products([asin], use_cache=use_cache)

    async def get_products(
        self,
        asins: List[str],
        use_cache: bool = True,
    ) -> Optional[AmazonProduct]:
        """
        获取多个商品详情（最多 10 个）
        如果只查一个 ASIN 返回单个对象，多个返回列表
        """
        logger.info(f"[AmazonProductDetail] Fetching products: {asins}")

        raw_result = await self.client.get_items(asins, use_cache=use_cache)

        if not raw_result:
            logger.warning(f"[AmazonProductDetail] No results for: {asins}")
            return None

        items = raw_result.get("ItemsResult", {}).get("Items", [])
        if not items:
            logger.warning(f"[AmazonProductDetail] Empty items in response for: {asins}")
            return None

        products = []
        for item in items:
            product = self._parse_item(item)
            if product:
                products.append(product)

        if not products:
            return None

        # 如果只查一个 ASIN，返回单个对象
        if len(asins) == 1:
            return products[0]

        return products

    def _parse_item(self, item: Dict[str, Any]) -> Optional[AmazonProduct]:
        """解析单个商品详情"""
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
                    saving = listings[0].get("SavingBasis", {})
                    if saving:
                        price.savings = saving.get("Amount", 0)
                        price.savings_percent = saving.get("Percentage", 0)

            # 评分
            rating = None
            star_rating = customer_reviews.get("StarRating", {})
            review_count = customer_reviews.get("Count", 0)
            if star_rating:
                rating_value = star_rating.get("Value", 0) if isinstance(star_rating, dict) else 0
                rating = AmazonRating(
                    overall_rating=float(rating_value),
                    total_reviews=int(review_count) if isinstance(review_count, (int, float)) else 0,
                )

            # BSR
            bsr = None
            sales_rank = browse_info.get("WebsiteSalesRank", {})
            if sales_rank:
                bsr = AmazonBSR(
                    rank=int(sales_rank.get("Value", 0)) if isinstance(sales_rank, dict) else 0,
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

            # 描述
            description = ""
            editorial_reviews = item_info.get("EditorialReviews", {})
            if editorial_reviews:
                reviews_list = editorial_reviews.get("DisplayValues", [])
                if reviews_list:
                    description = reviews_list[0] if isinstance(reviews_list, list) else ""

            # 变体信息
            variations = []
            variation_result = item.get("Variations", {})
            if variation_result:
                variation_items = variation_result.get("Items", [])
                for var_item in variation_items:
                    var_asin = var_item.get("ASIN", "")
                    var_title = var_item.get("ItemInfo", {}).get("Title", {}).get("Value", "")
                    var_price_info = var_item.get("Offers", {}).get("Listings", [{}])[0].get("Price", {})
                    variations.append({
                        "asin": var_asin,
                        "title": var_title,
                        "price": var_price_info.get("Amount", 0),
                        "currency": var_price_info.get("Currency", "USD"),
                        "display_amount": var_price_info.get("DisplayAmount", ""),
                    })

            product = AmazonProduct(
                asin=asin,
                title=title,
                url=f"https://{self.client.marketplace}/dp/{asin}",
                image_url=image_url,
                image_url_large=image_url_large,
                feature_bullets=feature_bullets,
                description=description,
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
                variations=variations,
            )

            return product

        except Exception as e:
            logger.error(f"[AmazonProductDetail] Error parsing item {item.get('ASIN', '')}: {e}")
            return None