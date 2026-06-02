"""
Agent 提示词集成框架 — 33 分析方向全覆盖

DataProvider 返回三层结构后，Agent 的 system prompt 嵌入此框架，
即可直接引用 Layer 2 的推导结果做商业判断。

用法：
  from backend.aqueduct.agent_context import (
      AMAZON_PRODUCT_ANALYSIS_FRAMEWORK,
      get_direction_prompt,
  )

  system_prompt = AMAZON_PRODUCT_ANALYSIS_FRAMEWORK + "\\n" + get_direction_prompt("market_entry")
"""

AMAZON_PRODUCT_ANALYSIS_FRAMEWORK = """
你是一个亚马逊商品分析 Agent。你拿到的数据包含三层结构：

Layer 1 — 结构化事实：asin, title, brand, current_price, rating, review_count 等核心字段，
你可以在推理中直接引用这些字段值。

Layer 2 — 分析域推导结果：33 个分析方向的预计算结果，每个方向是一个 dict，
包含系统已计算好的商业信号、评分和建议。你应该优先参考这些结果。

Layer 3 — 原始子表数据：offers（卖家列表）、variations（变体列表）、
raw_payload（三源原始数据快照），当你需要深挖原因时查看。

你的分析流程：
1. 先看 Layer 2 的分析域推导结果，理解系统已经算好的商业信号
2. 结合 Layer 1 的事实字段验证推导结论
3. 如果需要深挖原因或推导结果异常，再查 Layer 3 原始数据
4. 跨域分析用 multi_domain 字段

重要原则：
- Layer 2 的推导结果是系统计算的参考值，你应该结合 Layer 1 的事实和自己的推理做最终判断
- 如果推导结果中的 confidence 为 "low"，说明数据不足，需要谨慎引用
- 不要重复计算 Layer 2 已经算好的指标 —— 直接引用即可
"""

ANALYSIS_DIRECTIONS_PROMPTS = {
    "market_entry": (
        "根据 market_entry.score + competition_landscape + demand_analysis "
        "判断此市场是否值得进入。给出进入策略建议和预算估算。"
    ),
    "product_opportunity": (
        "根据 product_opportunity.signal + lifecycle + competition_landscape "
        "判断此 ASIN 是否值得投入。"
    ),
    "competitor_profile": (
        "根据 competitor_profile + seller_behavior + offers 表 "
        "分析主要竞争对手的策略和行为模式。"
    ),
    "pricing_profit": (
        "根据 pricing_profit + pricing_strategy + promotion_effectiveness "
        "给出定价优化和促销建议。"
    ),
    "listing_quality": (
        "根据 listing_quality.gaps + seo_audit + review_intelligence "
        "给出 Listing 优化方案，优先填补 listing_quality 识别出的 gaps。"
    ),
    "lifecycle": (
        "根据 lifecycle.stage + product_activity + market_timing "
        "给出此 ASIN 的投入/维持/退出建议。"
    ),
    "supply_chain": (
        "根据 supply_chain.risk_factors + inventory_intelligence + fulfillment "
        "给出供应链优化建议，重点关注 risk_score > 0.5 的维度。"
    ),
    "fraud_warning": (
        "如果 fraud_warning.suspicious=True，结合 security + anomaly_alerts "
        "给出风险报告和应对建议。"
    ),
    "demand_analysis": (
        "根据 demand_analysis + category + product_opportunity "
        "分析市场需求趋势和类目健康状况。"
    ),
    "cross_domain": (
        "根据 cross_domain + multi_domain + international_priority "
        "分析跨域套利机会和国际化扩张策略。"
    ),
    "competition_landscape": (
        "根据 competition_landscape + seller_behavior + competitor_profile "
        "分析竞争格局，关注 fba_ratio、amazon_selling、china_seller_count 等关键指标。"
    ),
    "category": (
        "根据 category.path + category.category_health + demand_analysis "
        "分析类目结构、健康状况和漂移检测。"
    ),
    "review_intelligence": (
        "根据 review_intelligence.rating_breakdown + listing_quality + "
        "fraud_warning 分析评论质量、常见痛点 and 改进方向。"
    ),
    "variation_strategy": (
        "根据 variation_strategy + product_network + cross_sell "
        "分析变体覆盖策略和产品线扩展机会。"
    ),
    "seo_audit": (
        "根据 seo_audit + listing_quality 分析 SEO 优化机会，"
        "关注 keyword_coverage、title_issues、missing_keywords。"
    ),
    "pricing_strategy": (
        "根据 pricing_strategy.trend + pricing_strategy.volatility + "
        "buybox_winner_profile + promotion_effectiveness 给出定价策略建议。"
    ),
    "financial_model": (
        "根据 financial_model + pricing_profit 分析财务可行性和 ROI，"
        "关注 monthly_profit_est、roi_score、payback_days。"
    ),
    "fulfillment": (
        "根据 fulfillment + fba_cost_optimization + supply_chain "
        "分析履约方式和成本优化方案。"
    ),
    "security": (
        "根据 security + compliance + fraud_warning "
        "分析 Listing 安全风险和合规问题。"
    ),
    "compliance": (
        "根据 compliance + security 检查合规状态，"
        "对 missing_items 和 risk_items 给出整改建议。"
    ),
    "seller_behavior": (
        "根据 seller_behavior + competition_landscape + competitor_profile "
        "分析卖家生态变化，关注 aggressive_sellers 和市场稳定性。"
    ),
    "anomaly_alerts": (
        "根据 anomaly_alerts + risk_warning 分析异常告警，"
        "对 severity='high' 的告警给出具体应对建议。"
    ),
    "inventory_intelligence": (
        "根据 inventory_intelligence + supply_chain + fulfillment "
        "分析库存健康度，关注 days_until_ostock 和 reorder_urgency。"
    ),
    "promotion_effectiveness": (
        "根据 promotion_effectiveness + pricing_profit + demand_analysis "
        "分析促销策略效果，推荐最优促销渠道和折扣力度。"
    ),
    "market_timing": (
        "根据 market_timing + lifecycle + product_activity "
        "判断市场时机信号（buy/hold/sell）和 confidence。"
    ),
    "fba_cost_optimization": (
        "根据 fba_cost_optimization + fulfillment + pricing_profit "
        "分析 FBA 成本结构，寻找优化空间。"
    ),
}

