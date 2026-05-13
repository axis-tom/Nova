# VOE事件交互层 (VOE Event Interaction Layer)

## 🎯 概述

VOE（Visual Orchestration Engine）事件交互层是一个解耦的事件驱动架构，实现了 **UI操作 → eventBus → dispatcher → graph → result** 的完整通信链路。

## 📁 文件结构

```
src/workspace/voe/
├── index.js                    # 主入口文件
├── eventBus.js                 # 全局事件总线
├── eventTypes.js               # 事件常量中心
├── dispatcher.js               # 事件调度中心
├── bridge/
│   ├── uiBridge.js            # UI → 事件转换
│   ├── graphBridge.js         # 事件 → Graph指令
│   └── resultBridge.js        # Graph → UI结果
├── listeners/
│   ├── nodeListener.js        # 节点事件监听器
│   ├── uiListener.js          # UI事件监听器
│   └── graphListener.js       # Graph事件监听器
├── utils/
│   └── helpers.js             # 工具函数
├── test-voe-system.js         # 测试文件
├── integration-example.js      # 集成示例
└── README.md                  # 本文档
```

## 🚀 快速开始

### 1. 安装和导入

```javascript
// 导入整个VOE系统
import { initializeVOESystem, getVOEStatus } from '@/workspace/voe'

// 或按需导入特定模块
import { eventBus, uiBridge, graphBridge, resultBridge } from '@/workspace/voe'
import * as eventTypes from '@/workspace/voe/eventTypes'
```

### 2. 初始化系统

```javascript
// 初始化整个VOE系统
async function initApp() {
  try {
    const voeSystem = await initializeVOESystem()
    console.log('VOE系统初始化成功')
    
    // 检查系统状态
    const status = getVOEStatus()
    console.log('系统状态:', status)
  } catch (error) {
    console.error('VOE系统初始化失败:', error)
  }
}
```

### 3. 基本使用

```javascript
// 触发UI操作
uiBridge.handleClickNode({
  id: 'node-1',
  type: 'analysis',
  label: '分析节点'
})

// 监听事件
const unsubscribe = eventBus.on(eventTypes.NODE_SELECT, (payload) => {
  console.log('节点被选择:', payload)
})

// 发射自定义事件
eventBus.emit('CUSTOM_EVENT', { data: '自定义数据' })

// 取消监听
unsubscribe()
```

## 🔄 标准事件流

### UI点击节点流程
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

### Graph执行流程
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

### 结果修改触发重算
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

## 🧩 核心模块

### 1. EventBus (事件总线)
- **功能**: 轻量级发布订阅系统
- **方法**: `on(event, callback)`, `emit(event, payload)`, `off(event)`
- **特点**: 单例模式，无业务逻辑

### 2. EventTypes (事件常量)
- 定义所有系统事件常量
- 包括: `UI_ACTION`, `NODE_SELECT`, `NODE_UPDATE`, `NODE_RUN`, `GRAPH_START`, `GRAPH_PROGRESS`, `GRAPH_FINISH`, `RESULT_UPDATE`, `RESULT_RENDER`

### 3. Dispatcher (调度中心)
- **功能**: 事件路由分发器
- **逻辑**: `eventBus.emit → dispatcher → 判断事件类型 → 转发到 bridge`
- **禁止**: 直接调用core graph，直接操作DOM

### 4. Bridges (桥接器)
- **UIBridge**: UI操作标准化为事件
- **GraphBridge**: 事件转换为graph指令
- **ResultBridge**: graph输出转换为UI结果

### 5. Listeners (监听器)
- **NodeListener**: 监听节点相关事件
- **UIListener**: 监听UI操作事件
- **GraphListener**: 监听graph执行状态

## ⚠️ 强约束规则

1. **禁止直接修改 graph/core**
2. **禁止组件直接互相调用**
3. **所有通信必须经过 eventBus**
4. **dispatcher 是唯一控制入口**
5. **bridge 只做数据转换，不写业务逻辑**

## 🚫 禁止直接依赖关系

```
❌ UI → core
❌ Graph → UI
❌ result → graph
❌ component → component
```

## 📋 集成指南

### Vue组件集成

```javascript
// 在Vue组件中使用
export default {
  data() {
    return {
      voeInitialized: false
    }
  },
  
  async mounted() {
    await initializeVOESystem()
    this.voeInitialized = true
    
    // 监听事件
    eventBus.on('NODE_SELECT', this.handleNodeSelect)
  },
  
  methods: {
    handleNodeClick(node) {
      uiBridge.handleClickNode(node)
    },
    
    handleNodeSelect(payload) {
      console.log('节点选择:', payload)
    }
  },
  
  beforeUnmount() {
    // 清理监听器
  }
}
```

