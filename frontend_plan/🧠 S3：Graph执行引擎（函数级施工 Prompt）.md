# 🧠 S3：Graph执行引擎（函数级施工 Prompt）

------

# 🎯 一、目标

构建 Nova 的“执行大脑”：

> 👉 让 Graph 能够运行、传播、回溯、重试

------

# 🚨 二、绝对禁止

```txt
❌ 不允许 UI 直接执行任务
❌ 不允许组件修改 node.status
❌ 不允许绕过 graphEngine
❌ 不允许在组件中写业务逻辑
```

------

# 🧠 三、核心文件结构

必须创建：

```txt
src/core/graph/
    ├── graphEngine.js
    ├── nodeRunner.js
    ├── nodeStateMachine.js
    ├── dependencyResolver.js
    └── executionQueue.js
```

------

# ⚙️ 四、核心对象模型（必须统一）

```js
Node = {
  id: string,
  type: string,
  status: "idle" | "running" | "done" | "error" | "dirty",
  input: any,
  output: any,
  config: object,
  upstream: string[],
  downstream: string[],
  retryCount: number
}
```

------

# 🧠 五、graphEngine.js（核心施工 Prompt）

------

## 📌 1️⃣ runNode（单节点执行）

```txt
实现函数 runNode(nodeId)

职责：
- 执行单个 node
- 更新状态流转

步骤：
1. 获取 node
2. status = "running"
3. 调用 nodeRunner.execute(node)
4. 成功 → status = "done"
5. 失败 → status = "error"
```

------

## 📌 2️⃣ runFromNode（链式执行）

```txt
实现函数 runFromNode(nodeId)

职责：
- 从某节点开始执行整个 downstream 链

步骤：
1. 找到 node
2. 执行 runNode(node)
3. 遍历 downstream
4. 递归执行
```

------

## 📌 3️⃣ markDirtyChain（脏链标记）

```txt
实现函数 markDirtyChain(nodeId)

职责：
- 标记当前节点及 downstream 为 dirty

规则：
- node.status = "dirty"
- 递归 downstream
```

------

## 📌 4️⃣ dependencyResolver（依赖解析）

```txt
实现函数 resolveDependencies(nodeId)

职责：
- 判断 node 是否可执行

规则：
- upstream 全部 done → 可执行
- 否则 return false
```

------

## 📌 5️⃣ executionQueue（执行队列）

```txt
实现队列机制：

职责：
- 控制执行顺序
- 防止并发冲突

规则：
- FIFO
- 同一 node 不重复执行
```

------

# ⚙️ 六、nodeRunner.js（执行层）

------

## 📌 execute(node)

```txt
实现 execute(node)

职责：
- 模拟 AI 执行

步骤：
1. switch(node.type)
2. 调用 mock handler
3. 返回 output
```

------

## 📦 Mock执行映射

```txt
listing_gen → generateListing()
image_gen → generateImages()
review_analysis → analyzeReviews()
```

------

# 🧠 七、nodeStateMachine.js（状态机）

------

## 📌 状态流转规则

```txt
idle → running → done
idle → running → error
error → retry → running
done → dirty → running
```

------

## 📌 状态函数

```txt
setStatus(nodeId, status)
getStatus(nodeId)
resetNode(nodeId)
```

------

# 🔁 八、执行规则（非常重要）

------

## 📌 规则1：必须检查依赖

```txt
runNode前必须调用 resolveDependencies
```

------

## 📌 规则2：禁止乱序执行

```txt
必须通过 executionQueue
```

------

## 📌 规则3：dirty必须触发重算

```txt
dirty → 必须重新 runFromNode
```

------

# ⚡ 九、完整执行流（系统核心）

```txt
UI click node
   ↓
store.setActiveNode
   ↓
graphEngine.runFromNode
   ↓
resolveDependencies
   ↓
executionQueue
   ↓
nodeRunner.execute
   ↓
update store.results
   ↓
ResultLayer更新
```

------

# 🧨 十、关键限制（防跑偏）

```txt
❌ UI不能触发 execute
❌ UI不能改 node.status
❌ UI只能 dispatch action
```

------

# 🧠 十一、验收标准

```txt
✔ node可单独执行
✔ node可链式执行
✔ dirty能触发重算
✔ executionQueue正常
✔ 状态流转正确
```

------

# 🧨 十二、一句话总结

> S3 = 把 Nova 从“静态界面”变成“可执行工作流机器”

------