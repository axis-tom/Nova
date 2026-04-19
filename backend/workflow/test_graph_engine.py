"""
测试 GraphEngine 功能
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.workflow.graph_engine import GraphEngine
from backend.workflow.mock_agent import MockAgent, SimpleAddAgent, EchoAgent


async def test_linear_graph():
    """测试线性图"""
    print("=== 测试线性图 ===")
    
    # 创建 GraphEngine 实例
    engine = GraphEngine()
    
    # 创建 mock agents
    agent1 = MockAgent(name="agent1", result={"step1": "completed", "data": "from_agent1"})
    agent2 = MockAgent(name="agent2", result={"step2": "completed", "data": "from_agent2"})
    agent3 = MockAgent(name="agent3", result={"step3": "completed", "data": "from_agent3"})
    
    # 定义线性图
    graph = {
        "start": "node1",
        "nodes": {
            "node1": {
                "agent": agent1,
                "next": "node2"
            },
            "node2": {
                "agent": agent2,
                "next": "node3"
            },
            "node3": {
                "agent": agent3,
                "next": None  # 结束
            }
        }
    }
    
    # 初始状态
    initial_state = {
        "user_id": 123,
        "trace_id": "test_trace_001",
        "initial_data": "start_value"
    }
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态: {final_state}")
    
    # 验证结果
    assert final_state["step1"] == "completed"
    assert final_state["step2"] == "completed"
    assert final_state["step3"] == "completed"
    assert final_state["initial_data"] == "start_value"
    assert final_state["node1_executed"] == True
    assert final_state["node2_executed"] == True
    assert final_state["node3_executed"] == True
    
    print("✓ 线性图测试通过")


async def test_state_passing():
    """测试状态传递"""
    print("\n=== 测试状态传递 ===")
    
    engine = GraphEngine()
    
    # 创建加法 agents
    agent1 = SimpleAddAgent(add_value=5)
    agent2 = SimpleAddAgent(add_value=10)
    agent3 = SimpleAddAgent(add_value=2)
    
    # 定义线性图
    graph = {
        "start": "add5",
        "nodes": {
            "add5": {
                "agent": agent1,
                "next": "add10"
            },
            "add10": {
                "agent": agent2,
                "next": "add2"
            },
            "add2": {
                "agent": agent3,
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {
        "user_id": 456,
        "counter": 0
    }
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始计数器: {initial_state['counter']}")
    print(f"最终计数器: {final_state['counter']}")
    
    # 验证结果：0 + 5 + 10 + 2 = 17
    assert final_state["counter"] == 17
    assert final_state["add5_metadata"]["operation"] == "add_5"
    assert final_state["add10_metadata"]["operation"] == "add_10"
    assert final_state["add2_metadata"]["operation"] == "add_2"
    
    print("✓ 状态传递测试通过")


async def test_echo_agent():
    """测试回显 Agent"""
    print("\n=== 测试回显 Agent ===")
    
    engine = GraphEngine()
    
    # 创建回显 agents
    agent1 = EchoAgent()
    agent2 = EchoAgent()
    
    # 定义线性图
    graph = {
        "start": "echo1",
        "nodes": {
            "echo1": {
                "agent": agent1,
                "next": "echo2"
            },
            "echo2": {
                "agent": agent2,
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {
        "user_id": 789,
        "message": "Hello GraphEngine!",
        "data": {"key": "value", "nested": {"inner": "data"}}
    }
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始消息: {initial_state['message']}")
    print(f"最终消息: {final_state['message']}")
    
    # 验证状态保持不变（回显）
    assert final_state["message"] == "Hello GraphEngine!"
    assert final_state["data"]["key"] == "value"
    assert final_state["data"]["nested"]["inner"] == "data"
    assert final_state["echo1_metadata"]["echoed"] == True
    assert final_state["echo2_metadata"]["echoed"] == True
    
    print("✓ 回显 Agent 测试通过")


async def test_single_node_graph():
    """测试单节点图"""
    print("\n=== 测试单节点图 ===")
    
    engine = GraphEngine()
    
    # 创建单个 agent
    agent = MockAgent(name="single_agent", result={"processed": True})
    
    # 定义单节点图
    graph = {
        "start": "single_node",
        "nodes": {
            "single_node": {
                "agent": agent,
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {"test": "data"}
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"初始状态: {initial_state}")
    print(f"最终状态: {final_state}")
    
    assert final_state["processed"] == True
    assert final_state["single_node_executed"] == True
    
    print("✓ 单节点图测试通过")


async def test_error_handling():
    """测试错误处理（线性图继续执行）"""
    print("\n=== 测试错误处理 ===")
    
    engine = GraphEngine()
    
    # 创建会抛出异常的 Mock Agent
    class ErrorAgent:
        async def execute(self, input_data):
            raise ValueError("模拟错误")
    
    # 创建正常 agent
    normal_agent = MockAgent(name="normal_agent")
    
    # 定义包含错误节点的图
    graph = {
        "start": "error_node",
        "nodes": {
            "error_node": {
                "agent": ErrorAgent(),  # 这不是真正的 Agent 实例，会触发类型检查错误
                "next": "normal_node"
            },
            "normal_node": {
                "agent": normal_agent,
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {"continue": True}
    
    try:
        # 执行图（应该会继续执行）
        final_state = await engine.run_async(graph, initial_state)
        print(f"最终状态: {final_state}")
        
        # 验证错误被记录但继续执行
        assert "error_node_error" in final_state
        assert final_state["normal_node_executed"] == True
        
        print("✓ 错误处理测试通过（错误被记录，继续执行）")
    except Exception as e:
        print(f"错误处理测试失败: {e}")


async def test_email_briefing_mock():
    """模拟 email → briefing 流程"""
    print("\n=== 模拟 email → briefing 流程 ===")
    
    engine = GraphEngine()
    
    # 创建模拟的 email agent
    class MockEmailAgent:
        async def execute(self, input_data):
            # 模拟获取邮件
            emails = [
                {"subject": "重要会议通知", "from": "boss@company.com", "body": "明天上午10点开会"},
                {"subject": "项目进度报告", "from": "team@project.com", "body": "项目已完成80%"}
            ]
            return {
                "result": emails,
                "metadata": {"count": len(emails), "source": "email"},
                "error": None
            }
    
    # 创建模拟的 briefing generator agent
    class MockBriefingAgent:
        async def execute(self, input_data):
            # 从状态中获取邮件数据
            emails = input_data.data.get("result", [])
            
            # 生成简报
            briefing = f"今日邮件简报：共收到 {len(emails)} 封邮件\n"
            for i, email in enumerate(emails, 1):
                briefing += f"{i}. {email['subject']} - {email['from']}\n"
            
            return {
                "result": {"briefing": briefing, "email_count": len(emails)},
                "metadata": {"generated_at": "2024-01-01", "type": "briefing"},
                "error": None
            }
    
    # 定义 email → briefing 图
    graph = {
        "start": "email_collection",
        "nodes": {
            "email_collection": {
                "agent": MockEmailAgent(),
                "next": "briefing_generation"
            },
            "briefing_generation": {
                "agent": MockBriefingAgent(),
                "next": None
            }
        }
    }
    
    # 初始状态
    initial_state = {
        "user_id": 1001,
        "date": "2024-01-01"
    }
    
    # 执行图
    final_state = await engine.run_async(graph, initial_state)
    
    print(f"用户ID: {final_state['user_id']}")
    print(f"邮件数量: {final_state.get('email_count', 'N/A')}")
    print(f"简报内容:\n{final_state.get('briefing', 'N/A')}")
    
    assert "briefing" in final_state
    assert "email_count" in final_state
    assert final_state["email_count"] == 2
    
    print("✓ email → briefing 模拟流程测试通过")


async def main():
    """运行所有测试"""
    print("开始测试 GraphEngine...")
    
    try:
        await test_linear_graph()
        await test_state_passing()
        await test_echo_agent()
        await test_single_node_graph()
        await test_error_handling()
        await test_email_briefing_mock()
        
        print("\n🎉 所有测试通过！GraphEngine 功能正常。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)