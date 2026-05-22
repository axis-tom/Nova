"""
P3 Step 5 验收：briefing_generator 端到端测试
product_collector → market_analyst → competitor_analyst → review_analyzer → briefing_generator
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.common.core.state import State
from backend.business.ecommerce.amazon_monitor.tools.keepa_connector import KeepaConnector
from backend.business.ecommerce.product_selection.agents.market_analyst import MarketAnalystAgent
from backend.business.ecommerce.product_selection.agents.competitor_analyst import CompetitorAnalystAgent
from backend.business.ecommerce.amazon_monitor.agents.review_analyzer import AmazonReviewAnalyzerAgent
from backend.business.ecommerce.product_selection.agents.briefing_generator import BriefingGeneratorAgent

ALL_ASINS = [
    "B0F9FS7WQQ", "B07QK9C9KT", "B0D97YVVQ2", "B0F43SPZCY",
    "B0GHYNVYMD", "B08911JGGW", "B0BKQ7MY3L", "B0CXM46BDK",
    "B0FG2WDNWL", "B0F8P5RMPD", "B0DZD77DN9", "B0CRDT715R",
]

# 1. Keepa 拉数据
connector = KeepaConnector()
products = connector.query_products(ALL_ASINS)
print(f"Keepa 拉取: {len(products)} 个商品\n")

# 2. 共享 State，模拟流水线
state = State()
state.set("collected_products", products)

# 3. 依次运行上游 Agent
print("Running market_analyst (market_trends)...")
state.set("analysis_type", "market_trends")
MarketAnalystAgent().run(state)
print(f"  → market_analysis_result: {'✅' if state.get('market_analysis_result') else '❌'}")

print("Running market_analyst (roi_analysis)...")
state.set("analysis_type", "roi_analysis")
MarketAnalystAgent().run(state)
print(f"  → profitability_result: {'✅' if state.get('profitability_result') else '❌'}")

print("Running competitor_analyst...")
CompetitorAnalystAgent().run(state)
print(f"  → competitor_analysis_result: {'✅' if state.get('competitor_analysis_result') else '❌'}")

print("Running review_analyzer...")
AmazonReviewAnalyzerAgent().run(state)
print(f"  → sentiment_summary: {'✅' if state.get('sentiment_summary') else '❌'}")

# 4. 生成简报
print("\nRunning briefing_generator...")
BriefingGeneratorAgent().run(state)

briefing = state.get("briefing", {})
md = state.get("result", "")

print(f"\n简报状态: {briefing.get('sections_available', {})}")
print(f"Markdown 长度: {len(md)} 字符\n")
print("=" * 60)
print(md)
print("=" * 60)
