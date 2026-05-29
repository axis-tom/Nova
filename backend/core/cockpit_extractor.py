"""
Cockpit Data Extractor
从每个 Agent 的 session state 中提取结构化驾驶舱数据，
供前端多维驾驶舱渲染图表和充足度标签。

完全不影响 Agent 调度 — 只在 Agent 执行完毕后读取 state.data 做一次映射。
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Agent → Category 中文标签映射 ──

AGENT_CATEGORY_LABELS: Dict[str, str] = {
    "keyword_expander": "关键词扩展",
    "product_collector": "商品采集",
    "review_analyzer": "评论分析",
    "traffic_analyzer": "流量分析",
    "opportunity_judge": "机会评估",
    "market_analyst": "市场分析",
    "competitor_analyst": "竞品分析",
    "briefing_generator": "简报汇总",
}

# 每个 Agent 会向 state.data 写入哪些 key
AGENT_STATE_KEYS: Dict[str, List[str]] = {
    "keyword_expander": ["keyword_groups", "expanded_keywords"],
    "product_collector": ["collected_products", "collection_stats", "product_map"],
    "review_analyzer": ["review_insights", "sentiment_summary", "customer_needs"],
    "traffic_analyzer": ["bsr_analysis", "price_analysis", "competitor_comparison", "price_alerts", "traffic_insights"],
    "opportunity_judge": ["opportunities", "top_picks", "alerts", "alert_summary", "market_report"],
    "market_analyst": ["market_analysis_result", "profitability_result"],
    "competitor_analyst": ["competitor_analysis_result"],
    "briefing_generator": ["briefing", "result"],
}


def extract_cockpit_data(agent_name: str, state_data: dict) -> Optional[dict]:
    """
    从 agent 执行后的 state.data 中提取驾驶舱数据。

    Args:
        agent_name: Agent 名称（如 product_collector）
        state_data: session store 中的 data dict

    Returns:
        cockpit_update 事件的 data 部分，或 None（无可展示数据）
    """
    extractor = _EXTRACTORS.get(agent_name)
    if not extractor:
        return None

    try:
        result = extractor(state_data)
        if result and result.get("dimensions"):
            return result
    except Exception as e:
        logger.debug(f"cockpit_extract: {agent_name} skipped ({e})")
        return None


# ── 提取器注册表 ──

_EXTRACTORS: Dict[str, callable] = {}


def _register(name: str):
    """装饰器：注册 agent_name 对应的提取函数"""
    def decorator(fn):
        _EXTRACTORS[name] = fn
        return fn
    return decorator


# ── 工具函数 ──

def _pct(pct: float) -> int:
    """转成 0-100 整数百分比"""
    return max(0, min(100, round(pct * 100 if pct < 1 else pct)))


def _sufficiency(percent: int) -> dict:
    """生成充足度对象"""
    if percent >= 80:
        return {"status": "sufficient", "percent": percent, "message": "数据充分"}
    elif percent >= 50:
        return {"status": "moderate", "percent": percent, "message": "数据一般"}
    else:
        return {"status": "insufficient", "percent": percent, "message": "数据不足"}


def _dim(name: str, status: str, percent: int, charts: dict, default_chart: str = "bar",
         message: str = "") -> dict:
    """构造单维度对象"""
    dim = {
        "dimension_id": f"{name.lower().replace(' ', '_')}",
        "name": name,
        "sufficiency": {
            "status": status,
            "percent": percent,
            "message": message,
        },
        "charts": charts,
        "default_chart": default_chart,
        "enabled": True,
    }
    if not dim["sufficiency"]["message"]:
        msg_map = {"sufficient": "数据充分", "moderate": "数据一般", "insufficient": "数据不足"}
        dim["sufficiency"]["message"] = msg_map.get(status, "")
    return dim


def _bar_chart(x_data: list, series: list, title: str = "") -> dict:
    return {"title": title, "xAxis": {"data": x_data}, "series": series}


def _pie_chart(data: list, title: str = "") -> dict:
    return {"title": title, "data": data}


# ══════════════════════════════════════════════
#  各 Agent 提取器
# ══════════════════════════════════════════════

@_register("keyword_expander")
def _extract_keyword_expander(data: dict) -> Optional[dict]:
    """关键词扩展 → 各组关键词数量柱状图"""
    groups = data.get("keyword_groups")
    if not groups or not isinstance(groups, dict):
        return None

    # 各分组的关键词数量
    labels = list(groups.keys())
    counts = [len(v) for v in groups.values()]

    return {
        "agent_name": "keyword_expander",
        "category_label": AGENT_CATEGORY_LABELS["keyword_expander"],
        "dimensions": [
            _dim(
                name="关键词分组分布",
                status="sufficient" if sum(counts) > 10 else "moderate",
                percent=_pct(min(sum(counts) / 100, 1.0)),
                charts={
                    "bar": _bar_chart(labels, [{"name": "关键词数", "data": counts}], "关键词分组分布"),
                    "pie": _pie_chart([{"name": labels[i], "value": counts[i]} for i in range(len(labels))], "关键词分组占比"),
                },
                default_chart="bar",
                message=f"共 {sum(counts)} 个关键词，{len(labels)} 个分组",
            )
        ],
    }


@_register("product_collector")
def _extract_product_collector(data: dict) -> Optional[dict]:
    """商品采集 → 采集统计 + 价格/评分/BSR 分布"""
    products = data.get("collected_products")
    stats = data.get("collection_stats")
    if not products or not isinstance(products, list):
        return None

    total = len(products)
    dimensions = []

    # 维度1: 采集概览
    if stats and isinstance(stats, dict):
        source_labels = stats.get("data_sources", [])
        dimensions.append(
            _dim(
                name="采集概览",
                status="sufficient" if total >= 10 else "moderate",
                percent=_pct(min(total / 50, 1.0)),
                charts={
                    "bar": _bar_chart(["采集商品数"], [{"name": "商品数", "data": [total]}], f"共采集 {total} 个商品"),
                    "pie": _pie_chart([{"name": s, "value": 1} for s in source_labels], "数据源分布"),
                },
                default_chart="bar",
                message=f"采集 {total} 个商品，来源: {', '.join(source_labels)}",
            )
        )

    # 维度2: 价格带分布
    prices = [p.get("current_price", 0) or 0 for p in products if p.get("current_price")]
    if prices:
        bands = {"<$20": 0, "$20-$50": 0, "$50-$100": 0, "$100+": 0}
        for p in prices:
            if p < 20:
                bands["<$20"] += 1
            elif p < 50:
                bands["$20-$50"] += 1
            elif p < 100:
                bands["$50-$100"] += 1
            else:
                bands["$100+"] += 1
        band_labels = list(bands.keys())
        band_counts = list(bands.values())
        avg_price = round(sum(prices) / len(prices), 2)
        dimensions.append(
            _dim(
                name="价格带分布",
                status="sufficient" if len(prices) >= 5 else "moderate",
                percent=_pct(len(prices) / total),
                charts={
                    "bar": _bar_chart(band_labels, [{"name": "商品数", "data": band_counts}], f"均价 ${avg_price}"),
                    "pie": _pie_chart([{"name": band_labels[i], "value": band_counts[i]} for i in range(len(band_labels))], "价格带占比"),
                },
                default_chart="bar",
                message=f"均价 ${avg_price}",
            )
        )

    # 维度3: 评分分布
    ratings = [p.get("rating", 0) or 0 for p in products if p.get("rating")]
    if ratings:
        rating_bands = {"4-5★": 0, "3-4★": 0, "2-3★": 0, "1-2★": 0}
        for r in ratings:
            if r >= 4:
                rating_bands["4-5★"] += 1
            elif r >= 3:
                rating_bands["3-4★"] += 1
            elif r >= 2:
                rating_bands["2-3★"] += 1
            else:
                rating_bands["1-2★"] += 1
        avg_rating = round(sum(ratings) / len(ratings), 2)
        dimensions.append(
            _dim(
                name="评分分布",
                status="sufficient" if len(ratings) >= 5 else "moderate",
                percent=_pct(len(ratings) / total),
                charts={
                    "bar": _bar_chart(list(rating_bands.keys()), [{"name": "商品数", "data": list(rating_bands.values())}], f"均分 {avg_rating}"),
                    "pie": _pie_chart([{"name": k, "value": v} for k, v in rating_bands.items()], "评分占比"),
                },
                default_chart="bar",
                message=f"均分 {avg_rating}",
            )
        )

    return {
        "agent_name": "product_collector",
        "category_label": AGENT_CATEGORY_LABELS["product_collector"],
        "dimensions": dimensions,
    }


@_register("review_analyzer")
def _extract_review_analyzer(data: dict) -> Optional[dict]:
    """评论分析 → 情感分析、评论壁垒分布、评分定位"""
    sentiment = data.get("sentiment_summary")
    insights = data.get("review_insights")
    if not sentiment and not insights:
        return None

    dimensions = []

    if sentiment and isinstance(sentiment, dict):
        # 维度1: 评论壁垒分布
        barrier_dist = sentiment.get("review_barrier_distribution")
        if barrier_dist and isinstance(barrier_dist, dict):
            dimensions.append(
                _dim(
                    name="评论壁垒分布",
                    status="sufficient",
                    percent=85,
                    charts={
                        "bar": _bar_chart(list(barrier_dist.keys()), [{"name": "商品数", "data": list(barrier_dist.values())}], "评论壁垒分布"),
                        "pie": _pie_chart([{"name": k, "value": v} for k, v in barrier_dist.items()], "评论壁垒占比"),
                    },
                    default_chart="bar",
                    message="评论壁垒越高，新品进入难度越大",
                )
            )

        # 维度2: 情感倾向
        pos = sentiment.get("avg_positive_pct", 0)
        neg = sentiment.get("avg_negative_pct", 0)
        neu = sentiment.get("avg_neutral_pct", 0)
        if pos or neg or neu:
            dimensions.append(
                _dim(
                    name="情感倾向",
                    status="sufficient",
                    percent=_pct(pos / 100) if pos else 70,
                    charts={
                        "pie": _pie_chart([
                            {"name": f"正面 {pos}%", "value": pos},
                            {"name": f"中性 {neu}%", "value": neu},
                            {"name": f"负面 {neg}%", "value": neg},
                        ], "评论情感分布"),
                        "bar": _bar_chart(["正面", "中性", "负面"], [{"name": "占比", "data": [pos, neu, neg]}], "评论情感分布"),
                    },
                    default_chart="pie",
                    message=f"市场情感: {sentiment.get('market_sentiment', '未知')}",
                )
            )

    if insights and isinstance(insights, list) and len(insights) > 0:
        # 维度3: 商品评分排序
        sorted_insights = sorted(insights, key=lambda x: x.get("rating", 0), reverse=True)[:10]
        dims = []
        for ins in sorted_insights:
            name = (ins.get("title") or ins.get("asin") or "未知")[:15]
            dims.append({"name": name, "value": ins.get("rating", 0)})
        dimensions.append(
            _dim(
                name="评分排序",
                status="sufficient",
                percent=80,
                charts={
                    "bar": _bar_chart(
                        [d["name"] for d in dims],
                        [{"name": "评分", "data": [d["value"] for d in dims]}],
                        "Top 商品评分",
                    ),
                },
                default_chart="bar",
                message=f"分析 {len(insights)} 个商品的评论",
            )
        )

    return {
        "agent_name": "review_analyzer",
        "category_label": AGENT_CATEGORY_LABELS["review_analyzer"],
        "dimensions": dimensions,
    }


@_register("traffic_analyzer")
def _extract_traffic_analyzer(data: dict) -> Optional[dict]:
    """流量分析 → BSR 分布、价格分布、竞品对比"""
    bsr = data.get("bsr_analysis")
    price = data.get("price_analysis")
    if not bsr and not price:
        return None

    dimensions = []

    if bsr and isinstance(bsr, dict):
        dist = bsr.get("distribution")
        if dist and isinstance(dist, dict):
            dimensions.append(
                _dim(
                    name="BSR 排名分布",
                    status="sufficient",
                    percent=85,
                    charts={
                        "bar": _bar_chart(list(dist.keys()), [{"name": "商品数", "data": list(dist.values())}], f"BSR 分布 (平均 {bsr.get('avg_bsr', '?')})"),
                        "pie": _pie_chart([{"name": k, "value": v} for k, v in dist.items()], "BSR 占比"),
                    },
                    default_chart="bar",
                    message=f"平均 BSR: {bsr.get('avg_bsr', '?')}",
                )
            )

    if price and isinstance(price, dict):
        price_dist = price.get("price_distribution")
        if price_dist and isinstance(price_dist, dict):
            dimensions.append(
                _dim(
                    name="价格分布",
                    status="sufficient",
                    percent=85,
                    charts={
                        "bar": _bar_chart(list(price_dist.keys()), [{"name": "商品数", "data": list(price_dist.values())}], f"均价 ${price.get('avg_price', '?')}"),
                        "pie": _pie_chart([{"name": k, "value": v} for k, v in price_dist.items()], "价格带占比"),
                    },
                    default_chart="bar",
                    message=f"均价 ${price.get('avg_price', '?')}，Prime 占比 {price.get('prime_ratio', 0)}%",
                )
            )

    return {
        "agent_name": "traffic_analyzer",
        "category_label": AGENT_CATEGORY_LABELS["traffic_analyzer"],
        "dimensions": dimensions,
    }


@_register("opportunity_judge")
def _extract_opportunity_judge(data: dict) -> Optional[dict]:
    """机会评估 → 评分雷达图、Top 选品排序、预警分布"""
    top_picks = data.get("top_picks") or data.get("opportunities", [])
    alerts = data.get("alert_summary")
    if not top_picks and not alerts:
        return None

    dimensions = []

    # 维度1: 评分详情（雷达图）
    picks = top_picks if isinstance(top_picks, list) else []
    if picks:
        # 取 Top 1 的评分雷达
        best = picks[0]
        if isinstance(best, dict) and "score_detail" in best:
            sd = best["score_detail"]
            radar_dims = list(sd.keys())
            radar_values = list(sd.values())
            dimensions.append(
                _dim(
                    name="综合评分",
                    status="sufficient",
                    percent=_pct(best.get("total_score", 0) / 100),
                    # 雷达图用 scatter+bar 近似；前端雷达图需自定义 series
                    charts={
                        "bar": _bar_chart(radar_dims, [{"name": "得分", "data": radar_values}], f"总分 {best.get('total_score', '?')}"),
                    },
                    default_chart="bar",
                    message=f"等级 {best.get('score_grade', '?')}: {best.get('opportunity_reason', '')}"[:60],
                )
            )

        # 维度2: Top 选品排序
        top10 = picks[:10]
        names = []
        scores = []
        for p in top10:
            title = (p.get("title") or p.get("asin") or "未知")[:12]
            names.append(title)
            scores.append(p.get("total_score", 0))
        dimensions.append(
            _dim(
                name="Top 选品评分",
                status="sufficient",
                percent=85,
                charts={
                    "bar": _bar_chart(names, [{"name": "综合评分", "data": scores}], "Top 选品评分排序"),
                },
                default_chart="bar",
                message=f"Top 1: {names[0] if names else ''} ({scores[0] if scores else 0}分)",
            )
        )

    # 维度3: 预警分布
    if alerts and isinstance(alerts, dict):
        by_type = alerts.get("by_type", {})
        by_severity = alerts.get("by_severity", {})
        if by_type:
            dimensions.append(
                _dim(
                    name="预警分布",
                    status="moderate" if alerts.get("total", 0) > 0 else "sufficient",
                    percent=_pct(1 - alerts.get("total", 0) / 20),
                    charts={
                        "pie": _pie_chart([{"name": k, "value": v} for k, v in by_type.items()], f"共 {alerts.get('total', 0)} 条预警"),
                        "bar": _bar_chart(list(by_type.keys()), [{"name": "预警数", "data": list(by_type.values())}], "预警类型分布"),
                    },
                    default_chart="pie",
                    message=f"{alerts.get('total', 0)} 条预警，高危 {alerts.get('high_severity_count', 0)} 条",
                )
            )

    return {
        "agent_name": "opportunity_judge",
        "category_label": AGENT_CATEGORY_LABELS["opportunity_judge"],
        "dimensions": dimensions,
    }


@_register("market_analyst")
def _extract_market_analyst(data: dict) -> Optional[dict]:
    """市场分析 → 品牌份额、价格带、评论壁垒、评分健康度、BSR 趋势、淡旺季"""
    market = data.get("market_analysis_result")
    if not market or not isinstance(market, dict):
        return None

    dimensions = []

    # 维度1: 品牌份额
    brand_analysis = market.get("brand_analysis", {})
    brands = brand_analysis.get("brands", [])
    if brands and isinstance(brands, list):
        top10 = brands[:10]
        dimensions.append(
            _dim(
                name="品牌份额",
                status="sufficient",
                percent=_pct(brand_analysis.get("top_3_market_share_pct", 50) / 100),
                charts={
                    "bar": _bar_chart(
                        [b.get("brand", "?")[:10] for b in top10],
                        [{"name": "月销量", "data": [b.get("total_monthly_sales", 0) for b in top10]}],
                        f"Top3 集中度 {brand_analysis.get('top_3_market_share_pct', '?')}%",
                    ),
                    "pie": _pie_chart(
                        [{"name": b.get("brand", "?")[:10], "value": b.get("total_monthly_sales", 0)} for b in top10],
                        "品牌份额",
                    ),
                },
                default_chart="bar",
                message=f"共 {brand_analysis.get('total_brands', '?')} 个品牌，集中度 {'高' if brand_analysis.get('top_3_market_share_pct', 0) > 60 else '中' if brand_analysis.get('top_3_market_share_pct', 0) > 40 else '低'}",
            )
        )

    # 维度2: 价格带分布
    price_bands = market.get("price_bands") or market.get("market_volume", {}).get("price_tier_distribution")
    if price_bands and isinstance(price_bands, dict):
        dims = []
        for band_name, band_data in price_bands.items():
            cnt = band_data.get("count", 0) if isinstance(band_data, dict) else (band_data if isinstance(band_data, (int, float)) else 0)
            dims.append({"name": band_name, "value": cnt})
        if dims:
            dimensions.append(
                _dim(
                    name="价格带分布",
                    status="sufficient",
                    percent=85,
                    charts={
                        "bar": _bar_chart([d["name"] for d in dims], [{"name": "商品数", "data": [d["value"] for d in dims]}], "各价格带商品数"),
                        "pie": _pie_chart(dims, "价格带占比"),
                    },
                    default_chart="bar",
                )
            )

    # 维度3: 评论壁垒分布
    review_barrier = market.get("review_barrier", {})
    barrier_dist = review_barrier.get("distribution", {})
    if barrier_dist:
        labels = list(barrier_dist.keys())
        values = list(barrier_dist.values())
        dimensions.append(
            _dim(
                name="评论壁垒",
                status="sufficient" if sum(values) > 10 else "moderate",
                percent=_pct(review_barrier.get("median_review_count", 0) / 5000) if review_barrier.get("median_review_count", 0) else 60,
                charts={
                    "bar": _bar_chart(labels, [{"name": "商品数", "data": values}], f"中位数 {review_barrier.get('median_review_count', '?')} 条评论"),
                    "pie": _pie_chart([{"name": labels[i], "value": values[i]} for i in range(len(labels))], "评论壁垒占比"),
                },
                default_chart="bar",
                message=f"壁垒等级: {review_barrier.get('review_barrier', '未知')}，中位数 {review_barrier.get('median_review_count', '?')}",
            )
        )

    # 维度4: 评分健康度
    rating_health = market.get("rating_health", {})
    health_dist = rating_health.get("distribution_detail", {})
    if health_dist:
        dim_names = ["优秀", "良好", "一般", "较差"]
        dim_vals = [health_dist.get("excellent_count", 0), health_dist.get("good_count", 0),
                    health_dist.get("average_count", 0), health_dist.get("poor_count", 0)]
        dimensions.append(
            _dim(
                name="评分健康度",
                status="sufficient" if rating_health.get("rating_health_score", 0) >= 60 else "moderate",
                percent=_pct(rating_health.get("rating_health_score", 50) / 100),
                charts={
                    "bar": _bar_chart(dim_names, [{"name": "商品数", "data": dim_vals}], f"健康分 {rating_health.get('rating_health_score', '?')}"),
                    "pie": _pie_chart([{"name": dim_names[i], "value": dim_vals[i]} for i in range(4) if dim_vals[i]], "评分健康分布"),
                },
                default_chart="bar",
                message=f"健康分 {rating_health.get('rating_health_score', '?')}，均分 {rating_health.get('avg_rating', '?')}",
            )
        )

    # 维度5: BSR 趋势
    trends = market.get("trends", {})
    bsr_trends = trends.get("bsr", {})
    if bsr_trends:
        trend_items = [
            {"name": "改善中", "value": bsr_trends.get("improving_pct", 0)},
            {"name": "下降", "value": bsr_trends.get("declining_pct", 0)},
            {"name": "稳定", "value": bsr_trends.get("stable_pct", 0)},
        ]
        dimensions.append(
            _dim(
                name="BSR 趋势",
                status="sufficient",
                percent=85,
                charts={
                    "pie": _pie_chart([t for t in trend_items if t["value"] > 0], f"市场方向: {bsr_trends.get('market_direction', '?')}"),
                    "bar": _bar_chart([t["name"] for t in trend_items], [{"name": "占比 %", "data": [t["value"] for t in trend_items]}], "BSR 趋势分布"),
                },
                default_chart="pie",
                message=f"市场方向: {bsr_trends.get('market_direction', '?')}",
            )
        )

    # 维度6: 淡旺季（月度 BSR 折线图）
    seasonality = market.get("seasonality", {})
    monthly_bsr = seasonality.get("monthly_bsr_median", {})
    if monthly_bsr and isinstance(monthly_bsr, dict):
        months = [f"{m}月" for m in range(1, 13)]
        bsr_vals = [monthly_bsr.get(m, 0) for m in range(1, 13)]
        dimensions.append(
            _dim(
                name="淡旺季趋势",
                status="sufficient" if any(v > 0 for v in bsr_vals) else "moderate",
                percent=80,
                charts={
                    "line": {
                        "title": "月度 BSR 中位数趋势",
                        "xAxis": {"name": "月份", "data": months},
                        "yAxis": {"name": "BSR 中位数"},
                        "series": [{"name": "BSR", "data": bsr_vals}],
                    },
                    "bar": _bar_chart(months, [{"name": "BSR", "data": bsr_vals}], "月度 BSR 中位数"),
                },
                default_chart="line",
                message=f"旺季: {', '.join(str(m)+'月' for m in seasonality.get('peak_season_months', []))}",
            )
        )

    # 维度7: 卖家构成
    seller = market.get("seller_composition", {})
    if seller and isinstance(seller, dict):
        dimensions.append(
            _dim(
                name="卖家构成",
                status="sufficient",
                percent=85,
                charts={
                    "pie": _pie_chart([
                        {"name": f"FBA ({seller.get('fba_pct', 0)}%)", "value": seller.get('fba_count', 0)},
                        {"name": f"FBM ({seller.get('fbm_pct', 0)}%)", "value": seller.get('fbm_count', 0)},
                    ], f"FBA {seller.get('fba_pct', 0)}% / Prime {seller.get('prime_pct', 0)}%"),
                },
                default_chart="pie",
                message=f"FBA {seller.get('fba_pct', 0)}%，Prime {seller.get('prime_pct', 0)}%",
            )
        )

    return {
        "agent_name": "market_analyst",
        "category_label": AGENT_CATEGORY_LABELS["market_analyst"],
        "dimensions": dimensions,
    } if dimensions else None


@_register("competitor_analyst")
def _extract_competitor_analyst(data: dict) -> Optional[dict]:
    """竞品分析 → 市场份额、Listing 质量、竞争梯队"""
    comp = data.get("competitor_analysis_result")
    if not comp or not isinstance(comp, dict):
        return None

    dimensions = []

    # 维度1: 市场份额
    share = comp.get("market_share_distribution", [])
    if share and isinstance(share, list):
        top8 = share[:8]
        dimensions.append(
            _dim(
                name="市场份额",
                status="sufficient",
                percent=85,
                charts={
                    "bar": _bar_chart(
                        [b.get("brand", "?") for b in top8],
                        [{"name": "份额 %", "data": [b.get("market_share_percent", 0) for b in top8]}],
                        "品牌市场份额 (%)",
                    ),
                    "pie": _pie_chart(
                        [{"name": b.get("brand", "?"), "value": b.get("market_share_percent", 0)} for b in top8],
                        "品牌份额",
                    ),
                },
                default_chart="bar",
                message=f"Top 品牌: {top8[0].get('brand', '?') if top8 else ''}",
            )
        )

    # 维度2: Listing 质量
    lq = comp.get("listing_quality", {})
    lq_dist = lq.get("distribution", {})
    if lq_dist:
        dimensions.append(
            _dim(
                name="Listing 质量",
                status="sufficient",
                percent=_pct(lq.get("average_listing_score", 5) / 10),
                charts={
                    "bar": _bar_chart(list(lq_dist.keys()), [{"name": "商品数", "data": list(lq_dist.values())}], f"均分 {lq.get('average_listing_score', '?')}/10"),
                    "pie": _pie_chart([{"name": k, "value": v} for k, v in lq_dist.items()], "Listing 质量分布"),
                },
                default_chart="bar",
                message=f"平均 {lq.get('average_listing_score', '?')}/10 分",
            )
        )

    return {
        "agent_name": "competitor_analyst",
        "category_label": AGENT_CATEGORY_LABELS["competitor_analyst"],
        "dimensions": dimensions,
    } if dimensions else None


@_register("briefing_generator")
def _extract_briefing_generator(data: dict) -> Optional[dict]:
    """简报汇总 → 显示已覆盖的分析维度"""
    briefing = data.get("briefing", {})
    sections = briefing.get("sections_available", {}) if isinstance(briefing, dict) else {}
    if not sections:
        return None

    avail = []
    for section_name, ok in sections.items():
        if ok:
            avail.append(section_name)

    return {
        "agent_name": "briefing_generator",
        "category_label": AGENT_CATEGORY_LABELS["briefing_generator"],
        "dimensions": [
            _dim(
                name="简报覆盖",
                status="sufficient" if len(avail) >= 3 else "moderate",
                percent=_pct(len(avail) / 5),
                charts={
                    "pie": _pie_chart([{"name": s, "value": 1} for s in avail] + [{"name": "未覆盖", "value": max(0, 5 - len(avail))}], "分析覆盖度"),
                },
                default_chart="pie",
                message=f"覆盖 {len(avail)}/5 个分析模块",
            )
        ],
    }