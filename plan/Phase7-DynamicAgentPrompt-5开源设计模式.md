# Phase 7 — Agent System Prompt 动态定制引擎

> 📍 **Layer 定位**：`backend/core/prompt_engine/` — 完整的 Prompt Engine 层
> 📍 **核心命题**：让每个 Agent 的 system prompt 根据用户意图动态变化，支持逐步深入和一次性多维
> 📍 **依赖管理**：`pip install dspy-ai prompty langfuse`（运行时直接用），Promptfoo/AutoPrompt 只借鉴设计模式
> 📍 **翻译专用模型**：gpt-5.4-mini-high（走 `.env` 的中转站 polaapi）
> 📍 **5 个参考项目**：DSPy / Prompty / Langfuse / Promptfoo / AutoPrompt

---

## 零、一句话说清楚做什么

**现状**：每个 Agent 的 system prompt 是硬编码的固定分析维度（`_REVIEW_SYSTEM_PROMPT` 等），用户说"看定价"和"全面分析"，Agent 产出的分析维度完全一样。

**改造后**：用户输入 → 意图分类 → 33 方向匹配 → 每个 Agent 的 system prompt 动态注入本次分析焦点。支持场景 A（逐步深入）和场景 B（一次性多维）。

---

## 一、5 个开源项目的定位

| 项目 | pip 装？ | 运行时调 AI 模型？ | 在 Nova 负责什么 |
|------|---------|------------------|----------------|
| **DSPy** | ✅ `pip install dspy-ai` | ✅ **是** — 用 LLM 做优化、生成示例 | IntentClassifier 用它的 Signature 模式 |
| **Prompty** | ✅ `pip install prompty` | ❌ 不调 LLM，只做格式加载+渲染 | PromptCustomizer 的文件格式 + Load→Render 管道 |
| **Langfuse** | ✅ `pip install langfuse` | ❌ 纯追踪，不调 LLM | IncrementalTracker 的 Trace/Span 层级 |
| **Promptfoo** | ❌ 无 Python 包（Node.js） | ⚠️ 评估用（LLM-as-judge） | 借鉴 YAML 评估配置格式 |
| **AutoPrompt** | ❌ 无 pip 包（GitHub） | ✅ **是** — 核心就是用 LLM 生成改进后的 prompt | 借鉴迭代优化循环理念 |

### 哪些项目调 AI 模型生成 prompt

**DSPy 和 AutoPrompt 是真正用 AI 模型生成/优化 prompt 的。**

- **DSPy**：定义 Signature → DSPy optimizer 自动调 LLM 优化 prompt 内容。`Module.__call__` → `forward()` 每次调用都走 LLM
- **AutoPrompt**：`MetaChain` 在 `optimization_pipeline.py` 里分析错误 → 调 LLM 生成改进版 prompt → 再跑 → 循环

### 批处理场景

对于**批量优化多个 Agent 的 prompt**（比如一次优化 8 个 Agent 的 33 方向定制指令），用 **DSPy + AutoPrompt** 的迭代优化模式：
1. 跑一轮评估，收集各 Agent 的输出
2. 分析哪些方向的定制效果不理想
3. 调 LLM 生成改进后的定制指令
4. 写入 `DimensionMapper` 的映射表
5. 再跑一轮，重复

这不是运行时行为，是**开发期批量优化**。

---

## 二、翻译专用模型：gpt-5.4-mini-high

```python
# backend/core/llm/config.py — 新增
PROMPT_ENGINE_MODEL = {
    "model": "gpt-5.4-mini-high",
    "temperature": 0.2,
    "max_tokens": 2000,
}

def get_prompt_engine_llm() -> ChatOpenAI:
    """获取 Prompt Engine 专用的小模型（翻译/生成/分类）"""
    return ChatOpenAI(
        model=PROMPT_ENGINE_MODEL["model"],
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL", ""),
        temperature=PROMPT_ENGINE_MODEL["temperature"],
        max_tokens=PROMPT_ENGINE_MODEL["max_tokens"],
    )
```

**两套模型各司其职**：

```
Prompt Engine（翻译层）                    Agent 分析层
─────────────────                         ─────────────────
gpt-5.4-mini-high              ←便宜→     gpt-5.2 / claude-sonnet-4-6 / claude-opus-4-6
意图分类（规则 + LLM fallback）             市场分析
维度匹配                                     评论分析
用户 query → 翻译 prompt                   竞品分析
增量判断                                     综合评分
```

