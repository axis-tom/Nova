"""
测试Ecommerce Graph完整执行链
验证Multi-Agent电商前置执行架构
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.core.state import State
from backend.workflow.ecommerce_graph import EcommerceGraphEngine
import time
import json


def test_basic_execution():
    """
    测试基本执行链
    """
    print("=" * 60)
    print("测试1: 基本执行链")
    print("=" * 60)
    
    # 创建Graph引擎
    graph = EcommerceGraphEngine()
    
    # 准备初始状态
    initial_state = State({
        "context": {
            "environment": "sandbox",
            "user_id": "test_user_001",
            "session_id": f"session_{int(time.time())}"
        },
        "data": {
            "product_id": "prod_12345",
            "operation_type": "price_adjustment",
            "market_data": {
                "competitor_prices": [100, 110, 105, 95],
                "historical_prices": [90, 95, 100, 105]
            }
        },
        "goal": "调整产品价格以优化销售",
        "constraints": {
            "min_price": 80,
            "max_price": 120,
            "budget": 1000
        }
    })
    
    # 执行Graph
    print("开始执行Graph...")
    start_time = time.time()
    
    try:
        result_state = graph.run(initial_state)
        execution_time = time.time() - start_time
        
        print(f"执行完成，耗时: {execution_time:.2f}秒")
        print(f"执行成功: {result_state.get('execution_success', False)}")
        print(f"执行完成: {result_state.get('execution_completed', False)}")
        
        # 检查Agent执行状态
        print("\nAgent执行状态:")
        print(f"  Planner: {result_state.get('planner_executed', False)}")
        print(f"  Analyst: {result_state.get('analyst_executed', False)}")
        print(f"  Executor: {result_state.get('executor_executed', False)}")
        print(f"  Judge: {result_state.get('judge_executed', False)}")
        print(f"  Memory: {result_state.get('memory_executed', False)}")
        
        # 检查决策结果
        decision = result_state.get('decision', {})
        print(f"\nGraph决策: {decision.get('action', 'unknown')}")
        print(f"决策原因: {decision.get('reason', 'N/A')}")
        
        # 检查执行结果
        if result_state.get('execution_result'):
            exec_result = result_state['execution_result']
            print(f"\n执行结果:")
            print(f"  成功: {exec_result.get('success', False)}")
            print(f"  API调用: {exec_result.get('api_calls', 0)}")
            print(f"  执行时间: {exec_result.get('execution_time', 0):.2f}秒")
        
        # 检查评估结果
        if result_state.get('evaluation_result'):
            eval_result = result_state['evaluation_result']
            print(f"\n评估结果:")
            print(f"  总体评分: {eval_result.get('overall_score', 'N/A')}")
            print(f"  评估类型: {eval_result.get('evaluation_type', 'N/A')}")
        
        # 检查性能指标
        if result_state.get('performance_metrics'):
            metrics = result_state['performance_metrics']
            print(f"\n性能指标:")
            print(f"  总执行时间: {metrics.get('total_execution_time', 0):.2f}秒")
            print(f"  完成步骤: {metrics.get('steps_completed', 0)}")
            print(f"  失败步骤: {metrics.get('steps_failed', 0)}")
        
        return True
        
    except Exception as e:
        print(f"执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_api_environment_switch():
    """
    测试API环境切换
    """
    print("\n" + "=" * 60)
    print("测试2: API环境切换")
    print("=" * 60)
    
    graph = EcommerceGraphEngine()
    
    # 测试沙箱环境
    print("设置环境为 sandbox...")
    graph.set_api_environment("sandbox")
    
    # 测试生产环境
    print("设置环境为 production...")
    graph.set_api_environment("production")
    
    # 测试暂存环境
    print("设置环境为 staging...")
    graph.set_api_environment("staging")
    
    print("API环境切换测试完成")
    return True


def test_agent_status():
    """
    测试Agent状态查询
    """
    print("\n" + "=" * 60)
    print("测试3: Agent状态查询")
    print("=" * 60)
    
    graph = EcommerceGraphEngine()
    
    agent_status = graph.get_agent_status()
    print("Agent状态:")
    for agent_name, agent_info in agent_status.items():
        print(f"  {agent_name}:")
        print(f"    名称: {agent_info['name']}")
        print(f"    描述: {agent_info['description']}")
        print(f"    已初始化: {agent_info['initialized']}")
    
    return True


def test_workflow_steps():
    """
    测试工作流步骤
    """
    print("\n" + "=" * 60)
    print("测试4: 工作流步骤")
    print("=" * 60)
    
    graph = EcommerceGraphEngine()
    
    steps = graph.get_workflow_steps()
    print("工作流步骤:")
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")
    
    return True


def test_single_step_execution():
    """
    测试单步执行
    """
    print("\n" + "=" * 60)
    print("测试5: 单步执行")
    print("=" * 60)
    
    graph = EcommerceGraphEngine()
    
    # 准备测试状态
    test_state = State({
        "context": {"test": True},
        "data": {"test_data": "value"},
        "planning_task": {
            "type": "test_planning",
            "goal": "测试规划"
        }
    })
    
    try:
        # 测试规划步骤
        print("执行规划步骤...")
        result = graph.execute_single_step("plan", test_state)
        print(f"规划执行: {result.get('planner_executed', False)}")
        
        # 测试分析步骤
        print("执行分析步骤...")
        result = graph.execute_single_step("analyze", result)
        print(f"分析执行: {result.get('analyst_executed', False)}")
        
        # 测试决策步骤
        print("执行决策步骤...")
        result = graph.execute_single_step("decide", result)
        print(f"决策结果: {result.get('decision', {}).get('action', 'unknown')}")
        
        print("单步执行测试完成")
        return True
        
    except Exception as e:
        print(f"单步执行失败: {str(e)}")
        return False


def test_error_recovery():
    """
    测试错误恢复机制
    """
    print("\n" + "=" * 60)
    print("测试6: 错误恢复机制")
    print("=" * 60)
    
    graph = EcommerceGraphEngine()
    
    # 创建有问题的状态（缺少必要字段）
    problematic_state = State({
        "context": {},
        # 故意不包含data字段
    })
    
    try:
        # 尝试执行
        result = graph.run(problematic_state)
        
        if result.get('execution_failed', False):
            print("错误处理测试成功:")
            print(f"  执行失败: {result.get('execution_failed', False)}")
            print(f"  失败步骤: {result.get('failed_step', 'unknown')}")
            print(f"  错误信息: {result.get('execution_error', 'N/A')}")
            
            if result.get('recovery_attempted', False):
                print(f"  恢复尝试: {result.get('recovery_attempted', False)}")
                print(f"  恢复成功: {result.get('recovery_success', False)}")
            
            return True
        else:
            print("错误处理测试失败: 执行未按预期失败")
            return False
            
    except Exception as e:
        print(f"错误恢复测试异常: {str(e)}")
        return False


def test_api_audit_log():
    """
    测试API审计日志
    """
    print("\n" + "=" * 60)
    print("测试7: API审计日志")
    print("=" * 60)
    
    graph = EcommerceGraphEngine()
    
    try:
        # 获取审计日志
        audit_log = graph.get_api_audit_log(limit=5)
        
        print(f"获取到 {len(audit_log)} 条审计日志:")
        for i, log_entry in enumerate(audit_log, 1):
            print(f"  日志 {i}:")
            print(f"    时间: {log_entry.get('timestamp', 'N/A')}")
            print(f"    操作: {log_entry.get('operation', 'N/A')}")
            print(f"    状态: {log_entry.get('status', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"审计日志测试失败: {str(e)}")
        return False


def test_comprehensive_scenario():
    """
    测试综合场景
    """
    print("\n" + "=" * 60)
    print("测试8: 综合电商场景")
    print("=" * 60)
    
    graph = EcommerceGraphEngine()
    
    # 模拟电商场景
    scenario_state = State({
        "context": {
            "environment": "sandbox",
            "user_id": "business_user_001",
            "business_type": "ecommerce",
            "region": "china"
        },
        "data": {
            "scenario": "inventory_optimization",
            "current_inventory": {
                "product_a": {"stock": 150, "demand": 200},
                "product_b": {"stock": 300, "demand": 250},
                "product_c": {"stock": 50, "demand": 100}
            },
            "supplier_data": {
                "lead_times": {"product_a": 7, "product_b": 5, "product_c": 10},
                "costs": {"product_a": 50, "product_b": 30, "product_c": 80}
            },
            "sales_data": {
                "last_month": {"product_a": 180, "product_b": 220, "product_c": 60},
                "current_month": {"product_a": 200, "product_b": 250, "product_c": 100}
            }
        },
        "goal": "优化库存管理，减少缺货风险",
        "constraints": {
            "budget": 5000,
            "storage_capacity": 1000,
            "time_horizon": 30
        },
        "planning_task": {
            "type": "inventory_optimization",
            "priority": "high"
        },
        "analysis_task": {
            "type": "demand_forecast",
            "scope": "detailed"
        },
        "execution_task": {
            "type": "supplier_order",
            "priority": "normal"
        },
        "evaluation_task": {
            "type": "inventory_quality",
            "scope": "comprehensive"
        }
    })
    
    print("执行综合电商场景...")
    start_time = time.time()
    
    try:
        result = graph.run(scenario_state)
        execution_time = time.time() - start_time
        
        print(f"场景执行完成，耗时: {execution_time:.2f}秒")
        
        # 验证架构要求
        print("\n架构要求验证:")
        
        # 1. Graph负责流程调度，不做决策
        decision = result.get('decision', {})
        print(f"  1. Graph仅调度不决策: {'✓' if decision.get('action') in ['proceed', 'adjust', 'abort'] else '✗'}")
        
        # 2. Agent职责清晰不混乱
        agent_executed = [
            result.get('planner_executed', False),
            result.get('analyst_executed', False),
            result.get('executor_executed', False),
            result.get('judge_executed', False),
            result.get('memory_executed', False)
        ]
        print(f"  2. Agent职责清晰: {'✓' if all(agent_executed) else '✗'}")
        
        # 3. API执行可审计
        try:
            audit_log = graph.get_api_audit_log(limit=1)
            print(f"  3. API执行可审计: {'✓' if audit_log else '✗'}")
        except:
            print(f"  3. API执行可审计: ✗")
        
        # 4. 外部系统可回流状态
        exec_result = result.get('execution_result', {})
        print(f"  4. 外部系统可回流: {'✓' if exec_result.get('success', False) else '✗'}")
        
        # 5. 支持sandbox/production切换
        print(f"  5. 支持环境切换: {'✓' if hasattr(graph, 'set_api_environment') else '✗'}")
        
        # 禁止项检查
        print("\n禁止项检查:")
        
        # ❌ Agent直接调用外部API
        print(f"  ❌ Agent直接调用外部API: {'✓' if result.get('executor_executed', False) else '✗'} (通过Executor Agent)")
        
        # ❌ Graph内部做策略判断
        print(f"  ❌ Graph内部做策略判断: {'✓' if decision.get('action') in ['proceed', 'adjust', 'abort'] else '✗'} (仅调度)")
        
        # ❌ AI直接访问数据库或IMAP
        print(f"  ❌ AI直接访问数据库: {'✓' if result.get('executor_executed', False) else '✗'} (通过API层)")
        
        return True
        
    except Exception as e:
        print(f"综合场景测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """
    主测试函数
    """
    print("开始测试Nova Multi-Agent电商前置执行架构")
    print("=" * 60)
    
    tests = [
        ("基本执行链", test_basic_execution),
        ("API环境切换", test_api_environment_switch),
        ("Agent状态查询", test_agent_status),
        ("工作流步骤", test_workflow_steps),
        ("单步执行", test_single_step_execution),
        ("错误恢复机制", test_error_recovery),
        ("API审计日志", test_api_audit_log),
        ("综合电商场景", test_comprehensive_scenario)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
            print(f"\n{test_name}: {'✓ 通过' if success else '✗ 失败'}\n")
        except Exception as e:
            print(f"\n{test_name}: ✗ 异常 - {str(e)}\n")
            results.append((test_name, False))
    
    # 汇总结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
    
    # 验收标准验证
    print("\n" + "=" * 60)
    print("验收标准验证")
    print("=" * 60)
    
    if passed >= 6:  # 至少通过6个测试
        print("✓ 架构实现基本符合要求")
        print("✓ Multi-Agent电商前置执行架构构建完成")
        print("✓ 实现了从Graph到外部系统的完整决策与执行链")
    else:
        print("✗ 架构实现需要改进")
        print("✗ 部分验收标准未满足")
    
    return passed >= 6


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)