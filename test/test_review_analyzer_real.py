"""
P3 Step 3 验收：review_analyzer 真数据端到端测试
用 Keepa 拉真实商品数据 → review_analyzer 分析 → 打印结果
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.common.core.state import State
from backend.business.ecommerce.amazon_monitor.tools.keepa_connector import KeepaConnector
from backend.business.ecommerce.amazon_monitor.agents.review_analyzer import AmazonReviewAnalyzerAgent


OUR_ASIN = "B0F9FS7WQQ"
COMPETITOR_ASINS = [
    "B07QK9C9KT", "B0D97YVVQ2", "B0F43SPZCY", "B0GHYNVYMD",
    "B08911JGGW", "B0BKQ7MY3L", "B0CXM46BDK", "B0FG2WDNWL",
    "B0F8P5RMPD", "B0DZD77DN9", "B0CRDT715R",
]
ALL_ASINS = [OUR_ASIN] + COMPETITOR_ASINS


async def main():
    # ── 1. Keepa 拉数据 ──
    print("=" * 60)
    print(f"📦 Keepa 拉取 {len(ALL_ASINS)} 个 ASIN 的商品数据...")
    print("=" * 60)

    connector = KeepaConnector()
    products = connector.query_products(ALL_ASINS)

    if not products:
        print("❌ Keepa 返回空数据，检查 API key / token 余量")
        return

    print(f"✅ 拉取成功：{len(products)} 个商品\n")

    for p in products:
        print(f"  {p['asin']} | {(p.get('title') or '')[:50]} | "
              f"★{p.get('rating') or 'N/A'} | "
              f"评论 {p.get('review_count') or 0} | "
              f"月销 {p.get('monthly_sold') or 0} | "
              f"${p.get('current_price') or 'N/A'}")
    print()

    # ── 2. review_analyzer 分析 ──
    print("=" * 60)
    print("🔍 运行 review_analyzer...")
    print("=" * 60)

    state = State()
    state.set("collected_products", products)

    agent = AmazonReviewAnalyzerAgent()
    result_state = agent.run(state)

    review_insights = result_state.get("review_insights", [])
    sentiment_summary = result_state.get("sentiment_summary", {})
    customer_needs = result_state.get("customer_needs", [])

    # ── 3. 打印结果 ──

    # 3a. 整体情感摘要
    print(f"\n{'=' * 60}")
    print("📊 整体情感摘要")
    print(f"{'=' * 60}")
    print(f"  分析商品数: {sentiment_summary.get('total_analyzed', 0)}")
    print(f"  平均评分: {sentiment_summary.get('avg_rating', 0)}")
    print(f"  平均正面占比: {sentiment_summary.get('avg_positive_pct', 0)}%")
    print(f"  平均负面占比: {sentiment_summary.get('avg_negative_pct', 0)}%")
    print(f"  高评分(≥4.5): {sentiment_summary.get('high_rated_count', 0)} 个")
    print(f"  低评分(<3.5): {sentiment_summary.get('low_rated_count', 0)} 个")
    print(f"  市场情感: {sentiment_summary.get('market_sentiment', 'N/A')}")

    barrier = sentiment_summary.get("review_barrier_distribution", {})
    if barrier:
        print(f"  评论壁垒分布: {json.dumps(barrier, ensure_ascii=False)}")

    top_praise = sentiment_summary.get("top_praise_keywords", [])
    if top_praise:
        print(f"\n  🟢 Top 好评关键词:")
        for kw in top_praise:
            print(f"    • {kw}")

    top_complaints = sentiment_summary.get("top_complaint_keywords", [])
    if top_complaints:
        print(f"\n  🔴 Top 差评关键词:")
        for kw in top_complaints:
            print(f"    • {kw}")

    # 3b. 客户需求
    if customer_needs:
        print(f"\n{'=' * 60}")
        print("💡 客户需求推断")
        print(f"{'=' * 60}")
        for need in customer_needs:
            print(f"  • {need}")

    # 3c. 自家产品详情
    print(f"\n{'=' * 60}")
    print(f"🏠 自家产品 [{OUR_ASIN}] 洞察")
    print(f"{'=' * 60}")
    our = next((i for i in review_insights if i.get("asin") == OUR_ASIN), None)
    if our:
        _print_insight(our)
    else:
        print("  ⚠️ 未找到自家产品数据")

    # 3d. 竞品分析
    print(f"\n{'=' * 60}")
    print(f"⚔️ 竞品洞察（{len(COMPETITOR_ASINS)} 个）")
    print(f"{'=' * 60}")
    for insight in review_insights:
        if insight.get("asin") != OUR_ASIN:
            _print_insight(insight)
            print()

    # 3e. 输出完整 JSON（可选）
    print(f"\n{'=' * 60}")
    print("📄 完整 JSON 输出已保存到 test/review_analyzer_output.json")
    print(f"{'=' * 60}")
    output = {
        "review_insights": review_insights,
        "sentiment_summary": sentiment_summary,
        "customer_needs": customer_needs,
    }
    output_path = os.path.join(os.path.dirname(__file__), "review_analyzer_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def _print_insight(insight: dict):
    asin = insight.get("asin", "?")
    title = insight.get("title", "")
    brand = insight.get("brand", "Unknown")
    rating = insight.get("rating", 0)
    review_count = insight.get("review_count", 0)

    print(f"\n  [{asin}] {title}")
    print(f"  品牌: {brand} | ★{rating} | 评论: {review_count} | "
          f"月销: {insight.get('monthly_sold', 0)} | BSR趋势: {insight.get('bsr_trend', '?')}")
    print(f"  评分定位: {insight.get('rating_position', '?')} | 评论壁垒: {insight.get('review_barrier', '?')}")
    print(f"  情感: 正面 {insight.get('sentiment_positive_pct', 0)}% / "
          f"负面 {insight.get('sentiment_negative_pct', 0)}% / "
          f"中性 {insight.get('sentiment_neutral_pct', 0)}%")

    praise = insight.get("common_praise", [])
    if praise:
        print(f"  🟢 好评: {' | '.join(praise)}")

    complaints = insight.get("common_complaints", [])
    if complaints:
        print(f"  🔴 差评: {' | '.join(complaints)}")

    needs = insight.get("customer_needs", [])
    if needs:
        print(f"  💡 需求: {' | '.join(needs)}")


if __name__ == "__main__":
    asyncio.run(main())