---

## 三、目录结构

```
backend/
├── core/
│   ├── prompt_engine/                   ← 完整的 Prompt Engine 层
│   │   ├── __init__.py                  ← 对外只暴露 PromptEngine
│   │   ├── prompt_engine.py             ← 6 个模块的协调器
│   │   ├── engines/
│   │   │   ├── intent_classifier.py     ← pip: dspy-ai（Signature 模式）
│   │   │   ├── incremental_tracker.py   ← pip: langfuse（Trace/Span）
│   │   │   ├── prompt_customizer.py     ← pip: prompty（Load→Render）
│   │   │   ├── evaluator.py             ← 借鉴 Promptfoo（YAML 评估格式）
│   │   │   └── weight_learner.py        ← 借鉴 AutoPrompt（迭代闭环）
│   │   ├── prompts/                     ← .prompty 模板在层内部
│   │   │   ├── review_analyzer.prompty
│   │   │   ├── market_analyst.prompty
│   │   │   ├── competitor_analyst.prompty
│   │   │   ├── traffic_analyzer.prompty
│   │   │   ├── opportunity_judge.prompty
│   │   │   ├── briefing_generator.prompty
│   │   │   ├── keyword_expander.prompty
│   │   │   └── base_agent.prompty
│   │   └── dimension_registry.py        ← 从 agent_context.py 读取，不重复定义
│   │
│   ├── orchestrator.py                  ← 改 10 行：Agent 调用时走 prompt_customizer
│   └── llm/config.py                    ← 新增 get_prompt_engine_llm()
│
├── aqueduct/
│   └── agent_context.py                 ← 保留，dimension_registry 从这里读
│
└── api/
    └── routes/agent_chat.py             ← 改 5 行：用户输入走 prompt_engine.translate()
```

### 关键技术决策

#### dimension_registry.py — 不搞 YAML，不走硬编码

```python
# backend/core/prompt_engine/dimension_registry.py
"""
33 分析方向的映射注册表。

不重复定义方向——直接从 aqueduct/agent_context.py 读取。
只扩展 agent_context.py 没有的部分：每个方向影响哪些 Agent + 定制指令。
"""

from backend.aqueduct.agent_context import (
    ANALYSIS_DIRECTIONS_PROMPTS,
    DIRECTION_META,
)

class DimensionRegistry:
    """维度映射注册表——从 agent_context.py 读取 + 扩展 Agent 映射"""
    
    def __init__(self):
        # 从 agent_context.py 读取——不重复定义
        self.directions = ANALYSIS_DIRECTIONS_PROMPTS       # 33 方向的 prompt 模板
        self.meta = DIRECTION_META                           # 33 方向的元信息
        
        # 扩展：每个方向影响哪些 Agent + 各 Agent 的定制指令
        # 这部分 agent_context.py 没有，是本层新增的
        self.agent_map = self._build_agent_map()
    
    def _build_agent_map(self) -> dict:
        """构建 33 方向 → Agent 映射表"""
        return {
            "pricing_strategy": {
                # 哪些 Agent 受影响
                "affects": ["review_analyzer", "market_analyst", 
                           "competitor_analyst", "opportunity_judge",
                           "briefing_generator"],
                # 每个 Agent 的定制指令（用 gpt-5.4-mini-high 生成/优化）
                "agent_prompts": {
                    "review_analyzer": "重点提取价格相关的评论信号...",
                    "market_analyst": "分析价格带结构...",
                    ...
                },
                # 弱化哪些方向
                "downgrades": ["review_barrier", "fulfillment"],
                # 依赖哪些方向必须先分析
                "depends_on": ["competition_landscape"],
            },
            # ... 其他 32 个方向
        }
    
    def get_agent_prompt(self, dim: str, agent: str) -> str:
        """获取某个方向对某个 Agent 的定制指令"""
        return self.agent_map.get(dim, {}).get("agent_prompts", {}).get(agent, "")
```

#### 为什么 dimension_registry 需要外挂 agent_map，不直接改 agent_context.py？

因为 `agent_context.py` 是 **aqueduct 层**（数据采集+推导），`prompt_engine/` 是 **core 层**。按照 Nova 架构"父目录不引用子目录"原则，core 读 aqueduct 是上层读下层，没问题。但反过来让 aqueduct 加 Agent 映射会打破目录职责。

