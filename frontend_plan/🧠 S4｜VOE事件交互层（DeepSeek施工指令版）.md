# 🧠 S4｜VOE事件交互层（DeepSeek施工指令版）

------

## 🎯 一、任务目标（必须严格执行）

构建 `src/workspace/voe/` 事件系统，实现：

> UI操作 → eventBus → dispatcher → graph → result 的完整通信链路

------

## ⚠️ 强约束（必须遵守）

```
1. 禁止直接修改 graph/core
2. 禁止组件直接互相调用
3. 所有通信必须经过 eventBus
4. dispatcher 是唯一控制入口
5. bridge 只做数据转换，不写业务逻辑
```

------

# 📦 二、必须创建的文件（逐个实现）

------

## 🧩 1. eventBus.js（全局事件总线）

📍路径：

```
src/workspace/voe/eventBus.js
```

### 🛠任务要求：

实现一个**轻量发布订阅系统**

### 必须支持：

- on(event, callback)
- emit(event, payload)
- off(event)

### ⚠️规则：

- 不能依赖第三方库
- 必须单例
- 不能包含业务逻辑

------

## 🧩 2. eventTypes.js（事件常量中心）

📍路径：

```
src/workspace/voe/eventTypes.js
```

### 🛠任务要求：

定义所有系统事件常量

### 必须包含：

```
UI_ACTION
NODE_SELECT
NODE_UPDATE
NODE_RUN

GRAPH_START
GRAPH_PROGRESS
GRAPH_FINISH

RESULT_UPDATE
RESULT_RENDER
```

------

## 🧩 3. dispatcher.js（事件调度中心）

📍路径：

```
src/workspace/voe/dispatcher.js
```

### 🛠任务要求：

实现**事件路由分发器**

### 核心逻辑：

```
eventBus.emit → dispatcher → 判断事件类型 → 转发到 bridge
```

### 必须实现：

- handle(event, payload)
- switch eventTypes
- 调用对应 bridge

### ⚠️禁止：

- 不允许调用 core graph 直接执行
- 不允许操作 DOM

------

## 🧩 4. bridge/uiBridge.js（UI → 事件转换）

📍路径：

```
src/workspace/voe/bridge/uiBridge.js
```

### 🛠任务要求：

将 UI 操作标准化为事件

### 必须实现：

- handleClickNode(node)
- handleTaskSubmit(data)
- handlePanelAction(action)

### 输出：

```
统一 emit(UI_ACTION, payload)
```

------

## 🧩 5. bridge/graphBridge.js（事件 → Graph指令）

📍路径：

```
src/workspace/voe/bridge/graphBridge.js
```

### 🛠任务要求：

把事件转换为 graph 可执行指令

### 必须实现：

- triggerNodeRun(nodeId)
- triggerGraphStart()
- triggerNodeUpdate()

### 输出：

```
event → nodeRunner command format
```

------

## 🧩 6. bridge/resultBridge.js（Graph → UI结果）

📍路径：

```
src/workspace/voe/bridge/resultBridge.js
```

### 🛠任务要求：

把 graph 输出转换为 Result UI 可识别结构

### 必须实现：

- formatNodeOutput(nodeData)
- formatGraphResult(graphData)

### 输出结构：

```
{
  type: "markdown | table | chart | image",
  payload: {},
  meta: {}
}
```

------

## 🧩 7. listeners/nodeListener.js

📍路径：

```
src/workspace/voe/listeners/nodeListener.js
```

### 🛠任务要求：

监听节点相关事件

### 必须监听：

- NODE_SELECT
- NODE_UPDATE
- NODE_RUN

### 行为：

```
eventBus.on → dispatcher → graphBridge
```

------

## 🧩 8. listeners/uiListener.js

📍路径：

```
src/workspace/voe/listeners/uiListener.js
```

### 🛠任务要求：

监听 UI 操作事件

### 必须监听：

- UI_ACTION

### 行为：

```
UI_ACTION → dispatcher → graphBridge / resultBridge
```

------

## 🧩 9. listeners/graphListener.js

📍路径：

```
src/workspace/voe/listeners/graphListener.js
```

### 🛠任务要求：

监听 graph 执行状态

### 必须监听：

- GRAPH_START
- GRAPH_PROGRESS
- GRAPH_FINISH

### 行为：

```
graph状态变化 → resultBridge → UI更新
```

------

# 🔄 三、标准事件流（必须实现）

------

## 🎯 UI点击节点流程

```
UI Click Node
  ↓
uiBridge
  ↓
eventBus(UI_ACTION)
  ↓
dispatcher
  ↓
graphBridge
  ↓
core graph执行
  ↓
graphListener
  ↓
resultBridge
  ↓
Result UI更新
```

------

## 🎯 Graph执行流程

```
GRAPH_START
  ↓
GRAPH_PROGRESS
  ↓
GRAPH_FINISH
  ↓
resultBridge
  ↓
ResultRenderer
```

------

## 🎯 结果修改触发重算

```
Result编辑
  ↓
UI_ACTION
  ↓
dispatcher
  ↓
graphBridge (re-run node)
  ↓
graph重新执行
```

------

# ⚠️ 四、禁止直接依赖关系

```
❌ UI → core
❌ Graph → UI
❌ result → graph
❌ component → component
```

------

# 🧠 五、验收标准（非常重要）

DeepSeek 完成后必须满足：

### ✔ UI点击节点 → Graph能执行

### ✔ Graph执行 → Result自动更新

### ✔ Result修改 → 能触发重新执行

### ✔ 全流程无组件直接耦合

------

# 🚀 六、S4完成后系统能力

完成后系统变成：

> 🧠 “可编排AI工作流系统（事件驱动版）”

能力：

- UI驱动AI执行
- Graph状态实时反馈
- Result可反向影响Graph
- 全系统解耦