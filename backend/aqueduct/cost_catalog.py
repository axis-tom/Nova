"""
API 成本目录 & 最小成本估算

定义每个源/端点的成本、覆盖的数据维度，以及给定所需维度时
计算最低成本采集方案的能力。
"""
from typing import Any, Dict, List, Optional, Tuple

logger = __import__("logging").getLogger(__name__)

# ── 成本目录 ──────────────────────────────────────────────────────────

_API_COST_CATALOG = {
    "keepa": {
        "product": {
            "token": 1,
            "covers": [
                "has_price", "has_bsr", "has_price_stats",
                "has_bsr_stats", "has_rating_history", "has_basic_info",
            ],
        },
        "product_offers": {
            "token": 20,
            "covers": [
                "has_buybox", "has_offer_counts",
                "has_fba_fee", "has_referral_fee",
            ],
        },
        "deal": {"token": 5, "covers": [], "disabled": False},
        "search": {"token": 10, "covers": [], "disabled": True},
    },
    "rainforest": {
        "product": {
            "credit": 1,
            "covers": [
                "has_listing", "has_aplus", "has_videos",
                "has_buybox", "has_rating_breakdown", "has_bsr",
            ],
        },
        "offers": {"credit": 1, "covers": ["has_offer_counts"]},
        "reviews": {"credit": 1, "covers": ["has_reviews_body"], "disabled": True},
        "seller_profile": {"credit": 1, "covers": []},
        "category": {"credit": 1, "covers": []},
    },
    "canopy": {
        "product": {"credit": 1, "covers": ["has_price", "has_listing"]},
        "reviews": {"credit": 1, "covers": ["has_reviews_body"]},
        "sales": {"credit": 1, "covers": ["has_sales_estimate"]},
        "stock": {"credit": 1, "covers": ["has_stock_level"]},
        "search": {"credit": 1, "covers": []},
    },
}


def get_available_endpoints(source: str) -> List[Tuple[str, Dict]]:
    """获取某个源所有可用的端点列表（排除 disabled）"""
    endpoints = _API_COST_CATALOG.get(source, {})
    return [(name, cfg) for name, cfg in endpoints.items() if not cfg.get("disabled")]


def dim_coverage_by_source(dim: str) -> List[Tuple[str, str, int]]:
    """
    返回能覆盖某维度的所有 (source, endpoint, cost_in_tokens) 列表。

    cost_in_tokens 是一个归一化的成本值（Keepa token 直接使用，
    RF/Canopy credit 按 1 credit = 1 token 换算）。
    """
    results = []
    for source, endpoints in _API_COST_CATALOG.items():
        for ep_name, ep_cfg in endpoints.items():
            if ep_cfg.get("disabled"):
                continue
            if dim in ep_cfg.get("covers", []):
                token_cost = ep_cfg.get("token", ep_cfg.get("credit", 1))
                results.append((source, ep_name, token_cost))
    return results


def estimate_min_cost(needed_dims: List[str], budget: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """
    给定需要的数据维度，在预算内计算最小成本方案。

    贪心算法：对每个未覆盖维度，选能覆盖它的最便宜端点（按 token 计）。
    优先用已选端点的覆盖面，减少额外端点数量。

    Args:
        needed_dims: 需要的数据维度列表，如 ["has_price", "has_aplus", "has_reviews_body"]
        budget: 可选预算约束，如 {"keepa_token": 50, "rf_credit": 10, "canopy_credit": 5}

    Returns:
        {
            "plan": [{"source": "keepa", "endpoint": "product", "token": 1}, ...],
            "total": {"keepa_token": 1, "rf_credit": 1, "canopy_credit": 0},
            "covered": ["has_price", "has_aplus", ...],
            "uncovered": ["has_reviews_body"],  # 超出预算或无可覆盖端点
            "feasible": True/False,
        }
    """
    if not needed_dims:
        return {"plan": [], "total": {}, "covered": [], "uncovered": [], "feasible": True}

    # 去重
    needed = list(dict.fromkeys(needed_dims))

    # 初始化
    selected_endpoints: List[Tuple[str, str]] = []  # (source, endpoint)
    covered: set = set()
    uncovered = set(needed)

    # 贪心：每轮选边际收益最高的端点
    MAX_ROUNDS = 20
    for _ in range(MAX_ROUNDS):
        best_gain = 0
        best_ep = None
        best_new_covered = set()

        for source, endpoints in _API_COST_CATALOG.items():
            for ep_name, ep_cfg in endpoints.items():
                if ep_cfg.get("disabled"):
                    continue

                # 跳过已选端点
                if (source, ep_name) in selected_endpoints:
                    continue

                ep_covers = set(ep_cfg.get("covers", []))
                new_covered = ep_covers & uncovered
                gain = len(new_covered)

                if gain > best_gain:
                    best_gain = gain
                    best_ep = (source, ep_name)
                    best_new_covered = new_covered

        if best_ep is None or best_gain == 0:
            break

        selected_endpoints.append(best_ep)
        covered |= best_new_covered
        uncovered -= best_new_covered

    # 构建 plan
    plan = []
    total_cost: Dict[str, int] = {}
    for source, ep in selected_endpoints:
        cfg = _API_COST_CATALOG[source][ep]
        entry: Dict[str, Any] = {"source": source, "endpoint": ep}
        if "token" in cfg:
            entry["token"] = cfg["token"]
            total_cost["keepa_token"] = total_cost.get("keepa_token", 0) + cfg["token"]
        if "credit" in cfg:
            entry["credit"] = cfg["credit"]
            if source == "rainforest":
                total_cost["rf_credit"] = total_cost.get("rf_credit", 0) + cfg["credit"]
            elif source == "canopy":
                total_cost["canopy_credit"] = total_cost.get("canopy_credit", 0) + cfg["credit"]
        covers = cfg.get("covers", [])
        if covers:
            entry["covers"] = covers
        plan.append(entry)

    # 预算检查
    feasible = True
    if budget:
        for cost_key, cost_val in total_cost.items():
            limit = budget.get(cost_key, float("inf"))
            if cost_val > limit:
                feasible = False
                break

    return {
        "plan": plan,
        "total": total_cost,
        "covered": sorted(covered),
        "uncovered": sorted(uncovered),
        "feasible": feasible,
    }