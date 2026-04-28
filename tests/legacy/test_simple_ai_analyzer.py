#!/usr/bin/env python3
"""
简单测试 ai_analyzer 是否已正确接入 Graph
不依赖外部模块
"""

import json

def test_graph_structure():
    """测试 Graph 结构"""
    print("=== 测试 Graph 结构 ===")
    
    # 直接读取 daily_graph.py 文件
    with open('backend/sop/daily_graph.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取 GRAPH 定义
    # 简单解析 Python 字典
    import ast
    # 找到 GRAPH = { 开始的位置
    start_idx = content.find('GRAPH = {')
    if start_idx == -1:
        print("❌ 未找到 GRAPH 定义")
        return False
    
    # 提取从 GRAPH = 开始到文件结束的内容
    graph_content = content[start_idx:]
    # 找到匹配的 }
    brace_count = 0
    end_idx = 0
    for i, char in enumerate(graph_content):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break
    
    if end_idx == 0:
        print("❌ 无法解析 GRAPH 定义")
        return False
    
    graph_str = graph_content[:end_idx]
    # 移除 GRAPH = 前缀
    graph_str = graph_str.replace('GRAPH = ', '', 1)
    
    try:
        graph = ast.literal_eval(graph_str)
    except:
        print("❌ 无法解析 GRAPH 为 Python 对象")
        return False
    
    # 验证 Graph 结构
    assert graph["start"] == "email", f"Graph start should be 'email', got {graph['start']}"
    
    # 验证节点
    nodes = graph["nodes"]
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
    print(f"  执行顺序: {graph['start']} → {nodes['email']['next']} → {nodes['ai_analyzer']['next']}")
    return True

def test_agent_wrapper():
    """测试 agent_wrapper.py 是否注册了 ai_analyzer"""
    print("\n=== 测试 agent_wrapper.py ===")
    
    with open('backend/workflow/agent_wrapper.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否导入了 AIAnalyzer
    if 'from backend.agents.executor.ai_analyzer import AIAnalyzer' not in content:
        print("❌ agent_wrapper.py 未导入 AIAnalyzer")
        return False
    
    # 检查是否注册了 ai_analyzer
    if 'AgentRegistry.register("ai_analyzer"' not in content:
        print("❌ agent_wrapper.py 未注册 ai_analyzer")
        return False
    
    # 检查是否使用了 llm_client
    if 'from backend.utils.llm_client import llm_client' not in content:
        print("❌ agent_wrapper.py 未导入 llm_client")
        return False
    
    print("✓ agent_wrapper.py 正确注册了 ai_analyzer")
    return True

def test_ai_analyzer_implementation():
    """测试 ai_analyzer.py 实现"""
    print("\n=== 测试 ai_analyzer.py 实现 ===")
    
    with open('backend/agents/executor/ai_analyzer.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否包含 AIAnalyzer 类
    if 'class AIAnalyzer' not in content:
        print("❌ ai_analyzer.py 未定义 AIAnalyzer 类")
        return False
    
    # 检查是否有 run 方法
    if 'def run(self, state):' not in content:
        print("❌ AIAnalyzer 没有 run 方法")
        return False
    
    # 检查是否使用 llm_client
    if 'self.llm_client.generate_briefing' not in content and 'self.llm_client.call' not in content:
        print("❌ AIAnalyzer 未使用 llm_client")
        return False
    
    print("✓ ai_analyzer.py 实现正确")
    return True

def test_briefing_agent_has_llm():
    """检查 briefing_agent 是否仍然包含 LLM 调用"""
    print("\n=== 检查 briefing_agent 是否包含 LLM 调用 ===")
    
    with open('backend/agents/executor/briefing_generator_agent.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否包含 LLM 调用
    llm_keywords = ["llm_client", "generate_briefing", "await llm_client", "LLM"]
    has_llm_call = any(keyword in content for keyword in llm_keywords)
    
    if has_llm_call:
        print("⚠️ 警告：briefing_agent 仍然包含 LLM 调用")
        print("   根据任务要求，ai_analyzer 应该是唯一的 AI 节点")
        print("   建议将 LLM 调用从 briefing_agent 移到 ai_analyzer")
        return False
    else:
        print("✓ briefing_agent 不包含 LLM 调用，ai_analyzer 是唯一的 AI 节点")
        return True

def main():
    """运行所有测试"""
    print("开始测试 ai_analyzer 接入 Graph...")
    print("=" * 60)
    
    results = []
    
    try:
        # 测试 1: Graph 结构
        result1 = test_graph_structure()
        results.append(("Graph 结构测试", result1))
        
        # 测试 2: Agent 注册
        result2 = test_agent_wrapper()
        results.append(("Agent 注册测试", result2))
        
        # 测试 3: AIAnalyzer 实现
        result3 = test_ai_analyzer_implementation()
        results.append(("AIAnalyzer 实现测试", result3))
        
        # 测试 4: 验证 ai_analyzer 是唯一的 AI 节点
        result4 = test_briefing_agent_has_llm()
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
        print("4. ✅ ai_analyzer 是唯一的 AI 节点")
    else:
        print("❌ 部分测试失败")
        print("\n注意：briefing_agent 仍然包含 LLM 调用")
        print("根据任务要求 'ai_analyzer 必须是唯一AI节点'")
        print("需要将 LLM 调用从 briefing_agent 移到 ai_analyzer")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)