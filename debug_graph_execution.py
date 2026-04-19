"""
调试Graph执行
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.api.v1.graph import create_graph_from_scenario
from backend.core.state import State
from backend.workflow.deterministic_graph_engine import DeterministicGraphEngine

async def debug_execution():
    """调试执行"""
    print("调试Graph执行...")
    
    try:
        # 创建图和状态
        graph = create_graph_from_scenario("email_briefing")
        print(f"图创建成功: {graph.graph_id}")
        
        initial_state = State(
            data={
                "input_data": {
                    "email_content": "测试邮件",
                    "sender": "test@example.com"
                }
            },
            metadata={
                "scenario": "email_briefing",
                "env": "test"
            }
        )
        
        # 执行Graph
        engine = DeterministicGraphEngine()
        print("开始执行Graph...")
        result = await engine.run_async(graph, initial_state)
        
        print(f"\n执行结果类型: {type(result)}")
        print(f"执行结果键: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        
        # 打印结果
        print("\n执行结果:")
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        
        # 检查是否有执行路径信息
        if "execution_metadata" in result:
            print(f"\n执行元数据: {result['execution_metadata'].keys()}")
            if "actual_path" in result["execution_metadata"]:
                print(f"实际执行路径: {result['execution_metadata']['actual_path']}")
        
    except Exception as e:
        print(f"执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_execution())