---

## 四、5 个开源项目的设计模式提炼

### ① DSPy（pip install dspy-ai）→ IntentClassifier

**DSPy 最值的借鉴的是"声明式 Signature"**：把 LLM 调用从"写 prompt 字符串"提升为"定义输入输出结构"。

```python
from dspy import Signature, InputField, OutputField

class ClassifyIntent(Signature):
    """分析用户输入，识别分析意图"""
    query = InputField()
    intent_type = OutputField(desc="market_analysis|deepen|focus_entity|multi_dim|...")
    dimensions = OutputField(desc="分析方向ID列表，从 33 方向中选择")
    depth = OutputField(desc="basic|moderate|deep|comprehensive")
    primary_dim = OutputField(desc="主线方向ID")
    entities = OutputField(desc="关注的实体列表，如 ['Anker']")
```

**Nova 怎么用 dspy**：
- 不直接用 dspy 做运行时分类（有自己的规则引擎）
- 用它的 **Signature 模式** 定义 IntentClassifier 的结构化输入输出
- 开发期用 dspy optimizer 生成 `dimension_registry.agent_map` 的定制指令

### ② Prompty（pip install prompty）→ PromptCustomizer

**Prompty 最值的借鉴的是 Load → Render 管道和 .prompty 文件格式**：

```yaml
# core/prompt_engine/prompts/review_analyzer.prompty
---
name: ReviewAnalyzer
description: 评论分析 Agent
version: 2.0
inputs:
  - name: tool_descriptions
  - name: core_dimensions
  - name: focus_directions
  - name: downgrade_directions
  - name: is_incremental
    type: boolean
---
system:
你是 Amazon 评论数据分析专家。你有以下分析工具可用：
{tool_descriptions}

【核心分析维度】（始终执行）
{core_dimensions}

{% if focus_directions %}
【本次重点方向 — 用户指定】
{focus_directions}
{% endif %}

{% if downgrade_directions %}
【弱化方向】（本次非重点）
{downgrade_directions}
{% endif %}

{% if is_incremental %}
注意：本轮是增量分析。上轮已覆盖的方向不再重复深挖。
{% endif %}

user:
商品数据：{products_summary}
```

**Nova 的 Prompty 用法**：
- 直接用 `from prompty import load` 加载 `.prompty` 文件
- 用它的 frontmatter 解析 + body 模板渲染
- 不改 Agent 代码结构，只改 system_prompt 的来源

### ③ Langfuse（pip install langfuse）→ IncrementalTracker

**Langfuse 最值的借鉴的是 Trace/Span 层级**：

```
Trace (conversation_xxx)
├── Span (round_1, input="分析蓝牙耳机")
│   ├── Generation (agent="market_analyst", tokens=...)
│   └── Generation (agent="briefing_generator", tokens=...)
├── Span (round_2, parent=round_1, input="价格呢")
│   └── Generation (agent="market_analyst", tokens=...)
```

**Nova 的 Langfuse 用法**：
- `from langfuse import Langfuse` 创建 client
- 每轮对话创建 Trace → Span → Generation
- 用它的父子关系追踪增量分析状态
- 用 tag/metadata 记录 `dimensions`、`is_incremental` 等信息

### ④ Promptfoo（无 pip 包，只借鉴格式）→ Evaluator

**借鉴它的 YAML 评估配置结构**：

```yaml
# 评估配置（开发期使用）
prompts:
  - strategy: "pricing_only"
    prompt_file: "prompts/market_analyst_pricing_v1.prompty"
  - strategy: "pricing_with_competition"
    prompt_file: "prompts/market_analyst_pricing_v2.prompty"

providers:
  - openai:gpt-4o-mini

tests:
  - description: "定价分析"
    vars:
      query: "分析蓝牙耳机，重点看定价"
    assert:
      - type: llm-rubric
        value: "包含：价格带分布、各价格带销量占比、定价锚点"
```

运行时要评估？**不。评估是开发期功能。**

### ⑤ AutoPrompt（无 pip 包，只借鉴理念）→ WeightLearner

**借鉴它的迭代优化循环理念**：

