"""
Keepa 数据连接器
基于 Keepa Python SDK，提供亚马逊商品历史数据查询

功能：
  - 关键词搜索 ASIN（Search API）
  - 批量查询商品历史数据（Product API）：BSR历史、价格历史、评论历史、销量估算
  - 获取价格异动商品（Deal API）
  - 数据解析与标准化

使用前提：
  - 在 .env 中配置 KEEPA_API_KEY
  - pip install keepa pandas
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Keepa 时间基准：2011-01-01 00:00 UTC（分钟数）
_KEEPA_EPOCH = datetime(2011, 1, 1, tzinfo=timezone.utc)


def _keepa_minutes_to_dt(minutes: int) -> str:
    """将 Keepa 时间戳（相对于2011-01-01的分钟数）转换为 ISO 字符串"""
    try:
        from datetime import timedelta
        dt = _KEEPA_EPOCH + timedelta(minutes=minutes)
        return dt.isoformat()
    except Exception:
        return ""


def _decode_keepa_csv(csv_data: List[int]) -> List[Dict[str, Any]]:
    """
    解码 Keepa 压缩的时间序列数据
    格式：[timestamp1, value1, timestamp2, value2, ...]
    value=-1 表示无数据
    """
    if not csv_data or len(csv_data) < 2:
        return []
    result = []
    for i in range(0, len(csv_data) - 1, 2):
        ts = csv_data[i]
        val = csv_data[i + 1]
        if val != -1:
            result.append({
                "timestamp": _keepa_minutes_to_dt(ts),
                "value": val / 100 if val > 100 else val,  # 价格单位是美分*100
            })
    return result


class KeepaConnector:
    """
    Keepa 数据连接器
    
    支持同步和异步两种调用方式：
    - 同步：KeepaConnector().search_asins(...)
    - 异步：await KeepaConnector().async_query_products(...)
    """

    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            from backend.config.config import settings
            api_key = settings.KEEPA_API_KEY
        
        if not api_key:
            raise ValueError(
                "KEEPA_API_KEY 未配置。请在 backend/config/.env 中设置 KEEPA_API_KEY=your_key\n"
                "获取 API Key: https://keepa.com/#!api"
            )
        self.api_key = api_key
        self._sync_api = None  # 懒加载

    def _get_sync_api(self):
        """懒加载同步 Keepa API 实例"""
        if self._sync_api is None:
            try:
                import keepa
                self._sync_api = keepa.Keepa(self.api_key)
            except ImportError:
                raise ImportError("请安装 keepa 库：pip install keepa pandas")
        return self._sync_api

    # ── 关键词搜索（Keepa REST API /search 端点）──

    # Keepa domain 字符串 → 数字映射
    _DOMAIN_MAP = {
        "US": 1, "GB": 2, "DE": 3, "FR": 4, "JP": 5,
        "CA": 6, "IT": 8, "ES": 9, "IN": 10, "MX": 11,
        "BR": 12, "AU": 13, "NL": 14, "PL": 15, "SE": 16,
        "BE": 17, "SG": 18, "AE": 19, "SA": 20, "TR": 21,
    }

    def search_asins(
        self,
        keyword: str,
        domain: str = "US",
        max_results: int = 50,
    ) -> List[str]:
        """
        通过关键词搜索 ASIN 列表（调用 Keepa REST API /search 端点）
        
        注意：Keepa Python SDK 不提供关键词搜索，需直接调用 REST API
        
        Args:
            keyword: 搜索关键词，如 "bluetooth earbuds"
            domain: 市场字符串，如 US/DE/JP
            max_results: 最大返回数量
            
        Returns:
            ASIN 列表
        """
        import requests
        domain_id = self._DOMAIN_MAP.get(domain.upper(), 1)
        url = "https://api.keepa.com/search"
        params = {
            "key": self.api_key,
            "domain": domain_id,
            "type": "product",
            "term": keyword,
        }
        try:
            logger.info(f"Keepa REST 关键词搜索: '{keyword}' (domain={domain})")
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            asins = data.get("asinList", []) or []
            result = list(asins[:max_results])
            logger.info(f"Keepa 搜索到 {len(result)} 个 ASIN")
            return result
        except Exception as e:
            logger.error(f"Keepa 搜索失败: {e}")
            return []

    async def async_search_asins(
        self,
        keyword: str,
        domain: str = "US",
        max_results: int = 50,
    ) -> List[str]:
        """异步版关键词搜索（在线程池中运行同步 HTTP 请求）"""
        return await asyncio.to_thread(
            self.search_asins, keyword, domain, max_results
        )

    # ── 商品历史数据查询 ──

    def query_products(
        self,
        asins: List[str],
        domain: str = "US",
        history: bool = True,
        stats: int = 180,
        offers: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        批量查询商品历史数据（最多100个ASIN）
        
        Args:
            asins: ASIN 列表（最多100个）
            domain: 市场
            history: 是否获取历史数据
            stats: 统计周期（天），如 30/90/180
            offers: 获取的 offer 数量
            
        Returns:
            标准化的商品数据列表
        """
        if not asins:
            return []
        
        # Keepa 单次最多100个
        asins = asins[:100]
        api = self._get_sync_api()
        
        try:
            logger.info(f"Keepa 查询 {len(asins)} 个商品历史数据")
            raw_products = api.query(
                asins,
                domain=domain,
                history=history,
                stats=stats,
                offers=offers,
            )
            
            results = []
            for p in raw_products:
                parsed = self._parse_product(p, stats)
                if parsed:
                    results.append(parsed)
            
            logger.info(f"Keepa 成功解析 {len(results)} 个商品")
            return results
            
        except Exception as e:
            logger.error(f"Keepa 查询失败: {e}")
            return []

    async def async_query_products(
        self,
        asins: List[str],
        domain: str = "US",
        history: bool = True,
        stats: int = 180,
    ) -> List[Dict[str, Any]]:
        """异步版商品历史查询"""
        return await asyncio.to_thread(
            self.query_products, asins, domain, history, stats
        )

    # ── 价格异动（Deal API） ──

    def get_deals(
        self,
        domain: str = "US",
        min_rating: int = 30,
        min_reviews: int = 50,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        获取最近价格异动的商品（用于监控告警）
        
        Args:
            domain: 市场
            min_rating: 最低评分（0-50，对应0-5星）
            min_reviews: 最低评论数
            max_results: 最大返回数量
            
        Returns:
            价格异动商品列表
        """
        api = self._get_sync_api()
        try:
            logger.info(f"Keepa 获取价格异动商品 (domain={domain})")
            # Deal API 参数
            deal_params = {
                "page": 0,
                "domainId": self._domain_to_id(domain),
                "excludeCategories": [],
                "includeCategories": [],
                "priceTypes": [0, 1],  # 0=Amazon, 1=New
                "deltaPercent": {"min": 10, "max": 100},  # 降价10%以上
                "current": {"min": 1, "max": 99999},
                "avg": {"min": 1, "max": 99999},
                "rating": {"min": min_rating, "max": 50},
                "reviewCount": {"min": min_reviews, "max": 999999},
            }
            deals = api.deals(deal_params)
            
            results = []
            if deals and "dr" in deals:
                for d in deals["dr"][:max_results]:
                    results.append({
                        "asin": d.get("asin", ""),
                        "title": d.get("title", ""),
                        "current_price": d.get("current", -1) / 100 if d.get("current", -1) > 0 else None,
                        "avg_price": d.get("avg", -1) / 100 if d.get("avg", -1) > 0 else None,
                        "delta_percent": d.get("deltaPercent", 0),
                        "rating": d.get("rating", 0) / 10,
                        "review_count": d.get("reviewCount", 0),
                    })
            
            logger.info(f"Keepa 获取到 {len(results)} 个价格异动商品")
            return results
            
        except Exception as e:
            logger.error(f"Keepa Deal API 失败: {e}")
            return []

    async def async_get_deals(
        self,
        domain: str = "US",
        min_rating: int = 30,
        min_reviews: int = 50,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """异步版价格异动查询"""
        return await asyncio.to_thread(
            self.get_deals, domain, min_rating, min_reviews, max_results
        )

    # ── 数据解析 ──

    def _parse_product(self, p: Dict, stats_days: int = 180) -> Optional[Dict[str, Any]]:
        """
        将 Keepa 原始商品数据解析为标准化格式
        
        标准化字段：
        - asin, title, brand, category
        - current_price, avg_price_30d, avg_price_90d, min_price_90d, max_price_90d
        - current_bsr, avg_bsr_30d, avg_bsr_90d, bsr_trend（上升/下降/稳定）
        - monthly_sold（月销量估算）
        - review_count, rating
        - new_offer_count（卖家数量）
        - price_history, bsr_history（最近N条历史点）
        """
        try:
            asin = p.get("asin", "")
            if not asin:
                return None

            # ── 基础信息 ──
            title = p.get("title", "")
            brand = p.get("brand", "")
            
            # 类目
            categories = p.get("categories", [])
            category = categories[0] if categories else 0

            # ── 价格数据 ──
            stats = p.get("stats", {}) or {}
            
            # 当前价格（Amazon 官方价，单位：美分）
            current_price_raw = p.get("csv", [None] * 20)
            amazon_csv = current_price_raw[0] if len(current_price_raw) > 0 else None
            current_price = None
            if amazon_csv and len(amazon_csv) >= 2:
                last_price = amazon_csv[-1]
                if last_price > 0:
                    current_price = last_price / 100

            # 统计摘要（stats 字段）
            avg_price_30d = None
            avg_price_90d = None
            min_price_90d = None
            max_price_90d = None
            
            if stats:
                # stats 结构：{"avg": [30d_avg, 90d_avg, 180d_avg, ...], ...}
                avg_list = stats.get("avg", [])
                if len(avg_list) > 0 and avg_list[0] > 0:
                    avg_price_30d = avg_list[0] / 100
                if len(avg_list) > 1 and avg_list[1] > 0:
                    avg_price_90d = avg_list[1] / 100
                
                min_list = stats.get("min", [])
                max_list = stats.get("max", [])
                if len(min_list) > 1 and min_list[1] > 0:
                    min_price_90d = min_list[1] / 100
                if len(max_list) > 1 and max_list[1] > 0:
                    max_price_90d = max_list[1] / 100

            # ── BSR（Best Seller Rank）数据 ──
            # csv[11] = SALES (BSR)
            csv_data = p.get("csv", [])
            bsr_csv = csv_data[11] if len(csv_data) > 11 else None
            
            current_bsr = None
            avg_bsr_30d = None
            avg_bsr_90d = None
            bsr_trend = "unknown"
            
            if bsr_csv and len(bsr_csv) >= 2:
                # 当前 BSR（最后一个有效值）
                for i in range(len(bsr_csv) - 1, -1, -2):
                    if i >= 1 and bsr_csv[i] > 0:
                        current_bsr = bsr_csv[i]
                        break
                
                # BSR 趋势分析（比较最近30天均值 vs 前30天均值）
                bsr_trend = self._calc_bsr_trend(bsr_csv)
            
            # BSR 统计摘要
            if stats:
                bsr_stats = stats.get("salesRankAvg", [])
                if len(bsr_stats) > 0 and bsr_stats[0] > 0:
                    avg_bsr_30d = bsr_stats[0]
                if len(bsr_stats) > 1 and bsr_stats[1] > 0:
                    avg_bsr_90d = bsr_stats[1]

            # ── 销量估算 ──
            monthly_sold = p.get("monthlySold", 0) or 0

            # ── 评论数据 ──
            # csv[16] = RATING, csv[17] = COUNT_REVIEWS
            rating_csv = csv_data[16] if len(csv_data) > 16 else None
            review_csv = csv_data[17] if len(csv_data) > 17 else None
            
            current_rating = None
            current_reviews = 0
            
            if rating_csv and len(rating_csv) >= 2:
                last_rating = rating_csv[-1]
                if last_rating > 0:
                    current_rating = last_rating / 10  # Keepa 评分 * 10
            
            if review_csv and len(review_csv) >= 2:
                last_reviews = review_csv[-1]
                if last_reviews > 0:
                    current_reviews = last_reviews

            # ── 卖家数量 ──
            # csv[11] 的 newOfferCount
            new_offer_count = p.get("newOfferCount", 0) or 0

            # ── 历史数据（最近50个点） ──
            price_history = []
            bsr_history = []
            
            if amazon_csv:
                price_history = _decode_keepa_csv(amazon_csv[-100:])[-50:]
            if bsr_csv:
                bsr_history = _decode_keepa_csv(bsr_csv[-100:])[-50:]

            return {
                # 基础信息
                "asin": asin,
                "title": title,
                "brand": brand,
                "category_id": category,
                
                # 价格
                "current_price": current_price,
                "avg_price_30d": avg_price_30d,
                "avg_price_90d": avg_price_90d,
                "min_price_90d": min_price_90d,
                "max_price_90d": max_price_90d,
                
                # BSR（排名越小越好）
                "current_bsr": current_bsr,
                "avg_bsr_30d": avg_bsr_30d,
                "avg_bsr_90d": avg_bsr_90d,
                "bsr_trend": bsr_trend,  # "improving" / "declining" / "stable" / "unknown"
                
                # 销量
                "monthly_sold": monthly_sold,
                
                # 评论
                "rating": current_rating,
                "review_count": current_reviews,
                
                # 竞争
                "seller_count": new_offer_count,
                
                # 历史曲线（用于图表展示）
                "price_history": price_history,
                "bsr_history": bsr_history,
                
                # 数据来源
                "data_source": "keepa",
            }
            
        except Exception as e:
            logger.warning(f"解析商品 {p.get('asin', '?')} 失败: {e}")
            return None

    def _calc_bsr_trend(self, bsr_csv: List[int]) -> str:
        """
        计算 BSR 趋势
        比较最近30天均值 vs 前30天均值
        BSR 越小越好，所以 recent < older 表示 improving
        """
        try:
            # 解码 BSR 历史
            points = []
            for i in range(0, len(bsr_csv) - 1, 2):
                val = bsr_csv[i + 1]
                if val > 0:
                    points.append(val)
            
            if len(points) < 10:
                return "unknown"
            
            # 取最近一半 vs 前一半
            mid = len(points) // 2
            recent_avg = sum(points[mid:]) / len(points[mid:])
            older_avg = sum(points[:mid]) / len(points[:mid])
            
            change_pct = (recent_avg - older_avg) / older_avg * 100
            
            if change_pct < -10:
                return "improving"   # BSR 下降 = 排名提升 = 销量增长
            elif change_pct > 10:
                return "declining"   # BSR 上升 = 排名下降 = 销量减少
            else:
                return "stable"
                
        except Exception:
            return "unknown"

    @staticmethod
    def _domain_to_id(domain: str) -> int:
        """域名转 Keepa domain ID"""
        mapping = {
            "US": 1, "GB": 2, "DE": 3, "FR": 4, "JP": 5,
            "CA": 6, "IT": 8, "ES": 9, "IN": 10, "MX": 11,
            "BR": 12, "AU": 13, "NL": 14, "SG": 15, "AE": 16,
            "SA": 17, "TR": 18, "PL": 19, "SE": 20, "BE": 21,
        }
        return mapping.get(domain.upper(), 1)


# ── 便捷函数 ──

def get_keepa_connector(api_key: Optional[str] = None) -> KeepaConnector:
    """获取 KeepaConnector 实例（带错误提示）"""
    return KeepaConnector(api_key)
