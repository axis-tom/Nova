"""
共享评分/分析工具函数 — 消除 Agent 与 REST API 层的重复逻辑

所有纯计算函数放在这里（不依赖 DB、不依赖 state），
Agent 和 Service 层都从此导入，避免两处实现不同步。

包含：
- 8 维机会评分
- 品牌聚合
- 价格稳定性
- 定价策略分类
- Listing 质量评分
- BSR / 价格分布
- 价格带分析
"""
from typing import Any, Dict, List, Optional


# ════════════════════════════════════════════
# 8 维机会评分
# ════════════════════════════════════════════

SCORE_WEIGHTS = {
    "bsr_rank": 0.20,
    "bsr_trend": 0.15,
    "rating": 0.15,
    "review_count": 0.10,
    "monthly_sold": 0.15,
    "price_stability": 0.10,
    "competition": 0.10,
    "sentiment": 0.05,
}


def score_single_product(p: Dict) -> Dict[str, Any]:
    """8 维加权评分（0-100），返回评分明细 + 分级"""
    scores = {}

    bsr = p.get("current_bsr")
    if bsr:
        if bsr <= 100: scores["bsr_rank"] = 100
        elif bsr <= 1000: scores["bsr_rank"] = 85
        elif bsr <= 5000: scores["bsr_rank"] = 70
        elif bsr <= 20000: scores["bsr_rank"] = 55
        elif bsr <= 100000: scores["bsr_rank"] = 35
        else: scores["bsr_rank"] = 15
    else:
        scores["bsr_rank"] = 30

    trend = p.get("bsr_trend", "unknown")
    scores["bsr_trend"] = {"improving": 100, "stable": 65, "declining": 20}.get(trend, 50)

    rating = p.get("rating") or 0
    scores["rating"] = (
        100 if rating >= 4.5 else
        80 if rating >= 4.0 else
        60 if rating >= 3.5 else
        40 if rating >= 3.0 else
        20
    )

    reviews = p.get("review_count") or 0
    scores["review_count"] = (
        100 if reviews >= 10000 else
        80 if reviews >= 1000 else
        60 if reviews >= 100 else
        40 if reviews >= 10 else
        20
    )

    sold = p.get("monthly_sold") or 0
    scores["monthly_sold"] = (
        100 if sold >= 5000 else
        80 if sold >= 1000 else
        60 if sold >= 300 else
        40 if sold >= 50 else
        20 if sold > 0 else
        max(20, scores["bsr_rank"] * 0.6)
    )

    min_p, max_p = p.get("min_price_90d"), p.get("max_price_90d")
    avg_p = p.get("avg_price_90d") or p.get("current_price")
    if min_p and max_p and avg_p and avg_p > 0:
        vol = (max_p - min_p) / avg_p
        scores["price_stability"] = (
            100 if vol <= 0.05 else
            80 if vol <= 0.15 else
            60 if vol <= 0.30 else
            40 if vol <= 0.50 else
            20
        )
    else:
        scores["price_stability"] = 60

    sellers = p.get("seller_count") or 0
    scores["competition"] = (
        60 if sellers == 0 else
        90 if sellers <= 3 else
        75 if sellers <= 10 else
        55 if sellers <= 30 else
        35 if sellers <= 100 else
        15
    )

    scores["sentiment"] = 60

    total = sum(scores.get(k, 0) * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS)

    highlights = []
    if trend == "improving":
        highlights.append("BSR 持续改善（销量增长）")
    if sold >= 1000:
        highlights.append(f"月销约 {sold:,} 件")
    if min_p and max_p and avg_p and avg_p > 0:
        vol = (max_p - min_p) / avg_p * 100
        if vol <= 10:
            highlights.append(f"价格稳定（90天波动 {vol:.0f}%）")
    if sellers > 0 and sellers <= 5:
        highlights.append(f"竞争少（仅 {sellers} 个卖家）")

    return {
        "total_score": round(total, 1),
        "score_detail": scores,
        "highlights": highlights,
        "score_grade": "A" if total >= 80 else "B" if total >= 70 else "C" if total >= 60 else "D",
    }


def grade_distribution(scored_list: List[Dict]) -> Dict[str, int]:
    """统计 A/B/C/D 分布"""
    dist: Dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}
    for s in scored_list:
        grade = s.get("score_grade", "D")
        dist[grade] = dist.get(grade, 0) + 1
    return dist


# ════════════════════════════════════════════
# 品牌聚合
# ════════════════════════════════════════════

