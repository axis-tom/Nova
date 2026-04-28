#!/usr/bin/env python3
"""
Nova Graph + AI 稳定性与语义一致性验证脚本
验证Data Context Layer支持下的稳定性与语义一致性
"""

import asyncio
import json
from typing import Dict, Any, List, Tuple
from backend.core.state import State
from backend.core.contextual_data import ContextualData, ContextWrapper, create_contextual_data
from backend.core.data_semantic_layer import DataSemanticLayer
from backend.workflow.contextual_graph_engine import ContextualGraphEngine
from backend.agents.executor.contextual_ai_analyzer import ContextualAIAnalyzer
from backend.utils.logger import logger

# 配置日志级别
logger.setLevel("INFO")

class MockLLMClient:
    """模拟LLM客户端，确保输出结构一致"""
    
    def __init__(self, fixed_response=None):
        self.fixed_response = fixed_response or "AI分析结果：数据已处理"
        self.call_count = 0
    
    async def generate_briefing(self, messages):
        """生成模拟简报，确保输出结构一致"""
        self.call_count += 1
        
        # 检查消息中是否包含环境信息
        combined_message = "\n".join(messages)
        env_keywords = ["sandbox", "production", "test", "env:", "environment:"]
        for keyword in env_keywords:
            if keyword in combined_message.lower():
                logger.warning(f"Mock LLM detected environment keyword in message: {keyword}")
        
        # 返回固定结构的响应，确保一致性
        return f"AI分析结果：{self.fixed_response} (调用次数: {self.call_count})"

class MockAgent:
    """模拟智能体，用于测试Graph一致性"""
    
    def __init__(self, name):
        self.name = name
        self.execution_count = 0
    
    def run(self, state):
        """模拟智能体运行，确保不访问环境信息"""
        self.execution_count += 1
        
        # 记录智能体访问的数据
        accessed_keys = list(state.data.keys())
        
        # 检查是否访问了环境信息
        forbidden_keys = ["env", "environment", "contextual_data", "context"]
        for key in forbidden_keys:
            if key in state.data:
                logger.warning(f"Agent {self.name} accessed forbidden key: {key}")
        
        # 只处理payload数据
        result_data = {}
        for key in state.data:
            if key not in forbidden_keys:
                value = state.data[key]
                if isinstance(value, (str, int, float, bool)):
                    result_data[f"processed_{key}"] = f"{value}_processed_by_{self.name}"
                elif isinstance(value, dict):
                    result_data[f"processed_{key}"] = {f"processed_{k}": v for k, v in value.items()}
        
        result_state = State(result_data)
        result_state.add_event(f"mock_agent_{self.name}_executed")
        result_state.set_meta("agent_name", self.name)
        result_state.set_meta("execution_count", self.execution_count)
        
        return result_state