```
优化循环（30 行 Python 实现）:
1. 策略 A（pricing 为主线）score=0.7
2. 策略 B（competition 为主线）score=0.85
3. 下次同类 query → B 被选中的概率更高
4. 执行后更新 score
5. 连续 N 次无提升 → 停止尝试某策略
```

---

## 五、Orchestrator 的 system_prompt 也动态生成

### 当前 orchestrator.py:328-365 的 system_prompt 问题

```
你是一个 Amazon 电商智能助手，负责帮助用户分析市场、选品、监控竞品。

你可以使用以下工具：
1. search_web(query) — ...
2. search_memory(query) — ...
3. query_db(natural_query) — ...
4. call_nova_agent(agent_name, params_json) — ...

可调用的 Agent（8 个）：
  - keyword_expander: ...
  - product_collector: ...
  - review_analyzer: ...
  - ...

Agent 流水线依赖：...
工作流程：...
记忆上下文：...
State 摘要：...
```

这个 system_prompt **没有针对性**——不管用户说什么，orchestrator 收到的都是同一套。LLM 在前 1-3 轮做的核心工作其实是"猜用户到底要什么"。

### 改造后

收到 `IntentAnalysisSpec` 后，orchestrator 的 system_prompt 动态组装：

```
             IntentAnalysisSpec
                   ↓
PromptEngine.build_orchestrator_prompt(spec, session_id)
                   ↓
    动态组装 orchestrator 的 system_prompt
```

具体组装逻辑：

```python
class PromptEngine:
    """协调器"""

    def build_orchestrator_prompt(
        self, 
        spec: IntentAnalysisSpec,
        session_id: str = None,
    ) -> str:
        """
        根据 IntentAnalysisSpec 动态生成 orchestrator 的 system_prompt。
        
        核心变化：
        - 原来 800 token 的通用 Agent 列表 → 只保留当前场景相关的 Agent
        - 原来"猜意图"的指令 → 精确的用户目标描述
        - 原来全量的流水线说明 → 只涉及本次维度的依赖链
        """
        prompt_parts = []
        
        # ── 头部：明确的用户目标（替换原来的"你是一个助手..."） ──
        prompt_parts.append(f"""# 任务：{self._describe_task(spec)}

用户需求：{spec.focus_description or spec.raw_query}
【分析类型】{spec.intent_type.value}
【分析深度】{spec.depth}
【主线方向】{self._dim_name(spec.primary_dim)}
【辅助方向】{', '.join(self._dim_name(d) for d in spec.dimensions if d != spec.primary_dim)}
【关注实体】{', '.join(spec.entities) if spec.entities else '无特定实体'}
""")

        # ── 数据源说明（从已有系统配置读取，不硬编码） ──
        prompt_parts.append(self._build_sources_section(spec))
        
        # ── 可用 Agent（只列出本次分析涉及的 Agent，不是全部 8 个） ──
        affected_agents = self.dimensions.get_affected_agents(spec.dimensions)
        prompt_parts.append(self._build_agents_section(affected_agents))
        
        # ── 增量标记（第 2 轮以后） ──
        if spec.is_incremental:
            prompt_parts.append(self._build_incremental_section(spec))
        
        # ── 输出要求 ──
        prompt_parts.append("""【输出要求】
1. 根据上述分析类型和主线方向，按需调用相关 Agent
2. 每个 Agent 已被注入定制指令，会按本次方向重点分析
3. 最终输出结构化中文报告""")
        
        return "\n\n".join(prompt_parts)
```

### 具体效果对比

**当前（通用）**：
```
你是一个 Amazon 电商智能助手...
可调用 Agent：keyword_expander, product_collector, review_analyzer, 
              traffic_analyzer, market_analyst, competitor_analyst,
              opportunity_judge, briefing_generator
Agent 流水线依赖：...
```

→ **LLM 需要自己判断"用户要什么"→ 猜 1-3 轮**

**改后（针对"分析蓝牙耳机，重点看定价"）**:
```
# 任务：Amazon US 站蓝牙耳机市场定价分析

【分析类型】市场分析（深度）
【主线方向】定价策略
【辅助方向】竞争格局
【关注实体】无

【可用 Agent】（本次分析涉及 4 个）：
- review_analyzer：提取价格相关的评论信号
- market_analyst：分析价格带结构
- competitor_analyst：竞品定价策略对比
- opportunity_judge：综合评分（定价权重 ↑）

【输出要求】聚焦定价分析，竞争格局为辅助。
```

