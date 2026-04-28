#!/usr/bin/env python3
"""
简化测试 Agent 返回 state patch 规范格式
不依赖外部库
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 模拟必要的类
class State:
    def __init__(self, *args, **kwargs):
        self._data = {}
        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                self._data = args[0].copy()
        if kwargs:
            self._data.update(kwargs)
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self._data[key] = value
    
    def to_plain_dict(self):
        return self._data.copy()
    
    def log(self, msg):
        if "logs" not in self._data:
            self._data["logs"] = []
        self._data["logs"].append(msg)
        return self


class BaseAgent:
    """
    所有Agent必须继承该接口
    输入：state（统一上下文，可以是dict或State对象）
    输出：state patch规范格式
    """
    
    def run(self, state):
        """
        执行Agent逻辑
        
        Args:
            state: 统一上下文，可以是普通字典或State对象
            
        Returns:
            state patch规范格式:
            {
                "state": state,      # 更新后的状态
                "events": [],        # 事件列表
                "status": "ok"       # 执行状态
            }
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError
    
    def _ensure_state(self, state):
        """
        确保输入是State对象
        
        Args:
            state: 输入状态
            
        Returns:
            State对象
        """
        if isinstance(state, State):
            return state
        return State(state)


class SimpleAgentWithPatch(BaseAgent):
    """简单的 Agent，返回规范格式的 state patch"""
    
    def run(self, state):
        # 确保输入是 State 对象
        state_obj = self._ensure_state(state)
        
        # 更新状态
        counter = state_obj.get("counter", 0)
        state_obj["counter"] = counter + 1
        state_obj["processed"] = True
        
        # 返回规范格式
        return {
            "state": state_obj.to_plain_dict(),
            "events": ["counter_incremented"],
            "status": "ok"
        }


class SimpleAgentWithError(BaseAgent):
    """返回错误状态的 Agent"""
    
    def run(self, state):
        # 确保输入是 State 对象
        state_obj = self._ensure_state(state)
        
        # 返回错误状态
        return {
            "state": state_obj.to_plain_dict(),
            "events": [],
            "status": "error",
            "error": "模拟错误"
        }


class LegacyAgent:
    """传统的 Agent（模拟有 execute 方法）"""
    
    def __init__(self, name="legacy_agent"):
        self.name = name
    
    async def execute(self, input_data):
        """执行逻辑"""
        data = input_data.get("data", {})
        counter = data.get("counter", 0)
        
        return {
            "result": {"counter": counter + 2, "legacy": True},
            "metadata": {"executed": True}
        }


class AgentAdapter(BaseAgent):
    """
    Agent 适配器类
    """
    
    def __init__(self, agent):
        """
        初始化适配器
        
        Args:
            agent: 要适配的 Agent 实例（必须有 execute 方法）
        """
        self.agent = agent
        
    def run(self, state):
        """
        执行 Agent 逻辑（适配器方法）
        
        Args:
            state: 统一上下文，可以是普通字典或 State 对象
            
        Returns:
            state patch规范格式:
            {
                "state": state,      # 更新后的状态
                "events": [],        # 事件列表
                "status": "ok"       # 执行状态
            }
        """
        # 确保输入是 State 对象
        state_obj = self._ensure_state(state)
        
        # 从 State 中提取必要信息
        user_id = state_obj.get("user_id", 0)
        trace_id = state_obj.get("trace_id")
        config = state_obj.get("config", {})
        
        # 创建 AgentInput
        agent_input = {
            "data": state_obj.to_plain_dict(),
            "user_id": user_id,
            "trace_id": trace_id,
            "config": config
        }
        
        try:
            # 执行 Agent（同步调用异步方法）
            import asyncio
            output = asyncio.run(self.agent.execute(agent_input))
            
            # 处理输出
            if isinstance(output, dict):
                result = output.get("result", {})
                metadata = output.get("metadata", {})
                
                # 将 result 合并到状态
                if isinstance(result, dict):
                    for key, value in result.items():
                        state_obj[key] = value
                else:
                    # 如果不是字典，将其存储在特定键下
                    state_obj[f"{self.agent.name}_result"] = result
                
                # 合并元数据
                if metadata:
                    state_obj[f"{self.agent.name}_metadata"] = metadata
                
            else:
                # 如果不是字典，直接存储
                state_obj[f"{self.agent.name}_result"] = output
            
            # 记录执行成功
            state_obj.log(f"Agent {self.agent.name} 执行成功")
            state_obj[f"{self.agent.name}_executed"] = True
            
            # 返回规范格式
            return {
                "state": state_obj.to_plain_dict(),
                "events": [],
                "status": "ok"
            }
            
        except Exception as e:
            # 记录错误
            state_obj[f"{self.agent.name}_error"] = str(e)
            state_obj[f"{self.agent.name}_executed"] = False
            state_obj.log(f"Agent {self.agent.name} 执行异常: {e}")
            
            # 返回错误状态的规范格式
            return {
                "state": state_obj.to_plain_dict(),
                "events": [],
                "status": "error",
                "error": str(e)
            }


