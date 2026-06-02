"""
推导函数层 — 将原始字段转为 33 个分析方向的商业信号

每个分析方向对应至少一个推导函数，输出 LLM 可直接消费的结构化结果。
函数输入来自 AmazonProduct 主表 + 子表（offers/variations）的原始数据。

设计原则：
  - 纯函数，无副作用，不调 DB/API
  - 输入 None-safe：任何字段缺失时优雅降级
  - 输出结构统一，每个方向返回 dict
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════
# 4.1 价格与利润相关（#01 #05 #08 #12 #29 #32）
# ═══════════════════════════════════════════════════════════════════

def price_trend(prices: Dict[str, Any]) -> str:
    """
    判断价格趋势。
    Input: {"avg30": float, "avg90": float, "avg180": float, "avg365": float}
    Output: "stable" / "rising" / "declining" / "unknown"
    """
    avg30 = prices.get("avg_price_30d")
    avg90 = prices.get("avg_price_90d")
    avg180 = prices.get("avg_price_180d")

    if not any([avg30, avg90, avg180]):
        return "unknown"

    # 用有数据的最长窗口判断
    if avg30 and avg90 and avg90 > 0:
        change = (avg30 - avg90) / avg90
        if change > 0.05:
            return "rising"
        elif change < -0.05:
            return "declining"
    if avg90 and avg180 and avg180 > 0:
        change = (avg90 - avg180) / avg180
        if change > 0.05:
            return "rising"
        elif change < -0.05:
            return "declining"
    return "stable"


def price_volatility(prices: Dict[str, Any]) -> float:
    """
    计算价格波动率。
    Input: {"min_price_90d": float, "max_price_90d": float, "avg_price_90d": float}
    Output: 0.0~1.0（低→高波动）
    """
    min_p = prices.get("min_price_90d")
    max_p = prices.get("max_price_90d")
    avg_p = prices.get("avg_price_90d")

    if not all([min_p, max_p, avg_p]) or avg_p <= 0:
        return 0.0

    spread = (max_p - min_p) / avg_p
    return min(spread, 1.0)


def buybox_winner_profile(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析 Buy Box 当前赢家。
    Output: {"seller_id": str, "is_amazon": bool, "price": float, "rotation_days": int or None}
    """
    return {
        "seller_id": product.get("buybox_seller_id"),
        "seller_name": product.get("buybox_seller_name"),
        "is_amazon": product.get("buybox_is_amazon", False),
        "is_fba": product.get("is_fba", False),
        "price": product.get("buybox_price") or product.get("current_price"),
        "availability": product.get("buybox_availability"),
        "condition": product.get("buybox_condition"),
    }


def price_elasticity(history: List[Dict], bsr_history: List[Dict]) -> float:
    """
    粗略计算价格弹性系数。
    比较价格变动±10% 时 BSR 的变化幅度。
    Output: -0.5~-3.0（数值越小弹性越大）；无可比数据返回 -1.0
    """
    if not history or not bsr_history or len(history) < 2 or len(bsr_history) < 2:
        return -1.0

    # 找价格变动 > 10% 的事件
    events = []
    for i in range(1, len(history)):
        prev_price = history[i - 1].get("value", 0)
        curr_price = history[i].get("value", 0)
        if prev_price and curr_price and prev_price > 0:
            change_pct = (curr_price - prev_price) / prev_price
            if abs(change_pct) > 0.1:
                events.append({"ts": history[i].get("timestamp"), "price_change": change_pct})

    if not events:
        return -1.0

    # 找对应 BSR 变化
    elasticities = []
    for event in events:
        ts = event["ts"]
        nearby_bsr = [b for b in bsr_history if b.get("timestamp", "") >= ts]
        if nearby_bsr and len(nearby_bsr) >= 2:
            bsr_before = nearby_bsr[0].get("value", 0)
            bsr_after = nearby_bsr[-1].get("value", 0)
            if bsr_before and bsr_after and bsr_before > 0:
                bsr_change = (bsr_after - bsr_before) / bsr_before
                if event["price_change"] != 0:
                    elasticity = round(bsr_change / event["price_change"], 2)
                    elasticities.append(elasticity)

    if elasticities:
        return round(sum(elasticities) / len(elasticities), 2)
    return -1.0


def profit_analysis(product: Dict[str, Any], offers: List[Dict] = None) -> Dict[str, Any]:
    """
    利润分析。
    Output: {"gross_margin": float, "net_profit": float, "breakeven_price": float}
    """
    price = product.get("current_price") or 0
    fba_fee = product.get("fba_fee") or 0
    referral_pct = (product.get("referral_fee_percent") or 15) / 100.0
    cost_of_goods = None

    # 试着从 offer 中找最低价（可能代表采购成本）
    if offers:
        fba_offers = [o.get("price") for o in offers if o.get("is_fba") and o.get("price")]
        if fba_offers:
            cost_of_goods = min(fba_offers)

    if price <= 0:
        return {"gross_margin": 0, "net_profit": 0, "breakeven_price": 0, "note": "no price data"}

    referral_fee = price * referral_pct
    total_cost = referral_fee + (fba_fee or 0)
    net = price - total_cost - (cost_of_goods or 0)
    margin = net / price if price > 0 else 0

    return {
        "gross_margin_pct": round(margin * 100, 1),
        "net_profit": round(net, 2),
        "referral_fee": round(referral_fee, 2),
        "fba_fee": fba_fee,
        "breakeven_price": round(total_cost + (cost_of_goods or 0), 2),
        "cost_of_goods_est": cost_of_goods,
    }


