"""
P3 Step 4 验收：keyword_expander 增强测试
场景 1: 有 collected_products（12 个风扇 ASIN）→ 标题关键词提取
场景 2: 只有 seed_keywords → 规则引擎 fallback
场景 3: 无 seeds 无 products → 错误提示
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.common.core.state import State
from backend.business.ecommerce.amazon_monitor.agents.keyword_expander import KeywordExpanderAgent
from backend.business.ecommerce.amazon_monitor.tools.keepa_connector import KeepaConnector

ALL_ASINS = [
    "B0F9FS7WQQ", "B07QK9C9KT", "B0D97YVVQ2", "B0F43SPZCY",
    "B0GHYNVYMD", "B08911JGGW", "B0BKQ7MY3L", "B0CXM46BDK",
    "B0FG2WDNWL", "B0F8P5RMPD", "B0DZD77DN9", "B0CRDT715R",
]

agent = KeywordExpanderAgent()

# ── 场景 1: 有 products + 有 seeds ──
print("=" * 60)
print("场景 1: seed_keywords + collected_products（标题提取增强）")
print("=" * 60)

connector = KeepaConnector()
products = connector.query_products(ALL_ASINS)
print(f"拉取商品: {len(products)} 个\n")

state = State()
state.set("collected_products", products)
state.set("seed_keywords", ["portable fan"])
state.set("expand_count", 30)

result = agent.run(state)
expanded = result.get("expanded_keywords", [])
groups = result.get("keyword_groups", {})

print(f"扩展关键词总数: {len(expanded)}")
for g, kws in groups.items():
    print(f"\n  [{g}] ({len(kws)} 个):")
    for kw in kws[:8]:
        print(f"    • {kw}")
    if len(kws) > 8:
        print(f"    ... 还有 {len(kws) - 8} 个")

# ── 场景 2: 有 products + 无 seeds（自动从标题提取种子） ──
print(f"\n{'=' * 60}")
print("场景 2: 无 seed_keywords + 有 collected_products（自动提取种子）")
print("=" * 60)

state2 = State()
state2.set("collected_products", products)

result2 = agent.run(state2)
expanded2 = result2.get("expanded_keywords", [])
groups2 = result2.get("keyword_groups", {})
seeds2 = groups2.get("seed", [])

print(f"自动提取的种子词: {seeds2}")
print(f"扩展关键词总数: {len(expanded2)}")
for g, kws in groups2.items():
    print(f"  [{g}] ({len(kws)} 个): {kws[:5]}{'...' if len(kws) > 5 else ''}")

# ── 场景 3: 只有 seeds（规则引擎 fallback） ──
print(f"\n{'=' * 60}")
print("场景 3: 只有 seed_keywords，无 products（规则引擎 fallback）")
print("=" * 60)

state3 = State()
state3.set("seed_keywords", ["bluetooth earbuds"])

result3 = agent.run(state3)
expanded3 = result3.get("expanded_keywords", [])
groups3 = result3.get("keyword_groups", {})

print(f"扩展关键词总数: {len(expanded3)}")
for g, kws in groups3.items():
    print(f"  [{g}] ({len(kws)} 个): {kws[:5]}{'...' if len(kws) > 5 else ''}")

# ── 场景 4: 无 seeds 无 products → 错误 ──
print(f"\n{'=' * 60}")
print("场景 4: 无 seeds + 无 products → 应返回错误")
print("=" * 60)

state4 = State()
result4 = agent.run(state4)
error = result4.get("error")
print(f"error: {error}")
print(f"expanded_keywords: {result4.get('expanded_keywords', [])}")
