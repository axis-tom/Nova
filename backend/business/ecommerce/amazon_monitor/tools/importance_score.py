"""
ASIN Importance Score 算法

四维评分体系 — 自动判定 ASIN 的 Hot/Active/Passive Tier：
  - Commercial (40%): 月营收、BSR、客单价
  - Engagement (25%): 评论增速、评分质量、变体丰富度
  - Investment (20%): A+、FBA、广告、Listing 质量
  - Momentum (15%): BSR 趋势、价格稳定性、卖家变化

数据源：Keepa + Rainforest + Canopy 三源数据综合计算
"""

import math
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def calc_commercial(data: Dict[str, Any]) -> float:
    """
    商业价值评分 (0-100)

    维度：
      - 月营收估算 (50%): monthly_sold × current_price
      - BSR 排名 (30%): 对数归一化，排名越小越好
      - 客单价 (20%): 越高越有价值

    权重 40%
    """
    # 月营收
    monthly_sold = data.get("monthly_sold") or 0
    current_price = data.get("current_price") or 0
    revenue = monthly_sold * current_price
    # $0→0, $5K→25, $20K→50, $100K→80, $500K+→100
    revenue_score = min(revenue / 2000, 100)

    # BSR 归一化（对数刻度）
    bsr = data.get("current_bsr") or 999999
    if bsr <= 0:
        bsr = 999999
    bsr_log = math.log10(bsr)
    # BSR #1 → 100, #100 → 60, #1000 → 40, #10000 → 20, #100000+ → 0
    bsr_score = max(0, 100 - (bsr_log / 5 * 100))

    # 客单价评分
    price = current_price or 0
    if price < 10:
        price_score = 10
    elif price < 20:
        price_score = 30
    elif price < 50:
        price_score = 60
    elif price < 100:
        price_score = 80
    else:
        price_score = 100

    return revenue_score * 0.50 + bsr_score * 0.30 + price_score * 0.20


def calc_engagement(data: Dict[str, Any]) -> float:
    """
    用户关注度评分 (0-100)

    维度：
      - 评论增速 (40%): 近 30 天新增评论数，反映近期活跃度
      - 评分质量 (40%): rating × 评论量置信度衰减
      - 变体丰富度 (20%): 子 ASIN 数量

    权重 25%
    """
    # 评论增速
    review_velocity = data.get("review_velocity_30d") or 0
    # 0→0, 10→20, 50→50, 200→80, 1000+→100
    velocity_score = min(review_velocity / 2.5, 100)

    # 评分质量（带评论量置信度衰减）
    rating = data.get("rating") or 0
    review_count = data.get("review_count") or 0
    confidence = min(review_count / 100, 1)  # 100 条以上置信度满分
    quality_score = (rating / 5 * 100) * confidence if rating > 0 else 0

    # 变体丰富度
    child_asins = data.get("child_asins") or []
    var_count = len(child_asins)
    if var_count == 0:
        var_score = 0
    elif var_count <= 2:
        var_score = 30
    elif var_count <= 5:
        var_score = 60
    elif var_count <= 10:
        var_score = 80
    else:
        var_score = 100

    return velocity_score * 0.40 + quality_score * 0.40 + var_score * 0.20


def calc_investment(data: Dict[str, Any]) -> float:
    """
    卖家投入度评分 (0-100)

    维度：
      - A+ Content (20分)
      - 广告投放 (20分)
      - FBA 发货 (25分)
      - Listing 质量 (20分): 五点描述 + 图片
      - 变体深度 (15分): ≥3 子 ASIN 加分

    权重 20%
    """
    score = 0.0

    # A+ Content
    aplus = data.get("aplus_content") or {}
    score += 20 if aplus else 0

    # 广告投放
    sponsored = data.get("sponsored_products") or []
    score += 20 if sponsored else 0

    # FBA 发货
    fulfillment = (data.get("fulfillment") or "").lower()
    score += 25 if "fba" in fulfillment else 0

    # Listing 质量
    bullets = data.get("feature_bullets") or []
    images = data.get("images") or []
    bullet_score = min(len(bullets) / 5 * 10, 10)
    image_score = min(len(images) / 6 * 10, 10)
    score += bullet_score + image_score

    # 变体深度（≥3 子 ASIN 说明卖家投了这条线）
    child_asins = data.get("child_asins") or []
    if len(child_asins) >= 3:
        score += 15
    elif len(child_asins) >= 1:
        score += 8

    return min(score, 100)


def calc_momentum(data: Dict[str, Any]) -> float:
    """
    增长势头评分 (0-100)

    维度：
      - BSR 趋势: improving=+30, stable=+0, declining=-15
      - 价格稳定性: 波动大=异常扣分，稳定=加分
      - 卖家数变化: 激增=竞争加剧扣分

    权重 15%
    """
    score = 50.0  # 基础分

    # BSR 趋势
    bsr_trend = data.get("bsr_trend", "unknown")
    if bsr_trend == "improving":
        score += 30
    elif bsr_trend == "declining":
        score -= 15

    # 价格稳定性
    price_history = data.get("price_history") or []
    if len(price_history) >= 10:
        prices = [p["value"] for p in price_history if p.get("value", 0) > 0]
        if prices:
            avg_p = sum(prices) / len(prices)
            volatility = max(prices) - min(prices)
            if avg_p > 0:
                ratio = volatility / avg_p
                if ratio > 0.3:
                    score -= 20
                elif ratio < 0.05:
                    score += 10

    # 卖家数变化
    current_sellers = data.get("seller_count") or 0
    seller_count_history = data.get("seller_count_history") or []
    if seller_count_history and current_sellers > 0:
        old_avg = sum(seller_count_history) / len(seller_count_history)
        if old_avg > 0:
            growth = (current_sellers - old_avg) / old_avg
            if growth > 0.5:
                score -= 10
            elif growth < -0.3:
                score += 5

    return max(0, min(100, score))


def calc_importance_score(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    计算 ASIN 综合重要性分，返回分值和 Tier 判定。

    Args:
        data: 三源合并后的 ASIN 数据（字段与 AmazonProduct 模型匹配）

    Returns:
        {
            "score": float,          # 总分 0-100
            "tier": str,             # hot / active / passive
            "details": {             # 各分量诊断
                "commercial": float,
                "engagement": float,
                "investment": float,
                "momentum": float,
            }
        }
    """
    c = calc_commercial(data)
    e = calc_engagement(data)
    i = calc_investment(data)
    m = calc_momentum(data)

    total = c * 0.40 + e * 0.25 + i * 0.20 + m * 0.15

    if total >= 65:
        tier = "hot"
    elif total >= 30:
        tier = "active"
    else:
        tier = "passive"

    return {
        "score": round(total, 1),
        "tier": tier,
        "details": {
            "commercial": round(c, 1),
            "engagement": round(e, 1),
            "investment": round(i, 1),
            "momentum": round(m, 1),
        },
    }


def calc_manual_override_tier(trigger: str, existing_tier: str) -> str:
    """
    手动覆盖规则：
      - 用户主动分析 → Hot（即时晋升）
      - 用户手动 Pin → Hot
      - Keepa Deal 发现 → 临时升至 Active（30 天后由调度器重算）
    """
    if trigger in ("user_analyze", "user_pin"):
        return "hot"
    if trigger == "deal_discovery":
        return "active"  # 临时，调度器下次 ETL 会重新评分
    return existing_tier