def fba_cost_breakdown(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    FBA 费用拆解。
    Output: {"fulfillment_tier": str, "pick_pack": float, "storage_cost": float}
    """
    weight_g = product.get("item_weight_g") or 0
    dims = product.get("package_dimensions_mm") or []

    # 粗略分档（基于 Amazon US FBA 标准）
    if weight_g <= 0 and not dims:
        tier = "unknown"
    elif weight_g and weight_g <= 340:
        tier = "small_standard"
    elif weight_g and weight_g <= 900:
        tier = "large_standard"
    elif weight_g and weight_g <= 7000:
        tier = "large_bulky"
    else:
        tier = "oversize"

    return {
        "fulfillment_tier": tier,
        "pick_pack_fee": product.get("fba_fee"),
        "weight_grams": weight_g,
        "dimensions_mm": dims,
    }


def promotion_effectiveness(product: Dict[str, Any], bsr_history: List[Dict] = None) -> Dict[str, Any]:
    """
    促销效果分析。
    Output: {"best_channel": str or None, "roi": str, "recommended_discount": str}
    """
    coupon = product.get("coupon_text")
    lightning = product.get("lightning_deal_info")
    promotions = product.get("promotions_json") or {}

    has_coupon = bool(coupon)
    has_lightning = bool(lightning)
    has_promotion = bool(promotions)

    active_channels = []
    if has_coupon:
        active_channels.append("coupon")
    if has_lightning:
        active_channels.append("lightning_deal")
    if has_promotion:
        active_channels.append("promotion")

    return {
        "active_channels": active_channels,
        "best_channel": "lightning_deal" if has_lightning else ("coupon" if has_coupon else None),
        "has_coupon": has_coupon,
        "has_lightning_deal": has_lightning,
        "recommended_discount": "15-20% Lightning Deal" if not has_lightning else "维持当前促销",
    }


# ═══════════════════════════════════════════════════════════════════
# 4.2 竞争与卖家相关（#01 #03 #13 #24）
# ═══════════════════════════════════════════════════════════════════

def competition_intensity(seller_count: int, offer_count: int = None) -> str:
    """
    竞争强度判断。
    Output: "low" / "medium" / "high"
    """
    count = offer_count or seller_count or 0
    if count <= 3:
        return "low"
    elif count <= 10:
        return "medium"
    else:
        return "high"


def competition_landscape(product: Dict[str, Any], offers: List[Dict] = None) -> Dict[str, Any]:
    """
    竞争格局分析。
    Output: {"total_sellers": int, "fba_ratio": float, "amazon_present": bool, ...}
    """
    seller_count = product.get("seller_count") or 0
    offer_count = product.get("offer_count") or 0
    offer_count_fba = product.get("offer_count_fba") or 0
    offer_count_fbm = product.get("offer_count_fbm") or 0

    fba_ratio = 0.0
    if (offer_count_fba + offer_count_fbm) > 0:
        fba_ratio = round(offer_count_fba / (offer_count_fba + offer_count_fbm), 2)

    # 如果 offer 子表数据可用，更准确
    china_sellers = 0
    amazon_selling = False
    if offers:
        for o in offers:
            if o.get("ships_from_china"):
                china_sellers += 1
            if o.get("is_amazon"):
                amazon_selling = True

    return {
        "total_sellers": seller_count,
        "total_offers": offer_count,
        "fba_offer_count": offer_count_fba,
        "fbm_offer_count": offer_count_fbm,
        "fba_ratio": fba_ratio,
        "amazon_selling": amazon_selling or product.get("has_amazon_selling", False),
        "china_seller_count": china_sellers or (1 if product.get("has_china_sellers") else 0),
        "intensity_label": competition_intensity(seller_count, offer_count),
        "buybox_is_amazon": product.get("buybox_is_amazon", False),
    }


def competitor_profile(offers: List[Dict], seller_id: str = None) -> Dict[str, Any]:
    """
    特定卖家/主要卖家分析。
    Output: {"behavior_pattern": str, "avg_pricing": float, "stock_pattern": str}
    """
    if not offers:
        return {"behavior_pattern": "unknown", "avg_pricing": None, "stock_pattern": "unknown"}

    target_offers = offers
    if seller_id:
        target_offers = [o for o in offers if o.get("seller_id") == seller_id]

    if not target_offers:
        return {"behavior_pattern": "unknown", "avg_pricing": None, "stock_pattern": "unknown", "note": f"seller {seller_id} not found"}

    prices = [o.get("price") for o in target_offers if o.get("price")]
    avg_price = round(sum(prices) / len(prices), 2) if prices else None

    # 行为模式判断
    is_fba = any(o.get("is_fba") for o in target_offers)
    is_amazon = any(o.get("is_amazon") for o in target_offers)

    if is_amazon:
        pattern = "amazon_retail"
    elif is_fba:
        pattern = "professional_fba"
    else:
        pattern = "fbm_individual"

    return {
        "behavior_pattern": pattern,
        "seller_count_analyzed": len(target_offers),
        "avg_pricing": avg_price,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "is_fba": is_fba,
        "is_amazon": is_amazon,
    }


def seller_behavior_profile(offers: List[Dict]) -> Dict[str, Any]:
    """
    卖家行为分析。
    Output: {"aggressive_sellers": list, "new_entrants": list, "market_stability": str}
    """
    if not offers:
        return {"aggressive_sellers": [], "new_entrants": [], "exiting_sellers": [], "market_stability": "unknown"}

    # 找低价卖家（aggressive = price < avg_price * 0.9）
    prices = [o.get("price") for o in offers if o.get("price")]
    avg_price = sum(prices) / len(prices) if prices else 0

    aggressive = []
    for o in offers:
        p = o.get("price")
        if p and avg_price > 0 and p < avg_price * 0.9:
            aggressive.append({
                "seller_id": o.get("seller_id"),
                "price": p,
                "delta_vs_avg": round((p - avg_price) / avg_price * 100, 1),
            })

    return {
        "aggressive_sellers": aggressive[:5],
        "aggressive_count": len(aggressive),
        "market_stability": "stable" if len(aggressive) <= 2 else ("competitive" if len(aggressive) <= 5 else "price_war"),
        "avg_market_price": round(avg_price, 2) if avg_price else None,
        "fba_ratio": round(sum(1 for o in offers if o.get("is_fba")) / len(offers), 2) if offers else 0,
    }


def china_seller_impact(offers: List[Dict]) -> Dict[str, Any]:
    """
    中国卖家影响分析。
    Output: {"count": int, "avg_price_diff": float, "bsr_impact": str}
    """
    if not offers:
        return {"count": 0, "avg_price_diff": None, "bsr_impact": "unknown", "note": "no offer data"}

    china = [o for o in offers if o.get("ships_from_china")]
    others = [o for o in offers if not o.get("ships_from_china")]

    china_avg = sum(o.get("price", 0) for o in china) / len(china) if china else 0
    other_avg = sum(o.get("price", 0) for o in others) / len(others) if others else 0

    price_diff = None
    if china_avg and other_avg:
        price_diff = round((china_avg - other_avg) / other_avg * 100, 1)

    return {
        "count": len(china),
        "ratio": round(len(china) / len(offers), 2) if offers else 0,
        "avg_price_china": round(china_avg, 2) if china_avg else None,
        "avg_price_others": round(other_avg, 2) if other_avg else None,
        "avg_price_diff_pct": price_diff,
        "bsr_impact": "significant" if len(china) > len(offers) * 0.3 else "moderate" if china else "none",
    }


# ═══════════════════════════════════════════════════════════════════
# 4.3 Listing 与 SEO（#02 #06 #11 #27）
# ═══════════════════════════════════════════════════════════════════

def listing_quality_score(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Listing 质量评分。
    多维度：图片/A+/视频/规格/五点/描述
    Output: {"score": 0.0~1.0, "gaps": list, "estimated_conversion_uplift": str}
    """
    score = 0.0
    total_weight = 0
    gaps = []

    # 主图（权重 20%）
    if product.get("main_image"):
        score += 0.20
    else:
        gaps.append("主图缺失")
    total_weight += 0.20

    # 多图（权重 15%）
    images = product.get("images") or []
    if len(images) >= 3:
        score += 0.15
    elif images:
        score += 0.08
    else:
        gaps.append("图片数量不足（<3张）")
    total_weight += 0.15

    # 五点描述（权重 15%）
    bullets = product.get("feature_bullets") or []
    if len(bullets) >= 5:
        score += 0.15
    elif bullets:
        score += 0.08
    else:
        gaps.append("五点描述缺失或不完整")
    total_weight += 0.15

    # 视频（权重 10%）
    if product.get("videos_count", 0) > 0 or product.get("videos"):
        score += 0.10
    else:
        gaps.append("视频缺失")
    total_weight += 0.10

    # A+ 内容（权重 15%）
    if product.get("aplus_content"):
        score += 0.15
    else:
        gaps.append("无 A+ 品牌故事")
    total_weight += 0.15

    # 规格参数（权重 10%）
    if product.get("specifications"):
        score += 0.10
    else:
        gaps.append("规格参数缺失")
    total_weight += 0.10

    # 产品描述（权重 10%）
    if product.get("description"):
        score += 0.10
    total_weight += 0.10

    # 品牌店铺（权重 5%）
    if product.get("brand_store"):
        score += 0.05
    total_weight += 0.05

    final_score = round(score / total_weight, 2) if total_weight > 0 else 0.0

    uplift = None
    if final_score < 0.4:
        uplift = "20-30%"
    elif final_score < 0.6:
        uplift = "10-15%"
    elif final_score < 0.8:
        uplift = "5-10%"

    return {
        "score": final_score,
        "gaps": gaps,
        "has_main_image": bool(product.get("main_image")),
        "image_count": len(images) if images else 0,
        "has_aplus": bool(product.get("aplus_content")),
        "has_video": product.get("videos_count", 0) > 0,
        "bullet_count": len(bullets),
        "estimated_conversion_uplift": uplift,
    }


def seo_audit(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    SEO 审计。
    Output: {"keyword_coverage": 0.0~1.0, "missing_keywords": list, "title_optimization": str}
    """
    title = product.get("title", "") or ""
    bullets = product.get("feature_bullets") or []
    keywords = product.get("keywords_list") or []
    url_slug = product.get("url_slug", "") or ""
    search_alias = product.get("search_alias", "") or ""

    # 标题优化检查
    title_issues = []
    if len(title) < 80:
        title_issues.append("标题过短（<80字符）")
    if len(title) > 200:
        title_issues.append("标题过长（>200字符）")
    if title.count(",") > 5:
        title_issues.append("标题关键词堆砌")

    # 关键词覆盖度估算
    coverage = 0.5
    if keywords:
        coverage = 0.7
    if url_slug:
        coverage += 0.1
    if search_alias:
        coverage += 0.1

    return {
        "keyword_coverage": round(min(coverage, 1.0), 2),
        "title_length": len(title),
        "title_issues": title_issues,
        "title_optimization": "建议添加核心关键词至标题前30字符",
        "has_url_slug": bool(url_slug),
        "has_search_alias": bool(search_alias),
        "bullet_count": len(bullets),
    }


def aplus_effectiveness(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    A+ 内容效果评估。
    Output: {"has_aplus": bool, "content_quality": str, "conversion_impact": str}
    """
    aplus = product.get("aplus_content")
    has_aplus = bool(aplus)

    if not has_aplus:
        return {"has_aplus": False, "content_quality": "none", "conversion_impact": "无 A+ 内容，转化率可能低于行业平均"}

    # 粗略判断 A+ 质量
    quality = "basic"
    if isinstance(aplus, dict):
        content_len = len(str(aplus))
        if content_len > 2000:
            quality = "rich"
        elif content_len > 500:
            quality = "standard"

    return {
        "has_aplus": True,
        "content_quality": quality,
        "conversion_impact": "有 A+ 内容，预计转化率提升 3-10%" if quality != "basic" else "A+ 内容较简单，建议优化",
    }


# ═══════════════════════════════════════════════════════════════════
# 4.4 生命周期与市场时机（#07 #15 #31）
# ═══════════════════════════════════════════════════════════════════

def lifecycle_stage(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    生命周期阶段判断。
    Output: {"stage": str, "age_days": int, "trend": str, "recommendation": str}
    """
    now = datetime.now(timezone.utc)

    # 估算产品年龄
    age_days = None
    for date_field in ["first_available", "listed_since", "tracking_since", "created_at"]:
        raw = product.get(date_field)
        if raw:
            try:
                if isinstance(raw, str):
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                else:
                    dt = raw.replace(tzinfo=timezone.utc) if raw.tzinfo is None else raw
                age_days = max(0, (now - dt).days)
                break
            except (ValueError, TypeError, AttributeError):
                continue

    # 价格变动频率
    price_history = product.get("price_history") or []
    price_changes = len(price_history) if price_history else 0

    # BSR 趋势
    bsr_trend = product.get("bsr_trend", "unknown")

    # 评分趋势
    rating = product.get("rating") or 0
    review_count = product.get("review_count") or 0

    # 阶段判断
    if age_days is None:
        stage = "unknown"
    elif age_days < 90:
        stage = "intro"
    elif age_days < 365:
        stage = "growth" if bsr_trend == "improving" else "mature"
    elif age_days < 1095:
        if bsr_trend == "declining" and price_changes < 5:
            stage = "decline"
        elif bsr_trend == "improving":
            stage = "growth"
        else:
            stage = "mature"
    else:
        stage = "mature" if review_count > 500 else "decline"

    # 推荐建议
    recommendations = {
        "intro": "加大广告投入，积累评论，关注竞品反应",
        "growth": "维持广告，扩大变体覆盖，关注库存稳定性",
        "mature": "优化利润，考虑变体更新，监控竞品新入场",
        "decline": "harvest模式，降低广告支出，准备替代品",
        "unknown": "需更多数据判断生命周期阶段",
    }

    return {
        "stage": stage,
        "age_days": age_days,
        "bsr_trend": bsr_trend,
        "price_change_count": price_changes,
        "recommendation": recommendations.get(stage, "维持当前策略"),
    }


def activity_score(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    产品活跃度评分。
    Output: {"score": 0.0~1.0, "last_price_change_days": int, "status": str}
    """
    now = datetime.now(timezone.utc)

    # 最近价格变动时间
    price_history = product.get("price_history") or []
    last_price_days = None
    if price_history:
        last_entry = price_history[-1]
        ts = last_entry.get("timestamp")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
                last_price_days = (now - dt).days if hasattr(dt, 'tzinfo') else None
            except (ValueError, TypeError):
                pass

    # 最近评分变动
    rating_history = product.get("rating_history") or []
    last_rating_days = None
    if rating_history:
        last_entry = rating_history[-1]
        ts = last_entry.get("timestamp")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
                last_rating_days = (now - dt).days if hasattr(dt, 'tzinfo') else None
            except (ValueError, TypeError):
                pass

    # 综合评分
    score = 0.5
    if last_price_days is not None:
        if last_price_days < 7:
            score += 0.25
        elif last_price_days < 30:
            score += 0.15
        elif last_price_days > 180:
            score -= 0.2

    review_velocity = product.get("review_velocity_30d") or 0
    if review_velocity > 10:
        score += 0.15
    elif review_velocity > 3:
        score += 0.1

    return {
        "score": round(max(0.0, min(1.0, score)), 2),
        "last_price_change_days": last_price_days,
        "last_rating_update_days": last_rating_days,
        "review_velocity_30d": review_velocity,
        "status": "高活跃" if score >= 0.7 else ("低活跃" if score < 0.4 else "中活跃"),
    }


def market_timing_score(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    市场时机评分。
    Output: {"signal": str, "confidence": str, "next_review_date": str}
    """
    lifecycle = lifecycle_stage(product)
    activity = activity_score(product)

    bsr_trend = product.get("bsr_trend", "unknown")
    rating = product.get("rating") or 0

    # 买入信号
    buy_signals = 0
    hold_signals = 0
    sell_signals = 0

    if lifecycle["stage"] in ("intro", "growth"):
        buy_signals += 2
    if bsr_trend == "improving":
        buy_signals += 1
    if activity["score"] >= 0.7:
        hold_signals += 1
    if lifecycle["stage"] == "decline":
        sell_signals += 2
    if bsr_trend == "declining":
        sell_signals += 1
    if rating < 3.5:
        sell_signals += 1

    if buy_signals > sell_signals and buy_signals > hold_signals:
        signal = "buy"
        confidence = "high" if buy_signals >= 3 else "medium"
    elif sell_signals > buy_signals and sell_signals >= hold_signals:
        signal = "sell"
        confidence = "high" if sell_signals >= 2 else "medium"
    else:
        signal = "hold"
        confidence = "medium"

    return {
        "signal": signal,
        "confidence": confidence,
        "lifecycle_stage": lifecycle["stage"],
        "bsr_trend": bsr_trend,
        "rating": rating,
        "activity_score": activity["score"],
        "next_review_date": "30天后复查",
    }


# ═══════════════════════════════════════════════════════════════════
# 4.5 库存与供应链（#04 #16 #28）
# ═══════════════════════════════════════════════════════════════════

def supply_chain_risk(product: Dict[str, Any], offers: List[Dict] = None) -> Dict[str, Any]:
    """
    供应链风险评分。
    Output: {"risk_score": 0.0~1.0, "days_until_ostock": int, "risk_factors": list}
    """
    risk = 0.0
    risk_factors = []

    stock = product.get("stock_level") or 0
    monthly_sold = product.get("monthly_sold") or 0

    # 低库存风险
    if stock <= 0:
        risk += 0.4
        risk_factors.append("库存为0")
    elif monthly_sold > 0 and stock / monthly_sold < 1:
        risk += 0.3
        risk_factors.append("库存不足1个月销量")
    elif monthly_sold > 0 and stock / monthly_sold < 2:
        risk += 0.15
        risk_factors.append("库存不足2个月销量")

    # 缺货历史
    oos_30d = product.get("out_of_stock_pct_30d") or 0
    if oos_30d > 20:
        risk += 0.3
        risk_factors.append(f"近30天缺货率{oos_30d}%")
    elif oos_30d > 5:
        risk += 0.1
        risk_factors.append(f"近30天缺货率{oos_30d}%")

    # 跨境发货
    if product.get("shipping_origin") and product["shipping_origin"] not in ("US", ""):
        risk += 0.1
        risk_factors.append("跨境发货")

    # 是否有亚马逊销售（可能抢购物车）
    if product.get("has_amazon_selling"):
        risk += 0.05
        risk_factors.append("Amazon 直营竞争")

    days_until_ostock = None
    if monthly_sold and monthly_sold > 0 and stock > 0:
        days_until_ostock = round(stock / (monthly_sold / 30))

    return {
        "risk_score": round(min(risk, 1.0), 2),
        "days_until_ostock": days_until_ostock,
        "current_stock": stock,
        "monthly_sold_est": monthly_sold,
        "risk_factors": risk_factors,
        "recommendation": "建议立即补货" if risk > 0.5 else ("建议30天内补货" if risk > 0.2 else "库存充足"),
    }


def fulfillment_analysis(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    履约分析。
    Output: {"current": str, "cost_optimal": bool, "speed_optimal": bool, "recommendation": str}
    """
    is_fba = product.get("is_fba", False)
    fulfillment = product.get("fulfillment") or {}
    fba_fee = product.get("fba_fee")
    shipping_origin = product.get("shipping_origin", "") or ""

    if isinstance(fulfillment, dict):
        fulfillment_type = fulfillment.get("type", "")
    else:
        fulfillment_type = str(fulfillment) if fulfillment else ""

    is_fba_confirmed = is_fba or ("fba" in fulfillment_type.lower())

    weight = product.get("item_weight_g") or 0
    price = product.get("current_price") or 0

    # 粗略判断成本最优
    cost_optimal = True
    if is_fba_confirmed and fba_fee and price > 0 and fba_fee / price > 0.3:
        cost_optimal = False

    return {
        "current": "FBA" if is_fba_confirmed else "FBM",
        "cost_optimal": cost_optimal,
        "fba_fee": fba_fee,
        "fba_fee_ratio": round(fba_fee / price, 3) if fba_fee and price else None,
        "weight_grams": weight,
        "shipping_origin": shipping_origin,
        "recommendation": "保持FBA" if is_fba_confirmed else "建议切换到FBA以提高转化率",
    }


# ═══════════════════════════════════════════════════════════════════
# 4.6 安全与欺诈（#21 #23 #25 #30）
# ═══════════════════════════════════════════════════════════════════

def security_audit(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Listing 安全审计。
    Output: {"risk": str, "flags": list}
    """
    flags = []

    if product.get("is_redirect_asin"):
        flags.append("ASIN 重定向（可能被篡改）")
    if product.get("is_adult_product"):
        flags.append("成人商品标记")

    if product.get("parent_asin_history"):
        flags.append("父ASIN历史变更")

    risk = "high" if any([product.get("is_redirect_asin")]) else "low"

    return {"risk": risk, "flags": flags, "is_redirect": product.get("is_redirect_asin", False), "is_adult": product.get("is_adult_product", False)}


def fraud_detector(product: Dict[str, Any], offers: List[Dict] = None, change_logs: List[Dict] = None) -> Dict[str, Any]:
    """
    欺诈检测。
    Output: {"suspicious": bool, "confidence": str, "indicators": list}
    """
    indicators = []

    # 评分异常
    rating = product.get("rating") or 0
    review_count = product.get("review_count") or 0
    if review_count > 10 and rating >= 4.8:
        indicators.append("评分异常偏高（>4.8），可能存在刷评")

    # 价格异常
    buybox_price = product.get("buybox_price")
    list_price = product.get("list_price")
    if buybox_price and list_price and list_price > 0:
        discount = (list_price - buybox_price) / list_price
        if discount > 0.7:
            indicators.append(f"折扣异常大（{round(discount*100)}%），可能存在虚假原价")

    # 卖家异常
    if offers:
        china_new = [o for o in offers if o.get("ships_from_china") and o.get("condition") == "NEW"]
        if len(china_new) > 5:
            indicators.append("大量中国新卖家涌入")

    # 变更日志异常
    if change_logs:
        recent_changes = [c for c in change_logs if c.get("field") == "current_price"]
        if len(recent_changes) > 20:
            indicators.append("价格频繁变动")

    return {
        "suspicious": len(indicators) > 0,
        "confidence": "high" if len(indicators) >= 2 else "medium" if indicators else "low",
        "indicators": indicators,
    }


def compliance_checklist(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    合规检查清单。
    Output: {"status": str, "missing_items": list, "risk_items": list}
    """
    missing = []
    risks = []

    # 危险品检查
    hazardous = product.get("hazardous_materials")
    if hazardous and isinstance(hazardous, dict) and hazardous:
        risks.append(f"危险品: {hazardous}")

    # 电池合规
    if product.get("batteries_included"):
        risks.append("含电池（需危险品申报）")

    # SNS 标记
    if product.get("is_sns"):
        risks.append("SNS 标记（需额外合规审查）")

    # 基本信息缺失
    if not product.get("brand"):
        missing.append("缺少品牌信息")
    if not product.get("manufacturer"):
        missing.append("缺少制造商信息")
    if not product.get("upc") and not product.get("ean"):
        missing.append("缺少条码（UPC/EAN）")

    status = "compliant" if not missing and not risks else "attention_needed" if risks else "incomplete"

    return {
        "status": status,
        "missing_items": missing,
        "risk_items": risks,
        "has_hazardous": bool(hazardous),
        "has_batteries": product.get("batteries_included", False),
        "has_sns": product.get("is_sns", False),
    }


# ═══════════════════════════════════════════════════════════════════
# 4.7 选品与市场机会（#02 #14 #20 #22 #26）
# ═══════════════════════════════════════════════════════════════════

def product_opportunity_score(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    选品机会评分 (0-100)。
    Output: {"score": int, "signal": str, "confidence": str}
    """
    score = 50

    # BSR 趋势
    bsr_trend = product.get("bsr_trend", "unknown")
    if bsr_trend == "improving":
        score += 15
    elif bsr_trend == "declining":
        score -= 10

    # 评分和评论
    rating = product.get("rating") or 0
    review_count = product.get("review_count") or 0
    if rating >= 4.0 and review_count < 100:
        score += 15  # 高评分低竞争
    elif rating >= 4.5:
        score += 10
    elif rating < 3.5:
        score -= 10

    # 竞争度
    seller_count = product.get("seller_count") or 0
    if seller_count <= 3:
        score += 10
    elif seller_count >= 20:
        score -= 10

    # 销量估算
    monthly_sold = product.get("monthly_sold") or 0
    if monthly_sold > 500:
        score += 10
    elif monthly_sold < 50:
        score -= 5

    # 亚马逊是否在卖
    if product.get("has_amazon_selling") or product.get("buybox_is_amazon"):
        score -= 15  # Amazon 直营竞争激烈

    signal = ""
    if score >= 70:
        signal = "BSR上升 + 评分稳定 + 竞争适中"
    elif score >= 50:
        signal = "中等机会，需要进一步分析"
    else:
        signal = "竞争激烈或需求下降，建议谨慎"

    return {
        "score": max(0, min(100, score)),
        "signal": signal,
        "confidence": "high" if review_count >= 50 else "medium" if review_count >= 10 else "low",
        "bsr_trend": bsr_trend,
        "seller_count": seller_count,
        "monthly_sold": monthly_sold,
    }


def demand_analysis(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    需求侧分析。
    Output: {"monthly_demand_est": int, "bsr_trend": str, "seasonality": str}
    """
    monthly_sold = product.get("monthly_sold") or 0
    bsr_trend = product.get("bsr_trend", "unknown")
    bsr = product.get("current_bsr")

    # 从 BSR 粗估月销（基于类目平均）
    bsr_based_est = None
    if bsr and bsr > 0:
        # 非常粗略的 BSR→销量映射
        if bsr < 100:
            bsr_based_est = 3000
        elif bsr < 500:
            bsr_based_est = 1000
        elif bsr < 1000:
            bsr_based_est = 500
        elif bsr < 5000:
            bsr_based_est = 200
        elif bsr < 10000:
            bsr_based_est = 100
        else:
            bsr_based_est = 50

    demand = max(monthly_sold, bsr_based_est or 0)

    return {
        "monthly_demand_est": demand,
        "bsr_trend": bsr_trend,
        "current_bsr": bsr,
        "monthly_sold_reported": monthly_sold,
        "bsr_based_estimate": bsr_based_est,
        "seasonality": "none_detected",
        "demand_label": "高" if demand > 1000 else ("中" if demand > 200 else "低"),
    }


def category_analysis(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    品类/类目分析。
    Output: {"category_path": str, "category_health": str}
    """
    bsr_category = product.get("bsr_category", "") or ""
    category_tree = product.get("category_tree") or []

    path_parts = []
    if category_tree and isinstance(category_tree, list):
        for cat in category_tree:
            if isinstance(cat, dict):
                path_parts.append(cat.get("name", ""))
            elif isinstance(cat, str):
                path_parts.append(cat)

    path = " > ".join(path_parts) if path_parts else bsr_category

    bsr = product.get("current_bsr")
    bsr_trend = product.get("bsr_trend", "unknown")

    if bsr and bsr < 1000 and bsr_trend == "improving":
        health = "healthy"
    elif bsr and bsr < 10000:
        health = "stable"
    else:
        health = "competitive"

    return {
        "path": path,
        "category_name": bsr_category,
        "category_id": product.get("bsr_category_id"),
        "root_category_id": product.get("root_category_id"),
        "current_bsr": bsr,
        "category_health": health,
        "drift_detected": False,
    }


def cross_sell_opportunity(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    交叉销售分析。
    Output: {"top_pairs": list, "bundle_potential": str, "estimated_uplift": str}
    """
    fbt = product.get("frequently_bought_together") or {}
    sponsored = product.get("sponsored_products") or []

    related_asins = []
    if isinstance(fbt, list):
        related_asins = fbt[:5]
    elif isinstance(fbt, dict):
        related_asins = fbt.get("items", fbt.get("asins", []))[:5]

    return {
        "fbt_items": related_asins,
        "sponsored_count": len(sponsored) if sponsored else 0,
        "bundle_potential": "high" if related_asins else "medium",
        "recommended_bundle": "可以组合 FBT 中的高频搭配品",
        "estimated_uplift": "15-25%" if related_asins else "需更多数据",
    }


def variation_strategy_score(product: Dict[str, Any], variations: List[Dict] = None) -> Dict[str, Any]:
    """
    变体策略评分。
    Output: {"variant_count": int, "dimensions": list, "gaps": list}
    """
    child_asins = product.get("child_asins") or []
    variants = variations or []

    variant_count = len(variants) if variants else (len(child_asins) if child_asins else 0)

    # 提取变体维度
    dimensions = set()
    for v in variants:
        attrs = v.get("attributes") or {}
        if isinstance(attrs, str):
            # 逗号分隔的维度
            dimensions.add("variation")
        elif isinstance(attrs, dict):
            for dim_name in attrs.keys():
                dimensions.add(dim_name)
        elif isinstance(attrs, list):
            for item in attrs:
                if isinstance(item, dict):
                    dim_name = item.get("dimension", "")
                    if dim_name:
                        dimensions.add(dim_name)

    return {
        "variant_count": variant_count,
        "dimensions": sorted(dimensions) if dimensions else ["unknown"],
        "has_variations": variant_count > 0,
        "child_asins": child_asins,
        "gaps": ["变体覆盖 - Color, Size"] if variant_count < 3 else [],
    }


def product_network_graph(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    产品关联网络。
    Output: {"related_asins": list, "bundle_opportunities": list}
    """
    fbt = product.get("frequently_bought_together") or {}
    sponsored = product.get("sponsored_products") or []

    related = []
    if isinstance(fbt, dict) and fbt.get("items"):
        related = fbt["items"]
    elif isinstance(fbt, list):
        related = fbt

    return {
        "related_asins": related[:10],
        "sponsored_asins": [s.get("asin") for s in (sponsored or []) if isinstance(s, dict)][:10],
        "bundle_opportunities": related[:3] if related else [],
    }


# ═══════════════════════════════════════════════════════════════════
# 4.8 全局与综合（#01 #08 #10 #19 #33）
# ═══════════════════════════════════════════════════════════════════

def market_entry_score(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    市场进入决策评分。
    Output: {"score": int, "recommendation": str, "estimated_budget": str}
    """
    competition = competition_intensity(product.get("seller_count") or 0, product.get("offer_count") or 0)
    opportunity = product_opportunity_score(product)

    score = opportunity["score"]

    # 竞争度修正
    if competition == "high":
        score -= 15
    elif competition == "low":
        score += 10

    # Amazon 直营修正
    if product.get("buybox_is_amazon") or product.get("has_amazon_selling"):
        score -= 20

    # 评分修正
    rating = product.get("rating") or 0
    if rating >= 4.5:
        score += 5

    score = max(0, min(100, score))

    if score >= 70:
        recommendation = "推荐入场"
        budget = "$2000-5000 初始库存 + $500-1000 广告"
    elif score >= 50:
        recommendation = "可入场，但需差异化"
        budget = "$1000-3000 初始库存 + $300-500 广告"
    else:
        recommendation = "不建议入场"
        budget = "-"

    return {
        "score": score,
        "competition_level": competition,
        "product_opportunity": opportunity["score"],
        "recommendation": recommendation,
        "estimated_budget": budget,
    }


def financial_model(product: Dict[str, Any], offers: List[Dict] = None) -> Dict[str, Any]:
    """
    财务建模与 ROI 估算。
    Output: {"monthly_revenue_est": float, "monthly_profit_est": float, "roi_score": int}
    """
    price = product.get("current_price") or 0
    monthly_sold = product.get("monthly_sold") or 0
    profit = profit_analysis(product, offers)

    revenue = price * monthly_sold
    net_profit_per_unit = profit.get("net_profit", 0) or 0
    total_profit = net_profit_per_unit * monthly_sold

    # ROI score (0-100)
    roi = round((net_profit_per_unit / price) * 100, 1) if price > 0 else 0
    roi_score = min(100, max(0, int(roi * 2)))

    return {
        "monthly_revenue_est": round(revenue, 2),
        "monthly_profit_est": round(total_profit, 2),
        "gross_margin_pct": profit.get("gross_margin_pct", 0),
        "net_profit_per_unit": net_profit_per_unit,
        "roi_pct": roi,
        "roi_score": roi_score,
        "payback_days": None,  # 需采购成本数据
    }


def cross_domain_arbitrage(multi_domain_data: Dict[str, Dict]) -> Dict[str, Any]:
    """
    跨域套利分析。
    Input: {"US": {...}, "DE": {...}, ...}
    Output: {"price_diff_pct": float, "profit_arbitrage": str, "recommend_market": str}
    """
    if not multi_domain_data or len(multi_domain_data) < 1:
        return {"note": "需要至少两个站点的数据才能进行跨域分析"}

    domains_with_price = {}
    for d, data in multi_domain_data.items():
        if data and data.get("current_price"):
            domains_with_price[d] = data["current_price"]

    diffs = {}
    sorted_domains = sorted(domains_with_price.keys())
    for i in range(len(sorted_domains)):
        for j in range(i + 1, len(sorted_domains)):
            d1, d2 = sorted_domains[i], sorted_domains[j]
            p1, p2 = domains_with_price[d1], domains_with_price[d2]
            diff = round((p2 - p1) / p1 * 100, 1) if p1 else 0
            diffs[f"{d1}_to_{d2}"] = diff

    max_diff_domain = max(domains_with_price, key=domains_with_price.get) if domains_with_price else None

    return {
        "domains_available": list(domains_with_price.keys()),
        "price_diffs": diffs,
        "highest_price_domain": max_diff_domain,
        "lowest_price_domain": min(domains_with_price, key=domains_with_price.get) if domains_with_price else None,
        "profit_arbitrage": f"从低价站点到高价站点可能存在套利机会" if max_diff_domain else "无可比数据",
        "recommend_market": max_diff_domain or "unknown",
    }


def multi_domain_comparison(multi_domain_data: Dict[str, Dict]) -> Dict[str, Any]:
    """
    多域对比分析。
    Input: {"US": {...}, "DE": {...}, ...}
    Output: {"by_domain": dict, "global_ranking": str}
    """
    if not multi_domain_data:
        return {"note": "no multi-domain data"}

    by_domain = {}
    for domain, data in multi_domain_data.items():
        if not data:
            by_domain[domain] = {"status": "no_data"}
            continue
        by_domain[domain] = {
            "price": data.get("current_price"),
            "rating": data.get("rating"),
            "review_count": data.get("review_count"),
            "bsr": data.get("current_bsr"),
            "offer_count": data.get("seller_count") or data.get("offer_count"),
        }

    return {
        "by_domain": by_domain,
        "domains_count": len(multi_domain_data),
        "global_ranking": "多域数据可用于扩张决策",
    }


def anomaly_detector(product: Dict[str, Any], changes: List[Dict] = None, anomalies: List[Dict] = None) -> Dict[str, Any]:
    """
    异常检测。
    Output: {"alerts": list, "severity": str, "status": str}
    """
    alerts = []
    severity = "low"

    # 价格异常
    price = product.get("current_price")
    avg90 = product.get("avg_price_90d")
    if price and avg90 and avg90 > 0:
        deviation = abs(price - avg90) / avg90
        if deviation > 0.3:
            alerts.append(f"价格偏离90日均价{round(deviation*100)}%")
            severity = "medium" if deviation > 0.3 else severity
            severity = "high" if deviation > 0.5 else severity

    # BSR 异常
    bsr = product.get("current_bsr")
    avg_bsr = product.get("avg_bsr_90d") or product.get("avg_bsr_30d")
    if bsr and avg_bsr and avg_bsr > 0:
        bsr_ratio = bsr / avg_bsr
        if bsr_ratio > 3:
            alerts.append(f"BSR 异常恶化（当前={bsr}, 90d平均={int(avg_bsr)}）")
            severity = "high"
        elif bsr_ratio < 0.3:
            alerts.append(f"BSR 异常好转（当前={bsr}, 90d平均={int(avg_bsr)}）")
            severity = "medium"

    # 变更日志异常
    if changes:
        high_severity = [c for c in changes if isinstance(c, dict) and c.get("severity") == "high"]
        if high_severity:
            alerts.extend([f"{h.get('field', 'unknown')}: {h.get('description', '')}" for h in high_severity[:3]])
            severity = "high"

    return {
        "alerts": alerts,
        "severity": severity,
        "status": "alert" if alerts else "normal",
        "alert_count": len(alerts),
    }


def root_cause_analysis(alert_type: str, changes: List[Dict], product: Dict[str, Any]) -> Dict[str, Any]:
    """
    归因分析。
    Output: {"root_cause": str, "impact": str, "timeline": str}
    """
    if not changes:
        return {"root_cause": "insufficient_data", "impact": "unknown", "timeline": "unknown"}

    # 找最近的变化
    recent = changes[:5]
    fields_changed = [c.get("field") for c in recent if isinstance(c, dict)]

    return {
        "root_cause": f"最近变更字段: {', '.join(fields_changed[:3])}",
        "impact": "需人工核查",
        "timeline": "最近24小时内" if recent else "unknown",
        "recent_changes": recent,
    }


def international_expansion_priority(multi_domain: Dict[str, Dict]) -> Dict[str, Any]:
    """
    国际化扩张优先级。
    Input: {"US": {...}, "DE": {...}, ...}
    Output: {"priority_order": list, "cost_estimate": str, "expected_revenue": str}
    """
    if not multi_domain:
        return {"priority_order": [], "cost_estimate": "unknown", "expected_revenue": "unknown"}

    # 基础优先级：US → DE → JP → other
    priority = ["US", "DE", "JP", "GB", "FR", "IT", "ES", "CA"]

    available = [d for d in priority if d in multi_domain and multi_domain[d]]
    missing = [d for d in priority if d not in multi_domain or not multi_domain[d]]

    return {
        "priority_order": missing,
        "already_in": available,
        "cost_estimate": "$500-2000/站点（首批数据采集）",
        "expected_revenue": "需采集目标站点数据后估算",
    }


# ═══════════════════════════════════════════════════════════════════
# 主入口：全方向推导
# ═══════════════════════════════════════════════════════════════════

def compute_all_derived_fields(
    product: Dict[str, Any],
    offers: List[Dict] = None,
    variations: List[Dict] = None,
    change_logs: List[Dict] = None,
    anomaly_logs: List[Dict] = None,
    multi_domain_data: Dict[str, Dict] = None,
) -> Dict[str, Any]:
    """
    计算所有 33 个分析方向的推导结果。

    Args:
        product: AmazonProduct 原始 dict
        offers: AmazonProductOffer 列表（可选）
        variations: AmazonProductVariation 列表（可选）
        change_logs: AmazonChangeLog 列表（可选）
        anomaly_logs: AmazonAnomalyLog 列表（可选）
        multi_domain_data: 多域数据（可选，#08 #19 #33）

    Returns:
        dict with 33 keys, one per analysis direction
    """
    result = {}

    # #01 市场进入
    result["market_entry"] = market_entry_score(product)

    # #02 选品
    result["product_opportunity"] = product_opportunity_score(product)

    # #03 竞争对手
    result["competitor_profile"] = competitor_profile(offers or []) if offers else {"note": "no offer data"}

    # #04 供应链
    result["supply_chain"] = supply_chain_risk(product, offers)

    # #05 定价利润
    result["pricing_profit"] = profit_analysis(product, offers)
    result["pricing_profit"]["trend"] = price_trend(product)
    result["pricing_profit"]["volatility"] = price_volatility(product)
    result["pricing_profit"]["elasticity"] = price_elasticity(
        product.get("price_history", []), product.get("bsr_history", [])
    )

    # #06 Listing 质量
    result["listing_quality"] = listing_quality_score(product)

    # #07 生命周期
    result["lifecycle"] = lifecycle_stage(product)

    # #08 跨域
    if multi_domain_data:
        result["cross_domain"] = cross_domain_arbitrage(multi_domain_data)
    else:
        result["cross_domain"] = {"domains_available": [product.get("domain", "US")], "expansion_candidates": ["DE", "JP"]}

    # #09 异常
    result["anomaly_alerts"] = anomaly_detector(product, change_logs, anomaly_logs)

    # #10 财务
    result["financial_model"] = financial_model(product, offers)

    # #11/#27 SEO
    result["seo_audit"] = seo_audit(product)

    # #12 定价策略
    result["pricing_strategy"] = {
        "trend": price_trend(product),
        "volatility": price_volatility(product),
        "buybox_winner": buybox_winner_profile(product),
        "recommended_action": "lowest_price" if product.get("is_lowest_price") else "维持当前定价",
    }

    # #13 竞争格局
    result["competition_landscape"] = competition_landscape(product, offers)

    # #14 需求
    result["demand_analysis"] = demand_analysis(product)

    # #15 活跃度
    result["product_activity"] = activity_score(product)

    # #16 履约
    result["fulfillment"] = fulfillment_analysis(product)

    # #17 评论智能
    result["review_intelligence"] = {
        "rating": product.get("rating"),
        "review_count": product.get("review_count"),
        "rating_breakdown": product.get("rating_breakdown"),
        "top_review_topics": [],  # 需要 LLM 提取
        "improvement_priority": "需评论数据",
    }

    # #18 变体策略
    result["variation_strategy"] = variation_strategy_score(product, variations)

    # #19 多域
    if multi_domain_data:
        result["multi_domain"] = multi_domain_comparison(multi_domain_data)
    else:
        result["multi_domain"] = {"note": f"当前仅 {product.get('domain', 'US')} 域有数据"}

    # #20 品类
    result["category"] = category_analysis(product)

    # #21 归因
    result["risk_warning"] = root_cause_analysis("general", change_logs or [], product) if change_logs else {"risks": [], "overall": "low"}

    # #22 交叉销售
    result["cross_sell"] = cross_sell_opportunity(product)

    # #23 安全
    result["security"] = security_audit(product)

    # #24 卖家行为
    result["seller_behavior"] = seller_behavior_profile(offers or []) if offers else {"note": "no offer data"}

    # #25 合规
    result["compliance"] = compliance_checklist(product)

    # #26 产品网络
    result["product_network"] = product_network_graph(product)

    # #28 库存智能
    days_until = None
    monthly = product.get("monthly_sold") or 0
    stock = product.get("stock_level") or 0
    if monthly and stock:
        days_until = round(stock / (monthly / 30)) if monthly > 0 else None
    result["inventory_intelligence"] = {
        "stock_level": stock,
        "monthly_sold": monthly,
        "days_until_ostock": days_until,
        "stock_trend": "stable",
        "reorder_urgency": f"{days_until}天内" if days_until and days_until < 30 else "充足",
    }

    # #29 促销
    result["promotion_effectiveness"] = promotion_effectiveness(product)

    # #30 欺诈
    result["fraud_warning"] = fraud_detector(product, offers, change_logs)

    # #31 市场时机
    result["market_timing"] = market_timing_score(product)

    # #32 FBA 成本
    result["fba_cost_optimization"] = fba_cost_breakdown(product)
    result["fba_cost_optimization"]["current_fba_fee"] = product.get("fba_fee")

    # #33 国际化
    if multi_domain_data:
        result["international_priority"] = international_expansion_priority(multi_domain_data)
    else:
        result["international_priority"] = {"note": f"仅{product.get('domain', 'US')}域有数据，建议先采集DE域再评估"}

    return result