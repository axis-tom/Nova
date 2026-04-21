# 🧠 S5｜Result渲染系统（DeepSeek施工指令版）

------

## 🎯 一、任务目标

构建 `src/workspace/result/`，实现：

> Graph输出 → 结构化解析 → 多形态渲染 → 可编辑 → 可回传S4

------

## ⚠️ 强约束（必须遵守）

```
1. Result层不允许执行graph逻辑
2. Result层不允许直接调用core
3. 只允许通过 eventBus 通信（S4）
4. 所有渲染必须基于统一数据结构
5. 所有结果必须可“被编辑”
```

------

# 📦 二、必须创建的文件结构

```
src/workspace/result/

├── ResultRenderer.vue        # 总入口（动态分发器）
├── ResultContainer.vue       # 容器层（状态接收）

├── parser/
│   ├── resultParser.js       # Graph输出 → UI结构

├── renderers/               # 多渲染器系统
│   ├── TextRenderer.vue
│   ├── MarkdownRenderer.vue
│   ├── TableRenderer.vue
│   ├── ChartRenderer.vue
│   ├── ImageCompareRenderer.vue

├── editor/
│   ├── InlineEditor.vue      # 可编辑能力核心
│   ├── EditToolbar.vue       # 操作工具栏
```

------

# 🧠 三、核心设计原则

------

## 1️⃣ Result不是“展示”，是“可操作产物”

```
展示 + 编辑 + 回传 = Result系统
```

------

## 2️⃣ 所有数据必须统一格式

### Graph输出必须被解析为：

```
{
  id: "node_x",
  type: "text | markdown | table | chart | image",
  content: {},
  editable: true,
  meta: {
    sourceNode: "",
    timestamp: ""
  }
}
```

------

## 3️⃣ Result必须支持“双向流”

```
Graph → Result（生成）
Result → Graph（修改触发重算）
```

------

# 🧩 四、核心文件施工指令

------

## 🧱 1. ResultRenderer.vue（入口分发器）

📍路径：

```
src/workspace/result/ResultRenderer.vue
```

### 🛠任务：

实现**动态组件渲染系统**

### 必须实现：

```
根据 result.type 动态加载 renderer
```

### 映射关系：

```
text → TextRenderer
markdown → MarkdownRenderer
table → TableRenderer
chart → ChartRenderer
image → ImageCompareRenderer
```

------

## 🧱 2. ResultContainer.vue（状态容器）

📍路径：

```
src/workspace/result/ResultContainer.vue
```

### 🛠任务：

接收 S4 eventBus 数据流

### 必须实现：

- 监听 RESULT_UPDATE
- 存储当前 result state
- 传递给 ResultRenderer

------

## 🧱 3. parser/resultParser.js（数据转换核心）

📍路径：

```
src/workspace/result/parser/resultParser.js
```

### 🛠任务：

将 graph output 转换为 UI结构

### 输入：

```
graph raw output
```

### 输出：

```
标准 result schema
```

------

## 🧱 4. TextRenderer.vue

📍路径：

```
src/workspace/result/renderers/TextRenderer.vue
```

### 🛠任务：

纯文本渲染 + 可编辑

### 必须支持：

- inline edit
- 保存触发 eventBus

------

## 🧱 5. MarkdownRenderer.vue

📍路径：

```
src/workspace/result/renderers/MarkdownRenderer.vue
```

### 🛠任务：

Markdown渲染 + 编辑模式切换

### 必须支持：

- preview / edit toggle
- 实时更新

------

## 🧱 6. TableRenderer.vue

📍路径：

```
src/workspace/result/renderers/TableRenderer.vue
```

### 🛠任务：

结构化数据展示

### 必须支持：

- sortable table
- row edit
- diff highlight

------

## 🧱 7. ChartRenderer.vue

📍路径：

```
src/workspace/result/renderers/ChartRenderer.vue
```

### 🛠任务：

数据可视化

### 必须支持：

- 动态数据更新
- hover inspection

------

## 🧱 8. ImageCompareRenderer.vue

📍路径：

```
src/workspace/result/renderers/ImageCompareRenderer.vue
```

### 🛠任务：

图像对比（AI生成 vs 原图）

### 必须支持：

- before / after slider
- hover zoom

------

## 🧱 9. InlineEditor.vue（核心能力）

📍路径：

```
src/workspace/result/editor/InlineEditor.vue
```

### 🛠任务：

实现“结果可直接修改”

### 必须实现：

- 点击即编辑
- blur 自动保存
- emit RESULT_UPDATE

------

# 🔄 五、完整Result数据流

------

## 🎯 Graph → Result

```
graphEngine
  ↓
node output
  ↓
resultParser
  ↓
RESULT_UPDATE
  ↓
ResultContainer
  ↓
ResultRenderer
```

------

## 🎯 用户编辑 → Graph重算

```
InlineEditor
  ↓
RESULT_UPDATE
  ↓
eventBus
  ↓
dispatcher (S4)
  ↓
graphBridge
  ↓
core re-run
```

------

# ⚠️ 六、禁止行为

```
❌ Result直接调用graph
❌ renderer之间互相调用
❌ UI组件写业务逻辑
❌ 绕过 parser
```

------

# 🧠 七、验收标准（必须全部满足）

### ✔ Graph输出能显示为不同类型UI

### ✔ Result支持编辑

### ✔ 编辑能触发Graph重算

### ✔ Result不会直接依赖core

### ✔ renderer可插拔扩展

------

# 🚀 八、S5完成后的系统状态

完成后你的系统会变成：

> 🧠 “AI工作流 + 可编辑产物系统”

能力：

- AI生成结果不是“死的”
- 可以直接修改AI输出
- 修改能反向驱动AI流程
- 产品已经具备“工具级体验”

------

# 🧭 九、你现在整个系统的阶段定位

```
S3 = 能算（Graph）
S4 = 能动（事件）
S5 = 能用（产品感）
```

------

# ⚡ 最后一句关键判断

做到S5之后，你这个 Nova 已经不是：

> ❌ demo系统
>  ❌ 工具集合
>  ❌ dashboard

而是：

> 🧠 “可编辑的AI工作流操作系统原型”