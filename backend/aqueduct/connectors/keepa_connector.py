"""
Keepa 数据连接器
直接调用 Keepa REST API（不经 Python SDK），提供亚马逊商品历史数据查询

历史背景：
  keepa Python SDK 1.4.4 调 /product 端点会被服务器返回 HTTP 400 (REQUEST_REJECTED)，
  原因疑似 SDK 加了某些不被 Pro 套餐授权的参数。
  原生 REST 调用同样的端点完全 OK，因此直接走 requests，少一份 SDK 依赖。
  详见 plan/Phase2-P2-Keepa.md。

功能：
  - 关键词搜索 ASIN（/search 端点 —— Pro 套餐烧 10 token/次且常返空，慎用）
  - 批量查询商品历史数据（/product 端点）：BSR / 价格 / 评论 / 销量估算
  - 获取价格异动商品（/deal 端点）
  - 数据解析与标准化

使用前提：
  - 在 .env 中配置 KEEPA_API_KEY
  - requests（已在 requirements.txt）
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

# Keepa REST 基础 URL
_KEEPA_BASE_URL = "https://api.keepa.com"
# 默认请求超时（秒）。/product 拉历史可能稍慢，给 30s
_KEEPA_TIMEOUT = 30

# Keepa 时间基准：2011-01-01 00:00 UTC（分钟数）
_KEEPA_EPOCH = datetime(2011, 1, 1, tzinfo=timezone.utc)


# ── 异常体系 ─────────────────────────────────────────────────────────
# 分四档让调用方能区分应对：配置错误、配额耗尽、被拒、网络层
# 通用 except KeepaError 也能一把抓
# ───────────────────────────────────────────────────────────────────


class KeepaError(Exception):
    """Keepa 调用的基类异常"""


class KeepaConfigError(KeepaError):
    """API key 缺失 / 不合法 — 调用前置阶段的错误"""


class KeepaQuotaError(KeepaError):
    """Token 配额相关 — HTTP 429 或 tokensLeft 极低导致拒绝"""

    def __init__(self, message: str, retry_after_minutes: Optional[float] = None):
        super().__init__(message)
        self.retry_after_minutes = retry_after_minutes


class KeepaRejectedError(KeepaError):
    """请求被服务器拒绝 — HTTP 400 invalidParameter / REQUEST_REJECTED / 403 套餐限制"""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class KeepaNetworkError(KeepaError):
    """网络层错误 — 超时 / DNS / 连接拒绝"""


def _keepa_minutes_to_dt(minutes: int) -> str:
    """将 Keepa 时间戳（相对于2011-01-01的分钟数）转换为 ISO 字符串"""
    try:
        from datetime import timedelta
        dt = _KEEPA_EPOCH + timedelta(minutes=minutes)
        return dt.isoformat()
    except Exception:
        return ""


def _decode_keepa_csv(csv_data: List[int], is_price: bool = False) -> List[Dict[str, Any]]:
    """
    解码 Keepa 压缩的时间序列数据
    格式：[timestamp1, value1, timestamp2, value2, ...]
    value=-1 表示无数据

    is_price=True 时把 value 视为美分并 / 100；否则保留原始整数（如 BSR / 评论数 / 评分×10）
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
                "value": val / 100 if is_price else val,
            })
    return result


# Keepa CSV 索引常量（官方约定）
_CSV_AMAZON = 0          # Amazon 直营价
_CSV_NEW = 1             # 3P New Marketplace 最低价
_CSV_USED = 2            # 二手
_CSV_SALES = 3           # BSR（Sales Rank）
_CSV_LISTPRICE = 4
_CSV_COUNT_NEW = 11      # 新品 offer 数（不是 BSR！老代码这里写错了）
_CSV_RATING = 16         # 评分 × 10（需 rating=1 参数）
_CSV_COUNT_REVIEWS = 17  # 评论数（需 rating=1 参数）


