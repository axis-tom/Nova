"""
Reanalysis Classifier — 重分析意图分流器

用户说"重新分析"时不是直接 rerun pipeline，而是先分类：
  A. full_pipeline → 数据或约束变了，需要全量重跑
  B. partial_metrics → 指出某个维度算错了，局部重算
  C. explain_only → 数据没错，结论解释不到位，重新生成注释
  D. new_question → 跟之前分析无关的新问题，走 ReAct

分类逻辑是确定性的（代码规则 > LLM 决策），仅在规则冲突时回退 LLM。
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set

# ── 重分析分类 ──

REANALYSIS_FULL = "full_pipeline"       # A: 全量重跑
REANALYSIS_PARTIAL = "partial_metrics"  # B: 局部重算
REANALYSIS_EXPLAIN = "explain_only"     # C: 重新解释
REANALYSIS_NEW = "new_question"         # D: 新问题

# ── 已知的确定性指标名（与 Pipeline 的 deterministic 维度对应） ──

KNOWN_METRICS: Set[str] = {
    "market_volume", "trends", "seasonality", "brand_distribution",
    "price_bands", "review_barrier", "rating_health",
    "seller_composition", "brand_concentration", "opportunities", "risks",
}

# ── 指标名到中文同义词映射（方便从用户自然语言匹配） ──

METRIC_ALIASES: Dict[str, List[str]] = {
    "market_volume": ["市场体量", "市场规模", "月销", "销量", "volume", "体量"],
    "price_bands": ["价格带", "价格", "定价", "价", "price"],
    "review_barrier": ["评论", "review", "评价", "壁垒"],
    "rating_health": ["评分", "健康", "rating", "星级"],
    "brand_concentration": ["品牌", "集中度", "brand", "垄断", "寡占"],
    "brand_distribution": ["品牌分布", "品牌"],
    "seller_composition": ["卖家", "seller", "fba", "fbm"],
    "trends": ["趋势", "bsr趋势", "价格趋势", "trend"],
    "seasonality": ["季节", "season", "淡季", "旺季"],
    "opportunities": ["机会", "opportunity", "切入点"],
    "risks": ["风险", "risk", "威胁"],
}


@dataclass
class ReanalysisDecision:
    """
    重分析决策结果

    核心原则：rerun 决策权从用户语言转移到系统判断。
    系统根据用户输入的语言特征 + 上次分析状态，判断"为什么要重跑"。
    """
    scope: str = REANALYSIS_FULL       # 分类结果
    metrics_to_recompute: List[str] = field(default_factory=list)  # 局部重算时指定
    filter_constraints: Dict[str, Any] = field(default_factory=dict)  # 过滤约束
    user_correction: str = ""          # 用户指出的具体问题
    confidence: str = "high"           # high / medium / low（low 时回退 LLM）

    # 原始匹配信息（调试用）
    _matched_pattern: str = ""
    _matched_metrics: List[str] = field(default_factory=list)


# ── 匹配模式词库 ──

# A 类：全量重跑
_FULL_PATTERNS = re.compile(
    r'(全[量面新]|从头|全部|整体|完全|whole|从头到尾|all|完整)'
    r'.*(分析|重新|重来)'
    r'|'
    r'(分析|重新|重来).*(全[量面新]|从头|全部|整体|完全|whole|从头到尾|all|完整)'
    r'|'
    r'重新分析$'  # 裸的"重新分析"→ 全量
)

# B 类：局部重算
_PARTIAL_PATTERNS = re.compile(
    r'(只看|单独|只关注|重点|具体|专门|针对|特别)'
    r'.*(价格|评论|评分|品牌|销量|趋势|卖家|fba|机会|风险|季节|体量|壁垒)'
    r'|'
    r'(价格|评论|评分|品牌|销量|趋势|卖家|fba|机会|风险|季节|体量|壁垒)'
    r'.*(重新|不对|错了|重算|修正|纠正|改)'
)

# C 类：重新解释
_EXPLAIN_PATTERNS = re.compile(
    r'(解释|说明|为什么|理由|依据|根据|原因|怎么看|怎么看出来的|分析不够|不详细|太简单|'
    r'看不懂|不明白|没理解|再说一遍|说清楚|详细说说|展开说说)'
)

# D 类：新问题（不匹配任何重分析模式 → new_question by default）


def classify_reanalysis(user_input: str, last_commentary: str = "",
                        last_metrics: Optional[List[str]] = None) -> ReanalysisDecision:
    """
    分类用户输入属于哪种重分析意图。

    匹配策略（确定性规则，不做 LLM 决策）：
      1. 先检测局部指标关键词 → B 类
      2. 再检测全量关键词 → A 类
      3. 再检测解释关键词 → C 类
      4. 都不匹配 → D 类

    Args:
        user_input: 用户输入
        last_commentary: 上次分析的 LLM 注释（用于 C 类检测上下文关联）
        last_metrics: 上次 Pipeline 计算的指标列表（用于 B 类限定范围）

    Returns:
        ReanalysisDecision
    """
    text = user_input.lower().strip()

    # ── Step 1: 检测局部指标 ──
    matched_metrics = _detect_metrics(text)

    if matched_metrics:
        # 用户指定了具体指标 → B 类
        scope = REANALYSIS_PARTIAL
        confidence = "high"
        # 提取用户指出的问题（去掉指标关键词后的剩余文本）
        correction = _extract_correction(text, matched_metrics)

        return ReanalysisDecision(
            scope=scope,
            metrics_to_recompute=matched_metrics,
            user_correction=correction,
            confidence=confidence,
            _matched_pattern="partial_metrics_keyword",
            _matched_metrics=matched_metrics,
        )

    # ── Step 2: 检测全量重跑 ──
    if _FULL_PATTERNS.search(text):
        # 检查是否同时有指标关键词（"全面分析价格带"→ 其实是局部）
        # 但上面 Step 1 已经处理了指标匹配，如果走到这里说明没有明确指标
        return ReanalysisDecision(
            scope=REANALYSIS_FULL,
            user_correction=user_input,
            confidence="high",
            _matched_pattern="full_rerun_keyword",
        )

    # ── Step 3: 检测解释类 ──
    if _EXPLAIN_PATTERNS.search(text):
        # 确认是否针对上次分析（不是全新的"为什么"问题）
        is_context_bound = _is_context_bound(text, last_commentary)
        if is_context_bound:
            return ReanalysisDecision(
                scope=REANALYSIS_EXPLAIN,
                user_correction=user_input,
                confidence="high" if is_context_bound else "medium",
                _matched_pattern="explain_keyword",
            )

    # ── Step 4: 不匹配任何重分析模式 → D 类新问题 ──
    return ReanalysisDecision(
        scope=REANALYSIS_NEW,
        user_correction="",
        confidence="high",
        _matched_pattern="no_match_new_question",
    )


def _detect_metrics(text: str) -> List[str]:
    """检测文本中提到了哪些已知指标"""
    matched = []
    for metric, aliases in METRIC_ALIASES.items():
        for alias in aliases:
            if alias.lower() in text:
                matched.append(metric)
                break
    return matched


def _extract_correction(text: str, matched_metrics: List[str]) -> str:
    """提取用户指出的问题（去掉指标关键词后的文本）"""
    # 收集所有匹配到的别名
    matched_aliases = set()
    for metric in matched_metrics:
        for alias in METRIC_ALIASES.get(metric, []):
            if alias.lower() in text:
                matched_aliases.add(alias.lower())

    # 去掉别名（避免残留关键词干扰 LLM 注释）
    cleaned = text
    for alias in sorted(matched_aliases, key=len, reverse=True):
        cleaned = cleaned.replace(alias, "").strip()
    return cleaned.strip() or "用户未具体说明，仅要求重新分析指定指标"


def _is_context_bound(text: str, last_commentary: str) -> bool:
    """判断用户的"为什么/解释"是否针对上次分析（vs 全新的问题）"""
    if not last_commentary:
        return False
    # 用 2-字和 3-字 ngram 判断用户输入是否与上次分析相关
    # 纯中文中 \w 不匹配中文字符，所以需要显式提取
    import unicodedata
    def extract_ngrams(s, n):
        """提取非 ASCII 字符的 n-gram（中文字符的片段）"""
        chars = [c for c in s.lower() if unicodedata.category(c).startswith('L') or c.isdigit()]
        return set(''.join(chars[i:i+n]) for i in range(len(chars)-n+1))

    input_bigrams = extract_ngrams(text, 2)
    input_trigrams = extract_ngrams(text, 3)
    comment_bigrams = extract_ngrams(last_commentary[:500], 2)
    comment_trigrams = extract_ngrams(last_commentary[:500], 3)

    stopwords = {"为什么", "怎么", "说明", "解释", "详细", "展开", "简单", "不够",
                 "清楚", "明白", "理解", "不懂", "再看", "再说", "重新", "一下",
                 "这个", "那个", "哪个", "什么", "如何", "可以", "能", "不能",
                 "一个", "还是", "或者", "然后", "而且", "但是", "因为", "所以",
                 "一下", "吗", "呢", "吧", "的", "了", "吧"}

    overlap_bigrams = input_bigrams & comment_bigrams - stopwords
    overlap_trigrams = input_trigrams & comment_trigrams - stopwords

    return len(overlap_bigrams) >= 2 or len(overlap_trigrams) >= 1


# ── 工具函数：从用户输入推断 filter_constraints ──

_FILTER_PATTERNS = [
    (re.compile(r'(只看|只看低价|低价.*[以]下|低于?\s*\$?(\d+))'), "price_upper"),
    (re.compile(r'(只看高价|高价.*[以]上|高于?\s*\$?(\d+))'), "price_lower"),
    (re.compile(r'(只看[a-zA-Z0-9一-鿿]+品牌|品牌.{0,4}(是|为)\s*[a-zA-Z0-9一-鿿]+)'), "brand"),
    (re.compile(r'(评分[以]上|至少.*?(\d\.?\d*)\s*星|(\d\.?\d*)\s*星[以]上)'), "min_rating"),
    (re.compile(r'(FBA|fba)'), "fba_only"),
]


def extract_filter_constraints(user_input: str) -> Dict[str, Any]:
    """从用户输入中提取过滤约束（如"只看低价产品"→ price < threshold）"""
    constraints = {}
    for pattern, key in _FILTER_PATTERNS:
        match = pattern.search(user_input)
        if match:
            if key == "price_upper" and match.lastindex and match.group(match.lastindex):
                try:
                    constraints["max_price"] = float(match.group(match.lastindex))
                except ValueError:
                    constraints["price_tier"] = "low"
            elif key == "price_lower":
                constraints["price_tier"] = "high"
            elif key == "brand":
                constraints["brand_filter"] = match.group(1)
            elif key == "min_rating" and match.lastindex:
                try:
                    constraints["min_rating"] = float(match.group(match.lastindex))
                except ValueError:
                    pass
            elif key == "fba_only":
                constraints["fba_only"] = True
    return constraints