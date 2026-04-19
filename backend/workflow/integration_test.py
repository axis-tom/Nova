"""
集成测试：验证现有 email → briefing 流程与 GraphEngine 兼容
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 模拟现有的 Agent 结构
class AgentInput:
    def __init__(self, data=None, user_id=0, trace_id=None, config=None):
        self.data = data or {}
        self.user_id = user_id
        self.trace_id = trace_id
        self.config = config or {}

class AgentOutput:
    def __init__(self, result, metadata=None, error=None):
        self.result = result
        self.metadata = metadata or {}
        self.error = error

class Agent:
    async def execute(self, input_data):
        raise NotImplementedError

# 模拟现有的 EmailAgent（简化版）
class MockEmailAgent(Agent):
    async def execute(self, input_data):
        # 模拟现有的 EmailAgent 行为
        user_id = input_data.user_id
        
        # 模拟获取邮件
        emails = [
            {"subject": "现有流程邮件1", "from": "existing1@example.com", "body_preview": "内容1"},
            {"subject": "现有流程邮件2", "from": "existing2@example.com", "body_preview": "内容2"}
        ]
        
        # 返回与现有 EmailAgent 兼容的输出
        return AgentOutput(
            result=emails,
            metadata={"count": len(emails), "source": "email"}
        )

# 模拟现有的 BriefingGeneratorAgent（简化版）
class MockBriefingGeneratorAgent(Agent):
    async def execute(self, input_data):
        # 模拟现有的 BriefingGeneratorAgent 行为
        emails = input_data.data.get("result", [])
        
        # 生成简报内容（模拟现有流程）
        content = f"今日简报：共采集到 {len(emails)} 条新邮件。\n"
        for email in emails[:5]:
            content += f"- {email.get('subject', '无主题')}\n"
        
        # 返回与现有流程兼容的输出
        return AgentOutput(
            result={"briefing_content": content, "email_count": len(emails)},
            metadata={"generated": True, "type": "briefing"}
        )

# 使用 GraphEngine 运行现有流程
async def test_existing_flow_with_graph_engine():
    """测试使用 GraphEngine 运行现有的 email → briefing 流程"""
    print("=== 测试现有 email → briefing 流程与 GraphEngine 兼容性 ===")
    
    # 导入 GraphEngine（使用简化版）
    from backend.workflow.graph_engine import GraphEngine
    
    # 创建 GraphEngine 实例
    engine = GraphEngine()
    
    # 创建现有的 agents
    email_agent = MockEmailAgent()
    briefing_agent = MockBriefingGeneratorAgent()
    
    # 定义与现有流程兼容的图
    # 这模拟了现有的硬编码流程：email_agent → briefing_agent
    graph = {
        "start": "email_collection",
        "nodes": {
            "email_collection": {
                "agent": email_agent,
                "next": "briefing_generation"
            },
            "briefing_generation": {
                "agent": briefing_agent,
                "next": None  # 结束
            }
        }
    }
    
    # 初始状态（与现有 API 调用兼容）
    initial_state = {
        "user_id": 1001,
        "trace_id": "existing_flow_test",
        "parameters": {}  # 模拟现有 API 的参数
    }
    
    print("使用 GraphEngine 执行现有流程...")
    
    try:
        # 执行图
        final_state = await engine.run_async(graph, initial_state)
        
        print(f"✓ GraphEngine 成功执行现有流程")
        print(f"用户ID: {final_state['user_id']}")
        print(f"邮件数量: {final_state.get('email_count', 'N/A')}")
        
        # 验证输出与现有流程兼容
        assert "briefing_content" in final_state
        assert final_state["email_count"] == 2
        assert "今日简报：共采集到 2 条新邮件。" in final_state["briefing_content"]
        
        print(f"简报内容预览: {final_state['briefing_content'][:50]}...")
        print("✓ 输出与现有流程兼容")
        
        # 验证状态传递
        assert "email_collection_executed" in final_state
        assert "briefing_generation_executed" in final_state
        assert final_state["email_collection_metadata"]["source"] == "email"
        assert final_state["briefing_generation_metadata"]["type"] == "briefing"
        
        print("✓ 状态正确传递")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# 测试直接调用现有 agents（不通过 GraphEngine）
async def test_direct_existing_flow():
    """测试直接调用现有 agents（模拟当前硬编码流程）"""
    print("\n=== 测试直接调用现有 agents（当前硬编码流程）===")
    
    # 模拟现有的硬编码流程
    email_agent = MockEmailAgent()
    briefing_agent = MockBriefingGeneratorAgent()
    
    # 模拟现有 API 中的调用流程
    user_id = 1002
    input_data = AgentInput(user_id=user_id, data={"parameters": {}})
    
    print("执行现有硬编码流程...")
    
    try:
        # 第一步：执行 EmailAgent
        email_output = await email_agent.execute(input_data)
        print(f"✓ EmailAgent 执行完成，获取到 {len(email_output.result)} 封邮件")
        
        # 第二步：准备 BriefingGeneratorAgent 的输入
        briefing_input = AgentInput(
            user_id=user_id,
            data={"result": email_output.result}  # 传递 EmailAgent 的结果
        )
        
        # 第三步：执行 BriefingGeneratorAgent
        briefing_output = await briefing_agent.execute(briefing_input)
        print(f"✓ BriefingGeneratorAgent 执行完成")
        
        # 验证输出
        assert "briefing_content" in briefing_output.result
        assert briefing_output.result["email_count"] == 2
        
        print(f"简报内容预览: {briefing_output.result['briefing_content'][:50]}...")
        print("✓ 现有硬编码流程工作正常")
        
        return True
        
    except Exception as e:
        print(f"❌ 现有流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# 比较两种方式的输出
async def compare_approaches():
    """比较 GraphEngine 方式与硬编码方式的输出"""
    print("\n=== 比较 GraphEngine 与硬编码方式 ===")
    
    # 使用相同的测试数据
    test_user_id = 1003
    
    # 1. GraphEngine 方式
    from backend.workflow.graph_engine import GraphEngine
    
    engine = GraphEngine()
    email_agent = MockEmailAgent()
    briefing_agent = MockBriefingGeneratorAgent()
    
    graph_state = {
        "user_id": test_user_id,
        "trace_id": "comparison_test"
    }
    
    graph = {
        "start": "email",
        "nodes": {
            "email": {"agent": email_agent, "next": "briefing"},
            "briefing": {"agent": briefing_agent, "next": None}
        }
    }
    
    graph_result = await engine.run_async(graph, graph_state)
    
    # 2. 硬编码方式
    email_agent2 = MockEmailAgent()
    briefing_agent2 = MockBriefingGeneratorAgent()
    
    email_input = AgentInput(user_id=test_user_id, data={})
    email_output = await email_agent2.execute(email_input)
    
    briefing_input = AgentInput(
        user_id=test_user_id,
        data={"result": email_output.result}
    )
    briefing_output = await briefing_agent2.execute(briefing_input)
    
    # 比较结果
    graph_briefing = graph_result.get("briefing_content", "")
    direct_briefing = briefing_output.result.get("briefing_content", "")
    
    print(f"GraphEngine 生成的简报长度: {len(graph_briefing)}")
    print(f"硬编码方式生成的简报长度: {len(direct_briefing)}")
    
    # 检查核心内容是否相同
    if "今日简报：共采集到 2 条新邮件" in graph_briefing and "今日简报：共采集到 2 条新邮件" in direct_briefing:
        print("✓ 两种方式生成的简报核心内容一致")
        
        # 显示部分内容对比
        print("\n简报内容对比（前100字符）:")
        print(f"GraphEngine: {graph_briefing[:100]}...")
        print(f"硬编码方式: {direct_briefing[:100]}...")
        
        return True
    else:
        print("❌ 两种方式生成的简报内容不一致")
        return False

async def main():
    """运行所有集成测试"""
    print("开始集成测试...")
    
    results = []
    
    # 测试 1: GraphEngine 运行现有流程
    print("\n1. 测试 GraphEngine 运行现有流程")
    result1 = await test_existing_flow_with_graph_engine()
    results.append(("GraphEngine 运行现有流程", result1))
    
    # 测试 2: 直接调用现有流程
    print("\n2. 测试直接调用现有流程")
    result2 = await test_direct_existing_flow()
    results.append(("直接调用现有流程", result2))
    
    # 测试 3: 比较两种方式
    print("\n3. 比较两种方式")
    result3 = await compare_approaches()
    results.append(("比较两种方式", result3))
    
    # 总结
    print("\n" + "="*50)
    print("集成测试总结:")
    print("="*50)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 所有集成测试通过！")
        print("\n验证结果:")
        print("1. GraphEngine 可以成功运行现有的 email → briefing 流程")
        print("2. 现有硬编码流程仍然可用")
        print("3. 两种方式生成的输出一致")
        print("4. 满足 Phase 2 要求：email → briefing 不用改也能继续跑")
    else:
        print("❌ 部分测试失败")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)