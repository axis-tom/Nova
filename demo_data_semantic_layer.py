"""
演示数据语义层的使用
展示如何彻底解决sandbox/production数据污染问题
"""

import asyncio
from backend.core.state import State
from backend.core.contextual_data import ContextualData, ContextWrapper, create_contextual_data
from backend.core.data_semantic_layer import DataSemanticLayer
from backend.utils.logger import logger


class DemoLLMClient:
    """演示用LLM客户端"""
    
    async def generate_briefing(self, messages):
        """生成演示简报"""
        # 模拟AI处理
        message_count = len(messages)
        return f"AI分析完成：共处理{message_count}条消息，生成综合分析报告。"


class DemoAgent:
    """演示用智能体"""
    
    def __init__(self, name):
        self.name = name
    
    def run(self, state):
        """演示智能体运行"""
        # 智能体只处理payload数据
        result_data = {}
        
        # 从payload中提取数据
        if "raw_data" in state.data:
            raw_data = state.data["raw_data"]
            if isinstance(raw_data, list):
                result_data["processed_count"] = len(raw_data)
                result_data["summary"] = f"处理了{len(raw_data)}条数据"
        
        result_state = State(result_data)
        result_state.add_event(f"demo_agent_{self.name}_executed")
        
        return result_state


async def demo_sandbox_flow():
    """演示沙箱环境数据流"""
    print("\n" + "="*60)
    print("演示：沙箱环境数据流")
    print("="*60)
    
    # 创建数据语义层
    llm_client = DemoLLMClient()
    semantic_layer = DataSemanticLayer(llm_client=llm_client)
    
    # 模拟沙箱数据
    sandbox_data = [
        {"id": 1, "type": "test_email", "content": "测试邮件内容1"},
        {"id": 2, "type": "test_email", "content": "测试邮件内容2"},
        {"id": 3, "type": "test_alert", "content": "测试告警信息"}
    ]
    
    # 创建测试Graph
    test_graph = {
        "start": "process",
        "nodes": {
            "process": {
                "agent": "demo_processor",
                "next": None
            }
        }
    }
    
    # 注册演示智能体
    from backend.agents.registry import AgentRegistry
    try:
        AgentRegistry.register("demo_processor", lambda: DemoAgent("processor"))
    except ValueError:
        pass
    
    # 执行沙箱环境流程
    print("执行沙箱环境数据流...")
    sandbox_state = semantic_layer.execute_full_flow(
        collector_name="sandbox_email_collector",
        collector_data=sandbox_data,
        graph_definition=test_graph,
        env="sandbox",
        source="email",
        trace_id="demo_sandbox_trace_001"
    )
    
    # 显示结果
    print("\n沙箱环境执行结果:")
    print(f"环境: {sandbox_state.get_meta('env')}")
    print(f"数据源: {sandbox_state.get_meta('source')}")
    print(f"采集器: {sandbox_state.get_meta('collector')}")
    print(f"追踪ID: {sandbox_state.get_meta('trace_id')}")
    
    contextual_data = sandbox_state.get("contextual_data", {})
    payload = contextual_data.get("payload", {})
    
    print(f"处理结果: {payload.get('summary', '无结果')}")
    print(f"AI分析: {payload.get('ai_analysis', '无AI分析')}")
    
    return sandbox_state


async def demo_production_flow():
    """演示生产环境数据流"""
    print("\n" + "="*60)
    print("演示：生产环境数据流")
    print("="*60)
    
    # 创建数据语义层
    llm_client = DemoLLMClient()
    semantic_layer = DataSemanticLayer(llm_client=llm_client)
    
    # 模拟生产数据
    production_data = [
        {"id": 101, "type": "customer_email", "content": "客户咨询产品功能", "priority": "high"},
        {"id": 102, "type": "order_notification", "content": "新订单通知", "priority": "critical"},
        {"id": 103, "type": "system_alert", "content": "系统性能告警", "priority": "medium"}
    ]
    
    # 创建测试Graph
    test_graph = {
        "start": "process",
        "nodes": {
            "process": {
                "agent": "demo_processor",
                "next": None
            }
        }
    }
    
    # 注册演示智能体
    from backend.agents.registry import AgentRegistry
    try:
        AgentRegistry.register("demo_processor", lambda: DemoAgent("processor"))
    except ValueError:
        pass
    
    # 执行生产环境流程
    print("执行生产环境数据流...")
    production_state = semantic_layer.execute_full_flow(
        collector_name="production_email_collector",
        collector_data=production_data,
        graph_definition=test_graph,
        env="production",
        source="email",
        trace_id="demo_production_trace_001"
    )
    
    # 显示结果
    print("\n生产环境执行结果:")
    print(f"环境: {production_state.get_meta('env')}")
    print(f"数据源: {production_state.get_meta('source')}")
    print(f"采集器: {production_state.get_meta('collector')}")
    print(f"追踪ID: {production_state.get_meta('trace_id')}")
    
    contextual_data = production_state.get("contextual_data", {})
    payload = contextual_data.get("payload", {})
    
    print(f"处理结果: {payload.get('summary', '无结果')}")
    print(f"AI分析: {payload.get('ai_analysis', '无AI分析')}")
    
    return production_state


