"""
Keepa 真数据冒烟测试

目的：在不改任何业务代码的前提下，独立验证：
  1. KEEPA_API_KEY 配置正确
  2. 账户当前 token 余量、套餐 refill 速率
  3. 关键词搜索（/search）能否真的返回 ASIN
  4. 商品查询（/product）能否真的返回历史数据
  5. Deal API 是否被套餐授权
  6. 每个动作真实烧了几个 token

运行：
  .venv/bin/python -m backend.scripts.keepa_smoke_test
  .venv/bin/python -m backend.scripts.keepa_smoke_test --keyword "bluetooth earbuds"
  .venv/bin/python -m backend.scripts.keepa_smoke_test --asin B08XYZABCD

无任何写操作；只读 + 打印。每步前打印"准备消耗 token 数"，每步后打印"实际消耗"。
"""

import argparse
import json
import sys
from typing import Any, Dict, Optional

import requests


def _box(title: str) -> None:
    line = "─" * 72
    print(f"\n{line}\n  {title}\n{line}")


def _kv(key: str, value: Any) -> None:
    print(f"  {key:<28} {value}")


def _pretty(obj: Any, max_chars: int = 800) -> str:
    s = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    if len(s) > max_chars:
        return s[:max_chars] + f"\n  ... (省略 {len(s) - max_chars} 字符)"
    return s


def load_api_key() -> str:
    """从 backend.config.config 读 KEEPA_API_KEY（自动加载 .env）"""
    from backend.config.config import settings

    key = settings.KEEPA_API_KEY or ""
    if not key:
        print("❌ KEEPA_API_KEY 未配置（backend/config/.env）")
        sys.exit(2)
    return key