def test_data_isolation():
    """测试1: 数据隔离测试"""
    print("\n" + "="*80)
    print("测试1: 数据隔离测试")
    print("="*80)
    
    failures = []
    
    # 1.1 创建沙箱和生产环境数据
    sandbox_data = create_contextual_data(
        env="sandbox",
        source="email",
        collector="sandbox_email_collector",
        payload={"emails": [{"id": 1, "subject": "沙箱测试邮件"}]},
        trace_id="sandbox_trace_001"
    )
    
    production_data = create_contextual_data(
        env="production",
        source="email",
        collector="production_email_collector",
        payload={"emails": [{"id": 2, "subject": "生产环境邮件"}]},
        trace_id="production_trace_001"
    )
    
    # 1.2 验证数据格式
    sandbox_dict = sandbox_data.to_dict()
    production_dict = production_data.to_dict()
    
    if sandbox_dict["context"]["env"] != "sandbox":
        failures.append("沙箱数据环境标识不正确")
    
    if production_dict["context"]["env"] != "production":
        failures.append("生产数据环境标识不正确")
    
    # 1.3 验证环境判断函数
    if not sandbox_data.is_sandbox():
        failures.append("is_sandbox() 函数对沙箱数据返回错误")
    
    if not production_data.is_production():
        failures.append("is_production() 函数对生产数据返回错误")
    
    # 1.4 验证数据不会混合
    try:
        # 尝试合并不同环境的数据（应该失败）
        sandbox_data.merge(production_data)
        failures.append("不同环境的数据不应该被允许合并")
    except ValueError as e:
        error_msg = str(e)
        # merge方法首先检查trace_id，然后检查env
        if "Cannot merge ContextualData with different trace_ids" not in error_msg and "different environments" not in error_msg:
            failures.append(f"合并错误消息不正确: {e}")
        else:
            print(f"  数据合并正确拒绝: {error_msg}")
    
    # 1.5 验证ContextWrapper自动推断
    auto_sandbox = ContextWrapper.wrap_collector_output(
        collector_name="sandbox_test_collector",
        data={"test": "data"}
    )
    
    auto_production = ContextWrapper.wrap_collector_output(
        collector_name="production_collector",
        data={"test": "data"}
    )
    
    if auto_sandbox.env != "sandbox":
        failures.append("ContextWrapper未能正确推断沙箱环境")
    
    if auto_production.env != "production":
        failures.append("ContextWrapper未能正确推断生产环境")
    
    # 输出结果
    if failures:
        print(f"❌ 数据隔离测试失败: {len(failures)}个问题")
        for i, failure in enumerate(failures, 1):
            print(f"  {i}. {failure}")
        return False, failures
    else:
        print("✅ 数据隔离测试通过")
        return True, []

def test_graph_consistency():
    """测试2: Graph一致性测试"""
    print("\n" + "="*80)
    print("测试2: Graph一致性测试")
    print("="*80)
    
    failures = []
    
    # 2.1 创建Graph引擎
    graph_engine = ContextualGraphEngine()
    
    # 2.2 创建测试Graph定义
    test_graph = {
        "start": "process",
        "nodes": {
            "process": {
                "agent": "test_processor",
                "next": "analyze"
            },
            "analyze": {
                "agent": "test_analyzer",
                "next": None
            }
        }
    }
    
    # 2.3 注册模拟智能体
    from backend.agents.registry import AgentRegistry
    try:
        AgentRegistry.register("test_processor", lambda: MockAgent("processor"))
        AgentRegistry.register("test_analyzer", lambda: MockAgent("analyzer"))
    except ValueError:
        # 如果已注册，忽略错误
        pass
    
    # 2.4 测试沙箱环境
    sandbox_contextual_data = create_contextual_data(
        env="sandbox",
        source="test",
        collector="test_collector",
        payload={"data": "sandbox_test_data", "count": 5},
        trace_id="graph_test_sandbox"
    )
    
    sandbox_state = State()
    sandbox_state.set("contextual_data", sandbox_contextual_data.to_dict())
    
    sandbox_result = graph_engine.run(test_graph, sandbox_state)
    
    # 2.5 测试生产环境
    production_contextual_data = create_contextual_data(
        env="production",
        source="test",
        collector="test_collector",
        payload={"data": "production_test_data", "count": 10},
        trace_id="graph_test_production"
    )
    
    production_state = State()
    production_state.set("contextual_data", production_contextual_data.to_dict())
    
    production_result = graph_engine.run(test_graph, production_state)
    
    # 2.6 验证Graph执行流程一致性
    sandbox_events = [e for e in sandbox_result.events if isinstance(e, str)]
    production_events = [e for e in production_result.events if isinstance(e, str)]
    
    # 检查事件类型是否一致（忽略具体数据）
    sandbox_event_types = [e.split("_")[0] for e in sandbox_events if "_" in e]
    production_event_types = [e.split("_")[0] for e in production_events if "_" in e]
    
    if sandbox_event_types != production_event_types:
        failures.append(f"Graph执行事件类型不一致: 沙箱={sandbox_event_types}, 生产={production_event_types}")
    
    # 2.7 验证Graph没有环境判断逻辑
    # 检查Graph引擎代码中是否有环境判断
    import inspect
    graph_engine_code = inspect.getsource(ContextualGraphEngine)
    
    env_check_patterns = [
        r'if.*env.*==.*["\']sandbox["\']',
        r'if.*env.*==.*["\']production["\']',
        r'env.*=.*["\']sandbox["\']',
        r'env.*=.*["\']production["\']',
        r'is_sandbox\(\)',
        r'is_production\(\)'
    ]
    
    import re
    for pattern in env_check_patterns:
        if re.search(pattern, graph_engine_code, re.IGNORECASE):
            failures.append(f"Graph引擎代码中包含环境判断逻辑: {pattern}")
    
    # 2.8 验证智能体执行次数一致
    sandbox_agent_executions = len([e for e in sandbox_events if "mock_agent" in e])
    production_agent_executions = len([e for e in production_events if "mock_agent" in e])
    
    if sandbox_agent_executions != production_agent_executions:
        failures.append(f"智能体执行次数不一致: 沙箱={sandbox_agent_executions}, 生产={production_agent_executions}")
    
    # 输出结果
    if failures:
        print(f"❌ Graph一致性测试失败: {len(failures)}个问题")
        for i, failure in enumerate(failures, 1):
            print(f"  {i}. {failure}")
        return False, failures
    else:
        print("✅ Graph一致性测试通过")
        print(f"  沙箱环境执行事件: {len(sandbox_events)}个")
        print(f"  生产环境执行事件: {len(production_events)}个")
        print(f"  智能体执行次数: {sandbox_agent_executions}次")
        return True, []