class MockRegistry:
    """模拟 Agent 注册表"""
    
    _agents = {}
    
    @classmethod
    def clear(cls):
        cls._agents.clear()
    
    @classmethod
    def register(cls, name, agent_factory):
        cls._agents[name] = agent_factory
    
    @classmethod
    def get(cls, name, *args, **kwargs):
        if name not in cls._agents:
            raise KeyError(f"Agent '{name}' not found")
        return cls._agents[name](*args, **kwargs)


class GraphEngine:
    """
    简化的 Graph Engine
    """
    
    def __init__(self, db=None):
        self.db = db
    
    async def run_async(self, graph, state):
        """
        异步执行线性图
        """
        # 获取起始节点
        current_node_id = graph.get("start")
        if not current_node_id:
            raise ValueError("Graph must have a 'start' node")
        
        nodes = graph.get("nodes", {})
        if not nodes:
            raise ValueError("Graph must have at least one node")
        
        # 确保状态是 State 对象
        if not isinstance(state, State):
            state = State(state)
        
        # 线性遍历节点
        while current_node_id:
            node_config = nodes.get(current_node_id)
            if not node_config:
                raise ValueError(f"Node '{current_node_id}' not found in graph")
            
            agent_name = node_config.get("agent")
            if not agent_name or not isinstance(agent_name, str):
                raise ValueError(f"Node '{current_node_id}' must have an 'agent' that is a string (agent name)")
            
            # 使用MockRegistry获取智能体实例
            try:
                agent = MockRegistry.get(agent_name)
            except Exception as e:
                raise ValueError(f"Failed to get agent '{agent_name}' from registry: {e}")
            
            # 执行智能体
            try:
                # 调用 run 方法
                result = agent.run(state)
                
                # 处理规范格式：{"state": state_dict, "events": [], "status": "ok"}
                if isinstance(result, dict) and "state" in result:
                    # 新的规范格式
                    state_dict = result["state"]
                    status = result.get("status", "ok")
                    events = result.get("events", [])
                    
                    # 更新状态
                    state = State(state_dict)
                    
                    # 记录执行状态
                    state[f"{current_node_id}_executed"] = True
                    state[f"{current_node_id}_status"] = status
                    if events:
                        state[f"{current_node_id}_events"] = events
                    state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行成功，状态: {status}")
                    
                    # 如果状态是错误，记录但不抛出
                    if status == "error":
                        error_msg = result.get("error", "Unknown error")
                        state[f"{current_node_id}_error"] = error_msg
                        state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行出错: {error_msg}")
                else:
                    # 兼容旧格式：直接返回状态字典
                    state_dict = result
                    state = State(state_dict)
                    state[f"{current_node_id}_executed"] = True
                    state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行成功（旧格式）")
                
            except Exception as e:
                # 记录错误但继续执行（线性图要求）
                state[f"{current_node_id}_error"] = str(e)
                state[f"{current_node_id}_executed"] = False
                state[f"{current_node_id}_status"] = "error"
                state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行失败: {e}")
            
            # 获取下一个节点
            current_node_id = node_config.get("next")
        
        return state.to_plain_dict()


