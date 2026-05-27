"""
Amazon 价格追踪模块
追踪商品价格变化，提供价格趋势分析和竞品比价
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json

from backend.connectors.amazon.client import AmazonPAAPIClient
from backend.connectors.amazon.models import (
    AmazonPrice, AmazonPriceHistory, AmazonProduct, AmazonCompetitor
)
from backend.utils.logger import logger


class AmazonPriceTracker:
    """亚马逊价格追踪器"""

    def __init__(self, client: AmazonPAAPIClient):
        self.client = client
        # 内存中的价格历史记录
        self._price_history: Dict[str, List[Dict[str, Any]]] = {}

    async def track_price(
        self,
        asin: str,
        use_cache: bool = True,
    ) -> Optional[AmazonPriceHistory]:
        """
        追踪商品价格
        获取当前价格并记录到历史
        """
        logger.info(f"[AmazonPriceTracker] Tracking price for: {asin}")

        # 获取商品详情
        product_data = await self.client.get_items([asin], use_cache=use_cache)
        if not product_data:
            logger.warning(f"[AmazonPriceTracker] No product data for: {asin}")
            return None

        items = product_data.get("ItemsResult", {}).get("Items", [])
        if not items:
            return None

        item = items[0]
        item_info = item.get("ItemInfo", {})
        offers = item.get("Offers", {})

        # 获取标题
        title = item_info.get("Title", {}).get("Value", "")

        # 获取当前价格
        current_price = None
        listings = offers.get("Listings", [])
        if listings:
            price_info = listings[0].get("Price", {})
            if price_info:
                current_price = AmazonPrice(
                    amount=price_info.get("Amount", 0),
                    currency=price_info.get("Currency", "USD"),
                    display_amount=price_info.get("DisplayAmount", ""),
                    is_prime=listings[0].get("IsPrimeExclusive", False),
                )

        if not current_price:
            logger.warning(f"[AmazonPriceTracker] No price found for: {asin}")
            return None

        # 记录价格历史
        if asin not in self._price_history:
            self._price_history[asin] = []

        self._price_history[asin].append({
            "price": current_price.amount,
            "timestamp": datetime.now().isoformat(),
        })

        # 分析价格趋势
        history = self._price_history[asin]
        price_history = AmazonPriceHistory(
            asin=asin,
            title=title,
            current_price=current_price,
        )

        # 计算 30 天内的价格统计
        if len(history) >= 2:
            prices_30d = [h["price"] for h in history[-30:]]
            price_history.lowest_price_30d = min(prices_30d)
            price_history.highest_price_30d = max(prices_30d)
            price_history.average_price_30d = sum(prices_30d) / len(prices_30d)

            # 判断趋势
            recent = prices_30d[-3:] if len(prices_30d) >= 3 else prices_30d
            older = prices_30d[:3] if len(prices_30d) >= 6 else prices_30d[:1]

            if recent and older:
                recent_avg = sum(recent) / len(recent)
                older_avg = sum(older) / len(older)

                if recent_avg > older_avg * 1.02:
                    price_history.price_trend = "up"
                elif recent_avg < older_avg * 0.98:
                    price_history.price_trend = "down"
                else:
                    price_history.price_trend = "stable"

        # 记录价格变化
        price_history.price_changes = history[-10:]  # 最近 10 次记录

        logger.info(
            f"[AmazonPriceTracker] Price tracked for {asin}: "
            f"${current_price.amount:.2f}, trend: {price_history.price_trend}"
        )
        return price_history

    async def compare_prices(
        self,
        main_asin: str,
        competitor_asins: List[str],
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        比价分析：主商品 vs 竞品
        """
        logger.info(f"[AmazonPriceTracker] Comparing prices: {main_asin} vs {competitor_asins}")

        all_asins = [main_asin] + competitor_asins
        product_data = await self.client.get_items(all_asins, use_cache=use_cache)

        if not product_data:
            return {"error": "No product data"}

        items = product_data.get("ItemsResult", {}).get("Items", [])
        if not items:
            return {"error": "No items found"}

        # 解析所有商品
        products = {}
        for item in items:
            asin = item.get("ASIN", "")
            item_info = item.get("ItemInfo", {})
            offers = item.get("Offers", {})
            customer_reviews = item.get("CustomerReviews", {})
            browse_info = item.get("BrowseNodeInfo", {})

            title = item_info.get("Title", {}).get("Value", "")
            listings = offers.get("Listings", [])
            price_amount = 0
            if listings:
                price_info = listings[0].get("Price", {})
                price_amount = price_info.get("Amount", 0)

            star_rating = customer_reviews.get("StarRating", {})
            rating = float(star_rating.get("Value", 0)) if isinstance(star_rating, dict) else 0
            review_count = customer_reviews.get("Count", 0)
            if isinstance(review_count, dict):
                review_count = 0

            sales_rank = browse_info.get("WebsiteSalesRank", {})
            bsr_value = int(sales_rank.get("Value", 0)) if isinstance(sales_rank, dict) else 0

            products[asin] = {
                "asin": asin,
                "title": title,
                "price": price_amount,
                "rating": float(rating),
                "review_count": int(review_count) if isinstance(review_count, (int, float)) else 0,
                "bsr": bsr_value,
            }

        # 计算对比指标
        main_product = products.get(main_asin)
        if not main_product:
            return {"error": f"Main product {main_asin} not found"}

        competitors = []
        for comp_asin in competitor_asins:
            comp = products.get(comp_asin)
            if comp and comp["price"] > 0:
                price_diff = main_product["price"] - comp["price"]
                price_diff_pct = round(price_diff / comp["price"] * 100, 1) if comp["price"] > 0 else 0

                competitors.append({
                    "asin": comp["asin"],
                    "title": comp["title"],
                    "price": comp["price"],
                    "price_diff": round(price_diff, 2),
                    "price_diff_pct": price_diff_pct,
                    "is_cheaper": price_diff > 0,
                    "rating": comp["rating"],
                    "review_count": comp["review_count"],
                    "bsr": comp["bsr"],
                })

        # 排序：按价格从低到高
        competitors.sort(key=lambda x: x["price"])

        result = {
            "main_product": main_product,
            "competitors": competitors,
            "summary": {
                "total_competitors": len(competitors),
                "average_competitor_price": round(
                    sum(c["price"] for c in competitors) / len(competitors), 2
                ) if competitors else 0,
                "cheapest_competitor": competitors[0] if competitors else None,
                "main_product_ranking": next(
                    (i + 1 for i, c in enumerate(competitors) if c["price"] > main_product["price"]),
                    len(competitors) + 1
                ) if competitors else 1,
            }
        }

        logger.info(
            f"[AmazonPriceTracker] Price comparison complete: "
            f"{len(competitors)} competitors analyzed"
        )
        return result

    async def get_price_drop_alerts(
        self,
        watchlist: List[str],
        drop_threshold_pct: float = 10.0,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        价格下降提醒
        监控关注列表中的商品，当价格下降超过阈值时发出提醒
        """
        logger.info(f"[AmazonPriceTracker] Checking price drops for {len(watchlist)} items")

        alerts = []
        for asin in watchlist:
            history = await self.track_price(asin, use_cache=use_cache)
            if not history or not history.current_price:
                continue

            # 检查是否有历史价格可对比
            if asin in self._price_history and len(self._price_history[asin]) >= 2:
                prices = [h["price"] for h in self._price_history[asin]]
                if len(prices) >= 2:
                    previous_price = prices[-2]
                    current_price = history.current_price.amount

                    if previous_price > 0:
                        drop_pct = (previous_price - current_price) / previous_price * 100
                        if drop_pct >= drop_threshold_pct:
                            alerts.append({
                                "asin": asin,
                                "title": history.title,
                                "previous_price": previous_price,
                                "current_price": current_price,
                                "drop_pct": round(drop_pct, 1),
                                "timestamp": datetime.now().isoformat(),
                            })
                            logger.info(
                                f"[AmazonPriceTracker] Price drop alert for {asin}: "
                                f"${previous_price:.2f} -> ${current_price:.2f} ({drop_pct:.1f}%)"
                            )

        return alerts

    def get_price_history(self, asin: str) -> List[Dict[str, Any]]:
        """获取指定商品的价格历史"""
        return self._price_history.get(asin, [])

    def clear_price_history(self, asin: Optional[str] = None):
        """清空价格历史"""
        if asin:
            self._price_history.pop(asin, None)
        else:
            self._price_history.clear()