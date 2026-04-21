# 🧱 S1：Workspace UI骨架层（施工级详细规范）

------

# 🎯 一、目标定义（必须严格理解）

构建 Nova 的唯一主入口：

> ❗一个不可跳转的 AI 工作台（Workspace）

它必须具备：

- 三栏结构（Left / Center / Right）
- 全屏沉浸式布局
- 组件可替换，但结构不可变
- 不包含任何业务逻辑

------

# 🚨 二、绝对约束（强制）

DeepSeek 必须遵守：

```txt
❌ 不允许写 Graph 逻辑
❌ 不允许写 node 数据结构
❌ 不允许调用 API
❌ 不允许做页面跳转
❌ 不允许出现 Dashboard / Home Page
```

------

# 🧭 三、文件结构（必须创建）

```txt
src/views/Workspace.vue
src/components/workspace/
    ├── LeftPanel.vue
    ├── ExecutionCanvas.vue
    ├── ResultLayer.vue
src/layout/
    └── workspaceLayout.css
```

------

# 🧱 四、Workspace.vue（唯一入口）

------

## 🎯 职责

- 只负责布局
- 不写任何业务逻辑
- 只做组件拼接

------

## 📐 布局结构（必须固定）

```txt
┌──────────────────────────────────────────────┐
│ HEADER（可选：工具栏）                        │
├──────────────┬────────────────────┬──────────┤
│ LEFT PANEL   │ CENTER GRAPH       │ RIGHT     │
│ 情报/策略     │ 执行流画布         │ 结果产出  │
└──────────────┴────────────────────┴──────────┘
```

------

## 💡 Vue结构（必须这样写）

```vue
<template>
  <div class="workspace">

    <HeaderBar />

    <div class="workspace-body">
      <LeftPanel />
      <ExecutionCanvas />
      <ResultLayer />
    </div>

  </div>
</template>
```

------

## 🎨 CSS布局规则（关键）

必须使用 Grid：

```css
.workspace-body {
  display: grid;
  grid-template-columns: 20% 55% 25%;
  height: 100vh;
  overflow: hidden;
}
```

------

## ❗禁止行为

```txt
❌ 不允许 flex 替代 grid（核心结构必须稳定）
❌ 不允许滚动破坏布局
❌ 不允许嵌套页面布局
```

------

# 🧩 五、三大区域定义（非常重要）

------

# 1️⃣ LEFT：Intelligence Panel（情报与策略）

------

## 📦 文件

```txt
LeftPanel.vue
```

------

## 🎯 职责

- 任务选择入口
- AI策略控制入口
- 市场信息展示入口

------

## 📌 内部结构（占位）

```txt
[ TaskLauncher ]
[ StrategyPanel ]
[ MarketFeed ]
```

------

## ❗禁止

```txt
❌ 不允许执行 Graph
❌ 不允许显示结果
```

------

------

# 2️⃣ CENTER：Execution Canvas（Graph画布）

------

## 📦 文件

```txt
ExecutionCanvas.vue
```

------

## 🎯 职责

- Graph容器（空壳）
- 后续挂载 workflow graph

------

## 📌 当前阶段要求

```txt
仅允许显示一个空白画布区域
```

------

## ❗禁止

```txt
❌ 不允许实现节点逻辑
❌ 不允许执行流程
```

------

------

# 3️⃣ RIGHT：Result Layer（结果层）

------

## 📦 文件

```txt
ResultLayer.vue
```

------

## 🎯 职责

- 结果展示容器
- 后续支持动态 renderer

------

## 📌 当前阶段

```txt
仅显示 placeholder（空容器）
```

------

## ❗禁止

```txt
❌ 不允许渲染数据
❌ 不允许接 Graph 输出
```

------

# 🧱 六、HeaderBar（可选但推荐）

------

## 🎯 职责

- 系统级工具入口
- 不参与业务逻辑

------

## 📌 内容

```txt
Logo | Workspace | Settings | User
```

------

# 🧠 七、状态规则（暂时不实现逻辑）

S1阶段仅允许：

```txt
UI存在，不允许状态驱动
```

------

# 🚨 八、验收标准（非常关键）

DeepSeek 必须满足：

```txt
✔ 页面只有一个 Workspace
✔ 三栏布局稳定
✔ 无路由跳转
✔ 无业务逻辑
✔ 无 Graph 实现
✔ 无 API 调用
```

------

# 🧭 九、S1完成后的系统状态

完成后系统应该是：

```txt
一个空的AI驾驶舱（没有大脑，但有结构）
```

------

# 🧨 十、绝对一句话总结

> S1 = 只是把“AI工作台的骨架”搭出来，不允许它开始思考。

------