# 📘 Nova 前端系统分层切片规划（Slice Map）

------

# 🧠 一、整体系统分层（你现在这个项目真正的结构）

Nova 前端 = 5 个 Slice 组成

```txt
S1：UI骨架层（Workspace Layout）
S2：业务组件层（Panel Components）
S3：Graph执行层（Workflow Engine）
S4：交互事件层（Event Bus）
S5：业务协议层（Node I/O Schema）
```

------

# 🚨 二、五层依赖关系（非常重要）

```txt
S1 → S2 → S3 → S4 → S5（最终锁死）
```

解释：

- 没有 S1：页面无法存在
- 没有 S3：系统不会“动”
- 没有 S4：不会有“交互感”
- 没有 S5：系统不可扩展（会变乱）

------

# 🧭 三、施工顺序（必须严格执行）

------

# ✅ STEP 1：S1 UI骨架层（必须最先做）

------

## 🎯 目标

建立“AI工作台空间结构”

------

## 📦 输出物

```txt
Workspace.vue
三栏布局（Left / Center / Right）
```

------

## ❗规则

- 不允许写业务逻辑
- 不允许 Graph 运算
- 只允许布局 + 容器

------

## ✔ 完成标准

```txt
页面稳定三栏 + 可扩展
```

------

# ✅ STEP 2：S2 业务组件层（模块化）

------

## 🎯 目标

把 UI 变成“可插拔工具”

------

## 📦 组件

```txt
LEFT:
- TaskLauncher
- StrategyPanel
- MarketFeed

CENTER:
- ExecutionCanvas
- BusinessNode

RIGHT:
- ResultContainer
- ListingEditor
- ImageCompare
```

------

## ❗规则

- 每个组件必须“单一职责”
- 禁止跨组件调用逻辑

------

## ✔ 完成标准

```txt
组件可以独立运行 + 可组合
```

------

# ✅ STEP 3：S3 Graph执行层（核心大脑）

------

## 🎯 目标

让系统“会动”

------

## 📦 核心模块

```txt
graphEngine.js
runNode()
runFromNode()
markDirtyChain()
nodeStateMachine
```

------

## 🧠 Node模型

```js
node = {
  id,
  type,
  status,
  config,
  input,
  output,
  upstream,
  downstream,
  dirty
}
```

------

## ❗规则

- 所有执行必须走 graphEngine
- 禁止组件直接修改 node.status

------

## ✔ 完成标准

```txt
节点可以执行 + rerun + 状态流转
```

------

# ✅ STEP 4：S4 事件交互层（神经系统）

------

## 🎯 目标

让系统“可被操作”

------

## 📦 事件流定义

```txt
nodeClick
nodeUpdate
nodeRerun
resultEdit
strategyUpdate
```

------

## 🔁 核心事件流

------

### ① 节点点击

```txt
UI → store.setActiveNode → Result更新
```

------

### ② 参数修改

```txt
NodeSettings → store → markDirty → graphEngine
```

------

### ③ Result修改（反向驱动）

```txt
ResultEditor → store → markDirty → rerun链
```

------

### ④ rerun

```txt
UI → graphEngine.runFromNode()
```

------

## ✔ 完成标准

```txt
任意操作都能驱动 Graph 状态变化
```

------

# ✅ STEP 5：S5 业务协议层（最终锁死层）

------

## 🎯 目标

定义“AI节点输入输出标准”

------

## 📦 Node协议标准

------

### 📌 Listing生成节点

```txt
input:
- product
- keywords
- market

output:
- title
- bullet_points
- seo_score
```

------

### 📌 图片生成节点

```txt
input:
- product
- style
- prompt

output:
- images[]
- prompt_trace
```

------

### 📌 评论分析节点

```txt
input:
- reviews[]

output:
- sentiment
- insights
- actions
```

------

## ❗规则

- 所有 node.type 必须绑定 schema
- Result renderer 必须匹配 output.type

------

## ✔ 完成标准

```txt
Graph 输出结构稳定 + UI可预测渲染
```

------

# 🧠 四、最终系统闭环（五层联动）

```txt
S1（布局）
  ↓
S2（组件）
  ↓
S3（执行）
  ↓
S4（交互）
  ↓
S5（协议）
```

------

# 🚀 五、施工节奏建议（非常重要）

------

## 🟢 第一阶段（必须先完成）

```txt
S1 + S2
```

👉 目标：页面长出来

------

## 🟡 第二阶段

```txt
S3
```

👉 目标：Graph 能跑

------

## 🟠 第三阶段

```txt
S4
```

👉 目标：能操作系统

------

## 🔴 第四阶段

```txt
S5
```

👉 目标：系统稳定可扩展

------

# 🧨 六、禁止行为（很关键）

```txt
❌ 先接后端
❌ 一步做完所有层
❌ Graph 里写业务逻辑
❌ Result 直接写死
```

------

# 🧠 七、最终一句话

> Nova 前端 = 五层切片系统，而不是一个页面项目

------