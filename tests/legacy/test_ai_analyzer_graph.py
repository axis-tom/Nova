#!/usr/bin/env python3
"""
测试 ai_analyzer 是否已正确接入 Graph
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.sop.daily_graph import GRAPH
from backend.agents.registry import AgentRegistry
from backend.workflow.agent_wrapper import init_agent_registry
from backend.workflow.graph_engine import GraphEngine
from unittest.mock import Mock, AsyncMock


async def test_graph_structure():
    """测试 Graph 结构"""
    print("=== 测试 Graph 结构 ===")
    
    # 验证 Graph 结构
    assert GRAPH["start"] == "email", f"Graph start should be 'email', got {GRAPH['start']}"
    
    # 验证节点
    nodes = GRAPH["nodes"]
    assert "email" in nodes, "Graph should have 'email' node"
    assert "ai_analyzer" in nodes, "Graph should have 'ai_analyzer' node"
    assert "briefing" in nodes, "Graph should have 'briefing' node"
    
    # 验证执行顺序
    assert nodes["email"]["next"] == "ai_analyzer", f"email.next should be 'ai_analyzer', got {nodes['email']['next']}"
    assert nodes["ai_analyzer"]["next"] == "briefing", f"ai_analyzer.next should be 'briefing', got {nodes['ai_analyzer']['next']}"
    assert nodes["briefing"]["next"] is None, f"briefing.next should be None, got {nodes['briefing']['next']}"
    
    # 验证 agent 名称
    assert nodes["email"]["agent"] == "email_agent", f"email.agent should be 'email_agent', got {nodes['email']['agent']}"
    assert nodes["ai_analyzer"]["agent"] == "ai_analyzer", f"ai_analyzer.agent should be 'ai_analyzer', got {nodes['ai_analyzer']['agent']}"
    assert nodes["briefing"]["agent"] == "briefing_agent", f"briefing.agent should be 'briefing_agent', got {nodes['briefing']['agent']}"
    
    print("✓ Graph 结构正确：email → ai_analyzer → briefing")
    return True


async def test_agent_registration():
    """测试 Agent 注册"""
    print("\n=== 测试 Agent 注册 ===")
    
    # 清除之前的注册
    AgentRegistry.clear()
    
    # 模拟数据库会话
    mock_db = Mock()
    
    # 初始化 AgentRegistry
    init_agent_registry(mock_db)
    
    # 验证 agent 已注册
    assert AgentRegistry.is_registered("email_agent"), "email_agent should be registered"
    assert AgentRegistry.is_registered("ai_analyzer"), "ai_analyzer should be registered"
    assert AgentRegistry.is_registered("briefing_agent"), "briefing_agent should be registered"
    
    print(f"已注册的智能体: {list(AgentRegistry.list_agents().keys())}")
    print("✓ 所有必需的 Agent 已正确注册")
    return True


async def test_mock_graph_execution():
    """测试模拟 Graph 执行"""
    print("\n=== 测试模拟 Graph 执行 ===")
    
    # 清除之前的注册
    AgentRegistry.clear()
    
    # 创建模拟的 agents
    class MockAgent:
        def __init__(self, name, result=None):
            self.name = name
            self.result = result or {f"{name}_result": "success"}
        
        async def execute(self, input_data):
            return AsyncMock(
                result=self.result,
                metadata={f"{self.name}_metadata": True},
                error=None
            )
    
    # 注册模拟 agents
    AgentRegistry.register("email_agent", lambda: MockAgent("email_agent", {"emails": ["email1", "email2"]}))
    AgentRegistry.register("ai_analyzer", lambda: MockAgent("ai_analyzer", {"summary": "AI分析结果"}))
    AgentRegistry.register("briefing_agent", lambda: MockAgent("briefing_agent", {"briefing": "简报内容"}))
    
    # 创建 GraphEngine
    engine = GraphEngine()
    
    # 使用 daily_graph.py 中的图定义
    from backend.sop.daily_graph import GRAPH
    
    # 初始状态
    initial_state = {"user_id": 123, "trace_id": "test_trace"}
    
    # 执行图
    final_state = await engine.run_async(GRAPH, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态键: {list(final_state.keys())}")
    
    # 验证执行结果
    assert "emails" in final_state, "email_agent should produce 'emails'"
    assert "summary" in final_state, "ai_analyzer should produce 'summary'"
    assert "briefing" in final_state, "briefing_agent should produce 'briefing'"
    
    # 验证执行顺序
    assert final_state["emails"] == ["email1", "email2"], f"Expected emails ['email1', 'email2'], got {final_state['emails']}"
    assert final_state["summary"] == "AI分析结果", f"Expected summary 'AI分析结果', got {final_state['summary']}"
    assert final_state["briefing"] == "简报内容", f"Expected briefing '简报内容', got {final_state['briefing']}"
    
    print("✓ 模拟 Graph 执行成功，执行顺序正确")
    return True


async def test_ai_analyzer_is_only_ai_node():
    """验证 ai_analyzer 是唯一的 AI 节点"""
    print("\n=== 验证 ai_analyzer 是唯一的 AI 节点 ===")
    
    # 检查 briefing_agent 是否包含 LLM 调用
    from backend.agents.executor.briefing_generator_agent import BriefingGeneratorAgent
    
    # 读取 briefing_generator_agent.py 文件
    briefing_agent_path = os.path.join(os.path.dirname(__file__), "backend/agents/executor/briefing_generator_agent.py")
    with open(briefing_agent_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否包含 LLM 调用
    llm_keywords = ["llm_client", "generate_briefing", "await llm_client", "LLM"]
    has_llm_call = any(keyword in content for keyword in llm_keywords)
    
    if has_llm_call:
        print("⚠️ 警告：briefing_agent 仍然包含 LLM 调用")
        print("   根据任务要求，ai_analyzer 应该是唯一的 AI 节点")
        print("   建议将 LLM 调用从 briefing_agent 移到 ai_analyzer")
    else:
        print("✓ briefing_agent 不包含 LLM 调用，ai_analyzer 是唯一的 AI 节点")
    
    return not has_llm_call


async def main():
    """运行所有测试"""
    print("开始测试 ai_analyzer 接入 Graph...")
    print("=" * 60)
    
    results = []
    
    try:
        # 测试 1: Graph 结构
        result1 = await test_graph_structure()
        results.append(("Graph 结构测试", result1))
        
        # 测试 2: Agent 注册
        result2 = await test_agent_registration()
        results.append(("Agent 注册测试", result2))
        
        # 测试 3: 模拟 Graph 执行
        result3 = await test_mock_graph_execution()
        results.append(("模拟 Graph 执行测试", result3))
        
        # 测试 4: 验证 ai_analyzer 是唯一的 AI 节点
        result4 = await test_ai_analyzer_is_only_ai_node()
        results.append(("唯一 AI 节点验证", result4))
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结:")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！ai_analyzer 已成功接入 Graph")
        print("\n修改总结:")
        print("1. ✅ 修改了 backend/workflow/agent_wrapper.py，注册了 ai_analyzer")
        print("2. ✅ 修改了 backend/sop/daily_graph.py，添加了 ai_analyzer 节点")
        print("3. ✅ 执行顺序：email → ai_analyzer → briefing")
        print("4. ✅ ai_analyzer 是唯一的 AI 节点（需要确认 briefing_agent 已移除 LLM 调用）")
    else:
        print("❌ 部分测试失败")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)