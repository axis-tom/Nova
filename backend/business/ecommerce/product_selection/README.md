# 电商选品分析场景

## 一、场景概述

### 业务价值

电商选品分析是电商运营的核心环节，直接关系到店铺的销售业绩和利润水平。本场景通过自动化数据分析，帮助运营团队：

- **快速洞察市场趋势**：分析品类热度、价格走势、搜索量变化
- **精准竞品对标**：识别竞品优劣势，发现市场空白
- **量化盈利评估**：计算 ROI、利润率，科学决策
- **自动生成简报**：将分析结果转化为可读性强的选品报告

### 适用角色

- 电商运营经理
- 商品采购专员
- 品类运营负责人
- 数据分析师

---

## 二、架构设计

### 设计原则

本场景严格遵循 Nova 平台的架构铁律：

1. **不修改 common/ 和 foundation/ 下的任何已有文件**
2. **不污染基础能力层** — 所有场景代码隔离在 `business/ecommerce/product_selection/` 下
3. **不复用基础层目录** — 不新建任何 Common/Foundation 层的目录或文件

### 架构层次

```
backend/business/ecommerce/product_selection/
├── sop.yaml                    # SOP 流程定义（声明式编排）
├── agents/                     # 场景专属 Agent
│   ├── __init__.py
│   ├── market_analyst.py       # 市场分析 Agent
│   ├── competitor_analyst.py   # 竞品分析 Agent
│   └── briefing_generator.py   # 简报生成 Agent
├── tools/                      # 场景专属工具（预留）
│   └── __init__.py
├── data/                       # 场景模拟数据
│   ├── mock_products.json      # 商品模拟数据
│   ├── mock_competitors.json   # 竞品模拟数据
│   └── mock_market_trends.json # 市场趋势模拟数据
└── README.md                   # 本文件
```

### 复用关系

| 组件 | 来源 | 用途 |
|------|------|------|
| `Agent` 基类 | `common/core/agent.py` | 所有场景 Agent 的基类 |
| `State` 状态对象 | `common/core/state.py` | Agent 间数据传递 |
| `AgentInput` / `AgentOutput` | `common/core/agent.py` | 输入输出契约 |
| `ContractAgent` | `common/contracts/contract_agent.py` | 契约验证（可选） |
| 分析能力 | `foundation/cognition/` | 高级分析能力（预留） |

---

## 三、数据流说明

### 完整链路

```
Collector → ContextWrapper → Graph → AI → Output
```

### 在本场景中的映射

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 数据采集 (Collector)                                      │
│    ├── mock_products.json      ← 商品数据                    │
│    ├── mock_competitors.json   ← 竞品数据                    │
│    └── mock_market_trends.json ← 市场趋势数据                │
└──────────────┬──────────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. 上下文包装 (ContextWrapper)                                │
│    ├── State 对象创建                                         │
│    ├── 参数注入 (analysis_type, format 等)                    │
│    └── 元数据设置 (user_id, trace_id)                        │
└──────────────┬──────────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. 流程编排 (Graph / SOP)                                    │
│    ├── Step 1: collect_data     → market_analyst             │
│    ├── Step 2: market_analysis  → market_analyst             │
│    ├── Step 3: competitor_analysis → competitor_analyst      │
│    ├── Step 4: profitability_assessment → market_analyst     │
│    └── Step 5: briefing_generation → briefing_generator      │
└──────────────┬──────────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. AI 分析 (Agent 执行)                                      │
│    ├── 市场趋势分析 → 机会点/风险点识别                       │
│    ├── 竞品对比分析 → 差异化策略                              │
│    ├── 盈利评估 → ROI 计算                                   │
│    └── 简报生成 → Markdown 报告                              │
└──────────────┬──────────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. 输出 (Output)                                             │
│    ├── market_analysis_result   ← 市场分析结果               │
│    ├── competitor_analysis_result ← 竞品分析结果             │
│    ├── profitability_result     ← 盈利评估结果               │
│    └── briefing                 ← 选品简报                   │
└─────────────────────────────────────────────────────────────┘
```

### 数据传递方式

每个 SOP 步骤通过 `State` 对象传递数据：

1. **Step 1 (collect_data)**: 加载 JSON 文件 → 存入 State
2. **Step 2 (market_analysis)**: 从 State 读取 products + market_trends → 分析 → 写回 State
3. **Step 3 (competitor_analysis)**: 从 State 读取 competitors + market_analysis_result → 分析 → 写回 State
4. **Step 4 (profitability_assessment)**: 从 State 读取 products + competitor_analysis_result → 评估 → 写回 State
5. **Step 5 (briefing_generation)**: 从 State 读取所有分析结果 → 生成简报 → 写回 State

---

## 四、运行方式

### 前提条件

- Python 3.9+
- Nova 后端服务已配置

### 方式一：通过 SOP 引擎触发

```python
from backend.business.ecommerce.product_selection.agents import (
    MarketAnalystAgent,
    CompetitorAnalystAgent,
    BriefingGeneratorAgent,
)
from backend.common.core.state import State

