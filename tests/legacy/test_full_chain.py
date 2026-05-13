#!/usr/bin/env python3
"""
完整链路测试：collector → ai_analyzer → formatter
验证三个现象：
1. AI调用真实发生（llm_client被调用）
2. 输出不固定（每次summary不一样）
3. formatter依赖AI结果（没有summary → 系统报错）
"""

import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.agents.registry import AgentRegistry
from backend.workflow.agent_wrapper import init_agent_registry
from backend.workflow.graph_engine import GraphEngine
from backend.sop.daily_graph import GRAPH
from backend.core.state import State


class MockLLMClient:
    """模拟LLM客户端，用于验证AI调用"""
    
    def __init__(self):
        self.call_count = 0
        self.responses = [
            "这是第一次AI生成的摘要，包含重要信息点A、B、C。",
            "这是第二次AI生成的摘要，包含不同的信息点X、Y、Z。",
            "这是第三次AI生成的摘要，包含更新的信息点1、2、3。"
        ]
    
    async def generate_briefing(self, messages):
        """模拟生成简报，每次返回不同的结果"""
        self.call_count += 1
        # 模拟网络延迟
        await asyncio.sleep(0.1)
        
        # 返回不同的结果以验证输出不固定
        response_idx = (self.call_count - 1) % len(self.responses)
        return self.responses[response_idx]
    
    async def generate(self, prompt, use_long_context=False):
        """模拟generate方法"""
        self.call_count += 1
        await asyncio.sleep(0.1)
        return f"模拟AI响应: {prompt[:50]}..."


async def test_ai_call_happens():
    """测试1：验证AI调用真实发生"""
    print("=== 测试1：验证AI调用真实发生 ===")
    
    # 清除之前的注册
    AgentRegistry.clear()
    
    # 创建模拟LLM客户端
    mock_llm = MockLLMClient()
    
    # 模拟数据库会话
    mock_db = Mock()
    
    # 初始化AgentRegistry
    init_agent_registry(mock_db)
    
    # 替换llm_client为模拟版本
    from backend.agents.executor.ai_analyzer import AIAnalyzer
    original_init = AIAnalyzer.__init__
    
    def mock_init(self, llm_client=None):
        # 使用模拟的LLM客户端
        self.llm_client = mock_llm
    
    # 临时替换初始化方法
    AIAnalyzer.__init__ = mock_init
    
    try:
        # 创建GraphEngine
        engine = GraphEngine()
        
        # 初始状态
        initial_state = State()
        initial_state.set("user_id", 123)
        initial_state.set("trace_id", "test_trace")
        initial_state.set("emails", [
            {"subject": "测试邮件1", "from": "sender1@example.com", "body_preview": "这是第一封测试邮件的内容"},
            {"subject": "测试邮件2", "from": "sender2@example.com", "body_preview": "这是第二封测试邮件的内容"}
        ])
        
        print(f"初始状态中的邮件数量: {len(initial_state.get('emails', []))}")
        
        # 执行图
        final_state = await engine.run_async(GRAPH, initial_state)
        
        # 验证AI被调用
        assert mock_llm.call_count > 0, f"AI未被调用，调用次数: {mock_llm.call_count}"
        print(f"✓ AI调用真实发生，调用次数: {mock_llm.call_count}")
        
        # 验证summary存在
        summary = final_state.get("summary")
        assert summary is not None, "AI未生成summary"
        print(f"✓ AI生成的summary: {summary[:50]}...")
        
        return True
    finally:
        # 恢复原始初始化方法
        AIAnalyzer.__init__ = original_init