def aggregate_brands(products: List[Dict]) -> Dict[str, Dict]:
    """按品牌聚合统计"""
    brands: Dict[str, Dict] = {}
    for p in products:
        brand = p.get("brand") or "Unknown"
        if brand not in brands:
            brands[brand] = {
                "count": 0, "total_sales": 0, "total_reviews": 0,
                "prices": [], "ratings": [], "bsrs": [],
                "improving_count": 0, "declining_count": 0,
            }
        b = brands[brand]
        b["count"] += 1
        b["total_sales"] += p.get("monthly_sold", 0) or 0
        b["total_reviews"] += p.get("review_count", 0) or 0
        if p.get("current_price"): b["prices"].append(p["current_price"])
        if p.get("rating"): b["ratings"].append(p["rating"])
        if p.get("current_bsr"): b["bsrs"].append(p["current_bsr"])
        if p.get("bsr_trend") == "improving": b["improving_count"] += 1
        if p.get("bsr_trend") == "declining": b["declining_count"] += 1

    result = {}
    for brand, b in brands.items():
        result[brand] = {
            "count": b["count"],
            "total_sales": b["total_sales"],
            "total_reviews": b["total_reviews"],
            "avg_price": round(sum(b["prices"]) / len(b["prices"]), 2) if b["prices"] else None,
            "avg_rating": round(sum(b["ratings"]) / len(b["ratings"]), 2) if b["ratings"] else None,
            "avg_bsr": round(sum(b["bsrs"]) / len(b["bsrs"])) if b["bsrs"] else None,
            "improving_count": b["improving_count"],
            "declining_count": b["declining_count"],
        }
    return result


# ════════════════════════════════════════════
# 价格稳定性
# ════════════════════════════════════════════

def calc_price_stability(p: Dict) -> Dict:
    """计算价格稳定性标签 + 波动率"""
    min_p = p.get("min_price_90d")
    max_p = p.get("max_price_90d")
    avg_p = p.get("avg_price_90d") or p.get("current_price")
    if min_p and max_p and avg_p and avg_p > 0:
        vol = (max_p - min_p) / avg_p
        if vol <= 0.05:
            return {"label": "极稳定", "volatility_pct": round(vol * 100, 1)}
        elif vol <= 0.15:
            return {"label": "稳定", "volatility_pct": round(vol * 100, 1)}
        elif vol <= 0.30:
            return {"label": "一般", "volatility_pct": round(vol * 100, 1)}
        else:
            return {"label": "不稳定", "volatility_pct": round(vol * 100, 1)}
    return {"label": "未知", "volatility_pct": None}


# ════════════════════════════════════════════
# 定价策略分类
# ════════════════════════════════════════════

def classify_price_pattern(price_history: List[Dict]) -> Dict:
    """从 price_history 识别定价模式"""
    if not price_history or len(price_history) < 10:
        return {"label": "数据不足", "detail": "历史数据不足 10 个点, 无法识别定价模式", "changes_30d": None, "changes_90d": None}

    prices = [p["value"] for p in price_history if p.get("value", 0) > 0]
    if len(prices) < 10:
        return {"label": "数据不足", "detail": "有效价格点不足 10 个", "changes_30d": None, "changes_90d": None}

    mid = len(prices) // 2
    recent_avg = sum(prices[mid:]) / len(prices[mid:])
    older_avg = sum(prices[:mid]) / len(prices[:mid])
    change_pct = (recent_avg - older_avg) / older_avg * 100 if older_avg > 0 else 0
    volatility = (max(prices) - min(prices)) / sum(prices) * len(prices) if prices else 0

    prices_30 = prices[-30:] if len(prices) >= 30 else prices
    changes_30d = None
    if len(prices_30) >= 10:
        mid_30 = len(prices_30) // 2
        recent_30 = sum(prices_30[mid_30:]) / len(prices_30[mid_30:])
        old_30 = sum(prices_30[:mid_30]) / len(prices_30[:mid_30])
        changes_30d = round((recent_30 - old_30) / old_30 * 100, 1) if old_30 > 0 else 0

    changes_90d = round(change_pct, 1)

    if volatility < 0.05 and abs(change_pct) < 3:
        label, detail = "稳定", "价格长期稳定，波动极小"
    elif change_pct < -5 and abs(change_pct) > 5:
        label, detail = "持续降价", "整体呈降价趋势，可能清仓或价格战"
    elif change_pct > 5:
        label, detail = "持续涨价", "持续涨价中，产品溢价能力强"
    elif volatility > 0.2:
        label, detail = "频繁波动", "价格波动频繁，可能频繁调价测试市场"
    else:
        label, detail = "小幅调整", "价格有微调，总体稳定"

    return {"label": label, "detail": detail, "changes_30d": changes_30d, "changes_90d": changes_90d}


# ════════════════════════════════════════════
# Listing 质量评分
# ════════════════════════════════════════════

def score_listing_quality(p: Dict) -> int:
    """10 分制 Listing 质量评分"""
    score = 0
    score += score_bullets(p.get("feature_bullets") or [])
    score += score_images(p.get("images") or [])
    score += 2 if p.get("aplus_content") else 0
    score += 1 if p.get("description") else 0
    score += 1 if ((p.get("images") or []) and len(p.get("images", [])) > 1) else 0
    return min(score, 10)


def score_bullets(bullets: List) -> int:
    count = len(bullets) if isinstance(bullets, list) else 0
    if count >= 5: return 3
    if count >= 3: return 2
    if count >= 1: return 1
    return 0


def score_images(images: List) -> int:
    count = len(images) if isinstance(images, list) else 0
    if count >= 7: return 3
    if count >= 4: return 2
    if count >= 1: return 1
    return 0