def test_ai_output_stability():
    """测试3: AI输出稳定性测试"""
    print("\n" + "="*80)
    print("测试3: AI输出稳定性测试")
    print("="*80)
    
    failures = []
    
    # 3.1 创建AI分析器
    mock_llm = MockLLMClient("标准AI分析响应")
    ai_analyzer = ContextualAIAnalyzer(mock_llm)
    
    # 3.2 测试沙箱环境数据
    sandbox_contextual_data = create_contextual_data(
        env="sandbox",
        source="email",
        collector="sandbox_email_collector",
        payload={
            "emails": [
                {"subject": "沙箱测试邮件1", "from": "test1@example.com", "content": "测试内容1"},
                {"subject": "沙箱测试邮件2", "from": "test2@example.com", "content": "测试内容2"}
            ]
        },
        trace_id="ai_test_sandbox"
    )
    
    sandbox_state = State()
    sandbox_state.set("contextual_data", sandbox_contextual_data.to_dict())
    
    # 3.3 测试生产环境数据
    production_contextual_data = create_contextual_data(
        env="production",
        source="email",
        collector="production_email_collector",
        payload={
            "emails": [
                {"subject": "生产重要邮件1", "from": "important1@company.com", "content": "重要内容1"},
                {"subject": "生产重要邮件2", "from": "important2@company.com", "content": "重要内容2"}
            ]
        },
        trace_id="ai_test_production"
    )
    
    production_state = State()
    production_state.set("contextual_data", production_contextual_data.to_dict())
    
    # 3.4 执行AI分析
    async def run_ai_analysis():
        sandbox_result = await ai_analyzer.run(sandbox_state.copy())
        production_result = await ai_analyzer.run(production_state.copy())
        return sandbox_result, production_result
    
    sandbox_ai_result, production_ai_result = asyncio.run(run_ai_analysis())
    
    # 3.5 验证AI输出结构一致性
    sandbox_output = sandbox_ai_result.get("contextual_data", {}).get("payload", {}).get("ai_analysis")
    production_output = production_ai_result.get("contextual_data", {}).get("payload", {}).get("ai_analysis")
    
    if not sandbox_output or not production_output:
        failures.append("AI分析结果缺失")
    else:
        # 检查输出结构是否相似（忽略具体内容）
        sandbox_output_str = str(sandbox_output)
        production_output_str = str(production_output)
        
        # 检查是否包含相同的结构元素
        structure_elements = ["AI分析结果", "调用次数", "标准AI分析响应"]
        for element in structure_elements:
            if element not in sandbox_output_str:
                failures.append(f"沙箱AI输出缺少结构元素: {element}")
            if element not in production_output_str:
                failures.append(f"生产AI输出缺少结构元素: {element}")
    
    # 3.6 验证AI不感知环境
    # 检查AI分析器代码中是否有环境访问（排除注释）
    import inspect
    import re
    
    # 获取源代码并移除注释
    ai_analyzer_code = inspect.getsource(ContextualAIAnalyzer)
    
    # 移除单行注释
    ai_analyzer_code = re.sub(r'#.*$', '', ai_analyzer_code, flags=re.MULTILINE)
    # 移除多行注释（如果有）
    ai_analyzer_code = re.sub(r'""".*?"""', '', ai_analyzer_code, flags=re.DOTALL)
    ai_analyzer_code = re.sub(r"'''.*?'''", '', ai_analyzer_code, flags=re.DOTALL)
    
    env_access_patterns = [
        r'context\.env',
        r'context\["env"\]',
        r'state\.get.*env',
        r'state\["env"\]',
        r'env.*==.*["\']sandbox["\']',
        r'env.*==.*["\']production["\']'
    ]
    
    for pattern in env_access_patterns:
        if re.search(pattern, ai_analyzer_code, re.IGNORECASE):
            failures.append(f"AI分析器代码中包含环境访问: {pattern}")
    
    # 3.7 验证AI输出验证函数
    good_outputs = [
        "这是一个正常的分析结果。",
        "数据分析完成，发现3个关键点。",
        "基于提供的数据，建议采取以下措施。"
    ]
    
    bad_outputs = [
        "这是sandbox环境的分析结果。",
        "生产环境数据显示...",
        "测试环境的数据表明...",
        "数据来源：sandbox环境"
    ]
    
    for output in good_outputs:
        if not ai_analyzer.validate_ai_output(output):
            failures.append(f"AI输出验证函数错误地拒绝了有效输出: {output}")
    
    for output in bad_outputs:
        if ai_analyzer.validate_ai_output(output):
            failures.append(f"AI输出验证函数错误地接受了包含环境信息的输出: {output}")
    
    # 输出结果
    if failures:
        print(f"❌ AI输出稳定性测试失败: {len(failures)}个问题")
        for i, failure in enumerate(failures, 1):
            print(f"  {i}. {failure}")
        return False, failures
    else:
        print("✅ AI输出稳定性测试通过")
        print(f"  沙箱AI输出长度: {len(str(sandbox_output)) if sandbox_output else 0}")
        print(f"  生产AI输出长度: {len(str(production_output)) if production_output else 0}")
        print(f"  AI调用次数: {mock_llm.call_count}")
        return True, []