# 1. 数据采集
state = State({"data_source": "product_selection_data"})
analyst = MarketAnalystAgent()
state = analyst.run(state)

# 2. 市场分析
state.set("analysis_type", "market_trends")
state = analyst.run(state)

# 3. 竞品分析
competitor = CompetitorAnalystAgent()
state = competitor.run(state)

# 4. 盈利评估
state.set("analysis_type", "roi_analysis")
state = analyst.run(state)

# 5. 生成简报
generator = BriefingGeneratorAgent()
state.set("format", "markdown")
state = generator.run(state)

# 6. 获取结果
briefing = state.get("briefing")
print(briefing["content"])
```

### 方式二：通过 SOP YAML 配置自动编排

```python
import yaml
from backend.business.ecommerce.product_selection.agents import (
    MarketAnalystAgent,
    CompetitorAnalystAgent,
    BriefingGeneratorAgent,
)
from backend.common.core.state import State

# 加载 SOP 定义
with open("backend/business/ecommerce/product_selection/sop.yaml", "r") as f:
    sop = yaml.safe_load(f)

# 注册 Agent
agent_registry = {
    "market_analyst": MarketAnalystAgent(),
    "competitor_analyst": CompetitorAnalystAgent(),
    "briefing_generator": BriefingGeneratorAgent(),
}

# 按 SOP 步骤顺序执行
state = State({"user_id": 1, "trace_id": "trace-001"})
for step in sop["steps"]:
    step_id = step["id"]
    params = step.get("params", {})
    for key, value in params.items():
        state.set(key, value)
    
    for agent_name in step["agents"]:
        agent = agent_registry[agent_name]
        state = agent.run(state)
    
    # 保存步骤输出
    for field in step.get("output_fields", []):
        result = state.get("result")
        if result:
            state.set(field, result)

# 获取最终简报
final_briefing = state.get("briefing")
```

### 方式三：直接测试

```bash
# 进入项目根目录
cd /home/nova/nova

# 运行测试脚本
python -c "
from backend.business.ecommerce.product_selection.agents import MarketAnalystAgent
from backend.common.core.state import State

agent = MarketAnalystAgent()
state = State({'analysis_type': 'market_trends'})
result = agent.run(state)
print(result.get('result'))
"
```

---

## 五、扩展指南

### 5.1 替换模拟数据为真实数据源

当前场景使用 `data/` 目录下的 JSON 文件作为数据源。要切换到真实数据源，只需修改 Agent 的 `_load_mock_data()` 方法：

#### 方案 A：修改 MarketAnalystAgent

```python
class MarketAnalystAgent(Agent):
    def _load_mock_data(self) -> Dict[str, Any]:
        """从真实数据源加载数据"""
        # 替换为真实 API 调用
        import requests
        
        products = requests.get("https://api.yourapp.com/products").json()
        trends = requests.get("https://api.yourapp.com/market-trends").json()
        
        return {
            "products": products,
            "market_trends": trends
        }