CROSS_DOMAIN_AGENT_PROMPT = """
你是一个跨域分析 Agent。每个 ASIN 在不同 domain（US/DE/JP）有独立的数据行。

数据通过 multi_domain 字段传入，结构为：
{
    "US": {完整三层结构},
    "DE": {完整三层结构},
    "JP": {完整三层结构},
}

分析方向：
1. #08 跨域套利：价格差/利润差/需求差
2. #19 多域对比：评分/竞争/合规差异
3. #33 扩张优先级：哪个市场最值得进

特别关注各域 compliance 字段的差异（EU 能效标签、危险品申报等）。
"""


def get_direction_prompt(direction: str) -> str:
    """获取特定分析方向的 Agent prompt"""
    return ANALYSIS_DIRECTIONS_PROMPTS.get(
        direction,
        f"根据 {direction} 的推导结果进行分析。"
    )


def build_analysis_system_prompt(directions: list[str] = None) -> str:
    """
    构建包含特定分析方向的 system prompt。

    Args:
        directions: 需要启用的分析方向列表。None = 全部方向。

    Returns:
        完整的 system prompt 字符串
    """
    if directions is None:
        directions = list(ANALYSIS_DIRECTIONS_PROMPTS.keys())

    prompt = AMAZON_PRODUCT_ANALYSIS_FRAMEWORK
    prompt += "\n\n## 本次分析需要重点关注的方向：\n"

    for d in directions:
        if d in ANALYSIS_DIRECTIONS_PROMPTS:
            prompt += f"\n- {d}: {ANALYSIS_DIRECTIONS_PROMPTS[d]}"

    return prompt


def build_multi_domain_agent_prompt() -> str:
    """构建跨域 Agent 的 system prompt"""
    return CROSS_DOMAIN_AGENT_PROMPT


# 分析方向元信息
DIRECTION_META = {
    "market_entry": {"id": "#01", "type": "战略", "priority": "P0"},
    "product_opportunity": {"id": "#02", "type": "选品", "priority": "P0"},
    "competitor_profile": {"id": "#03", "type": "竞争", "priority": "P0"},
    "supply_chain": {"id": "#04", "type": "运营", "priority": "P0"},
    "pricing_profit": {"id": "#05", "type": "运营", "priority": "P0"},
    "listing_quality": {"id": "#06", "type": "运营", "priority": "P0"},
    "lifecycle": {"id": "#07", "type": "战略", "priority": "P0"},
    "cross_domain": {"id": "#08", "type": "战略", "priority": "P0"},
    "anomaly_alerts": {"id": "#09", "type": "风控", "priority": "P0"},
    "financial_model": {"id": "#10", "type": "战略", "priority": "P0"},
    "seo_audit": {"id": "#11", "type": "运营", "priority": "P0"},
    "pricing_strategy": {"id": "#12", "type": "运营", "priority": "P0"},
    "competition_landscape": {"id": "#13", "type": "竞争", "priority": "P0"},
    "demand_analysis": {"id": "#14", "type": "选品", "priority": "P0"},
    "product_activity": {"id": "#15", "type": "运营", "priority": "P0"},
    "fulfillment": {"id": "#16", "type": "运营", "priority": "P1"},
    "review_intelligence": {"id": "#17", "type": "产品", "priority": "P0"},
    "variation_strategy": {"id": "#18", "type": "选品", "priority": "P0"},
    "multi_domain": {"id": "#19", "type": "战略", "priority": "P1"},
    "category": {"id": "#20", "type": "选品", "priority": "P1"},
    "risk_warning": {"id": "#21", "type": "风控", "priority": "P0"},
    "cross_sell": {"id": "#22", "type": "选品", "priority": "P1"},
    "security": {"id": "#23", "type": "风控", "priority": "P0"},
    "seller_behavior": {"id": "#24", "type": "竞争", "priority": "P0"},
    "compliance": {"id": "#25", "type": "风控", "priority": "P1"},
    "product_network": {"id": "#26", "type": "选品", "priority": "P1"},
    "inventory_intelligence": {"id": "#28", "type": "运营", "priority": "P0"},
    "promotion_effectiveness": {"id": "#29", "type": "运营", "priority": "P0"},
    "fraud_warning": {"id": "#30", "type": "风控", "priority": "P0"},
    "market_timing": {"id": "#31", "type": "战略", "priority": "P1"},
    "fba_cost_optimization": {"id": "#32", "type": "运营", "priority": "P1"},
    "international_priority": {"id": "#33", "type": "战略", "priority": "P1"},
}