def test_full_integration():
    """测试4: 完整集成测试"""
    print("\n" + "="*80)
    print("测试4: 完整集成测试")
    print("="*80)
    
    failures = []
    
    # 4.1 创建数据语义层
    mock_llm = MockLLMClient("集成测试AI响应")
    semantic_layer = DataSemanticLayer(llm_client=mock_llm)
    
    # 4.2 注册模拟智能体
    from backend.agents.registry import AgentRegistry
    try:
        AgentRegistry.register("integration_processor", lambda: MockAgent("integration_processor"))
    except ValueError:
        pass
    
    # 4.3 创建测试Graph
    integration_graph = {
        "start": "process",
        "nodes": {
            "process": {
                "agent": "integration_processor",
                "next": None
            }
        }
    }
    
    # 4.4 执行沙箱环境完整流程
    sandbox_result = semantic_layer.execute_full_flow(
        collector_name="sandbox_integration_collector",
        collector_data={"items": [{"id": 1, "value": "sandbox_value"}]},
        graph_definition=integration_graph,
        env="sandbox",
        source="integration_test",
        trace_id="integration_sandbox_001"
    )
    
    # 4.5 执行生产环境完整流程
    production_result = semantic_layer.execute_full_flow(
        collector_name="production_integration_collector",
        collector_data={"items": [{"id": 2, "value": "production_value"}]},
        graph_definition=integration_graph,
        env="production",
        source="integration_test",
        trace_id="integration_production_001"
    )
    
    # 4.6 验证trace_id追踪
    sandbox_trace_id = sandbox_result.get_meta("trace_id")
    production_trace_id = production_result.get_meta("trace_id")
    
    if sandbox_trace_id != "integration_sandbox_001":
        failures.append(f"沙箱环境trace_id追踪失败: 期望=integration_sandbox_001, 实际={sandbox_trace_id}")
    
    if production_trace_id != "integration_production_001":
        failures.append(f"生产环境trace_id追踪失败: 期望=integration_production_001, 实际={production_trace_id}")
    
    # 4.7 验证context字段始终存在
    sandbox_contextual_data = sandbox_result.get("contextual_data", {})
    production_contextual_data = production_result.get("contextual_data", {})
    
    if "context" not in sandbox_contextual_data:
        failures.append("沙箱环境结果缺少context字段")
    
    if "context" not in production_contextual_data:
        failures.append("生产环境结果缺少context字段")
    
    # 4.8 验证数据隔离
    if semantic_layer.validate_data_isolation(sandbox_result, production_result) != True:
        failures.append("数据语义层数据隔离验证失败")
    
    # 4.9 验证执行轨迹
    execution_trace = semantic_layer.get_execution_trace()
    if len(execution_trace) != 2:
        failures.append(f"执行轨迹数量不正确: 期望=2, 实际={len(execution_trace)}")
    else:
        trace_envs = [trace["env"] for trace in execution_trace]
        if set(trace_envs) != {"sandbox", "production"}:
            failures.append(f"执行轨迹环境不正确: {trace_envs}")
    
    # 输出结果
    if failures:
        print(f"❌ 完整集成测试失败: {len(failures)}个问题")
        for i, failure in enumerate(failures, 1):
            print(f"  {i}. {failure}")
        return False, failures
    else:
        print("✅ 完整集成测试通过")
        print(f"  沙箱环境trace_id: {sandbox_trace_id}")
        print(f"  生产环境trace_id: {production_trace_id}")
        print(f"  执行轨迹记录: {len(execution_trace)}条")
        print(f"  AI调用总次数: {mock_llm.call_count}")
        return True, []

