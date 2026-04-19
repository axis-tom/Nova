"""
测试AgentRegistry集成 - 验证轻量接入改造

测试GraphEngine是否能够通过AgentRegistry.get(name)获取智能体并执行。
"""

import asyncio
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import Agent, AgentInput, AgentOutput
from backend.agents.registry import AgentRegistry
from backend.workflow.graph_engine import GraphEngine
from backend.workflow.agent_wrapper import init_agent_registry


class MockAgent(Agent):
    """测试用的Mock智能体"""
    
    def __init__(self, name="mock_agent", result=None):
        self.name = name
        self.result = result or {"status": "success", "agent": name}
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """模拟执行"""
        return AgentOutput(
            result=self.result,
            metadata={"agent_name": self.name, "executed": True}
        )


async def test_agent_registry_basic():
    """测试AgentRegistry基本功能"""
    print("=== 测试AgentRegistry基本功能 ===")
    
    # 清除之前的注册
    AgentRegistry.clear()
    
    # 注册一个Mock智能体
    AgentRegistry.register("test_agent", MockAgent)
    
    # 获取智能体实例
    agent = AgentRegistry.get("test_agent")
    
    assert isinstance(agent, MockAgent)
    assert agent.name == "mock_agent"
    
    print("✓ AgentRegistry基本功能测试通过")


async def test_agent_registry_with_factory():
    """测试AgentRegistry工厂函数"""
    print("\n=== 测试AgentRegistry工厂函数 ===")
    
    AgentRegistry.clear()
    
    # 注册一个工厂函数
    def create_mock_agent(custom_name="custom"):
        return MockAgent(name=custom_name, result={"custom": True})
    
    AgentRegistry.register("factory_agent", create_mock_agent)
    
    # 获取智能体实例（带参数）
    agent = AgentRegistry.get("factory_agent", "custom_name")
    
    assert isinstance(agent, MockAgent)
    assert agent.name == "custom_name"
    assert agent.result["custom"] == True
    
    print("✓ AgentRegistry工厂函数测试通过")


async def test_graph_engine_with_registry():
    """测试GraphEngine集成AgentRegistry"""
    print("\n=== 测试GraphEngine集成AgentRegistry ===")
    
    # 清除注册表
    AgentRegistry.clear()
    
    # 注册测试智能体
    AgentRegistry.register("agent1", lambda: MockAgent(name="agent1", result={"step1": "done"}))
    AgentRegistry.register("agent2", lambda: MockAgent(name="agent2", result={"step2": "done"}))
    
    # 创建GraphEngine（不需要db参数，因为我们的MockAgent不需要db）
    engine = GraphEngine()
    
    # 创建图定义（使用agent名称）
    graph = {
        "start": "node1",
        "nodes": {
            "node1": {
                "agent": "agent1",  # 使用字符串名称
                "next": "node2"
            },
            "node2": {
                "agent": "agent2",  # 使用字符串名称
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {"user_id": 123, "data": "test"}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态: {final_state}")
    
    # 验证结果
    assert final_state["step1"] == "done"
    assert final_state["step2"] == "done"
    assert final_state["node1_executed"] == True
    assert final_state["node2_executed"] == True
    assert "agent1" in str(final_state.get("node1_metadata", {}))
    assert "agent2" in str(final_state.get("node2_metadata", {}))
    
    print("✓ GraphEngine集成AgentRegistry测试通过")


async def test_email_briefing_registry_integration():
    """测试email → briefing流程的registry集成"""
    print("\n=== 测试email → briefing流程的registry集成 ===")
    
    # 模拟数据库会话
    mock_db = Mock(spec=AsyncSession)
    
    # 初始化AgentRegistry（使用模拟db）
    init_agent_registry(mock_db)
    
    # 验证agent已注册
    assert AgentRegistry.is_registered("email_agent")
    assert AgentRegistry.is_registered("briefing_agent")
    
    print(f"已注册的智能体: {list(AgentRegistry.list_agents().keys())}")
    
    # 创建GraphEngine（传递db参数）
    engine = GraphEngine(db=mock_db)
    
    # 使用daily_graph.py中的图定义
    from backend.sop.daily_graph import GRAPH
    
    # 验证图定义使用字符串名称
    assert GRAPH["nodes"]["email"]["agent"] == "email_agent"
    assert GRAPH["nodes"]["briefing"]["agent"] == "briefing_agent"
    
    print("✓ email → briefing流程的registry集成测试通过（结构验证）")
    
    # 注意：由于实际agent需要真实的数据库连接，这里只做结构验证
    # 实际执行测试需要真实的数据库环境


async def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n=== 测试向后兼容性 ===")
    
    # 验证现有的daily_graph.py仍然有效
    from backend.sop.daily_graph import GRAPH
    
    # 检查图结构
    assert GRAPH["start"] == "email"
    assert "email" in GRAPH["nodes"]
    assert "briefing" in GRAPH["nodes"]
    assert GRAPH["nodes"]["email"]["agent"] == "email_agent"
    assert GRAPH["nodes"]["briefing"]["agent"] == "briefing_agent"
    assert GRAPH["nodes"]["email"]["next"] == "briefing"
    assert GRAPH["nodes"]["briefing"]["next"] is None
    
    print("✓ 向后兼容性测试通过：daily_graph.py结构保持不变")


async def main():
    """运行所有测试"""
    print("开始测试AgentRegistry轻量接入改造...")
    print("=" * 60)
    
    try:
        await test_agent_registry_basic()
        await test_agent_registry_with_factory()
        await test_graph_engine_with_registry()
        await test_email_briefing_registry_integration()
        await test_backward_compatibility()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过！AgentRegistry轻量接入改造成功。")
        print("\n改造总结：")
        print("1. ✅ 修改了AgentRegistry，支持工厂函数和类")
        print("2. ✅ 修改了GraphEngine，使用AgentRegistry.get(name)获取智能体")
        print("3. ✅ 保持了daily_graph.py的结构不变（使用字符串名称）")
        print("4. ✅ 实现了'包一层调用'，不改email_agent和briefing_agent")
        print("5. ✅ 验证了向后兼容性")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)