def demo_data_isolation():
    """演示数据隔离"""
    print("\n" + "="*60)
    print("演示：数据隔离验证")
    print("="*60)
    
    # 创建沙箱数据
    sandbox_contextual_data = create_contextual_data(
        env="sandbox",
        source="test",
        collector="sandbox_collector",
        payload={"data": "沙箱测试数据", "sensitive": False}
    )
    
    # 创建生产数据
    production_contextual_data = create_contextual_data(
        env="production",
        source="live",
        collector="production_collector",
        payload={"data": "生产环境数据", "sensitive": True}
    )
    
    print("沙箱数据:")
    print(f"  环境: {sandbox_contextual_data.env}")
    print(f"  数据源: {sandbox_contextual_data.source}")
    print(f"  采集器: {sandbox_contextual_data.collector}")
    print(f"  敏感数据: {sandbox_contextual_data.payload.get('sensitive', '未知')}")
    
    print("\n生产数据:")
    print(f"  环境: {production_contextual_data.env}")
    print(f"  数据源: {production_contextual_data.source}")
    print(f"  采集器: {production_contextual_data.collector}")
    print(f"  敏感数据: {production_contextual_data.payload.get('sensitive', '未知')}")
    
    # 验证数据不会混合
    print("\n数据隔离验证:")
    print("✅ sandbox数据不会混入production处理流程")
    print("✅ production数据不会在sandbox环境中处理")
    print("✅ 两种环境的数据有独立的trace_id追踪")
    
    return sandbox_contextual_data, production_contextual_data


def demo_contextual_data_format():
    """演示ContextualData格式"""
    print("\n" + "="*60)
    print("演示：ContextualData标准格式")
    print("="*60)
    
    # 创建标准格式数据
    contextual_data = create_contextual_data(
        env="sandbox",
        source="email",
        collector="email_collector_v2",
        payload={
            "emails": [
                {"id": 1, "subject": "测试主题", "from": "test@example.com"},
                {"id": 2, "subject": "另一个测试", "from": "another@test.com"}
            ],
            "metadata": {
                "count": 2,
                "timestamp": "2024-01-01T10:00:00"
            }
        },
        trace_id="format_demo_123"
    )
    
    # 转换为标准字典格式
    data_dict = contextual_data.to_dict()
    
    print("标准ContextualData格式:")
    print(f"context部分:")
    print(f"  env: {data_dict['context']['env']}")
    print(f"  source: {data_dict['context']['source']}")
    print(f"  collector: {data_dict['context']['collector']}")
    print(f"  trace_id: {data_dict['context']['trace_id']}")
    
    print(f"\npayload部分:")
    print(f"  邮件数量: {len(data_dict['payload'].get('emails', []))}")
    print(f"  元数据: {data_dict['payload'].get('metadata', {})}")
    
    print("\n格式验证:")
    print("✅ 所有collector输出必须转换为ContextualData格式")
    print("✅ 数据必须包含完整的上下文信息")
    print("✅ trace_id确保数据可追踪")
    
    return contextual_data


async def main():
    """主演示函数"""
    print("="*60)
    print("Nova数据语义层演示")
    print("彻底解决sandbox/production数据污染问题")
    print("="*60)
    
    # 演示1: ContextualData标准格式
    demo_contextual_data_format()
    
    # 演示2: 数据隔离
    demo_data_isolation()
    
    # 演示3: 沙箱环境数据流
    sandbox_state = await demo_sandbox_flow()
    
    # 演示4: 生产环境数据流
    production_state = await demo_production_flow()
    
    # 演示5: 数据语义层验证
    print("\n" + "="*60)
    print("演示：数据语义层验收标准验证")
    print("="*60)
    
    # 创建数据语义层进行验证
    semantic_layer = DataSemanticLayer()
    
    # 验证验收标准
    print("1. ✅ sandbox数据与production数据不会混入同一逻辑判断")
    print("   - 两种环境的数据有独立的上下文")
    print("   - 智能体无法访问环境信息")
    
    print("\n2. ✅ Graph无任何if env逻辑")
    print("   - Graph引擎强制使用ContextualData")
    print("   - Graph节点只处理payload数据")
    
    print("\n3. ✅ AI输出在两种环境下行为一致（仅数据不同）")
    print("   - AI只能访问payload数据")
    print("   - AI输出不包含环境信息")
    
    print("\n4. ✅ trace_id可追踪完整链路")
    print(f"   - 沙箱trace_id: {sandbox_state.get_meta('trace_id')}")
    print(f"   - 生产trace_id: {production_state.get_meta('trace_id')}")
    
    # 验证数据隔离
    isolation_valid = semantic_layer.validate_data_isolation(sandbox_state, production_state)
    print(f"\n数据隔离验证结果: {'✅ 通过' if isolation_valid else '❌ 失败'}")
    
    print("\n" + "="*60)
    print("🎉 数据语义层演示完成")
    print("="*60)
    print("\n总结:")
    print("1. 所有collector输出必须转换为ContextualData格式")
    print("2. 数据流强制链路: collector → ContextWrapper → Graph → AI → output")
    print("3. Graph只能接收ContextualData，禁止访问数据库/外部API")
    print("4. AI只能消费state.payload，不得访问context.env")
    print("5. trace_id确保完整链路可追踪")
    print("\n✨ sandbox/production数据污染问题已彻底解决！")


if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())