def grade_listing(score: int) -> str:
    if score >= 9: return "优秀"
    if score >= 7: return "良好"
    if score >= 5: return "一般"
    return "薄弱"


def listing_quality_analysis(p: Dict, score: int) -> Dict:
    """返回评分 + 改进建议"""
    suggestions = []
    bullets = p.get("feature_bullets") or []
    images = p.get("images") or []
    if len(bullets) < 5:
        suggestions.append(f"五点描述仅 {len(bullets)} 条，建议补全至 5 条")
    if len(images) < 6:
        suggestions.append("主图数量不足 6 张，建议增加")
    if not p.get("aplus_content"):
        suggestions.append("缺少 A+ Content，可显著提升转化率")
    if not p.get("description"):
        suggestions.append("缺少商品描述")
    if len(images) <= 1:
        suggestions.append("缺少商品视频/多角度图")
    return {"score": score, "grade": grade_listing(score), "suggestions": suggestions}


# ════════════════════════════════════════════
# BSR / 价格分布
# ════════════════════════════════════════════

def calc_bsr_distribution(products: List[Dict]) -> Dict[str, int]:
    """BSR 排名分层分布"""
    bsr_ranks = [p.get("bsr_rank") or p.get("current_bsr") for p in products if p.get("bsr_rank") or p.get("current_bsr")]
    return {
        "top_100": sum(1 for r in bsr_ranks if r <= 100),
        "top_1000": sum(1 for r in bsr_ranks if 100 < r <= 1000),
        "top_10000": sum(1 for r in bsr_ranks if 1000 < r <= 10000),
        "others": sum(1 for r in bsr_ranks if r > 10000),
    }


def calc_price_distribution(products: List[Dict], bands: Optional[Dict[str, tuple]] = None) -> Dict[str, int]:
    """价格带分布"""
    if bands is None:
        bands = {
            "<$20": (0, 20), "$20-50": (20, 50), "$50-100": (50, 100),
            "$100-200": (100, 200), "$200+": (200, float("inf")),
        }
    result = {}
    for label, (lo, hi) in bands.items():
        result[label] = sum(
            1 for p in products
            if (p.get("current_price") or p.get("price")) and lo <= (p["current_price"] if "current_price" in p and p["current_price"] else p.get("price", 0)) < hi
        )
    return result


def calc_price_band_gaps(products: List[Dict]) -> Dict[str, Dict]:
    """价格带分析（含 BSR）"""
    bands = {
        "<$20": (0, 20), "$20-50": (20, 50), "$50-100": (50, 100),
        "$100-200": (100, 200), "$200+": (200, float("inf")),
    }
    result = {}
    for label, (lo, hi) in bands.items():
        in_band = [
            p for p in products
            if (p.get("current_price") or p.get("price"))
            and lo <= (p["current_price"] if "current_price" in p and p["current_price"] else p.get("price", 0)) < hi
        ]
        bsrs = [
            (p.get("current_bsr") or p.get("bsr_rank")) for p in in_band
            if (p.get("current_bsr") or p.get("bsr_rank"))
        ]
        result[label] = {
            "count": len(in_band),
            "avg_bsr": round(sum(bsrs) / len(bsrs)) if bsrs else None,
        }
    return result


def detect_price_alerts(products: List[Dict], std_dev_threshold: float = 2.0) -> List[Dict]:
    """价格异常检测（基于标准差）"""
    from datetime import datetime, timezone

    alerts = []
    products_with_price = [p for p in products if p.get("current_price") or p.get("price")]
    if len(products_with_price) < 3:
        return alerts

    prices = [p["current_price"] if "current_price" in p and p["current_price"] else p["price"] for p in products_with_price]
    avg_price = sum(prices) / len(prices)
    std_dev = (sum((p - avg_price) ** 2 for p in prices) / len(prices)) ** 0.5

    for product in products_with_price:
        price = product["current_price"] if "current_price" in product and product["current_price"] else product.get("price", 0)
        deviation = abs(price - avg_price)

        if std_dev > 0 and deviation > std_dev_threshold * std_dev:
            alert_type = "price_too_low" if price < avg_price else "price_too_high"
            asin = product.get("asin", "")
            alerts.append({
                "asin": asin,
                "title": (product.get("title", "") or "")[:60],
                "current_price": price,
                "avg_market_price": round(avg_price, 2),
                "deviation_pct": round((price - avg_price) / avg_price * 100, 1),
                "alert_type": alert_type,
                "message": (
                    f"价格 ${price:.2f} 远低于市场均价 ${avg_price:.2f}，"
                    f"偏差 {abs(price - avg_price) / avg_price * 100:.1f}%"
                    if alert_type == "price_too_low" else
                    f"价格 ${price:.2f} 远高于市场均价 ${avg_price:.2f}，"
                    f"偏差 {(price - avg_price) / avg_price * 100:.1f}%"
                ),
                "detected_at": datetime.now(timezone.utc).isoformat(),
            })

    return alerts