### React组件集成

```javascript
// React Hook示例
import { useState, useEffect } from 'react'
import { initializeVOESystem, uiBridge, eventBus } from '@/workspace/voe'

function useVOEIntegration() {
  const [initialized, setInitialized] = useState(false)
  
  useEffect(() => {
    const init = async () => {
      await initializeVOESystem()
      setInitialized(true)
    }
    
    init()
    
    // 监听事件
    const unsubscribe = eventBus.on('RESULT_UPDATE', handleResultUpdate)
    
    return () => {
      unsubscribe()
    }
  }, [])
  
  return {
    initialized,
    handleNodeClick: uiBridge.handleClickNode,
    handleTaskSubmit: uiBridge.handleTaskSubmit
  }
}
```

## 🧪 测试

### 运行测试

```bash
# 运行简单测试
node test-voe-system.js

# 运行完整测试
node test-voe-system.js full
```

### 测试内容
1. 系统初始化
2. 事件总线功能
3. UI Bridge功能
4. 节点运行
5. Graph开始
6. 事件流完整性

## 🎯 验收标准

完成后的系统必须满足：

- ✅ UI点击节点 → Graph能执行
- ✅ Graph执行 → Result自动更新
- ✅ Result修改 → 能触发重新执行
- ✅ 全流程无组件直接耦合

## 🚀 S4完成后系统能力

完成后系统变成：**"可编排AI工作流系统（事件驱动版）"**

**能力包括：**
- UI驱动AI执行
- Graph状态实时反馈
- Result可反向影响Graph
- 全系统解耦

## 🔧 工具函数

`utils/helpers.js` 提供以下工具函数：

- `generateId()` - 生成唯一ID
- `validateEventData()` - 验证事件数据格式
- `normalizeEventData()` - 标准化事件数据
- `safeExecute()` - 安全执行函数
- `debounce()` / `throttle()` - 防抖和节流
- `deepMerge()` - 深度合并对象
- `createEventTracker()` - 创建事件追踪器

## 📝 事件数据格式

### 标准事件格式
```javascript
{
  eventType: '事件类型',
  timestamp: 时间戳,
  source: '事件来源',
  eventId: '唯一ID',
  // 其他自定义数据
  data: { ... }
}
```

### 节点选择事件示例
```javascript
{
  eventType: 'NODE_SELECT',
  nodeId: 'node-123',
  nodeType: 'analysis',
  nodeLabel: '数据分析',
  timestamp: 1640995200000,
  source: 'ui-click'
}
```

## 🐛 故障排除

### 常见问题

1. **事件未触发**
   - 检查事件类型是否正确
   - 确认监听器已正确注册
   - 检查事件数据格式

2. **系统未初始化**
   - 确保调用 `initializeVOESystem()`
   - 检查初始化错误信息

3. **组件间通信失败**
   - 确认所有通信都通过eventBus
   - 检查dispatcher是否正确路由

### 调试技巧

```javascript
// 启用事件日志
import { eventBus } from '@/workspace/voe'

// 监听所有事件
eventBus.on('*', (eventType, payload) => {
  console.log(`[VOE Debug] ${eventType}:`, payload)
})

// 检查系统状态
import { getVOEStatus } from '@/workspace/voe'
console.log('VOE状态:', getVOEStatus())
```

## 📚 相关文档

- [S4施工指令](./🧠 S4｜VOE事件交互层（DeepSeek施工指令版）.md)
- [前端系统分层规划](../frontend_plan/📘 Nova 前端系统分层切片规划（Slice Map）.md)
- [Graph执行引擎](../core/graph/README.md)

## 🏗️ 架构图

```
┌─────────┐    ┌──────────┐    ┌─────────────┐    ┌──────────┐
│   UI    │───▶│ UIBridge │───▶│  EventBus   │───▶│Dispatcher│
└─────────┘    └──────────┘    └─────────────┘    └──────────┘
                                                    │    │
┌─────────┐    ┌──────────┐    ┌─────────────┐    │    │    ┌──────────┐
│ Result  │◀───│ResultBridge│◀──│GraphListener│◀───┘    └───▶│GraphBridge│
└─────────┘    └──────────┘    └─────────────┘              └──────────┘
                                                    │              │
                                              ┌─────┴─────┐        │
                                              │NodeListener│        │
                                              └───────────┘        │
                                                                   │
                                                            ┌──────┴──────┐
                                                            │  Core Graph │
                                                            │   Engine    │
                                                            └─────────────┘
```

## 📞 支持

如有问题，请参考：
1. 检查本文档的"故障排除"部分
2. 查看测试文件中的示例
3. 检查事件流是否符合标准流程
4. 确保遵守所有强约束规则