→ **LLM 直接知道目标 → 直接调度，0 轮猜测**

### 这项改动对应的代码位置

```python
# orchestrator.py 的 call_model() — 当前 line 284
async def call_model(state: AgentState) -> Dict[str, Any]:
    llm = _get_llm()
    llm_with_tools = llm.bind_tools(get_tools())
    
    # 当前：构建通用 system_prompt（~800 token）
    system_prompt = self._build_generic_system_prompt(state)  # ← 替换这里
    
    # 改后：从 IntentAnalysisSpec 动态构建
    spec = state.get("intent_spec")  # PromptEngine.translate() 的输出
    system_prompt = prompt_engine.build_orchestrator_prompt(spec, conv_id)
    
    # 后面逻辑不变
    langchain_messages = [SystemMessage(content=system_prompt)]
    ...
```

**改动量：orchestrator.py 改约 15 行**（替换 `call_model()` 中的 system_prompt 构建逻辑，加一个 `build_orchestrator_prompt()` 在 `prompt_engine.py`）。

---

## 六、prompt_engine.py（协调器）

```python
class PromptEngine:
    """
    Agent System Prompt 动态定制引擎—6 个模块的协调器。
    
    用法：
        engine = PromptEngine(config)
        
        # Step 1: translate — 用户输入 → 意图分析规格
        spec = engine.translate("分析蓝牙耳机，重点看定价", session_id="conv_xxx")
        # → IntentAnalysisSpec {intent_type, depth, dimensions, primary_dim, ...}
        
        # Step 2: customize — 为特定 Agent 生成定制 system prompt
        system_prompt = engine.customize("market_analyst", spec, session_id="conv_xxx")
        # → 含核心维度 + 重点方向 + 弱化方向 的完整 system prompt
        
        # Step 3: evaluate — 对话结束后评估效果
        engine.evaluate("conv_xxx", spec, {"result": ..., "tokens": ...})
    """
    
    def __init__(self, config):
        self.classifier = IntentClassifier(config)       # pip: dspy-ai
        self.tracker = IncrementalTracker(config)         # pip: langfuse
        self.customizer = PromptCustomizer(config)        # pip: prompty
        self.evaluator = Evaluator(config)                # 借鉴 Promptfoo
        self.learner = WeightLearner(config)              # 借鉴 AutoPrompt
        self.dimensions = DimensionRegistry()             # 从 agent_context.py 读取
    
    def translate(self, raw_input: str, session_id: str = None) -> "IntentAnalysisSpec":
        """
        用户输入 → 意图分析规格。
        
        流程：
        1. 规则引擎初步分类（关键词匹配，零 LLM）
        2. 边界模糊时调 gpt-5.4-mini-high（DSPy Signature 模式做 LLM 分类）
        3. 如果有历史对话 → 增量标记
        4. WeightLearner 优化策略选择
        """
        ...
    
    def customize(self, agent_name: str, spec: "IntentAnalysisSpec", 
                  session_id: str = None) -> str:
        """
        Agent 调用时：意图规格 → 定制 system prompt。
        
        流程：
        1. Prompty 加载 agent.prompty 文件
        2. DimensionRegistry 读取该 Agent 的定制指令
        3. 注入 spec 中的维度+权重+增量标记
        4. Jinja2 渲染 → 返回完整 system prompt
        """
        ...
    
    def evaluate(self, conversation_id: str, spec: "IntentAnalysisSpec", 
                 result: dict):
        """对话结束后评估效果"""
        ...
```

---

## 七、完整数据流

