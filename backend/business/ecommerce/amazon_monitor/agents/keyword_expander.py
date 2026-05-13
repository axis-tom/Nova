"""
关键词扩展 Agent - Amazon 监控场景
对应文章第1步：关键词研究与扩展

职责：
1. 接收种子关键词（来自配置或前端）
2. 基于规则扩展长尾词、相关词、竞品词
3. 对关键词分组（品类/功能/场景/竞品）
4. 输出扩展后的关键词列表供后续采集使用
"""

from typing import Any, Dict, List, Optional
from backend.common.core.agent import Agent
from backend.common.core.state import State
from backend.utils.logger import logger


# 关键词扩展规则库（基于跨境电商常见模式）
KEYWORD_MODIFIERS = {
    "quality": ["best", "top", "premium", "high quality", "professional"],
    "price": ["cheap", "affordable", "budget", "under $20", "under $50"],
    "feature": ["wireless", "bluetooth", "rechargeable", "waterproof", "portable"],
    "audience": ["for women", "for men", "for kids", "for home", "for office"],
    "action": ["buy", "review", "vs", "alternative", "replacement"],
}

# 常见跨境电商品类关键词扩展模板
CATEGORY_EXPANSIONS = {
    "earbuds": ["wireless earbuds", "bluetooth earbuds", "true wireless earbuds",
                "noise cancelling earbuds", "earbuds with mic", "sport earbuds"],
    "speaker": ["bluetooth speaker", "portable speaker", "waterproof speaker",
                "outdoor speaker", "mini speaker", "smart speaker"],
    "stand": ["phone stand", "laptop stand", "tablet stand", "desk stand",
              "adjustable stand", "foldable stand"],
    "hub": ["usb hub", "usb c hub", "4 port hub", "7 port hub", "powered hub"],
    "charger": ["wireless charger", "fast charger", "car charger", "portable charger",
                "multi port charger"],
    "cable": ["usb c cable", "lightning cable", "charging cable", "braided cable"],
    "case": ["phone case", "laptop case", "airpods case", "protective case"],
    "light": ["led light", "ring light", "desk light", "night light", "smart light"],
    "bag": ["laptop bag", "backpack", "travel bag", "gym bag", "tote bag"],
    "watch": ["smart watch", "fitness tracker", "sport watch", "apple watch band"],
}


class KeywordExpanderAgent(Agent):
    """
    关键词扩展 Agent
    基于种子关键词生成扩展词列表，为商品采集提供搜索词
    """

    name = "keyword_expander"
    description = "Amazon 关键词扩展 Agent，基于种子词生成长尾词和相关词"

    def run(self, state: State) -> State:
        """
        执行关键词扩展

        输入（从 state 读取）：
          - seed_keywords: List[str] 种子关键词
          - expand_count: int 每个种子词扩展数量（默认20）
          - include_long_tail: bool 是否包含长尾词（默认True）

        输出（写入 state）：
          - expanded_keywords: List[str] 扩展后的关键词列表
          - keyword_groups: Dict[str, List[str]] 按类型分组的关键词
        """
        state.add_event("keyword_expander_start")
        logger.info("[KeywordExpander] Starting keyword expansion")

        try:
            # 读取输入参数
            seed_keywords: List[str] = state.get("seed_keywords", [])
            expand_count: int = state.get("expand_count", 20)
            include_long_tail: bool = state.get("include_long_tail", True)

            # 如果没有种子词，使用默认词
            if not seed_keywords:
                seed_keywords = [
                    "wireless earbuds",
                    "bluetooth speaker",
                    "phone stand",
                    "laptop stand",
                    "usb hub",
                ]
                logger.info(f"[KeywordExpander] No seed keywords provided, using defaults: {seed_keywords}")

            # 执行扩展
            expanded_keywords, keyword_groups = self._expand_keywords(
                seed_keywords, expand_count, include_long_tail
            )

            # 写入结果
            state.set("expanded_keywords", expanded_keywords)
            state.set("keyword_groups", keyword_groups)
            state.set_meta("keyword_count", len(expanded_keywords))
            state.set_meta("seed_count", len(seed_keywords))

            logger.info(
                f"[KeywordExpander] Expanded {len(seed_keywords)} seeds → "
                f"{len(expanded_keywords)} keywords in {len(keyword_groups)} groups"
            )
            state.add_event(f"keyword_expander_success: {len(expanded_keywords)} keywords")

        except Exception as e:
            logger.error(f"[KeywordExpander] Error: {e}")
            state.set("error", str(e))
            state.set("expanded_keywords", [])
            state.set("keyword_groups", {})
            state.add_event(f"keyword_expander_error: {e}")

        return state

    def _expand_keywords(
        self,
        seeds: List[str],
        expand_count: int,
        include_long_tail: bool,
    ) -> tuple:
        """
        扩展关键词

        Returns:
            (expanded_keywords, keyword_groups)
        """
        all_keywords = set(seeds)
        keyword_groups: Dict[str, List[str]] = {
            "seed": list(seeds),
            "long_tail": [],
            "feature_based": [],
            "price_based": [],
            "audience_based": [],
            "competitor_related": [],
        }

        for seed in seeds:
            seed_lower = seed.lower()

            # 1. 基于品类模板扩展
            for category_key, expansions in CATEGORY_EXPANSIONS.items():
                if category_key in seed_lower:
                    for exp in expansions[:5]:
                        if exp not in all_keywords:
                            all_keywords.add(exp)
                            keyword_groups["long_tail"].append(exp)

            # 2. 功能修饰词扩展
            if include_long_tail:
                for modifier in KEYWORD_MODIFIERS["feature"][:3]:
                    kw = f"{modifier} {seed}"
                    if kw not in all_keywords:
                        all_keywords.add(kw)
                        keyword_groups["feature_based"].append(kw)

            # 3. 价格修饰词扩展
            for modifier in KEYWORD_MODIFIERS["price"][:2]:
                kw = f"{modifier} {seed}"
                if kw not in all_keywords:
                    all_keywords.add(kw)
                    keyword_groups["price_based"].append(kw)

            # 4. 受众修饰词扩展
            for modifier in KEYWORD_MODIFIERS["audience"][:2]:
                kw = f"{seed} {modifier}"
                if kw not in all_keywords:
                    all_keywords.add(kw)
                    keyword_groups["audience_based"].append(kw)

            # 5. 竞品相关词
            for modifier in KEYWORD_MODIFIERS["action"][:2]:
                kw = f"{seed} {modifier}"
                if kw not in all_keywords:
                    all_keywords.add(kw)
                    keyword_groups["competitor_related"].append(kw)

        # 限制总数量
        expanded_list = list(all_keywords)
        if len(expanded_list) > expand_count * len(seeds):
            expanded_list = expanded_list[:expand_count * len(seeds)]

        # 清理空分组
        keyword_groups = {k: v for k, v in keyword_groups.items() if v}

        return expanded_list, keyword_groups
