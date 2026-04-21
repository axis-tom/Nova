# 🧩 S2：组件层施工指令（可执行 Prompt规范）

------

# 🎯 一、目标

将 UI 拆解为**可控、可组合、不可越权的组件系统**

每个组件必须具备：

- 明确职责
- 明确输入（props）
- 明确输出（emit）
- 明确状态来源（store）
- 明确禁止行为

------

# 🚨 二、全局强约束

```txt
❌ 不允许组件之间直接调用函数
❌ 不允许跨模块 import 业务逻辑
❌ 不允许组件自己发起 Graph 执行
❌ 不允许绕过 store
```

------

# 🧠 三、组件设计统一模板（所有组件必须遵守）

每个组件必须按这个结构写：

```txt
组件名称：
职责：
输入（props）：
输出（emit）：
依赖（store）：
行为规则：
禁止行为：
```

------

# 📦 四、组件施工 Prompt（逐个定义）

------

# 1️⃣ LEFT：TaskLauncher.vue

------

## 🎯 Prompt（给 DeepSeek）

```txt
创建组件 TaskLauncher.vue

职责：
- 用户选择 AI 任务（Listing / 客服 / 选品）
- 初始化 Graph 执行流程

输入：
- 无（内部任务列表）

输出：
- emit('taskSelected', task)

依赖：
- useWorkspaceStore

行为：
- 点击任务 → store.setActiveTask(task)
- 触发 Graph 初始化（仅设置数据，不执行）

禁止行为：
- ❌ 不允许直接调用 graphEngine.run
- ❌ 不允许生成 UI 逻辑以外的数据处理
```

------

# 2️⃣ LEFT：StrategyPanel.vue

------

```txt
创建组件 StrategyPanel.vue

职责：
- 控制 AI 行为参数（语气 / 市场 / SEO强度）

输入：
- store.strategy

输出：
- emit('updateStrategy', strategy)

依赖：
- useWorkspaceStore

行为：
- 修改参数 → store.updateStrategy
- 自动标记所有 nodes 为 dirty

禁止行为：
- ❌ 不允许直接修改 node.output
```

------

# 3️⃣ CENTER：ExecutionCanvas.vue

------

```txt
创建组件 ExecutionCanvas.vue

职责：
- Graph 容器（仅渲染，不执行逻辑）

输入：
- store.nodes
- store.edges

输出：
- emit('nodeClick', nodeId)

依赖：
- useWorkspaceStore

行为：
- 负责渲染 WorkflowGraph
- 接收 nodeClick 并传递 store

禁止行为：
- ❌ 不允许执行 node
- ❌ 不允许修改状态
```

------

# 4️⃣ CENTER：BusinessNode.vue

------

```txt
创建组件 BusinessNode.vue

职责：
- 单个 Graph 节点展示 + 状态反馈

输入：
- node

输出：
- emit('click', node.id)
- emit('rerun', node.id)

依赖：
- useWorkspaceStore

行为：
- 点击 → setActiveNode
- 显示 status（idle / running / done / dirty）

UI规则：
- running → 流光动画
- done → 高亮
- dirty → 黄色提示

禁止行为：
- ❌ 不允许执行 Graph
- ❌ 不允许修改 node.data
```

------

# 5️⃣ RIGHT：ResultContainer.vue

------

```txt
创建组件 ResultContainer.vue

职责：
- 根据 activeNode 渲染结果

输入：
- store.activeNode
- store.results[nodeId]

输出：
- emit('updateResult', data)

依赖：
- useWorkspaceStore

行为：
- 根据 node.type 选择 renderer
- 动态加载 Listing / Image / Chart

禁止行为：
- ❌ 不允许直接修改 Graph
- ❌ 不允许执行 rerun
```

------

# 6️⃣ RIGHT：ListingEditor.vue（重点）

------

```txt
创建组件 ListingEditor.vue

职责：
- 编辑 AI生成的 Listing 文案

输入：
- content

输出：
- emit('update', newContent)

依赖：
- useWorkspaceStore

行为：
- 用户编辑 → updateResult(nodeId)
- 自动触发 markNodeDirty

禁止行为：
- ❌ 不允许修改 node.status
```

------

# 7️⃣ RIGHT：ImageCompare.vue

------

```txt
创建组件 ImageCompare.vue

职责：
- 对比 AI生成图片版本

输入：
- images[]

行为：
- 左右对比视图
- 版本切换

禁止行为：
- ❌ 不允许修改 Graph
```

------

# 8️⃣ RIGHT：ChartPanel.vue

------

```txt
创建组件 ChartPanel.vue

职责：
- 展示 AI分析数据

输入：
- metrics

行为：
- 图表展示（CTR / CVR / ranking）

禁止行为：
- ❌ 不允许修改状态
```

------

# 🧠 五、组件通信规则（核心）

------

## 🔁 标准数据流

```txt
props → UI展示
emit → 事件上抛
store → 状态同步
graphEngine → 执行控制
```

------

## ❗禁止直连

```txt
组件A ❌ 组件B
组件 ❌ graphEngine
组件 ❌ API
```

------

# 🧩 六、组件行为分级（很关键）

------

## 🟢 Level 1：展示组件

- ChartPanel
- ImageCompare

👉 只显示数据

------

## 🟡 Level 2：编辑组件

- ListingEditor
- StrategyPanel

👉 可修改数据，但不能控制执行

------

## 🔴 Level 3：控制组件

- TaskLauncher
- BusinessNode

👉 可触发行为（但必须走 store）

------

# 🚨 七、验收标准（S2完成标志）

```txt
✔ 所有组件独立可运行
✔ 无组件跨调用
✔ 所有状态通过 store
✔ Graph 不在组件中执行
✔ Result 可编辑但不控制执行
```

------

# 🧨 八、最终一句话

> S2 = 把 UI 拆成“可控零件”，但不给它“控制权”。

------