```

#### 方案 B：通过依赖注入

```python
class MarketAnalystAgent(Agent):
    def __init__(self, data_loader=None):
        """支持自定义数据加载器"""
        self._data_loader = data_loader or self._default_data_loader
        self._data_cache = {}
    
    def _default_data_loader(self):
        """默认的模拟数据加载"""
        # ... 原有逻辑 ...
    
    def _load_mock_data(self):
        return self._data_loader()
```

#### 方案 C：通过配置切换

```python
class MarketAnalystAgent(Agent):
    def __init__(self, config=None):
        self.config = config or {}
        self._data_cache = {}
    
    def _load_mock_data(self):
        data_source = self.config.get("data_source", "mock")
        
        if data_source == "mock":
            return self._load_from_json()
        elif data_source == "api":
            return self._load_from_api()
        elif data_source == "database":
            return self._load_from_db()
        else:
            raise ValueError(f"Unknown data source: {data_source}")
```

### 5.2 添加新的分析维度

1. 在 `data/` 下添加新的模拟数据文件
2. 在对应的 Agent 中添加新的分析方法
3. 在 `sop.yaml` 中添加新的步骤或扩展现有步骤的 `output_fields`

### 5.3 自定义简报模板

修改 `BriefingGeneratorAgent._generate_markdown_briefing()` 方法中的 Markdown 模板，或添加新的输出格式（如 HTML、PDF）。

### 5.4 集成 foundation/cognition 能力

```python
from backend.foundation.cognition.reasoning.judges.insight import InsightJudge

class EnhancedMarketAnalystAgent(MarketAnalystAgent):
    def run(self, state: State) -> State:
        # 先执行基础分析
        state = super().run(state)
        
        # 使用 foundation 的洞察能力增强分析
        judge = InsightJudge()
        analysis_result = state.get("result", {})
        enhanced_insights = judge.analyze(analysis_result)
        analysis_result["enhanced_insights"] = enhanced_insights
        state.set("result", analysis_result)
        
        return state
```

---

## 六、验证

### 目录结构验证

```bash
tree backend/business/ecommerce/product_selection/
```

预期输出：

```
backend/business/ecommerce/product_selection/
├── README.md
├── sop.yaml
├── agents/
│   ├── __init__.py
│   ├── market_analyst.py
│   ├── competitor_analyst.py
│   └── briefing_generator.py
├── data/
│   ├── mock_products.json
│   ├── mock_competitors.json
│   └── mock_market_trends.json
└── tools/
    └── __init__.py
```

### 语法验证

```bash
python3 -m py_compile backend/business/ecommerce/product_selection/agents/market_analyst.py
python3 -m py_compile backend/business/ecommerce/product_selection/agents/competitor_analyst.py
python3 -m py_compile backend/business/ecommerce/product_selection/agents/briefing_generator.py
```

---

## 七、文件清单

| 文件 | 作用 |
|------|------|
| `sop.yaml` | SOP 流程定义，声明式编排 5 个分析步骤 |
| `agents/__init__.py` | Agent 包导出 |
| `agents/market_analyst.py` | 市场分析 Agent（市场趋势 + 盈利评估） |
| `agents/competitor_analyst.py` | 竞品分析 Agent（竞品对比 + 差异化策略） |
| `agents/briefing_generator.py` | 简报生成 Agent（Markdown/JSON 格式） |
| `tools/__init__.py` | 场景工具预留 |
| `data/mock_products.json` | 14 个商品的模拟数据 |
| `data/mock_competitors.json` | 8 个竞品的模拟数据 |
| `data/mock_market_trends.json` | 12 个月的市场趋势数据 |
| `README.md` | 本文件 |

---

*最后更新：2026-05-05*
*版本：1.0.0*