class KeepaConnector:
    """
    Keepa 数据连接器（原生 REST）

    支持同步和异步两种调用方式：
    - 同步：KeepaConnector().search_asins(...)
    - 异步：await KeepaConnector().async_query_products(...)
    """

    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            from backend.config.config import settings
            api_key = settings.KEEPA_API_KEY

        if not api_key:
            raise KeepaConfigError(
                "KEEPA_API_KEY 未配置。请在 backend/config/.env 中设置 KEEPA_API_KEY=your_key\n"
                "获取 API Key: https://keepa.com/#!api"
            )
        self.api_key = api_key

    # ── 内部：REST 调用 ──

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET 调用 Keepa REST。失败时抛 KeepaError 子类：
          - 超时 / 连接拒绝 → KeepaNetworkError
          - HTTP 429 → KeepaQuotaError(retry_after_minutes=...)
          - HTTP 403 → KeepaRejectedError("套餐权限不足", ...)
          - HTTP 400 → KeepaRejectedError(详细 body, ...)
          - 其他 4xx/5xx → KeepaError
          - JSON 解析失败 → KeepaError
        """
        url = f"{_KEEPA_BASE_URL}/{path.lstrip('/')}"
        full_params = {"key": self.api_key, **params}

        try:
            resp = requests.get(url, params=full_params, timeout=_KEEPA_TIMEOUT)
        except requests.Timeout as e:
            raise KeepaNetworkError(f"Keepa 请求超时（{_KEEPA_TIMEOUT}s）: {e}") from e
        except requests.ConnectionError as e:
            raise KeepaNetworkError(f"Keepa 连接失败: {e}") from e
        except requests.RequestException as e:
            raise KeepaNetworkError(f"Keepa 请求异常: {e}") from e

        status = resp.status_code
        body_text = resp.text or ""

        if status == 200:
            try:
                return resp.json()
            except ValueError as e:
                raise KeepaError(f"Keepa 响应不是合法 JSON: {e}; body[:200]={body_text[:200]}") from e

        # ── 错误状态码分流 ──

        if status == 429:
            retry_min = self._parse_retry_after_minutes(resp)
            msg = "Keepa token 配额耗尽 (HTTP 429)"
            if retry_min is not None:
                msg += f"，约 {retry_min:.1f} 分钟后恢复"
            raise KeepaQuotaError(msg, retry_after_minutes=retry_min)

        if status == 403:
            raise KeepaRejectedError(
                f"Keepa 套餐权限不足或被拒 (HTTP 403): {body_text[:200]}",
                status_code=status,
                body=body_text,
            )

        if status == 400:
            # Keepa 把参数错误 / REQUEST_REJECTED 都用 400 返回
            detail = self._extract_error_detail(body_text)
            raise KeepaRejectedError(
                f"Keepa 拒绝请求 (HTTP 400): {detail}",
                status_code=status,
                body=body_text,
            )

        raise KeepaError(f"Keepa 返回非预期状态 HTTP {status}: {body_text[:200]}")

    @staticmethod
    def _parse_retry_after_minutes(resp: "requests.Response") -> Optional[float]:
        """从 429 响应里抽出恢复等待时长（分钟）。
        优先级：响应 body 的 refillIn(ms) > Retry-After 头(秒)"""
        # 先试 JSON body
        try:
            data = resp.json()
            refill_ms = data.get("refillIn")
            if isinstance(refill_ms, (int, float)) and refill_ms > 0:
                return refill_ms / 60000.0
        except ValueError:
            pass
        # 再试 Retry-After 头
        ra = resp.headers.get("Retry-After")
        if ra:
            try:
                return float(ra) / 60.0
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_error_detail(body_text: str) -> str:
        """从 400 响应里抽出简要错误说明"""
        if not body_text:
            return "(空 body)"
        try:
            data = json.loads(body_text)
            err = data.get("error") or {}
            if isinstance(err, dict):
                msg = err.get("message") or err.get("type") or ""
                if msg:
                    return msg
            return body_text[:200]
        except (ValueError, AttributeError):
            return body_text[:200]

    # ── 关键词搜索（Keepa REST API /search 端点）──

    # Keepa domain 字符串 → 数字映射
    _DOMAIN_MAP = {
        "US": 1, "GB": 2, "DE": 3, "FR": 4, "JP": 5,
        "CA": 6, "IT": 8, "ES": 9, "IN": 10, "MX": 11,
        "BR": 12, "AU": 13, "NL": 14, "PL": 15, "SE": 16,
        "BE": 17, "SG": 18, "AE": 19, "SA": 20, "TR": 21,
    }

    # ── Token 余量查询 ──

    def get_token_status(self) -> Dict[str, Any]:
        """
        查询 Keepa token 余量（/token 端点，免费，0 消耗）。

        Returns:
            {
                "tokens_left": int,
                "refill_rate": int,        # token/min
                "refill_in_seconds": float, # 下次 refill 倒计时
                "max_tokens": int,          # 桶上限 = refill_rate × 60
            }
        """
        data = self._get("token", {})
        refill_in_ms = data.get("refillIn", 0)
        refill_rate = data.get("refillRate", 1)
        return {
            "tokens_left": data.get("tokensLeft", 0),
            "refill_rate": refill_rate,
            "refill_in_seconds": refill_in_ms / 1000.0,
            "max_tokens": refill_rate * 60,
        }

    def _check_quota(self, tokens_needed: int) -> None:
        """
        调 API 前预检 token 余量。不足时抛 KeepaQuotaError 并告知等待时间。
        /token 端点免费（0 消耗），所以多调一次不烧钱。
        """
        try:
            status = self.get_token_status()
        except KeepaError:
            return  # 查余量本身失败不阻塞主流程

        left = status["tokens_left"]
        if left < tokens_needed:
            refill_rate = status["refill_rate"] or 1
            wait_minutes = (tokens_needed - left) / refill_rate
            raise KeepaQuotaError(
                f"Keepa token 不足：需要 {tokens_needed}，剩余 {left}，"
                f"约 {wait_minutes:.0f} 分钟后可用 "
                f"(refill {refill_rate} token/min, 桶上限 {status['max_tokens']})",
                retry_after_minutes=wait_minutes,
            )

    # ── 关键词搜索（Keepa REST API /search 端点）──

    def search_asins(
        self,
        keyword: str,
        domain: str = "US",
        max_results: int = 50,
    ) -> List[str]:
        """
        通过关键词搜索 ASIN 列表（Keepa REST /search 端点）

        ⚠️ Token 消耗：Pro 套餐每次 /search 烧 **10 tokens**，且经常返空（asinList=[]）。
                       优先用 watchlist ASIN，不要依赖 keyword → search 入口。
                       详见 plan/Phase2-P2-Keepa.md。

        Args:
            keyword: 搜索关键词，如 "bluetooth earbuds"
            domain: 市场字符串，如 US/DE/JP
            max_results: 最大返回数量

        Returns:
            ASIN 列表（空列表表示「调用成功但无结果」；失败时抛 KeepaError 子类）

        Raises:
            KeepaError 子类 —— 调用方决定如何处理（捕获/降级/上抛）
        """
        domain_id = self._DOMAIN_MAP.get(domain.upper(), 1)
        self._check_quota(10)  # /search 每次 10 tokens
        logger.warning(
            f"Keepa /search '{keyword}' (domain={domain}) — "
            f"预计消耗 10 tokens，Pro 套餐常返空"
        )
        data = self._get("search", {
            "domain": domain_id,
            "type": "product",
            "term": keyword,
        })
        asins = data.get("asinList", []) or []
        result = list(asins[:max_results])
        logger.info(
            f"Keepa 搜索到 {len(result)} 个 ASIN "
            f"(tokensLeft={data.get('tokensLeft')})"
        )
        return result

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
        offers: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        批量查询商品历史数据（Keepa REST /product 端点，最多 100 个 ASIN）

        Args:
            asins: ASIN 列表（最多 100 个）
            domain: 市场字符串（US/DE/JP 等），内部转 domain ID
            history: 是否获取历史时间序列。False 时只拿当前快照
            stats: 统计周期（天），如 30/90/180。控制 stats.avg/min/max 的窗口
            offers: 获取的 offer 数量。
                    ⚠️ Keepa 计费：每个 offer entry 多消耗 1 token，
                    50 ASIN × offers=20 = 单次额外 1000 tokens。
                    基础款用户保持 0；只有需要查 buy box / 多卖家详情时再调大。

        Returns:
            标准化的商品数据列表（_parse_product 输出格式）
        """
        if not asins:
            return []

        # Keepa 单次最多 100 个
        asins = asins[:100]

        # ── 缓存查询 ──
        from backend.core.cache.keepa import get_cache
        cache = get_cache()
        cached: Dict[str, Dict] = cache.get_many(asins, domain) if cache else {}
        uncached = [a for a in asins if a not in cached]

        if not uncached:
            logger.info(
                f"Keepa 缓存全部命中 {len(cached)}/{len(asins)} ASIN，跳过 API"
            )
            return [cached[a] for a in asins if a in cached]

        if cached:
            logger.info(
                f"Keepa 缓存命中 {len(cached)}/{len(asins)}，"
                f"API 查询剩余 {len(uncached)}"
            )

        # ── 调 API 查未命中的 ASIN ──
        tokens_needed = len(uncached) + (len(uncached) * offers if offers > 0 else 0)
        self._check_quota(tokens_needed)

        domain_id = self._DOMAIN_MAP.get(domain.upper(), 1)
        params: Dict[str, Any] = {
            "domain": domain_id,
            "asin": ",".join(uncached),
            "history": 1 if history else 0,
            "rating": 1,
        }
        if offers and offers > 0:
            params["offers"] = offers
        if stats:
            params["stats"] = stats

        logger.info(
            f"Keepa /product 查询 {len(uncached)} 个 ASIN "
            f"(domain={domain}, history={history}, stats={stats}, offers={offers})"
        )
        data = self._get("product", params)
        raw_products = data.get("products", []) or []
        new_results = []
        for p in raw_products:
            parsed = self._parse_product(p, stats)
            if parsed:
                new_results.append(parsed)

        logger.info(
            f"Keepa 成功解析 {len(new_results)}/{len(raw_products)} 个商品 "
            f"(tokensLeft={data.get('tokensLeft')}, "
            f"tokensConsumed={data.get('tokensConsumed')})"
        )

        # ── 写入缓存 ──
        if cache and new_results:
            try:
                cache.put_many(new_results, domain)
            except Exception as e:
                logger.warning(f"Keepa 缓存写入失败: {e}")

        # ── 合并（保持原 asins 顺序）──
        merged = {**cached}
        for p in new_results:
            merged[p["asin"]] = p
        return [merged[a] for a in asins if a in merged]

    async def async_query_products(
        self,
        asins: List[str],
        domain: str = "US",
        history: bool = True,
        stats: int = 180,
        offers: int = 0,
    ) -> List[Dict[str, Any]]:
        """异步版商品历史查询。offers 默认 0 节省 token，见 query_products 说明"""
        return await asyncio.to_thread(
            self.query_products, asins, domain, history, stats, offers
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
        获取最近价格异动的商品（Keepa REST /deal 端点，用于监控告警）

        Args:
            domain: 市场
            min_rating: 最低评分（0-50，对应 0-5 星）
            min_reviews: 最低评论数
            max_results: 最大返回数量

        Returns:
            价格异动商品列表
        """
        self._check_quota(5)  # /deal 约 5 tokens

        deal_selection = {
            "page": 0,
            "domainId": self._domain_to_id(domain),
            "excludeCategories": [],
            "includeCategories": [],
            "priceTypes": [0, 1],  # 0=Amazon, 1=New
            "deltaPercent": {"min": 10, "max": 100},  # 降价 10% 以上
            "current": {"min": 1, "max": 99999},
            "avg": {"min": 1, "max": 99999},
            "rating": {"min": min_rating, "max": 50},
            "reviewCount": {"min": min_reviews, "max": 999999},
        }
        logger.info(f"Keepa /deal 获取价格异动 (domain={domain})")
        # /deal 端点：selection 用 URL-encoded JSON 传
        data = self._get("deal", {"selection": json.dumps(deal_selection)})
        deals = data.get("deals") or data  # Keepa 不同版本字段不一致
        deal_rows = []
        if isinstance(deals, dict):
            deal_rows = deals.get("dr", []) or []
        elif isinstance(deals, list):
            deal_rows = deals

        results = []
        for d in deal_rows[:max_results]:
            results.append({
                "asin": d.get("asin", ""),
                "title": d.get("title", ""),
                "current_price": d.get("current", -1) / 100 if d.get("current", -1) > 0 else None,
                "avg_price": d.get("avg", -1) / 100 if d.get("avg", -1) > 0 else None,
                "delta_percent": d.get("deltaPercent", 0),
                "rating": d.get("rating", 0) / 10,
                "review_count": d.get("reviewCount", 0),
            })

        logger.info(
            f"Keepa /deal 获取到 {len(results)} 个商品 "
            f"(tokensLeft={data.get('tokensLeft')})"
        )
        return results

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
        将 Keepa 原生 REST /product 返回的单个商品对象解析为标准化格式

        标准化字段：
        - asin, title, brand, category
        - current_price, avg_price_30d, avg_price_90d, min_price_90d, max_price_90d
        - current_bsr, avg_bsr_30d, avg_bsr_90d, bsr_trend（improving/declining/stable/unknown）
        - monthly_sold（月销量估算）
        - review_count, rating（仅当请求时传 rating=1 才有值）
        - new_offer_count（卖家数量）
        - price_history, bsr_history（最近 N 条历史点）

        关键格式说明（native REST 不经 SDK 规范化）：
        - p["csv"][i] 是 [ts, val, ts, val, ...] 或 None
        - p["stats"]["min"|"max"|"minInInterval"|"maxInInterval"][i] 是 [ts, val] 元组
        - p["stats"]["avg"|"avg30"|"avg90"|"avg180"|"current"][i] 是平铺标量数组（按 CSV type 索引）
        """
        try:
            asin = p.get("asin", "")
            if not asin:
                return None

            title = p.get("title", "") or ""
            brand = p.get("brand", "") or ""

            categories = p.get("categories") or []
            category = categories[0] if categories else 0

            csv = p.get("csv") or []
            stats_obj = p.get("stats") or {}

            def _csv(i: int):
                """安全取 csv[i]；None / 越界返回 None"""
                return csv[i] if i < len(csv) and csv[i] else None

            def _last_csv_value(series):
                """[ts, val, ts, val, ...] 中最后一个非 -1 的 val"""
                if not series or len(series) < 2:
                    return None
                for k in range(len(series) - 1, 0, -2):
                    v = series[k]
                    if isinstance(v, (int, float)) and v != -1:
                        return v
                return None

            def _stats_scalar(key: str, idx: int):
                """读 stats[key][idx]。
                兼容两种 shape：平铺 [val, val, ...] 和 2D [[ts, val], ...]。
                返回原始整数（价格单位仍是美分），-1/None 视作无数据返回 None"""
                arr = stats_obj.get(key)
                if not isinstance(arr, list) or len(arr) <= idx:
                    return None
                entry = arr[idx]
                if isinstance(entry, list):
                    val = entry[1] if len(entry) >= 2 else None
                else:
                    val = entry
                if isinstance(val, (int, float)) and val != -1:
                    return val
                return None

            def _cents_to_usd(v):
                return v / 100 if isinstance(v, (int, float)) and v > 0 else None

            # ── 价格 ──
            amazon_csv = _csv(_CSV_AMAZON)
            current_price = _cents_to_usd(_last_csv_value(amazon_csv))
            # Amazon 下架时回落到 3P New Marketplace 最低价
            if current_price is None:
                new_csv = _csv(_CSV_NEW)
                current_price = _cents_to_usd(_last_csv_value(new_csv))

            avg_price_30d = _cents_to_usd(_stats_scalar("avg30", _CSV_AMAZON))
            avg_price_90d = _cents_to_usd(_stats_scalar("avg90", _CSV_AMAZON))
            min_price_90d = _cents_to_usd(_stats_scalar("min", _CSV_AMAZON))
            max_price_90d = _cents_to_usd(_stats_scalar("max", _CSV_AMAZON))

            # ── BSR ──
            bsr_csv = _csv(_CSV_SALES)
            current_bsr = _last_csv_value(bsr_csv)
            avg_bsr_30d = _stats_scalar("avg30", _CSV_SALES)
            avg_bsr_90d = _stats_scalar("avg90", _CSV_SALES)
            bsr_trend = self._calc_bsr_trend(bsr_csv) if bsr_csv else "unknown"

            # ── 销量估算 ──
            monthly_sold = p.get("monthlySold") or 0

            # ── 评论（需请求时传 rating=1，否则 csv[16/17] 为 None） ──
            rating_csv = _csv(_CSV_RATING)
            last_rating = _last_csv_value(rating_csv)
            current_rating = last_rating / 10 if last_rating else None

            review_csv = _csv(_CSV_COUNT_REVIEWS)
            last_reviews = _last_csv_value(review_csv)
            current_reviews = last_reviews or 0

            # ── 卖家数量 ──
            new_offer_count = p.get("newOfferCount") or 0

            # ── 历史曲线（最近 50 个有效点） ──
            price_history = []
            bsr_history = []
            if amazon_csv:
                price_history = _decode_keepa_csv(amazon_csv[-100:], is_price=True)[-50:]
            if bsr_csv:
                bsr_history = _decode_keepa_csv(bsr_csv[-100:], is_price=False)[-50:]

            # ── 类目树 ──
            category_tree = p.get("categoryTree") or []
            root_category = p.get("rootCategory") or 0

            # ── 商品类型 ──
            product_type = p.get("type")  # 0=standard, 1=parent/variation, 2=child
            product_group = p.get("productGroup", "") or ""
            binding = p.get("binding", "") or ""

            # ── 制造信息 ──
            manufacturer = p.get("manufacturer", "") or ""
            model = p.get("model", "") or ""
            part_number = p.get("partNumber", "") or ""

            # ── 条形码 ──
            upc = p.get("upc", "") or ""
            ean = p.get("ean", "") or ""
            isbn = p.get("isbn", "") or ""

            # ── 变体属性 ──
            color = p.get("color", "") or ""
            size = p.get("size", "") or ""
            weight = p.get("weight")  # 单位由 packageDimension 决定，通常 1/100 克
            package_quantity = p.get("packageQuantity")

            # ── Listing 内容 ──
            features = p.get("features") or []
            description = p.get("description", "") or ""
            images_csv = p.get("imagesCSV", "") or ""
            feature_bullets = features  # 别名：与模型列名一致

            # ── 变体关系 ──
            parent_asin = p.get("parentAsin", "") or ""
            variation_csv = p.get("variationCSV", "") or ""

            # ── 额外字段 ──
            sales_rank_history = p.get("salesRanks") or p.get("salesRankHistory") or []
            parent_asin_history = p.get("parentAsinHistory") or []
            whats_in_the_box = p.get("includedComponents") or []
            availability_text = p.get("availability") or ""  # Keepa /product 顶层
            unit_count = p.get("unitCount") or {}

            # ── 扩展字段提取 ─────────────────────────────────────────
            # 物理属性
            style = p.get("style", "") or ""
            material = p.get("material", "") or ""
            item_weight_g = (p.get("itemWeight", 0) or 0) / 100 if p.get("itemWeight") else None
            item_height_mm = p.get("itemHeight")
            item_length_mm = p.get("itemLength")
            item_width_mm = p.get("itemWidth")
            package_weight_g = (p.get("packageWeight", 0) or 0) / 100 if p.get("packageWeight") else None
            package_dimensions_mm = p.get("packageDimensions")
            number_of_items = p.get("numberOfItems")
            item_type_keyword = p.get("itemTypeKeyword", "") or ""

            # unit count
            unit_count_raw = p.get("unitCount") or {}
            unit_count_type = None
            unit_count_value = None
            if isinstance(unit_count_raw, dict):
                unit_count_type = unit_count_raw.get("type") or unit_count_raw.get("unitType")
                unit_count_value = unit_count_raw.get("value") or unit_count_raw.get("unitValue")

            # BuyBox 扩展 — 用模型列名
            is_lowest_price = p.get("isLowestPrice")
            buybox_price = _cents_to_usd(p.get("buyBoxPrice"))
            buybox_seller_id = p.get("buyBoxSellerId", "") or ""
            buybox_seller_name = p.get("buyBoxSellerName", "") or ""
            buybox_is_amazon = p.get("buyBoxIsAmazon", False)
            buybox_is_prime_eligible = p.get("buyBoxIsPrimeEligible", False)
            buybox_shipping = _cents_to_usd(p.get("buyBoxShipping"))
            is_fba = p.get("buyBoxIsFBA", False)

            # Offer 统计
            offer_count_p = p.get("offerCount", 0) or 0
            offer_count_fba_p = p.get("offerCountFBA", 0) or 0
            offer_count_fbm_p = p.get("offerCountFBM", 0) or 0
            seller_ids_lowest_fba_p = p.get("sellerIdsLowestFBA", []) or []
            seller_ids_lowest_fbm_p = p.get("sellerIdsLowestFBM", []) or []
            buybox_eligible_offer_counts_p = p.get("buyBoxEligibleOfferCounts", {}) or {}

            # 商品标记
            is_warehouse_deal_p = p.get("isWarehouseDeal", False)
            is_preorder_p = p.get("isPreorder", False)
            is_map_restricted_p = p.get("isMapRestricted", False)
            batteries_included_p = p.get("batteriesIncluded", False)
            batteries_required_p = p.get("batteriesRequired", False)
            is_sns_p = p.get("isSNS", False)
            is_heat_sensitive_p = p.get("isHeatSensitive", False)
            is_adult_product_p = p.get("isAdultProduct", False)
            is_eligible_for_trade_in_p = p.get("isEligibleForTradeIn", False)
            is_redirect_asin_p = p.get("isRedirectASIN", False)
            launchpad_p = p.get("launchpad", False)

            # 时间戳
            tracking_since_raw = p.get("trackingSince")
            tracking_since = _keepa_minutes_to_dt(tracking_since_raw) if isinstance(tracking_since_raw, int) else None
            listed_since_raw = p.get("listedSince")
            listed_since = _keepa_minutes_to_dt(listed_since_raw) if isinstance(listed_since_raw, int) else None

            # 品牌/链接/促销
            brand_store_p = p.get("brandStore", {}) or {}
            url_slug_p = p.get("urlSlug", "") or ""
            coupon_text_p = p.get("coupon", "") or ""
            promotions_json_p = p.get("promotions", {}) or {}
            lightning_deal_info_p = p.get("lightningDealInfo", {}) or {}
            shipping_origin_p = p.get("shippingOrigin", "") or ""
            is_eligible_for_free_shipping_p = p.get("isEligibleForFreeShipping", False)
            isEligibleForSuperSaverShipping_p = p.get("isEligibleForSuperSaverShipping", False)
            available_prime_exclusive_p = p.get("availablePrimeExclusive", False)
            hazardous_materials_p = p.get("hazardousMaterials", {}) or {}

            # 费用
            fba_fees = p.get("fbaFees") or {}
            fba_fee_p = _cents_to_usd(fba_fees.get("pickAndPackFee")) if isinstance(fba_fees, dict) else None
            referral_fee_percent_p = p.get("referralFeePercent", 0) or 0

            # Sales Rank Reference
            sales_rank_reference_id_p = p.get("salesRankReference", 0) or 0
            root_category_id_p = p.get("rootCategory", 0) or 0
            sales_rank_reference_history_p = p.get("salesRankReferenceHistory", []) or []

            # Offer history (keepa offers=20 时可用)
            offer_history_p = p.get("offers", []) or []

            # 扩展统计价格
            avg_price_180d = _cents_to_usd(_stats_scalar("avg180", _CSV_AMAZON))
            avg_price_365d = _cents_to_usd(_stats_scalar("avg365", _CSV_AMAZON))
            min_price_30d = _cents_to_usd(_stats_scalar("min", _CSV_AMAZON))
            min_price_180d = _cents_to_usd(_stats_scalar("min180", _CSV_AMAZON))
            max_price_180d = _cents_to_usd(_stats_scalar("max", _CSV_AMAZON))

            # 扩展 BSR 统计
            avg_bsr_180d = _stats_scalar("avg180", _CSV_SALES)
            avg_bsr_365d = _stats_scalar("avg365", _CSV_SALES)

            # Sales Rank Drops
            sales_rank_drops_30d_p = p.get("salesRankDrops30") or _stats_scalar("salesRankDrops30", 0)
            sales_rank_drops_90d_p = p.get("salesRankDrops90") or _stats_scalar("salesRankDrops90", 0)
            sales_rank_drops_180d_p = p.get("salesRankDrops180") or 0
            sales_rank_drops_365d_p = p.get("salesRankDrops365") or 0

            # 扩展历史序列
            rating_history = []
            review_count_history = []
            rating_csv_full = _csv(_CSV_RATING)
            review_csv_full = _csv(_CSV_COUNT_REVIEWS)
            if rating_csv_full:
                raw_rh = _decode_keepa_csv(rating_csv_full[-100:], is_price=False)
                # rating 值需要 /10
                rh = []
                for pt in raw_rh:
                    rh.append({"timestamp": pt["timestamp"], "value": round(pt["value"] / 10, 1)})
                rating_history = rh[-50:]
            if review_csv_full:
                review_count_history = _decode_keepa_csv(review_csv_full[-100:], is_price=False)[-50:]

            # 缺货统计
            out_of_stock_pct_30d_p = p.get("outOfStockPercentage30", 0) or 0
            out_of_stock_pct_90d_p = p.get("outOfStockPercentage90", 0) or 0
            out_of_stock_pct_180d_p = p.get("outOfStockPercentage180", 0) or 0
            out_of_stock_count_amazon_p = p.get("outOfStockCountAmazon", 0) or 0

            # ── product_type_name ──
            product_type_name = {0: "STANDARD", 1: "VARIATION_PARENT", 2: "VARIATION_CHILD"}.get(p.get("type"), "")
            if not product_type_name:
                product_type_name = p.get("productTypeName", "") or ""

            # domain + currency
            domain = p.get("domain", "US")
            currency_map = {"US": "USD", "DE": "EUR", "GB": "GBP", "JP": "JPY", "CA": "CAD",
                            "FR": "EUR", "IT": "EUR", "ES": "EUR", "IN": "INR", "MX": "MXN",
                            "BR": "BRL", "AU": "AUD", "NL": "EUR", "SG": "SGD", "AE": "AED",
                            "SA": "SAR", "TR": "TRY", "SE": "SEK", "PL": "PLN"}
            currency = currency_map.get(domain, "USD")

            return {
                # 基础信息
                "asin": asin,
                "title": title,
                "brand": brand,
                "category_id": category,
                "root_category": root_category,
                "category_tree": category_tree,

                # 商品类型
                "product_type": product_type,
                "product_type_name": product_type_name,
                "product_group": product_group,
                "binding": binding,

                # 制造信息
                "manufacturer": manufacturer,
                "model": model,
                "part_number": part_number,

                # 条形码
                "upc": upc,
                "ean": ean,
                "isbn": isbn,

                # 变体属性
                "color": color,
                "size": size,
                "style": style,
                "material": material,
                "weight": weight,
                "item_weight_g": item_weight_g,
                "item_height_mm": item_height_mm,
                "item_length_mm": item_length_mm,
                "item_width_mm": item_width_mm,
                "package_weight_g": package_weight_g,
                "package_dimensions_mm": package_dimensions_mm,
                "package_quantity": package_quantity,
                "number_of_items": number_of_items,
                "item_type_keyword": item_type_keyword,
                "unit_count_type": unit_count_type,
                "unit_count_value": unit_count_value,

                # Listing 内容
                "features": features,
                "description": description,
                "images_csv": images_csv,
                "brand_store": brand_store_p,
                "url_slug": url_slug_p,

                # 变体关系
                "parent_asin": parent_asin,
                "variation_csv": variation_csv,
                "feature_bullets": feature_bullets,
                "domain": domain,

                # 价格
                "current_price": current_price,
                "avg_price_30d": avg_price_30d,
                "avg_price_90d": avg_price_90d,
                "avg_price_180d": avg_price_180d,
                "avg_price_365d": avg_price_365d,
                "min_price_30d": min_price_30d,
                "min_price_90d": min_price_90d,
                "min_price_180d": min_price_180d,
                "max_price_90d": max_price_90d,
                "max_price_180d": max_price_180d,
                "is_lowest_price": is_lowest_price,
                "buybox_price": buybox_price,
                "buybox_seller_id": buybox_seller_id,
                "buybox_seller_name": buybox_seller_name,
                "buybox_is_amazon": buybox_is_amazon,
                "buybox_is_prime_eligible": buybox_is_prime_eligible,
                "buybox_shipping": buybox_shipping,
                "currency": currency,

                # BSR（排名越小越好）
                "current_bsr": current_bsr,
                "avg_bsr_30d": avg_bsr_30d,
                "avg_bsr_90d": avg_bsr_90d,
                "avg_bsr_180d": avg_bsr_180d,
                "avg_bsr_365d": avg_bsr_365d,
                "bsr_trend": bsr_trend,
                "sales_rank_drops_30d": sales_rank_drops_30d_p,
                "sales_rank_drops_90d": sales_rank_drops_90d_p,
                "sales_rank_drops_180d": sales_rank_drops_180d_p,
                "sales_rank_drops_365d": sales_rank_drops_365d_p,
                "sales_rank_reference_id": sales_rank_reference_id_p,
                "root_category_id": root_category_id_p,
                "sales_rank_reference_history": sales_rank_reference_history_p,

                # 销量
                "monthly_sold": monthly_sold,

                # 评论
                "rating": current_rating,
                "review_count": current_reviews,

                # 竞争
                "seller_count": new_offer_count,
                "offer_count": offer_count_p,
                "offer_count_fba": offer_count_fba_p,
                "offer_count_fbm": offer_count_fbm_p,
                "seller_ids_lowest_fba": seller_ids_lowest_fba_p,
                "seller_ids_lowest_fbm": seller_ids_lowest_fbm_p,
                "buybox_eligible_offer_counts": buybox_eligible_offer_counts_p,

                # 费用
                "fba_fee": fba_fee_p,
                "referral_fee_percent": referral_fee_percent_p,

                # 商品标记
                "is_warehouse_deal": is_warehouse_deal_p,
                "is_preorder": is_preorder_p,
                "is_map_restricted": is_map_restricted_p,
                "batteries_included": batteries_included_p,
                "batteries_required": batteries_required_p,
                "is_fba": is_fba,
                "is_sns": is_sns_p,
                "is_heat_sensitive": is_heat_sensitive_p,
                "is_adult_product": is_adult_product_p,
                "is_eligible_for_trade_in": is_eligible_for_trade_in_p,
                "is_redirect_asin": is_redirect_asin_p,
                "launchpad": launchpad_p,
                "shipping_origin": shipping_origin_p,
                "is_eligible_for_free_shipping": is_eligible_for_free_shipping_p,
                "isEligibleForSuperSaverShipping": isEligibleForSuperSaverShipping_p,
                "available_prime_exclusive": available_prime_exclusive_p,
                "hazardous_materials": hazardous_materials_p,

                # 促销
                "coupon_text": coupon_text_p,
                "promotions_json": promotions_json_p,
                "lightning_deal_info": lightning_deal_info_p,

                # Listing 内容补充
                "availability_text": availability_text,
                "whats_in_the_box": whats_in_the_box,

                # 历史曲线
                "price_history": price_history,
                "bsr_history": bsr_history,
                "rating_history": rating_history,
                "review_count_history": review_count_history,
                "sales_rank_history": sales_rank_history,

                # 父体变更历史
                "parent_asin_history": parent_asin_history,

                # 缺货统计
                "out_of_stock_pct_30d": out_of_stock_pct_30d_p,
                "out_of_stock_pct_90d": out_of_stock_pct_90d_p,
                "out_of_stock_pct_180d": out_of_stock_pct_180d_p,
                "out_of_stock_count_amazon": out_of_stock_count_amazon_p,

                # Offer 历史（子表原始数据）
                "offer_history": offer_history_p,

                # 时间戳
                "tracking_since": tracking_since,
                "listed_since": listed_since,

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