```
用户: "分析蓝牙耳机，重点看定价"
  │
  ▼
① PromptEngine.translate("分析蓝牙耳机，重点看定价")
  ├── IntentClassifier.classify()
  │   规则匹配 "分析"+"蓝牙耳机"+"定价" → market_analysis
  │   边界模糊 → 调 gpt-5.4-mini-high 做 LLM 分类
  │
  ├── DimensionRegistry
  │   定价方向 "pricing_strategy" → affects [5 个 Agent]
  │
  ├── IncrementalTracker
  │   新会话，无历史 → is_incremental=False
  │
  └── → IntentAnalysisSpec {
        intent_type: "market_analysis",
        depth: "deep",
        dimensions: ["pricing_strategy", "competition_landscape"],
        primary_dim: "pricing_strategy",
        is_incremental: false,
      }

  │
  ▼
② Orchestrator 收到 IntentAnalysisSpec
  |
  PromptEngine.build_orchestrator_prompt(spec)
  └── → system_prompt = "# 任务：Amazon US 站蓝牙耳机定价分析
                          【主线】定价策略【辅助】竞争格局
                          可用 Agent（4 个）：review_analyzer, market_analyst..."
  |
  orchestoror 不再需要猜意图，直接知道目标
  LangGraph ReAct 开始执行

  │
  ▼
③ 调 market_analyst 时：
  PromptEngine.customize("market_analyst", spec)
  ├── prompty.load("prompts/market_analyst.prompty")
  ├── DimensionRegistry.get_agent_prompt("pricing_strategy", "market_analyst")
  │   → "分析价格带结构、各价格带的品牌分布和销量贡献"
  ├── Jinja2 渲染
  └── → system prompt = [核心维度] + [重点]定价带分析 + [弱化]评论壁垒

  │
  ▼
④ 其他 Agent 同理各自拿到定制 prompt
    review_analyzer → [重点]提取价格敏感度评论信号
    competitor_analyst → [重点]竞品定价策略对比
    opportunity_judge → [重点]定价权重↑

  │
  ▼
⑤ Orchestrator 汇总 → 回复用户

─────────────────────────────────────────
第 2 轮: "价格呢，低价品牌活得怎么样"
  │
  ▼
① PromptEngine.translate("价格呢", session_id="conv_xxx")
  ├── IntentClassifier → intent_type: "deepen", dimensions: ["pricing_strategy"]
  ├── IncrementalTracker → is_incremental: true, previous_dimensions: [...]
  └── WeightLearner → pricing_strategy 在"deepen"场景下 score 0.85 → 选最优子策略

  │
  ▼
② Orchestrator 收到增量 IntentAnalysisSpec
   PromptEngine.build_orchestrator_prompt(spec)
   └── → "增量分析：已有蓝牙耳机数据，新增低价格带聚焦"

  │
  ▼
③ PromptEngine.customize("market_analyst", spec)
   ├── [核心]不变
   ├── [本次重点] 价格带底部（<$20）分析，上次未覆盖
   ├── [弱化] 品牌分布（上轮已覆盖）
   └── [增量标记] 已有数据不重复采集
```

---

## 七、实现清单

### 基础设施

- [ ] `pip install dspy-ai prompty langfuse` — 加入 requirements.txt
- [ ] `backend/core/llm/config.py` — 新增 `get_prompt_engine_llm()`（gpt-5.4-mini-high）
- [ ] `backend/core/prompt_engine/engines/` — 5 个引擎模块
- [ ] `backend/core/prompt_engine/prompts/` — 8 个 Agent 的 .prompty 文件
- [ ] `backend/core/prompt_engine/dimension_registry.py` — 从 agent_context.py 读取
- [ ] `backend/core/prompt_engine/prompt_engine.py` — 协调器

### Agent 集成

- [ ] `orchestrator.py` — Agent 调用时走 `PromptEngine.customize()`
- [ ] `agent_chat.py` — 用户输入走 `PromptEngine.translate()`
- [ ] 各 Agent 的 system_prompt 来源从硬编码 → `.prompty` 模板渲染

### 开发期

- [ ] 用 DSPy Signature + gpt-5.4-mini-high 生成 `dimension_registry.agent_map` 的定制指令
- [ ] 批量优化：一轮跑 8 个 Agent × 33 方向，评估效果，迭代 agent_map
- [ ] Evaluator YAML 配置定义评估用例

---

## 八、不做的事（明确边界）

1. **不引入 Promptfoo/AutoPrompt 作为 pip 依赖** — 只借鉴设计模式
2. **不部署额外服务** — Langfuse 直接 `from langfuse import Langfuse`，不走自建 server
3. **不改 Agent 基类代码** — 只改 system_prompt 的来源
4. **不改 orchestrator 的 LangGraph 逻辑** — 只改入口和 Agent 注入点
5. **不通篇改** — 改 `orchestrator.py` 10 行、`agent_chat.py` 5 行、各 Agent 替换 system_prompt 来源
6. **不搞 YAML 定义方向** — 直接从 `agent_context.py` 读取 33 方向，零重复