async def test_base_agent_with_patch():
    """测试 BaseAgent 返回规范格式"""
    print("=== 测试 BaseAgent 返回规范格式 ===")
    
    agent = SimpleAgentWithPatch()
    
    # 测试同步执行
    initial_state = {"counter": 5, "test": "data"}
    result = agent.run(initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"Agent 返回结果: {result}")
    
    # 验证规范格式
    assert isinstance(result, dict), "结果应该是字典"
    assert "state" in result, "结果应该包含 'state' 字段"
    assert "events" in result, "结果应该包含 'events' 字段"
    assert "status" in result, "结果应该包含 'status' 字段"
    assert result["status"] == "ok", "状态应该是 'ok'"
    assert result["state"]["counter"] == 6, "计数器应该增加"
    assert result["state"]["processed"] == True, "应该标记为已处理"
    assert "counter_incremented" in result["events"], "应该包含事件"
    
    print("✓ BaseAgent 规范格式测试通过")


async def test_agent_with_error():
    """测试返回错误状态的 Agent"""
    print("\n=== 测试返回错误状态的 Agent ===")
    
    agent = SimpleAgentWithError()
    
    initial_state = {"counter": 10}
    result = agent.run(initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"Agent 返回结果: {result}")
    
    # 验证错误格式
    assert result["status"] == "error", "状态应该是 'error'"
    assert "error" in result, "应该包含错误信息"
    assert result["error"] == "模拟错误", "错误信息应该正确"
    assert result["state"]["counter"] == 10, "状态应该保持不变"
    
    print("✓ Agent 错误状态测试通过")


async def test_legacy_agent_adaptation():
    """测试传统 Agent 的适配"""
    print("\n=== 测试传统 Agent 的适配 ===")
    
    legacy_agent = LegacyAgent()
    adapter = AgentAdapter(legacy_agent)
    
    initial_state = {"counter": 20, "user_id": 123}
    result = adapter.run(initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"适配器返回结果: {result}")
    
    # 验证适配器返回规范格式
    assert isinstance(result, dict), "结果应该是字典"
    assert "state" in result, "结果应该包含 'state' 字段"
    assert "status" in result, "结果应该包含 'status' 字段"
    assert result["status"] == "ok", "状态应该是 'ok'"
    assert result["state"]["counter"] == 22, "计数器应该增加2"
    assert result["state"]["legacy"] == True, "应该包含 legacy 标记"
    assert result["state"]["legacy_agent_executed"] == True, "应该标记为已执行"
    
    print("✓ 传统 Agent 适配测试通过")


async def test_graph_engine_with_patch():
    """测试 GraphEngine 处理规范格式"""
    print("\n=== 测试 GraphEngine 处理规范格式 ===")
    
    # 注册测试 Agent
    MockRegistry.clear()
    MockRegistry.register("patch_agent", SimpleAgentWithPatch)
    MockRegistry.register("error_agent", SimpleAgentWithError)
    
    # 创建 GraphEngine
    engine = GraphEngine()
    
    # 定义图
    graph = {
        "start": "node1",
        "nodes": {
            "node1": {
                "agent": "patch_agent",
                "next": "node2"
            },
            "node2": {
                "agent": "error_agent",
                "next": "node3"
            },
            "node3": {
                "agent": "patch_agent",
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {"counter": 0, "user_id": 456}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态: {final_state}")
    
    # 验证执行结果
    assert final_state["counter"] == 2, "应该执行了两次 patch_agent"
    assert final_state["node1_executed"] == True, "node1 应该已执行"
    assert final_state["node1_status"] == "ok", "node1 状态应该是 ok"
    assert final_state["node2_executed"] == True, "node2 应该已执行"
    assert final_state["node2_status"] == "error", "node2 状态应该是 error"
    assert "node2_error" in final_state, "node2 应该有错误信息"
    assert final_state["node3_executed"] == True, "node3 应该已执行"
    assert final_state["node3_status"] == "ok", "node3 状态应该是 ok"
    
    print("✓ GraphEngine 规范格式处理测试通过")


async def main():
    """运行所有测试"""
    print("开始测试 Agent 返回 state patch 规范格式...")
    
    try:
        await test_base_agent_with_patch()
        await test_agent_with_error()
        await test_legacy_agent_adaptation()
        await test_graph_engine_with_patch()
        
        print("\n🎉 所有测试通过！Agent 已成功支持返回 state patch 规范格式。")
        print("规范格式: {\"state\": state_dict, \"events\": [], \"status\": \"ok\"}")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)