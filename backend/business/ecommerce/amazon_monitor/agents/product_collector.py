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
from backend.business.ecommerce.amazon_monitor.tools.keepa_connector import (
    KeepaError,
    KeepaConfigError,
    KeepaQuotaError,
    KeepaRejectedError,
    KeepaNetworkError,
)

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


def _set_error(
    state: State,
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    把 Keepa / 其他错误统一写到 state，供 agent_wrapper 暴露给 LLM。

    Args:
        state: Agent 共享的状态对象
        error_type: keepa_config / keepa_quota / keepa_rejected / keepa_network /
                    keepa_other / unexpected
        message: 人类可读的错误消息（LLM 会用它生成回复）
        details: 结构化字段，如 retry_after_minutes / status_code
    """
    state.set("error", message)
    state.set("error_type", error_type)
    state.set("error_details", details or {})
    # 保持下游兼容：失败时仍写空集合
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
    商品采集 Agent
    纯 Keepa 模式：关键词搜索 ASIN + 批量查询历史数据
    """

    name = "product_collector"
    description = "Amazon 商品采集 Agent，基于 Keepa 历史数据"

    async def run(self, state: State) -> State:
        """
        执行商品采集

        输入（从 state 读取）：
          - watchlist_asins: List[str]  **推荐**：用户/LLM 直接传 ASIN 列表，
                                        跳过烧钱的 /search 端点（Pro 套餐 10 token/次还常返空）
          - expanded_keywords: List[str] 关键词列表（兼容旧入口）
          - allow_keyword_search: bool   显式允许走 keyword → /search 路径，默认 False。
                                        仅在没有 ASIN 来源、且确认套餐 /search 有效时打开
          - max_results_per_keyword: int 每个关键词最大结果数（默认10，仅 search 模式）
          - domain: str 市场（默认 US）

        输出（写入 state）：
          - collected_products: List[dict] 采集到的商品列表（含历史数据）
          - product_map: Dict[str, dict] ASIN → 商品详情映射
          - collection_stats: dict 采集统计信息 (含 asin_source: watchlist | keyword_search)
          - error / error_type / error_details: 失败时填充
        """
        state.add_event("product_collector_start")
        logger.info("[ProductCollector] Starting product collection (Keepa only)")
        return await self._async_run(state)

    async def _async_run(self, state: State) -> State:
        """异步执行商品采集"""
        try:
            # 读取输入参数
            watchlist_asins: List[str] = state.get("watchlist_asins", []) or []
            keywords: List[str] = state.get("expanded_keywords", []) or []
            allow_keyword_search: bool = bool(state.get("allow_keyword_search", False))
            max_results: int = state.get("max_results_per_keyword", 10)
            domain: str = state.get("domain", "US")

            keepa = self._get_keepa()
            if not keepa:
                _set_error(
                    state,
                    "keepa_config",
                    "Keepa API 未配置：请在 backend/config/.env 中设置 KEEPA_API_KEY",
                )
                return state

            # ── 决定 ASIN 来源 ──
            all_asins: List[str] = []
            keyword_asin_map: Dict[str, List[str]] = {}
            failed_keywords: List[str] = []
            filtered_keywords: List[str] = []
            asin_source: str  # "watchlist" | "keyword_search"

            if watchlist_asins:
                # 模式 A: 用户直接传 ASIN，跳过 /search 省 token
                all_asins = [a.strip() for a in watchlist_asins if a and a.strip()]
                asin_source = "watchlist"
                logger.info(
                    f"[ProductCollector] Using watchlist_asins: {len(all_asins)} ASINs "
                    f"(直接走 /product，省 /search 的 10 token/次)"
                )
                if keywords:
                    logger.warning(
                        "[ProductCollector] 同时传入了 watchlist_asins 和 expanded_keywords; "
                        "优先使用 watchlist_asins，忽略 keywords"
                    )

            elif allow_keyword_search and keywords:
                # 模式 B: 显式允许走 keyword → /search（Pro 套餐烧 10 token/次，慎用）
                asin_source = "keyword_search"
                filtered_keywords = _filter_keywords(keywords)[:5]
                logger.warning(
                    f"[ProductCollector] keyword search 模式 "
                    f"({len(filtered_keywords)} keywords × 10 token = ~{len(filtered_keywords)*10} token)"
                )
                all_asins, keyword_asin_map, failed_keywords = await self._search_by_keywords(
                    keepa, filtered_keywords, domain, max_results,
                )
            else:
                # 模式 C: 既没 ASIN 又没显式开搜词 → 给清楚的提示
                _set_error(
                    state,
                    "no_input",
                    (
                        "ProductCollector 需要明确的 ASIN 来源：\n"
                        "  - 推荐：在 state 设 watchlist_asins=['B0XXXXXXXX', ...] 直接查商品（每 ASIN 1 token）\n"
                        "  - 或显式 allow_keyword_search=True + expanded_keywords 走 /search "
                        "(Pro 套餐每次烧 10 token 且常返空，不推荐)"
                    ),
                )
                return state

            # ── 拉历史数据（/product 端点，最多 100/批）──
            keepa_products: Dict[str, Dict] = {}
            if all_asins:
                logger.info(f"[ProductCollector] Keepa /product querying {len(all_asins)} ASINs")
                for i in range(0, len(all_asins), 100):
                    batch = all_asins[i:i + 100]
                    products = await keepa.async_query_products(batch, domain=domain, stats=180)
                    for p in products:
                        keepa_products[p["asin"]] = p
                logger.info(
                    f"[ProductCollector] Keepa returned {len(keepa_products)}/{len(all_asins)} products"
                )

            # ── 整理商品列表 ──
            products_list = []
            product_map = {}
            for asin in all_asins:
                product = keepa_products.get(asin)
                if product:
                    product["collected_at"] = datetime.now().isoformat()
                    products_list.append(product)
                    product_map[asin] = product

            # 按 BSR 排序（BSR 越小越好）
            products_list.sort(key=lambda p: p.get("current_bsr") or 999999)

            # 统计信息
            collection_stats = {
                "total": len(products_list),
                "unique_asins": len(all_asins),
                "asin_source": asin_source,
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
                f"(source={asin_source}, Keepa: {len(keepa_products)})"
            )
            state.add_event(
                f"product_collector_success: {len(products_list)} products from {asin_source}"
            )

        except KeepaConfigError as e:
            logger.error(f"[ProductCollector] Keepa config error: {e}")
            _set_error(state, "keepa_config", str(e))
        except KeepaQuotaError as e:
            logger.warning(f"[ProductCollector] Keepa quota exhausted: {e}")
            _set_error(
                state,
                "keepa_quota",
                str(e),
                {"retry_after_minutes": e.retry_after_minutes},
            )
        except KeepaRejectedError as e:
            logger.error(f"[ProductCollector] Keepa rejected: {e}")
            _set_error(
                state,
                "keepa_rejected",
                str(e),
                {
                    "status_code": e.status_code,
                    "body": (e.body or "")[:300],
                },
            )
        except KeepaNetworkError as e:
            logger.error(f"[ProductCollector] Keepa network error: {e}")
            _set_error(state, "keepa_network", str(e))
        except KeepaError as e:
            logger.error(f"[ProductCollector] Keepa unspecified error: {e}")
            _set_error(state, "keepa_other", str(e))
        except Exception as e:
            logger.error(f"[ProductCollector] Unexpected error: {e}")
            _set_error(state, "unexpected", str(e))

        return state

    # ── 内部辅助方法 ──

    async def _search_by_keywords(
        self,
        keepa,
        filtered_keywords: List[str],
        domain: str,
        max_results: int,
    ):
        """
        通过 keyword → /search 拿 ASIN 列表（兼容旧入口）。
        ⚠️ Pro 套餐每次烧 10 token，且常返空，仅在 allow_keyword_search=True 时调。

        Returns:
            (all_asins, keyword_asin_map, failed_keywords)

        Raises:
            KeepaConfigError / KeepaQuotaError —— 致命错，让 outer except 接管
            其它 KeepaError 子类 —— 仅在「全部 keyword 都失败且 0 ASIN」时上抛
        """
        all_asins: List[str] = []
        keyword_asin_map: Dict[str, List[str]] = {}
        failed_keywords: List[str] = []
        last_keyword_error: Optional[KeepaError] = None

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
            except (KeepaConfigError, KeepaQuotaError):
                raise
            except (KeepaRejectedError, KeepaNetworkError, KeepaError) as e:
                logger.warning(
                    f"[ProductCollector] Keepa search '{kw}' failed "
                    f"({type(e).__name__}): {e}"
                )
                failed_keywords.append(kw)
                keyword_asin_map[kw] = []
                last_keyword_error = e
            except Exception as e:
                logger.error(f"[ProductCollector] Keepa search '{kw}' unexpected: {e}")
                failed_keywords.append(kw)
                keyword_asin_map[kw] = []

        # 全部 keyword 都失败且没拿到任何 ASIN —— 上抛分类错误而非默默返回空
        if (
            filtered_keywords
            and len(failed_keywords) == len(filtered_keywords)
            and not all_asins
            and last_keyword_error is not None
        ):
            raise last_keyword_error

        return all_asins, keyword_asin_map, failed_keywords

    def _get_keepa(self):
        """获取 Keepa 连接器（如果未配置则返回 None）"""
        try:
            from backend.business.ecommerce.amazon_monitor.tools.keepa_connector import KeepaConnector
            return KeepaConnector()
        except KeepaConfigError as e:
            logger.warning(f"[ProductCollector] Keepa not configured: {e}")
            return None
        except Exception as e:
            logger.warning(f"[ProductCollector] Keepa init failed: {e}")
            return None
