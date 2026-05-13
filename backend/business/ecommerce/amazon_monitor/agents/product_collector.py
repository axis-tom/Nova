"""
商品采集 Agent - Amazon 监控场景
对应文章第2步：商品数据采集

职责：
1. 接收扩展后的关键词列表
2. 调用 Amazon PAAPI 搜索商品
3. 获取商品详情（价格、BSR、评分等）
4. 去重、过滤、整理商品数据
5. 输出结构化商品列表
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.common.core.agent import Agent
from backend.common.core.state import State
from backend.foundation.perception.connectors.amazon.models import AmazonProduct, AmazonSearchResult
from backend.utils.logger import logger


class ProductCollectorAgent(Agent):
    """
    商品采集 Agent
    通过 Amazon PAAPI 搜索并采集商品数据
    """

    name = "product_collector"
    description = "Amazon 商品采集 Agent，通过 PAAPI 搜索并采集商品数据"

    def run(self, state: State) -> State:
        """
        执行商品采集（同步入口，内部调用异步）

        输入（从 state 读取）：
          - expanded_keywords: List[str] 扩展后的关键词
          - max_results_per_keyword: int 每个关键词最大结果数（默认10）
          - sort_by: str 排序方式（默认 Relevance）
          - condition: str 商品状态（默认 New）

        输出（写入 state）：
          - collected_products: List[dict] 采集到的商品列表
          - product_map: Dict[str, dict] ASIN → 商品详情映射
          - collection_stats: dict 采集统计信息
        """
        state.add_event("product_collector_start")
        logger.info("[ProductCollector] Starting product collection")

        try:
            result = asyncio.get_event_loop().run_until_complete(
                self._async_run(state)
            )
            return result
        except RuntimeError:
            # 如果没有事件循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._async_run(state))
            finally:
                loop.close()

    async def _async_run(self, state: State) -> State:
        """异步执行商品采集"""
        try:
            # 读取输入参数
            keywords: List[str] = state.get("expanded_keywords", [])
            max_results: int = state.get("max_results_per_keyword", 10)
            sort_by: str = state.get("sort_by", "Relevance")
            condition: str = state.get("condition", "New")

            if not keywords:
                logger.warning("[ProductCollector] No keywords provided")
                state.set("collected_products", [])
                state.set("product_map", {})
                state.set("collection_stats", {"total": 0, "keywords_searched": 0})
                state.add_event("product_collector_no_keywords")
                return state

            # 限制关键词数量（避免 API 配额超限）
            keywords_to_search = keywords[:10]
            logger.info(f"[ProductCollector] Searching {len(keywords_to_search)} keywords")

            # 导入工具（延迟导入避免循环依赖）
            from backend.business.ecommerce.amazon_monitor.tools.amazon_api import get_product_search
            searcher = get_product_search()

            # 并发搜索（限制并发数为3，避免 API 限流）
            all_products: Dict[str, AmazonProduct] = {}
            keyword_results: Dict[str, int] = {}
            failed_keywords: List[str] = []

            semaphore = asyncio.Semaphore(3)

            async def search_one(keyword: str):
                async with semaphore:
                    try:
                        result: AmazonSearchResult = await searcher.search(
                            keywords=keyword,
                            max_results=max_results,
                            sort_by=sort_by,
                            condition=condition,
                            use_cache=True,
                        )
                        count = len(result.products)
                        keyword_results[keyword] = count
                        for product in result.products:
                            if product.asin not in all_products:
                                all_products[product.asin] = product
                        logger.info(f"[ProductCollector] '{keyword}': {count} products")
                    except Exception as e:
                        logger.error(f"[ProductCollector] Failed to search '{keyword}': {e}")
                        failed_keywords.append(keyword)
                        keyword_results[keyword] = 0

            # 执行并发搜索
            await asyncio.gather(*[search_one(kw) for kw in keywords_to_search])

            # 序列化商品数据（Pydantic → dict）
            products_list = []
            product_map = {}
            for asin, product in all_products.items():
                product_dict = self._serialize_product(product)
                products_list.append(product_dict)
                product_map[asin] = product_dict

            # 按 BSR 排名排序（BSR 越小越好）
            products_list.sort(
                key=lambda p: p.get("bsr_rank", 999999) if p.get("bsr_rank") else 999999
            )

            # 统计信息
            collection_stats = {
                "total": len(products_list),
                "unique_asins": len(all_products),
                "keywords_searched": len(keywords_to_search),
                "keywords_succeeded": len(keywords_to_search) - len(failed_keywords),
                "keywords_failed": len(failed_keywords),
                "failed_keywords": failed_keywords,
                "keyword_results": keyword_results,
                "collected_at": datetime.now().isoformat(),
            }

            # 写入结果
            state.set("collected_products", products_list)
            state.set("product_map", product_map)
            state.set("collection_stats", collection_stats)
            state.set_meta("products_collected", len(products_list))

            logger.info(
                f"[ProductCollector] Collected {len(products_list)} unique products "
                f"from {len(keywords_to_search)} keywords"
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

    def _serialize_product(self, product: AmazonProduct) -> Dict[str, Any]:
        """将 AmazonProduct 序列化为可存储的 dict"""
        return {
            "asin": product.asin,
            "title": product.title,
            "url": product.url,
            "image_url": product.image_url,
            "brand": product.brand,
            "category": product.category,
            "price": product.price.amount if product.price else None,
            "price_display": product.price.display_amount if product.price else None,
            "currency": product.price.currency if product.price else "USD",
            "is_prime": product.price.is_prime if product.price else False,
            "rating": product.rating.overall_rating if product.rating else None,
            "review_count": product.rating.total_reviews if product.rating else 0,
            "bsr_rank": product.bsr.rank if product.bsr else None,
            "bsr_category": product.bsr.category if product.bsr else None,
            "feature_bullets": product.feature_bullets[:3] if product.feature_bullets else [],
            "availability": product.availability,
            "fetched_at": product.fetched_at.isoformat() if product.fetched_at else None,
        }