def query_token_status(api_key: str) -> Optional[Dict[str, Any]]:
    """
    直接调 Keepa REST /token 端点。
    免费动作，不烧 token，但能拿到账户全貌：
      tokensLeft / refillIn(ms) / refillRate(per min) / tokensConsumed / ...
    """
    url = "https://api.keepa.com/token"
    try:
        resp = requests.get(url, params={"key": api_key}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  ⚠️  /token 端点调用失败: {e}")
        return None


def keepa_search_raw(api_key: str, keyword: str, domain: int = 1) -> Dict[str, Any]:
    """直接调 REST /search 端点。每次 search 消耗一些 token（通常 1）"""
    url = "https://api.keepa.com/search"
    params = {
        "key": api_key,
        "domain": domain,
        "type": "product",
        "term": keyword,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def keepa_product_raw(
    api_key: str,
    asin: str,
    domain: int = 1,
    history: bool = True,
    stats: Optional[int] = 180,
    offers: int = 0,
) -> Dict[str, Any]:
    """直接调 REST /product 端点。单 ASIN 一般消耗 1 token（offers/buybox 会加价）"""
    url = "https://api.keepa.com/product"
    params: Dict[str, Any] = {
        "key": api_key,
        "domain": domain,
        "asin": asin,
        "history": 1 if history else 0,
    }
    # Keepa /product 拒绝 offers=0 —— 只在 >0 时传
    if offers and offers > 0:
        params["offers"] = offers
    if stats:
        params["stats"] = stats
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def keepa_deal_raw(api_key: str, selection: Dict[str, Any]) -> Dict[str, Any]:
    """直接调 REST /deal 端点。selection 用 URL-encoded JSON 传"""
    url = "https://api.keepa.com/deal"
    resp = requests.get(
        url,
        params={"key": api_key, "selection": json.dumps(selection)},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def run() -> int:
    parser = argparse.ArgumentParser(description="Keepa 真数据冒烟测试")
    parser.add_argument("--keyword", default=None,
                        help="如指定才跑 /search 测试（每次烧 10 token，默认跳过）")
    parser.add_argument("--asin", default=None,
                        help="测试 ASIN；若不传则跳过 /product 测试")
    parser.add_argument("--domain", default="US", help="市场（US/DE/JP 等）")
    parser.add_argument("--skip-deal", action="store_true",
                        help="跳过 Deal API 测试")
    parser.add_argument("--minimal", action="store_true",
                        help="/product 用最简参数（无 history、无 stats），看是否套餐拒绝")
    args = parser.parse_args()

    domain_map = {
        "US": 1, "GB": 2, "DE": 3, "FR": 4, "JP": 5,
        "CA": 6, "IT": 8, "ES": 9, "IN": 10, "MX": 11,
    }
    domain_id = domain_map.get(args.domain.upper(), 1)

    api_key = load_api_key()
    masked = api_key[:6] + "..." + api_key[-4:]

    # ─── 1. 账户状态 ───
    _box("1. 账户状态 / Token 余量（不烧 token）")
    _kv("API Key", masked)
    _kv("Domain", f"{args.domain} ({domain_id})")

    status = query_token_status(api_key)
    if status is None:
        print("  ❌ 无法获取账户状态，后续测试可能不准")
        tokens_before = None
    else:
        tokens_before = status.get("tokensLeft")
        refill_in_ms = status.get("refillIn", 0)
        refill_min = refill_in_ms / 60000 if refill_in_ms else 0
        _kv("tokensLeft (当前剩余)", tokens_before)
        _kv("refillRate (每分钟补充)", status.get("refillRate"))
        _kv("refillIn (距下次补充)", f"{refill_min:.1f} 分钟")
        _kv("tokensConsumed (总消耗)", status.get("tokensConsumed"))
        _kv("processingTimeInMs", status.get("processingTimeInMs"))

        if tokens_before is not None and tokens_before <= 5:
            print("  ⚠️  token 余量极低，建议先等几分钟让 refill 再跑")

    # ─── 2. REST 客户端就绪 ───
    _box("2. REST 客户端就绪（不依赖 keepa Python SDK）")
    _kv("requests version", getattr(requests, "__version__", "unknown"))
    _kv("base URL", "https://api.keepa.com")
    print("  ✅ 原生 REST 模式，无需 SDK 初始化")

    # ─── 3. 关键词搜索（仅当显式指定 --keyword 才跑）───
    asins = []
    if args.keyword:
        _box(f"3. 关键词搜索: '{args.keyword}' (/search 端点，会烧 10 token)")
        try:
            result = keepa_search_raw(api_key, args.keyword, domain=domain_id)
            asin_list = result.get("asinList") or []
            asins = list(asin_list[:5])
            _kv("asinList 长度", len(asin_list))
            _kv("前 5 个 ASIN", asins)
            _kv("totalResults", result.get("totalResults"))
            _kv("tokensLeft (调用后)", result.get("tokensLeft"))

            if tokens_before is not None and result.get("tokensLeft") is not None:
                delta = tokens_before - result["tokensLeft"]
                _kv("💰 本次烧掉 token", delta)
                tokens_before = result["tokensLeft"]

            if not asins:
                print("  ⚠️  关键词搜不到 ASIN")
            else:
                print("  ✅ 搜索返回真实 ASIN")
        except requests.HTTPError as e:
            print(f"  ❌ HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            print(f"  ❌ 搜索失败: {e}")
    else:
        _box("3. 关键词搜索 (跳过；用 --keyword xxx 启用)")

    # ─── 4. 商品历史查询（原生 REST /product） ───
    target_asin = args.asin or (asins[0] if asins else None)
    if args.minimal:
        query_kwargs = {"history": False, "stats": None, "offers": 0}
        mode_label = "minimal (无 history/stats/offers, 应消耗 1 token)"
    else:
        query_kwargs = {"history": True, "stats": 180, "offers": 0}
        mode_label = "full (history=True, stats=180, offers=0)"
    _box(f"4. 商品历史查询: {target_asin} /product 端点, {mode_label}")
    if not target_asin:
        print("  ⏭️  无可用 ASIN（用 --asin B0XXXXXXXX 启用）")
    else:
        try:
            result = keepa_product_raw(
                api_key,
                target_asin,
                domain=domain_id,
                **query_kwargs,
            )
            products = result.get("products") or []
            _kv("返回商品数", len(products))
            if products:
                p = products[0]
                _kv("asin", p.get("asin"))
                _kv("title", (p.get("title") or "")[:60])
                _kv("brand", p.get("brand"))
                _kv("monthlySold", p.get("monthlySold"))
                _kv("newOfferCount", p.get("newOfferCount"))
                csv = p.get("csv") or []
                _kv("csv 数组长度", len(csv))
                if csv and csv[0]:
                    _kv("csv[0] (Amazon 价格历史) 点数", len(csv[0]) // 2)
                if len(csv) > 3 and csv[3]:
                    _kv("csv[3] (BSR 历史) 点数", len(csv[3]) // 2)
                stats_obj = p.get("stats") or {}
                if stats_obj:
                    _kv("stats.avg", stats_obj.get("avg"))

            tokens_after = result.get("tokensLeft")
            if tokens_after is not None and tokens_before is not None:
                delta = tokens_before - tokens_after
                _kv("tokensLeft (调用后)", tokens_after)
                _kv("💰 本次烧掉 token", delta)
                tokens_before = tokens_after

            print("  ✅ 商品历史查询成功（真数据）")
        except requests.HTTPError as e:
            body = e.response.text[:200] if e.response is not None else ""
            print(f"  ❌ HTTP {e.response.status_code}: {body}")
            if "REJECTED" in body.upper():
                print("     → REQUEST_REJECTED: 一般是套餐不允许此请求 / 参数组合不被授权")
                print("       建议先用 --minimal 跑一次（最简参数），仍失败 = 套餐问题")
        except Exception as e:
            print(f"  ❌ /product 调用失败: {e}")

    # ─── 5. Deal API（套餐权限测试） ───
    if not args.skip_deal:
        _box("5. Deal API 权限测试（基础款可能无权）")
        try:
            deal_selection = {
                "page": 0,
                "domainId": domain_id,
                "excludeCategories": [],
                "includeCategories": [],
                "priceTypes": [0, 1],
                "deltaPercent": {"min": 10, "max": 100},
                "current": {"min": 1, "max": 99999},
                "avg": {"min": 1, "max": 99999},
                "rating": {"min": 30, "max": 50},
                "reviewCount": {"min": 50, "max": 999999},
            }
            deals = keepa_deal_raw(api_key, deal_selection)
            dr = (deals.get("deals") or {}).get("dr") if isinstance(deals.get("deals"), dict) else None
            if dr is None:
                # 旧字段
                dr = deals.get("dr", []) if isinstance(deals, dict) else []
            deal_count = len(dr) if dr else 0
            _kv("Deal 返回条数", deal_count)
            if dr:
                first = dr[0]
                _kv("首条 ASIN", first.get("asin"))
                _kv("首条 title", (first.get("title") or "")[:50])
            print("  ✅ Deal API 可用")

            tokens_after = deals.get("tokensLeft")
            if tokens_after is not None and tokens_before is not None:
                delta = tokens_before - tokens_after
                _kv("💰 本次烧掉 token", delta)
                tokens_before = tokens_after
        except requests.HTTPError as e:
            body = e.response.text[:200] if e.response is not None else ""
            print(f"  ❌ HTTP {e.response.status_code}: {body}")
            print("     → 多半是基础款套餐不支持 Deal API")
        except Exception as e:
            print(f"  ❌ Deal API 失败: {e}")
            print("     → 多半是基础款套餐不支持 Deal API")

    # ─── 6. 最终状态 ───
    _box("6. 最终账户状态")
    final = query_token_status(api_key)
    if final:
        _kv("tokensLeft (最终)", final.get("tokensLeft"))
        _kv("refillRate", final.get("refillRate"))
        _kv("tokensConsumed (累计)", final.get("tokensConsumed"))

    _box("结论自查清单")
    print("""
  ▢ tokensLeft 是否 > 0？        → 决定调用是否被限流
  ▢ refillRate 是多少 /min？      → 看清套餐档位（基础约 5；其他更高）
  ▢ /search 是否返回非空 asinList？ → 关键词搜索功能可用性
  ▢ /product 是否返回 title/csv？  → 历史数据查询功能可用性
  ▢ Deal API 是否报错？          → 决定后台调度器价格监控能否用

  如果上面前 4 项都通过，Keepa 数据链路就是健康的。
  如果某项失败，把这次输出复制给 Claude 即可针对修。
""")
    return 0


if __name__ == "__main__":
    sys.exit(run())
