"""
关键词扩展 Agent - Amazon 监控场景

职责：
1. 接收种子关键词（来自用户或 state）
2. 如果有 collected_products，从竞品标题提取真实市场关键词
3. 基于规则 + 标题提取扩展长尾词、相关词
4. 对关键词分组（品类/功能/场景/标题提取）
5. 输出扩展后的关键词列表供后续采集使用

数据源：seed_keywords（必须）+ state.collected_products（可选增强）
"""

import re
from typing import Any, Dict, List, Tuple
from collections import Counter

from backend.common.core.agent import Agent
from backend.common.core.state import State
from backend.utils.logger import logger


KEYWORD_MODIFIERS = {
    "quality": ["best", "top", "premium", "high quality", "professional"],
    "price": ["cheap", "affordable", "budget", "under $20", "under $50"],
    "feature": ["wireless", "bluetooth", "rechargeable", "waterproof", "portable"],
    "audience": ["for women", "for men", "for kids", "for home", "for office"],
    "action": ["buy", "review", "vs", "alternative", "replacement"],
}

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

_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "be", "was", "are",
    "this", "that", "not", "no", "so", "if", "up", "out", "all", "can",
    "has", "had", "do", "does", "will", "just", "more", "also", "very",
    "only", "into", "over", "such", "than", "its", "you", "your", "our",
    "-", "--", "&", "+", "/", "|",
})

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9'-]*[a-zA-Z0-9]|[a-zA-Z]")


class KeywordExpanderAgent(Agent):
    """关键词扩展 Agent — 规则引擎 + 竞品标题提取"""

    name = "keyword_expander"
    description = "Amazon 关键词扩展 Agent，基于种子词和竞品标题生成长尾词"

    def run(self, state: State) -> State:
        state.add_event("keyword_expander_start")

        try:
            seed_keywords: List[str] = state.get("seed_keywords", [])
            expand_count: int = state.get("expand_count", 20)
            include_long_tail: bool = state.get("include_long_tail", True)
            products: List[Dict] = state.get("collected_products", []) or []

            title_kw = self._extract_from_titles(products) if products else {}

            if not seed_keywords and title_kw:
                seed_keywords = title_kw.get("core_terms", [])[:5]
                logger.info(f"[KeywordExpander] 无种子词，从标题提取: {seed_keywords}")

            if not seed_keywords:
                state.set("error", "请提供 seed_keywords 或先调用 product_collector 采集商品")
                state.set("expanded_keywords", [])
                state.set("keyword_groups", {})
                state.add_event("keyword_expander_no_seeds")
                return state

            expanded, groups = self._expand_keywords(
                seed_keywords, expand_count, include_long_tail, title_kw
            )

            state.set("expanded_keywords", expanded)
            state.set("keyword_groups", groups)
            state.set_meta("keyword_count", len(expanded))
            state.set_meta("seed_count", len(seed_keywords))
            state.set_meta("title_extracted", bool(title_kw))

            logger.info(
                f"[KeywordExpander] {len(seed_keywords)} seeds → "
                f"{len(expanded)} keywords in {len(groups)} groups"
                f"{' (含标题提取)' if title_kw else ''}"
            )
            state.add_event(f"keyword_expander_success: {len(expanded)} keywords")

        except Exception as e:
            logger.error(f"[KeywordExpander] Error: {e}")
            state.set("error", str(e))
            state.set("expanded_keywords", [])
            state.set("keyword_groups", {})
            state.add_event(f"keyword_expander_error: {e}")

        return state

    # ── 标题关键词提取 ──

    def _extract_from_titles(self, products: List[Dict]) -> Dict[str, Any]:
        """从竞品标题提取高频关键词和短语"""
        brands = {(p.get("brand") or "").lower() for p in products} - {"", "unknown", "generic"}

        word_counter: Counter = Counter()
        bigram_counter: Counter = Counter()
        all_words_per_title: List[List[str]] = []

        for p in products:
            title = p.get("title") or ""
            words = [w.lower() for w in _WORD_RE.findall(title)]
            filtered = [
                w for w in words
                if w not in _STOP_WORDS
                and w not in brands
                and len(w) > 2
                and not w.isdigit()
            ]

            word_counter.update(filtered)
            all_words_per_title.append(filtered)

            for i in range(len(filtered) - 1):
                bigram_counter[(filtered[i], filtered[i + 1])] += 1

        min_freq = max(2, len(products) // 4)

        core_terms = [w for w, c in word_counter.most_common(30) if c >= min_freq]

        phrases = [
            f"{a} {b}"
            for (a, b), c in bigram_counter.most_common(20)
            if c >= min_freq
        ]

        return {
            "core_terms": core_terms,
            "phrases": phrases,
            "brands": sorted(brands),
        }

    # ── 关键词扩展 ──

    def _expand_keywords(
        self,
        seeds: List[str],
        expand_count: int,
        include_long_tail: bool,
        title_kw: Dict[str, Any],
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        all_keywords = set(s.lower() for s in seeds)
        groups: Dict[str, List[str]] = {
            "seed": list(seeds),
        }

        def _add(kw: str, group: str):
            kw_lower = kw.lower()
            words = kw_lower.split()
            if len(words) != len(set(words)):
                return
            if kw_lower not in all_keywords:
                all_keywords.add(kw_lower)
                groups.setdefault(group, []).append(kw)

        # ── Phase 1: 标题提取词（如有） ──
        if title_kw:
            for phrase in title_kw.get("phrases", []):
                _add(phrase, "title_extracted")

            phrases_set = set(title_kw.get("phrases", []))
            core = title_kw.get("core_terms", [])
            for seed in seeds:
                seed_lower = seed.lower()
                for term in core[:15]:
                    if term not in seed_lower:
                        combo = f"{seed} {term}"
                        if combo not in phrases_set:
                            _add(combo, "title_cross")

        # ── Phase 2: 规则引擎 ──
        for seed in seeds:
            seed_lower = seed.lower()

            if not title_kw:
                for cat_key, expansions in CATEGORY_EXPANSIONS.items():
                    if cat_key in seed_lower:
                        for exp in expansions[:5]:
                            _add(exp, "category")

            if include_long_tail:
                for mod in KEYWORD_MODIFIERS["feature"][:3]:
                    _add(f"{mod} {seed}", "feature_based")

            for mod in KEYWORD_MODIFIERS["price"][:2]:
                _add(f"{mod} {seed}", "price_based")

            for mod in KEYWORD_MODIFIERS["audience"][:2]:
                _add(f"{seed} {mod}", "audience_based")

            for mod in KEYWORD_MODIFIERS["action"][:2]:
                _add(f"{seed} {mod}", "competitor_related")

        # ── Phase 3: 品牌词（如有） ──
        if title_kw:
            for brand in title_kw.get("brands", [])[:5]:
                for seed in seeds[:3]:
                    _add(f"{brand} {seed}", "brand_related")

        max_total = expand_count * len(seeds)
        expanded = list(all_keywords)[:max_total]

        groups = {k: v for k, v in groups.items() if v}

        return expanded, groups