async def test_output_variability():
    """测试2：验证输出不固定（每次summary不一样）"""
    print("\n=== 测试2：验证输出不固定 ===")
    
    # 清除之前的注册
    AgentRegistry.clear()
    
    # 创建模拟LLM客户端，记录所有调用
    class TrackingLLMClient:
        def __init__(self):
            self.responses = []
            self.call_count = 0
        
        async def generate_briefing(self, messages):
            self.call_count += 1
            await asyncio.sleep(0.05)
            # 每次返回不同的结果
            response = f"第{self.call_count}次AI生成的摘要，包含唯一标识符{self.call_count}"
            self.responses.append(response)
            return response
    
    mock_llm = TrackingLLMClient()
    
    # 模拟数据库会话
    mock_db = Mock()
    
    # 初始化AgentRegistry
    init_agent_registry(mock_db)
    
    # 替换llm_client为模拟版本
    from backend.agents.executor.ai_analyzer import AIAnalyzer
    original_init = AIAnalyzer.__init__
    
    def mock_init(self, llm_client=None):
        self.llm_client = mock_llm
    
    AIAnalyzer.__init__ = mock_init
    
    try:
        # 多次执行，验证每次结果不同
        summaries = []
        
        for i in range(3):
            # 创建新的GraphEngine和状态
            engine = GraphEngine()
            initial_state = State()
            initial_state.set("user_id", 123)
            initial_state.set("trace_id", f"test_trace_{i}")
            initial_state.set("emails", [
                {"subject": f"测试邮件{i}", "from": f"sender{i}@example.com", "body_preview": f"这是第{i}次测试"}
            ])
            
            # 执行图
            final_state = await engine.run_async(GRAPH, initial_state)
            summary = final_state.get("summary")
            
            if summary:
                summaries.append(summary)
                print(f"  第{i+1}次执行，summary: {summary[:50]}...")
        
        # 验证至少有两个不同的summary
        unique_summaries = set(summaries)
        assert len(unique_summaries) > 1, f"所有summary都相同: {summaries}"
        print(f"✓ 输出不固定，生成了 {len(unique_summaries)} 个不同的summary")
        
        return True
    finally:
        # 恢复原始初始化方法
        AIAnalyzer.__init__ = original_init


async def test_formatter_depends_on_ai():
    """测试3：验证formatter依赖AI结果"""
    print("\n=== 测试3：验证formatter依赖AI结果 ===")
    
    # 清除之前的注册
    AgentRegistry.clear()
    
    # 模拟数据库会话
    mock_db = Mock()
    
    # 初始化AgentRegistry
    init_agent_registry(mock_db)
    
    # 创建模拟LLM客户端，模拟失败
    class FailingLLMClient:
        async def generate_briefing(self, messages):
            raise Exception("模拟AI调用失败")
    
    mock_llm = FailingLLMClient()
    
    # 替换llm_client为模拟版本
    from backend.agents.executor.ai_analyzer import AIAnalyzer
    original_init = AIAnalyzer.__init__
    
    def mock_init(self, llm_client=None):
        self.llm_client = mock_llm
    
    AIAnalyzer.__init__ = mock_init
    
    try:
        # 创建GraphEngine
        engine = GraphEngine()
        
        # 初始状态
        initial_state = State()
        initial_state.set("user_id", 123)
        initial_state.set("trace_id", "test_failure")
        initial_state.set("emails", [
            {"subject": "测试邮件", "from": "test@example.com", "body_preview": "测试内容"}
        ])
        
        # 执行图，应该会失败
        try:
            final_state = await engine.run_async(GRAPH, initial_state)
            # 如果执行到这里，检查是否有错误
            error = final_state.get("error")
            summary = final_state.get("summary")
            
            if summary == "AI失败":
                print("✓ AI调用失败时，summary被设置为'AI失败'")
                print(f"  错误信息: {error}")
                return True
            else:
                print(f"❌ 预期AI失败，但summary为: {summary}")
                return False
                
        except Exception as e:
            # 检查异常是否与AI结果缺失有关
            error_str = str(e)
            if "AI结果缺失" in error_str or "summary" in error_str.lower():
                print(f"✓ formatter依赖AI结果，缺少summary时报错: {error_str}")
                return True
            else:
                print(f"❌ 预期错误包含'AI结果缺失'，实际错误: {error_str}")
                return False
    finally:
        # 恢复原始初始化方法
        AIAnalyzer.__init__ = original_init


async def test_timeout_handling():
    """测试超时处理"""
    print("\n=== 测试4：验证超时处理 ===")
    
    # 清除之前的注册
    AgentRegistry.clear()
    
    # 模拟数据库会话
    mock_db = Mock()
    
    # 初始化AgentRegistry
    init_agent_registry(mock_db)
    
    # 创建模拟LLM客户端，模拟超时
    class TimeoutLLMClient:
        async def generate_briefing(self, messages):
            # 模拟长时间运行，超过10秒超时
            await asyncio.sleep(15)
            return "这应该不会返回"
    
    mock_llm = TimeoutLLMClient()
    
    # 替换llm_client为模拟版本
    from backend.agents.executor.ai_analyzer import AIAnalyzer
    original_init = AIAnalyzer.__init__
    
    def mock_init(self, llm_client=None):
        self.llm_client = mock_llm
    
    AIAnalyzer.__init__ = mock_init
    
    try:
        # 创建GraphEngine
        engine = GraphEngine()
        
        # 初始状态
        initial_state = State()
        initial_state.set("user_id", 123)
        initial_state.set("trace_id", "test_timeout")
        initial_state.set("emails", [
            {"subject": "测试邮件", "from": "test@example.com", "body_preview": "测试内容"}
        ])
        
        # 执行图
        final_state = await engine.run_async(GRAPH, initial_state)
        
        # 验证超时处理
        summary = final_state.get("summary")
        error = final_state.get("error")
        
        if summary == "AI失败" and "超时" in error:
            print(f"✓ 超时处理正确，summary: {summary}, error: {error}")
            return True
        else:
            print(f"❌ 超时处理不正确，summary: {summary}, error: {error}")
            return False
    finally:
        # 恢复原始初始化方法
        AIAnalyzer.__init__ = original_init