def main():
    """主函数：运行所有测试"""
    print("="*80)
    print("Nova Graph + AI 稳定性与语义一致性验证")
    print("验证Data Context Layer支持下的稳定性与语义一致性")
    print("="*80)
    
    all_failures = []
    test_results = []
    
    # 运行测试1: 数据隔离测试
    passed, failures = test_data_isolation()
    test_results.append(("数据隔离测试", passed))
    all_failures.extend([("数据隔离测试", f) for f in failures])
    
    # 运行测试2: Graph一致性测试
    passed, failures = test_graph_consistency()
    test_results.append(("Graph一致性测试", passed))
    all_failures.extend([("Graph一致性测试", f) for f in failures])
    
    # 运行测试3: AI输出稳定性测试
    passed, failures = test_ai_output_stability()
    test_results.append(("AI输出稳定性测试", passed))
    all_failures.extend([("AI输出稳定性测试", f) for f in failures])
    
    # 运行测试4: 完整集成测试
    passed, failures = test_full_integration()
    test_results.append(("完整集成测试", passed))
    all_failures.extend([("完整集成测试", f) for f in failures])
    
    # 输出最终结果
    print("\n" + "="*80)
    print("验证结果汇总")
    print("="*80)
    
    all_passed = True
    for test_name, passed in test_results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 所有验证通过！Nova Graph + AI 在Data Context Layer支持下表现稳定且语义一致。")
        print("\n验证标准检查:")
        print("✔ context字段始终存在且正确")
        print("✔ Graph无环境判断逻辑")
        print("✔ AI不感知env/source")
        print("✔ 输出结构稳定一致")
        print("✔ trace_id可追踪全链路")
    else:
        print(f"⚠️  验证失败: {len(all_failures)}个问题")
        print("\n失败点列表:")
        for i, (test_name, failure) in enumerate(all_failures, 1):
            print(f"  {i}. [{test_name}] {failure}")
        
        print("\n修复建议:")
        print("1. 检查ContextualData实现，确保环境标识正确")
        print("2. 审查Graph引擎代码，移除所有环境判断逻辑")
        print("3. 验证AI分析器是否完全隔离环境信息")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
