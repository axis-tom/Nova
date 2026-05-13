# F5 系统基线锁定文档

## 概述
本文档记录了Nova系统的F5稳定基线状态，用于冻结当前系统行为，防止结构性漂移。

**基线版本**: v1.0-stable  
**锁定时间**: 2026-04-19  
**目标**: 确保Graph + Agent + API + Trace系统行为可预测、可回放、可调试

## 1. Graph执行结构（已冻结）

### 1.1 Graph引擎架构
当前系统使用两种Graph引擎实现：

1. **GraphEngineV2** (backend/workflow/graph_engine.py)
   - 支持 `state = agent.run(state)` 统一接口
   - 自动适配现有的 `Agent.execute(AgentInput)` 接口
   - 支持同步和异步执行
   - 使用State对象进行状态管理

2. **GraphEngine** (状态驱动版)
   - Graph不再处理data，只负责"调度"
   - 数据全部交给State对象管理
   - 使用 `state.add_event()` 追踪执行路径

### 1.2 Graph定义格式（固定）
```json
{
  "start": "node_id",
  "nodes": {
    "node_id": {
      "agent": "agent_name",
      "next": "next_node_id"
    }
  }
}
```

### 1.3 执行流程（禁止动态修改）
1. 获取起始节点
2. 线性遍历节点（禁止运行时变更节点顺序）
3. 从AgentRegistry获取智能体实例
4. 执行智能体：`state = agent.run(state)`
5. 记录执行状态和事件
6. 移动到下一个节点

## 2. Agent类型与职责定义（已标记为v1 stable）

### 2.1 核心Agent（v1 stable）
| Agent名称 | 类型 | 职责 | 状态 |
|-----------|------|------|------|
| email_agent | Collector | 邮件数据采集 | v1-stable |
| briefing_agent | Executor | 简报生成 | v1-stable |
| ai_analyzer | Executor | AI分析 | v1-stable |

### 2.2 电商Agent（v1 stable）
| Agent名称 | 类型 | 职责 | 状态 |
|-----------|------|------|------|
| planner | Planner | 任务规划 | v1-stable |
| analyst | Analyst | 市场分析 | v1-stable |
| executor | Executor | 外部API执行 | v1-stable |
| judge | Judge | 执行评估 | v1-stable |
| memory | Memory | 执行记忆 | v1-stable |

### 2.3 Agent接口规范（已固定）
所有Agent必须实现以下接口之一：
1. **统一接口**: `run(state: State) -> State`
2. **传统接口**: `execute(input: AgentInput) -> AgentOutput`
3. **异步接口**: `run_async(state: State) -> State`

## 3. Agent注册表（已冻结）

### 3.1 注册机制
- 使用 `AgentRegistry.register(name, agent_or_factory)` 注册
- 支持类注册和工厂函数注册
- 通过 `AgentRegistry.get(name, *args, **kwargs)` 获取实例

### 3.2 当前注册的Agent（基线版本）
```python
# 在backend/workflow/agent_wrapper.py中注册
AgentRegistry.register("email_agent", email_factory)
AgentRegistry.register("briefing_agent", briefing_factory)
AgentRegistry.register("ai_analyzer", ai_analyzer_factory)
```

## 4. 状态管理（已固定）

### 4.1 State对象
- 位置: `backend/core/state.py`
- 功能: 统一的状态容器
- 方法: `add_event()`, `to_plain_dict()`, `log()`

### 4.2 状态流转规范
```
初始状态 → Graph调度 → Agent执行 → 更新状态 → 下一个Agent
```

## 5. 执行追踪（已固定）

### 5.1 事件追踪
- 使用 `state.add_event(event_name)` 记录执行路径
- 每个节点执行后记录 `{node}_executed`, `{node}_status`, `{node}_events`

### 5.2 错误处理
- 错误不中断Graph执行
- 记录错误信息到状态：`{node}_error`
- 继续执行下一个节点

## 6. 系统约束（禁止修改）

### 6.1 禁止行为
❌ 不允许新增业务逻辑  
❌ 不允许优化流程  
❌ 不允许重构Graph结构  
❌ 不允许动态if分支控制流程  
❌ 不允许Agent内部跳流程  
❌ 不允许Agent修改Graph flow

### 6.2 必须遵守
✅ 同样input → 同样path  
✅ 不允许runtime变更节点顺序  
✅ Agent职责边界明确  
✅ Graph结构可描述成一张固定图

## 7. 基线验证标准

### 7.1 当前系统运行流程不再变化
- [x] Graph执行路径固定
- [x] Agent调用顺序固定
- [x] 状态流转路径固定

### 7.2 所有Agent有明确职责边界文档
- [x] email_agent: 邮件数据采集
- [x] briefing_agent: 简报生成
- [x] ai_analyzer: AI分析
- [x] planner: 任务规划
- [x] analyst: 市场分析
- [x] executor: 外部API执行
- [x] judge: 执行评估
- [x] memory: 执行记忆

### 7.3 Graph结构可描述成一张固定图
- [x] 线性图结构
- [x] 节点定义固定
- [x] 流转路径固定

## 8. 测试验证

### 8.1 确定性测试
```python
# 同一输入运行3次 → path完全一致
for i in range(3):
    result = graph_engine.run(graph, input_state)
    assert result["execution_path"] == expected_path
```

### 8.2 可回放测试
```python
# Graph执行日志可复现路径
execution_log = state.get("execution_events")
replay_result = replay_from_log(execution_log)
assert replay_result == original_result
```

## 9. 变更控制

### 9.1 基线锁定后
- 任何对Graph结构、Agent接口、执行流程的修改必须经过F5变更评审
- 修改必须创建新版本（v2, v3等），保持v1-stable不变
- 所有修改必须更新本文档

### 9.2 版本管理
- v1-stable: 当前基线版本（已锁定）
- v2-dev: 开发中的新版本
- 版本切换必须通过配置开关控制

## 10. 附录

### 10.1 文件清单
```
backend/workflow/graph_engine.py          # Graph引擎实现
backend/agents/registry.py                # Agent注册表
backend/workflow/agent_wrapper.py         # Agent注册初始化
backend/core/state.py                     # 状态管理
backend/agents/base.py                    # Agent基类
backend/agents/standard_base.py           # 标准Agent基类
```

### 10.2 测试文件
```
test_ecommerce_graph.py                   # 电商Graph测试
test_graph_engine.py                      # Graph引擎测试
test_state_flow.py                        # 状态流转测试
```

---

**基线锁定确认**: ✅ 已完成  
**锁定责任人**: Nova F5稳定系统  
**下次评审时间**: 2026-05-19