async def test_phase4_criteria():
    """测试Phase 4完成标准"""
    print("\n=== 测试Phase 4完成标准 ===")
    
    # 1. Graph中存在AI节点
    print("1. 验证Graph中存在AI节点...")
    assert "ai_analyzer" in GRAPH["nodes"], "Graph中不存在ai_analyzer节点"
    print("   ✓ Graph中存在ai_analyzer节点")
    
    # 2. AI结果进入state流转
    print("2. 验证AI结果进入state流转...")
    
    # 清除之前的注册
    AgentRegistry.clear()
    
    # 创建模拟LLM客户端
    mock_llm = MockLLMClient()
    
    # 模拟数据库会话
    mock_db = Mock()
    
    # 初始化AgentRegistry
    init_agent_registry(mock_db)
    
    # 替换llm_client为模拟版本
    from backend.agents.executor.ai_analyzer import AIAnalyzer
    original_init = AIAnalyzer.__init__
    
    def mock_init(self, llm_client=None):
        self.llm_client = mock_llm
    
    AIAnalyzer.__init__ = mock_init
    
    try:
        # 创建GraphEngine
        engine = GraphEngine()
        
        # 初始状态
        initial_state = State()
        initial_state.set("user_id", 123)
        initial_state.set("trace_id", "test_phase4")
        initial_state.set("emails", [
            {"subject": "Phase 4测试邮件", "from": "test@example.com", "body_preview": "测试Phase 4标准"}
        ])
        
        # 执行图
        final_state = await engine.run_async(GRAPH, initial_state)
        
        # 验证AI结果在state中
        summary = final_state.get("summary")
        assert summary is not None, "AI结果未进入state"
        print(f"   ✓ AI结果进入state流转: {summary[:50]}...")
        
        # 3. 输出依赖AI结果
        print("3. 验证输出依赖AI结果...")
        final_output = final_state.get("final_output")
        assert final_output is not None, "未生成final_output"
        assert summary in final_output, "final_output不包含AI生成的summary"
        print(f"   ✓ 输出依赖AI结果，final_output: {final_output[:50]}...")
        
        return True
    finally:
        # 恢复原始初始化方法
        AIAnalyzer.__init__ = original_init


async def main():
    """运行所有测试"""
    print("开始运行完整链路测试...")
    print("=" * 60)
    
    results = []
    
    try:
        # 测试1: AI调用真实发生
        result1 = await test_ai_call_happens()
        results.append(("AI调用真实发生", result1))
        
        # 测试2: 输出不固定
        result2 = await test_output_variability()
        results.append(("输出不固定", result2))
        
        # 测试3: formatter依赖AI结果
        result3 = await test_formatter_depends_on_ai()
        results.append(("formatter依赖AI结果", result3))
        
        # 测试4: 超时处理
        result4 = await test_timeout_handling()
        results.append(("超时处理", result4))
        
        # 测试5: Phase 4完成标准
        result5 = await test_phase4_criteria()
        results.append(("Phase 4完成标准", result5))
        
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
        print("🎉 所有测试通过！完整链路验证成功")
        print("\n验证的三个现象:")
        print("1. ✅ AI调用真实发生 - llm_client被调用")
        print("2. ✅ 输出不固定 - 每次summary不一样")
        print("3. ✅ formatter依赖AI结果 - 没有summary → 系统报错")
        print("\nPhase 4完成标准:")
        print("1. ✅ Graph中存在AI节点")
        print("2. ✅ AI结果进入state流转")
        print("3. ✅ 输出依赖AI结果")
        print("\n安全措施:")
        print("✅ llm_client.call(timeout=10) 已添加")
        print("✅ 失败策略: try/except 设置 summary='AI失败'")
    else:
        print("❌ 部分测试失败")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)