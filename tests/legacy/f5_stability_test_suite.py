"""
F5稳定性验证系统

验证系统是否真的"稳定"
要求：
1. 10次重复执行测试
2. graph path一致性检测
3. agent output一致性检测
4. 输出：f5_test_report.json
"""

import asyncio
import json
import time
from typing import Dict, Any, List
from datetime import datetime
import hashlib

from backend.core.state import State
from backend.workflow.deterministic_graph_engine import (
    DeterministicGraphEngine,
    GraphDefinition,
    NodeDefinition,
    NodeType
)

class F5StabilityTestSuite:
    """F5稳定性测试套件"""
    
    def __init__(self):
        self.engine = DeterministicGraphEngine()
        self.test_results = []
        self.report = {
            "test_name": "F5稳定性验证",
            "timestamp": datetime.now().isoformat(),
            "total_runs": 10,
            "consistency_requirements": {
                "graph_path_consistency": "100%",
                "agent_output_consistency": "100%",
                "no_graph_drift": True,
                "no_agent_responsibility_violation": True
            }
        }
    
    def create_test_graph(self) -> GraphDefinition:
        """创建测试图"""
        graph = GraphDefinition(
            graph_id="f5_stability_test_graph",
            version="1.0",
            description="F5稳定性测试图"
        )
        
        # 添加数据节点
        graph.add_node(NodeDefinition(
            node_id="validate_input",
            node_type=NodeType.DATA_NODE,
            config={
                "validate": {
                    "test_data": ["required"]
                }
            },
            next_node="process_data"
        ))
        
        # 添加Agent节点 - 使用正确的配置格式
        graph.add_node(NodeDefinition(
            node_id="process_data",
            node_type=NodeType.AGENT_NODE,
            config={
                "agent": "ai_analyzer",  # 注意：应该是"agent"而不是"agent_name"
                "params": {
                    "task": "stability_test"
                }
            },
            next_node="generate_output"
        ))
        
        # 添加输出节点
        graph.add_node(NodeDefinition(
            node_id="generate_output",
            node_type=NodeType.OUTPUT_NODE,
            config={
                "output_fields": ["result", "processed_data", "test_id"]
            }
        ))
        
        return graph
    
    def create_test_state(self, test_id: int) -> State:
        """创建测试状态"""
        test_data = {
            "test_id": test_id,
            "timestamp": time.time(),
            "data": {
                "sample_field": f"test_value_{test_id}",
                "numeric_value": test_id * 10,
                "array_data": [1, 2, 3, test_id]
            }
        }
        
        return State(
            data=test_data,
            metadata={
                "test_run": test_id,
                "environment": "stability_test",
                "request_id": f"f5_test_{test_id}"
            }
        )
    
    def calculate_hash(self, data: Any) -> str:
        """计算数据的哈希值用于一致性检查"""
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def extract_execution_path(self, result: Dict[str, Any]) -> List[str]:
        """提取执行路径"""
        execution_path = []
        if "execution_path" in result:
            for step in result["execution_path"]:
                if "node_id" in step:
                    execution_path.append(step["node_id"])
        return execution_path
    
    def check_agent_output_consistency(self, outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """检查Agent输出一致性"""
        if not outputs:
            return {
                "consistent": True, 
                "hash": None, 
                "details": "No outputs to compare",
                "consistency_rate": "0/0"
            }
        
        # 计算所有输出的哈希值
        hashes = []
        for output in outputs:
            # 提取Agent相关的输出部分
            agent_output = output.get("data", {}).get("processed_data", {})
            hash_value = self.calculate_hash(agent_output)
            hashes.append(hash_value)
        
        # 检查是否所有哈希值相同
        first_hash = hashes[0]
        all_same = all(h == first_hash for h in hashes)
        
        return {
            "consistent": all_same,
            "hash": first_hash if all_same else None,
            "hash_list": hashes,
            "consistency_rate": f"{hashes.count(first_hash)}/{len(hashes)}"
        }
    
    def check_graph_path_consistency(self, paths: List[List[str]]) -> Dict[str, Any]:
        """检查Graph路径一致性"""
        if not paths:
            return {
                "consistent": True, 
                "path": None, 
                "details": "No paths to compare",
                "consistency_rate": "0/0"
            }
        
        # 检查所有路径是否相同
        first_path = paths[0]
        all_same = all(p == first_path for p in paths)
        
        return {
            "consistent": all_same,
            "path": first_path if all_same else None,
            "path_list": paths,
            "consistency_rate": f"{paths.count(first_path)}/{len(paths)}"
        }
    
    async def run_single_test(self, test_id: int) -> Dict[str, Any]:
        """运行单次测试"""
        try:
            # 创建图和状态
            graph = self.create_test_graph()
            initial_state = self.create_test_state(test_id)
            
            # 执行Graph
            start_time = time.time()
            result = await self.engine.run_async(graph, initial_state)
            execution_time = time.time() - start_time
            
            # 提取结果信息
            execution_metadata = result.get("execution_metadata", {})
            execution_path = execution_metadata.get("actual_path", [])
            
            test_result = {
                "test_id": test_id,
                "success": True,
                "execution_time": execution_time,
                "execution_path": execution_path,
                "output": result.get("data", {}),
                "metadata": result.get("metadata", {}),
                "error": None
            }
            
            return test_result
            
        except Exception as e:
            return {
                "test_id": test_id,
                "success": False,
                "execution_time": 0,
                "execution_path": [],
                "output": {},
                "metadata": {},
                "error": str(e)
            }
    
    async def run_stability_test(self, num_runs: int = 10) -> Dict[str, Any]:
        """运行稳定性测试"""
        print("=" * 60)
        print("F5稳定性验证系统 - 开始测试")
        print("=" * 60)
        
        # 运行多次测试
        tasks = []
        for i in range(num_runs):
            print(f"运行测试 {i+1}/{num_runs}...")
            task = self.run_single_test(i + 1)
            tasks.append(task)
        
        # 等待所有测试完成
        results = await asyncio.gather(*tasks)
        self.test_results = results
        
        # 分析结果
        analysis = self.analyze_results()
        
        # 生成报告
        self.generate_report(analysis)
        
        return analysis
    
    def analyze_results(self) -> Dict[str, Any]:
        """分析测试结果"""
        successful_runs = [r for r in self.test_results if r["success"]]
        failed_runs = [r for r in self.test_results if not r["success"]]
        
        # 提取执行路径
        execution_paths = [r["execution_path"] for r in successful_runs]
        
        # 提取Agent输出
        agent_outputs = [r["output"] for r in successful_runs]
        
        # 检查一致性
        path_consistency = self.check_graph_path_consistency(execution_paths)
        output_consistency = self.check_agent_output_consistency(agent_outputs)
        
        # 检查Graph漂移
        graph_drift_detected = not path_consistency["consistent"]
        
        # 检查Agent职责越界
        agent_responsibility_violation = False
        for result in successful_runs:
            output = result.get("output", {})
            # 这里可以添加更复杂的Agent职责检查逻辑
            if "error" in output and "unauthorized" in str(output["error"]).lower():
                agent_responsibility_violation = True
                break
        
        return {
            "total_runs": len(self.test_results),
            "successful_runs": len(successful_runs),
            "failed_runs": len(failed_runs),
            "success_rate": f"{len(successful_runs)}/{len(self.test_results)}",
            "graph_path_consistency": path_consistency,
            "agent_output_consistency": output_consistency,
            "graph_drift_detected": graph_drift_detected,
            "agent_responsibility_violation": agent_responsibility_violation,
            "execution_times": [r.get("execution_time", 0) for r in successful_runs],
            "average_execution_time": sum(r.get("execution_time", 0) for r in successful_runs) / len(successful_runs) if successful_runs else 0
        }
    
    def generate_report(self, analysis: Dict[str, Any]):
        """生成测试报告"""
        self.report["test_results"] = self.test_results
        self.report["analysis"] = analysis
        
        # 计算总体通过率
        all_passed = (
            analysis["graph_path_consistency"]["consistent"] and
            analysis["agent_output_consistency"]["consistent"] and
            not analysis["graph_drift_detected"] and
            not analysis["agent_responsibility_violation"] and
            analysis["successful_runs"] == analysis["total_runs"]
        )
        
        self.report["overall_passed"] = all_passed
        self.report["verdict"] = "PASS" if all_passed else "FAIL"
        
        # 保存报告到文件
        report_filename = "f5_test_report.json"
        with open(report_filename, "w", encoding="utf-8") as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n测试报告已保存到: {report_filename}")
        
        # 打印摘要
        self.print_summary(analysis, all_passed)
    
    def print_summary(self, analysis: Dict[str, Any], all_passed: bool):
        """打印测试摘要"""
        print("\n" + "=" * 60)
        print("F5稳定性验证 - 测试摘要")
        print("=" * 60)
        
        print(f"总运行次数: {analysis['total_runs']}")
        print(f"成功次数: {analysis['successful_runs']}")
        print(f"失败次数: {analysis['failed_runs']}")
        print(f"成功率: {analysis['success_rate']}")
        print(f"平均执行时间: {analysis['average_execution_time']:.3f}秒")
        
        print(f"\nGraph路径一致性: {analysis['graph_path_consistency']['consistent']}")
        print(f"一致性率: {analysis['graph_path_consistency']['consistency_rate']}")
        
        print(f"\nAgent输出一致性: {analysis['agent_output_consistency']['consistent']}")
        print(f"一致性率: {analysis['agent_output_consistency']['consistency_rate']}")
        
        print(f"\nGraph漂移检测: {'未检测到' if not analysis['graph_drift_detected'] else '检测到漂移'}")
        print(f"Agent职责越界: {'未检测到' if not analysis['agent_responsibility_violation'] else '检测到越界'}")
        
        print(f"\n总体结果: {'通过' if all_passed else '失败'}")
        print("=" * 60)
        
        if all_passed:
            print("✅ F5稳定性验证通过！")
            print("系统满足以下要求：")
            print("  - Graph固定")
            print("  - Agent收敛")
            print("  - 无Graph漂移")
            print("  - 无Agent职责越界")
            print("  - 10次运行结构一致率 = 100%")
        else:
            print("❌ F5稳定性验证失败！")
            print("请检查以下问题：")
            if not analysis["graph_path_consistency"]["consistent"]:
                print("  - Graph路径不一致")
            if not analysis["agent_output_consistency"]["consistent"]:
                print("  - Agent输出不一致")
            if analysis["graph_drift_detected"]:
                print("  - 检测到Graph漂移")
            if analysis["agent_responsibility_violation"]:
                print("  - 检测到Agent职责越界")
            if analysis["successful_runs"] != analysis["total_runs"]:
                print("  - 有失败的测试运行")

async def main():
    """主函数"""
    test_suite = F5StabilityTestSuite()
    await test_suite.run_stability_test(num_runs=10)

if __name__ == "__main__":
    asyncio.run(main())