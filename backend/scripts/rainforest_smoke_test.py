"""
Rainforest API Smoke Test
每次只测一个端点，默认测 /product（1 credit）。

用法:
    cd backend
    python -m scripts.rainforest_smoke_test              # 测 /product (1 credit)
    python -m scripts.rainforest_smoke_test --search      # 测 /search  (1 credit)
    python -m scripts.rainforest_smoke_test --reviews     # 测 /reviews (1 credit)
    python -m scripts.rainforest_smoke_test --all         # 全部三个  (3 credits)
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.config.config import settings
from backend.business.ecommerce.amazon_monitor.tools.rainforest_connector import (
    RainforestConnector,
    RainforestError,
)


TEST_ASIN = "B0F9FS7WQQ"
TEST_KEYWORD = "bluetooth earbuds"


def test_product(connector):
    """1 credit"""
    print(f"\n/product: {TEST_ASIN}")
    product = connector.get_product(TEST_ASIN)
    ok = 0
    total = 0
    for name, check in [
        ("ASIN", product.get("asin") == TEST_ASIN),
        ("Title", bool(product.get("title"))),
        ("Feature bullets", len(product.get("feature_bullets", [])) > 0),
        ("Images", len(product.get("images", [])) > 0),
        ("Price", product.get("current_price") is not None),
        ("Rating", product.get("rating") is not None),
        ("Rating breakdown", len(product.get("rating_breakdown", {})) == 5),
        ("Variations", isinstance(product.get("variations"), list)),
        ("Specifications", len(product.get("specifications", {})) > 0),
        ("BSR", product.get("bsr_rank") is not None),
        ("Category", bool(product.get("category_name"))),
        ("Manufacturer", bool(product.get("manufacturer") or product.get("model_number"))),
        ("Parent ASIN", isinstance(product.get("parent_asin"), str)),
    ]:
        total += 1
        flag = "✅" if check else "❌"
        if check: ok += 1
        print(f"  {flag} {name}")
    print(f"  → {ok}/{total} 通过")
    return ok == total


def test_search(connector):
    """1 credit"""
    print(f"\n/search: '{TEST_KEYWORD}'")
    result = connector.search(TEST_KEYWORD, max_results=5)
    asins = result.get("asins", [])
    print(f"  Total: {result.get('total_results', 0)}, ASINs: {len(asins)}")
    for i, item in enumerate(result.get("items", [])[:3]):
        print(f"  #{i+1} {item.get('asin')} {(item.get('title') or '')[:60]}")
    ok = len(asins) > 0
    print(f"  → {'✅ 通过' if ok else '❌ 无结果'}")
    return ok


def test_reviews(connector):
    """1 credit"""
    print(f"\n/reviews: {TEST_ASIN} page 1")
    result = connector.get_reviews(TEST_ASIN, page=1, sort_by="most_recent")
    revs = result.get("reviews", [])
    print(f"  Total: {result.get('total_reviews', 0)}, 本页: {len(revs)}")
    for r in revs[:2]:
        print(f"  [{r.get('rating')}★] {r.get('title', '')[:50]}")
        body = r.get("body", "")
        if body:
            print(f"  {body[:80]}...")
    ok = isinstance(revs, list)
    print(f"  → {'✅ 通过' if ok else '❌ 失败'}")
    return ok


async def main():
    api_key = settings.RAINFOREST_API_KEY
    if not api_key or api_key == "your_rainforest_api_key_here":
        print("❌ RAINFOREST_API_KEY 未配置")
        return 1

    args = set(sys.argv[1:])
    if not args:
        args = {"--product"}

    connector = RainforestConnector(api_key)
    all_ok = True

    if "--all" in args:
        args = {"--product", "--search", "--reviews"}

    credits = 0
    if "--product" in args:
        credits += 1
        try:
            if not test_product(connector):
                all_ok = False
        except RainforestError as e:
            print(f"  ❌ {e}")
            all_ok = False

    if "--search" in args:
        credits += 1
        try:
            if not test_search(connector):
                all_ok = False
        except RainforestError as e:
            print(f"  ❌ {e}")
            all_ok = False

    if "--reviews" in args:
        credits += 1
        try:
            if not test_reviews(connector):
                all_ok = False
        except RainforestError as e:
            print(f"  ❌ {e}")
            all_ok = False

    print(f"\n消耗 {credits} credit | {'✅ 全部通过' if all_ok else '❌ 有失败项'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))