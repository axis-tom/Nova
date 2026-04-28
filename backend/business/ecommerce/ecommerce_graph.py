"""
Ecommerce Graph Engine - 电商前置执行Graph引擎
负责调度Multi-Agent执行链，实现从Graph到外部系统的完整决策与执行
"""

from typing import Dict, Any, List, Optional
from backend.foundation.cognition.state_machine.state_machine import State
from backend.foundation.cognition.state_machine.graph_engine import GraphEngine
from backend.business.ecommerce.planner import PlannerAgent
from backend.business.ecommerce.analyst import AnalystAgent
from backend.business.ecommerce.executor import ExecutorAgent
from backend.business.ecommerce.judge import JudgeAgent
from backend.business.ecommerce.memory import MemoryAgent
from backend.business.ecommerce.api_layer import APILayer, get_api_layer
import time
import json


class EcommerceGraphEngine(GraphEngine):
    """
    Ecommerce Graph Engine - 电商前置执行Graph引擎
    
    职责：
    1. 调度Multi-Agent执行链
    2. 管理执行流程状态
    3. 协调Agent间通信
    4. 处理执行结果和错误
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化Ecommerce Graph Engine
        
        Args:
            config: 配置参数
        """
        super().__init__(config)
        
        # 初始化Agent
        self.planner = PlannerAgent()
        self.analyst = AnalystAgent()
        self.executor = ExecutorAgent()
        self.judge = JudgeAgent()
        self.memory = MemoryAgent()
        
        # 初始化API层
        self.api_layer = get_api_layer()
        
        # 执行流程定义
        self.workflow_steps = [
            "initialize",
            "plan",
            "analyze",
            "decide",
            "execute",
            "judge",
            "memorize",
            "finalize"
        ]
        
        # 执行状态
        self.execution_state = {
            "current_step": None,
            "completed_steps": [],
            "failed_steps": [],
            "start_time": None,
            "end_time": None,
            "success": False
        }
    
    def run(self, initial_state: State) -> State:
        """
        执行完整电商前置执行链
        
        Args:
            initial_state: 初始状态
            
        Returns:
            最终状态
        """
        # 记录开始时间
        self.execution_state["start_time"] = time.time()
        self.execution_state["current_step"] = "initialize"
        
        # 初始化状态
        state = self._initialize_state(initial_state)
        
        try:
            # 步骤1: 规划 (Planner Agent)
            self.execution_state["current_step"] = "plan"
            state = self._execute_planner(state)
            self.execution_state["completed_steps"].append("plan")
            
            # 步骤2: 分析 (Analyst Agent)
            self.execution_state["current_step"] = "analyze"
            state = self._execute_analyst(state)
            self.execution_state["completed_steps"].append("analyze")
            
            # 步骤3: 决策 (Graph决策，不涉及Agent)
            self.execution_state["current_step"] = "decide"
            state = self._make_decision(state)
            self.execution_state["completed_steps"].append("decide")
            
            # 步骤4: 执行 (Executor Agent)
            self.execution_state["current_step"] = "execute"
            state = self._execute_executor(state)
            self.execution_state["completed_steps"].append("execute")
            
            # 步骤5: 评估 (Judge Agent)
            self.execution_state["current_step"] = "judge"
            state = self._execute_judge(state)
            self.execution_state["completed_steps"].append("judge")
            
            # 步骤6: 记忆 (Memory Agent)
            self.execution_state["current_step"] = "memorize"
            state = self._execute_memory(state)
            self.execution_state["completed_steps"].append("memorize")
            
            # 步骤7: 完成
            self.execution_state["current_step"] = "finalize"
            state = self._finalize_execution(state)
            self.execution_state["completed_steps"].append("finalize")
            
            # 标记执行成功
            self.execution_state["success"] = True
            
        except Exception as e:
            # 记录失败步骤
            current_step = self.execution_state["current_step"]
            self.execution_state["failed_steps"].append({
                "step": current_step,
                "error": str(e),
                "timestamp": time.time()
            })
            
            # 更新状态
            state["execution_error"] = str(e)
            state["execution_failed"] = True
            state["failed_step"] = current_step
            
            # 执行错误处理
            state = self._handle_execution_error(state, e)
        
        # 记录结束时间
        self.execution_state["end_time"] = time.time()
        
        # 添加执行摘要
        state["execution_summary"] = self._generate_execution_summary()
        
        return state
    
    def _initialize_state(self, initial_state: State) -> State:
        """
        初始化执行状态
        
        Args:
            initial_state: 初始状态
            
        Returns:
            初始化后的状态
        """
        # 确保状态包含必要字段
        if "context" not in initial_state:
            initial_state["context"] = {}
        
        if "data" not in initial_state:
            initial_state["data"] = {}
        
        if "metadata" not in initial_state:
            initial_state["metadata"] = {
                "execution_id": f"exec_{int(time.time())}",
                "start_time": time.time(),
                "graph_engine": "ecommerce_graph",
                "version": "1.0"
            }
        
        # 添加执行跟踪信息
        initial_state["execution_tracking"] = {
            "steps_completed": [],
            "steps_failed": [],
            "current_step": "initialize",
            "start_time": time.time()
        }
        
        return initial_state
    
    def _execute_planner(self, state: State) -> State:
        """
        执行Planner Agent
        
        Args:
            state: 当前状态
            
        Returns:
            Planner执行后的状态
        """
        # 准备Planner输入
        planner_input = {
            "planning_task": state.get("planning_task", {
                "type": "ecommerce_operation",
                "goal": state.get("goal", "执行电商操作"),
                "constraints": state.get("constraints", {})
            }),
            "data": state.get("data", {}),
            "context": state.get("context", {})
        }
        
        # 更新状态
        state["planner_input"] = planner_input
        
        # 执行Planner Agent
        planner_state = State(planner_input)
        planner_result = self.planner.run(planner_state)
        
        # 合并结果到状态
        state["planning_result"] = planner_result.get("planning_result", {})
        state["planner_executed"] = planner_result.get("planner_executed", False)
        state["planner_error"] = planner_result.get("planner_error")
        
        # 更新执行跟踪
        state["execution_tracking"]["steps_completed"].append("planner")
        
        return state
    
    def _execute_analyst(self, state: State) -> State:
        """
        执行Analyst Agent
        
        Args:
            state: 当前状态
            
        Returns:
            Analyst执行后的状态
        """
        # 准备Analyst输入
        analyst_input = {
            "analysis_task": state.get("analysis_task", {
                "type": "market_analysis",
                "scope": "comprehensive"
            }),
            "data": state.get("data", {}),
            "context": state.get("context", {})
        }
        
        # 如果有规划结果，添加到分析任务
        if "planning_result" in state:
            analyst_input["analysis_task"]["plan"] = state["planning_result"]
        
        # 更新状态
        state["analyst_input"] = analyst_input
        
        # 执行Analyst Agent
        analyst_state = State(analyst_input)
        analyst_result = self.analyst.run(analyst_state)
        
        # 合并结果到状态
        state["analysis_result"] = analyst_result.get("analysis_result", {})
        state["analyst_executed"] = analyst_result.get("analyst_executed", False)
        state["analyst_error"] = analyst_result.get("analyst_error")
        
        # 更新执行跟踪
        state["execution_tracking"]["steps_completed"].append("analyst")
        
        return state
    
    def _make_decision(self, state: State) -> State:
        """
        Graph决策（不涉及Agent）
        
        Args:
            state: 当前状态
            
        Returns:
            决策后的状态
        """
        # 基于规划和分析结果做出决策
        planning_result = state.get("planning_result", {})
        analysis_result = state.get("analysis_result", {})
        
        # 决策逻辑
        decision = {
            "action": "proceed",  # proceed, adjust, abort
            "reason": "基于规划和分析结果",
            "timestamp": time.time()
        }
        
        # 检查规划和分析是否成功
        if not state.get("planner_executed", False):
            decision["action"] = "abort"
            decision["reason"] = "规划失败"
        elif not state.get("analyst_executed", False):
            decision["action"] = "abort"
            decision["reason"] = "分析失败"
        
        # 检查分析结果中的风险
        if "analysis_result" in state:
            risks = analysis_result.get("risks", [])
            high_risks = [r for r in risks if r.get("severity") in ["high", "critical"]]
            
            if high_risks:
                decision["action"] = "adjust"
                decision["reason"] = f"发现{len(high_risks)}个高风险"
                decision["risk_details"] = high_risks
        
        # 更新状态
        state["decision"] = decision
        
        # 根据决策调整执行计划
        if decision["action"] == "proceed":
            # 正常执行
            state["execution_plan"] = planning_result.get("execution_plan", {})
        elif decision["action"] == "adjust":
            # 调整执行计划
            state["execution_plan"] = self._adjust_execution_plan(planning_result, analysis_result)
        elif decision["action"] == "abort":
            # 中止执行
            state["execution_aborted"] = True
            state["abort_reason"] = decision["reason"]
        
        # 更新执行跟踪
        state["execution_tracking"]["steps_completed"].append("decision")
        
        return state
    
    def _adjust_execution_plan(self, planning_result: Dict[str, Any], 
                              analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        调整执行计划
        
        Args:
            planning_result: 规划结果
            analysis_result: 分析结果
            
        Returns:
            调整后的执行计划
        """
        original_plan = planning_result.get("execution_plan", {})
        
        # 基于分析结果调整计划
        adjusted_plan = original_plan.copy()
        
        # 添加风险缓解措施
        risks = analysis_result.get("risks", [])
        if risks:
            adjusted_plan["risk_mitigation"] = {
                "risks_identified": len(risks),
                "mitigation_strategies": [
                    {
                        "risk": risk.get("type", "unknown"),
                        "mitigation": risk.get("mitigation", "采取适当措施")
                    }
                    for risk in risks
                ]
            }
        
        # 基于洞察优化计划
        insights = analysis_result.get("insights", [])
        if insights:
            adjusted_plan["optimizations"] = [
                {
                    "insight": insight.get("type", "unknown"),
                    "action": insight.get("action", "优化执行")
                }
                for insight in insights
            ]
        
        adjusted_plan["adjusted_at"] = time.time()
        adjusted_plan["adjustment_reason"] = "基于分析结果优化"
        
        return adjusted_plan
    
    def _execute_executor(self, state: State) -> State:
        """
        执行Executor Agent
        
        Args:
            state: 当前状态
            
        Returns:
            Executor执行后的状态
        """
        # 检查是否中止执行
        if state.get("execution_aborted", False):
            state["executor_skipped"] = True
            state["executor_skip_reason"] = "执行已中止"
            state["execution_tracking"]["steps_completed"].append("executor_skipped")
            return state
        
        # 准备Executor输入
        executor_input = {
            "execution_task": state.get("execution_task", {
                "type": "general_api",
                "priority": "normal"
            }),
            "parameters": state.get("execution_plan", {}).get("parameters", {}),
            "context": state.get("context", {})
        }
        
        # 添加执行计划
        if "execution_plan" in state:
            executor_input["execution_plan"] = state["execution_plan"]
        
        # 更新状态
        state["executor_input"] = executor_input
        
        # 执行Executor Agent
        executor_state = State(executor_input)
        executor_result = self.executor.run(executor_state)
        
        # 合并结果到状态
        state["execution_result"] = executor_result.get("execution_result", {})
        state["executor_executed"] = executor_result.get("executor_executed", False)
        state["executor_error"] = executor_result.get("executor_error")
        
        # 更新执行跟踪
        state["execution_tracking"]["steps_completed"].append("executor")
        
        return state
    
    def _execute_judge(self, state: State) -> State:
        """
        执行Judge Agent
        
        Args:
            state: 当前状态
            
        Returns:
            Judge执行后的状态
        """
        # 检查是否跳过执行
        if state.get("executor_skipped", False):
            state["judge_skipped"] = True
            state["judge_skip_reason"] = "执行已跳过"
            state["execution_tracking"]["steps_completed"].append("judge_skipped")
            return state
        
        # 准备Judge输入
        judge_input = {
            "evaluation_task": state.get("evaluation_task", {
                "type": "quality_assessment",
                "scope": "comprehensive"
            }),
            "execution_result": state.get("execution_result", {}),
            "context": state.get("context", {})
        }
        
        # 更新状态
        state["judge_input"] = judge_input
        
        # 执行Judge Agent
        judge_state = State(judge_input)
        judge_result = self.judge.run(judge_state)
        
        # 合并结果到状态
        state["evaluation_result"] = judge_result.get("evaluation_result", {})
        state["judge_executed"] = judge_result.get("judge_executed", False)
        state["judge_error"] = judge_result.get("judge_error")
        
        # 更新执行跟踪
        state["execution_tracking"]["steps_completed"].append("judge")
        
        return state
    
    def _execute_memory(self, state: State) -> State:
        """
        执行Memory Agent
        
        Args:
            state: 当前状态
            
        Returns:
            Memory执行后的状态
        """
        # 准备Memory输入
        memory_data = {
            "execution_summary": self._generate_execution_summary(),
            "agent_results": {
                "planner": {
                    "executed": state.get("planner_executed", False),
                    "error": state.get("planner_error"),
                    "result": state.get("planning_result", {})
                },
                "analyst": {
                    "executed": state.get("analyst_executed", False),
                    "error": state.get("analyst_error"),
                    "result": state.get("analysis_result", {})
                },
                "executor": {
                    "executed": state.get("executor_executed", False),
                    "error": state.get("executor_error"),
                    "result": state.get("execution_result", {})
                },
                "judge": {
                    "executed": state.get("judge_executed", False),
                    "error": state.get("judge_error"),
                    "result": state.get("evaluation_result", {})
                }
            },
            "graph_decision": state.get("decision", {}),
            "execution_status": {
                "success": not state.get("execution_failed", False),
                "failed": state.get("execution_failed", False),
                "aborted": state.get("execution_aborted", False)
            }
        }
        
        memory_input = {
            "memory_operation": {
                "type": "store",
                "purpose": "记录执行历史"
            },
            "data": memory_data,
            "context": {
                "agent": "ecommerce_graph",
                "operation": "complete_execution",
                "tags": ["ecommerce", "execution", "learning"],
                "importance": 8  # 高重要性
            }
        }
        
        # 更新状态
        state["memory_input"] = memory_input
        
        # 执行Memory Agent
        memory_state = State(memory_input)
        memory_result = self.memory.run(memory_state)
        
        # 合并结果到状态
        state["memory_result"] = memory_result.get("memory_result", {})
        state["memory_executed"] = memory_result.get("memory_executed", False)
        state["memory_error"] = memory_result.get("memory_error")
        
        # 更新执行跟踪
        state["execution_tracking"]["steps_completed"].append("memory")
        
        return state
    
    def _finalize_execution(self, state: State) -> State:
        """
        完成执行
        
        Args:
            state: 当前状态
            
        Returns:
            最终状态
        """
        # 计算执行时间
        start_time = state["execution_tracking"]["start_time"]
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 更新执行跟踪
        state["execution_tracking"]["end_time"] = end_time
        state["execution_tracking"]["execution_time"] = execution_time
        state["execution_tracking"]["current_step"] = "completed"
        
        # 生成执行摘要
        execution_summary = self._generate_execution_summary()
        state["execution_summary"] = execution_summary
        
        # 标记执行完成
        state["execution_completed"] = True
        state["execution_success"] = not state.get("execution_failed", False)
        
        # 添加性能指标
        state["performance_metrics"] = {
            "total_execution_time": execution_time,
            "steps_completed": len(state["execution_tracking"]["steps_completed"]),
            "steps_failed": len(state["execution_tracking"]["steps_failed"]),
            "agent_success_rates": {
                "planner": state.get("planner_executed", False),
                "analyst": state.get("analyst_executed", False),
                "executor": state.get("executor_executed", False),
                "judge": state.get("judge_executed", False),
                "memory": state.get("memory_executed", False)
            }
        }
        
        return state
    
    def _handle_execution_error(self, state: State, error: Exception) -> State:
        """
        处理执行错误
        
        Args:
            state: 当前状态
            error: 错误对象
            
        Returns:
            错误处理后的状态
        """
        # 记录错误
        state["execution_tracking"]["steps_failed"].append({
            "step": self.execution_state["current_step"],
            "error": str(error),
            "timestamp": time.time()
        })
        
        # 尝试恢复或回滚
        recovery_result = self._attempt_recovery(state, error)
        
        if recovery_result.get("success", False):
            state["recovery_attempted"] = True
            state["recovery_success"] = True
            state["recovery_details"] = recovery_result
        else:
            state["recovery_attempted"] = True
            state["recovery_success"] = False
            state["recovery_details"] = recovery_result
        
        return state
    
    def _attempt_recovery(self, state: State, error: Exception) -> Dict[str, Any]:
        """
        尝试恢复执行
        
        Args:
            state: 当前状态
            error: 错误对象
            
        Returns:
            恢复结果
        """
        current_step = self.execution_state["current_step"]
        
        recovery_strategies = {
            "plan": self._recover_from_plan_failure,
            "analyze": self._recover_from_analyze_failure,
            "execute": self._recover_from_execute_failure,
            "judge": self._recover_from_judge_failure,
            "memory": self._recover_from_memory_failure
        }
        
        if current_step in recovery_strategies:
            return recovery_strategies[current_step](state, error)
        else:
            return {
                "success": False,
                "strategy": "no_recovery_strategy",
                "message": f"没有为步骤'{current_step}'定义恢复策略",
                "error": str(error)
            }
    
    def _recover_from_plan_failure(self, state: State, error: Exception) -> Dict[str, Any]:
        """
        从规划失败中恢复
        
        Args:
            state: 当前状态
            error: 错误对象
            
        Returns:
            恢复结果
        """
        # 简化规划任务
        simplified_task = {
            "type": "simple_operation",
            "goal": "执行基本电商操作",
            "constraints": {"simplified": True}
        }
        
        state["planning_task"] = simplified_task
        
        return {
            "success": True,
            "strategy": "simplify_planning",
            "message": "使用简化规划任务重试",
            "simplified_task": simplified_task
        }
    
    def _recover_from_analyze_failure(self, state: State, error: Exception) -> Dict[str, Any]:
        """
        从分析失败中恢复
        
        Args:
            state: 当前状态
            error: 错误对象
            
        Returns:
            恢复结果
        """
        # 跳过详细分析，使用基本分析
        basic_analysis = {
            "analysis_type": "basic_analysis",
            "insights": [{"type": "recovery_mode", "description": "从分析失败中恢复"}],
            "risks": [{"type": "analysis_failed", "severity": "medium", "mitigation": "谨慎执行"}]
        }
        
        state["analysis_result"] = basic_analysis
        state["analyst_executed"] = True
        
        return {
            "success": True,
            "strategy": "skip_detailed_analysis",
            "message": "使用基本分析结果继续执行",
            "basic_analysis": basic_analysis
        }
    
    def _recover_from_execute_failure(self, state: State, error: Exception) -> Dict[str, Any]:
        """
        从执行失败中恢复
        
        Args:
            state: 当前状态
            error: 错误对象
            
        Returns:
            恢复结果
        """
        # 使用模拟执行
        mock_execution = {
            "success": True,
            "api_calls": 0,
            "execution_time": 0.1,
            "mock_execution": True,
            "message": "模拟执行（实际执行失败）"
        }
        
        state["execution_result"] = mock_execution
        state["executor_executed"] = True
        
        return {
            "success": True,
            "strategy": "mock_execution",
            "message": "使用模拟执行结果继续",
            "mock_execution": mock_execution
        }
    
    def _recover_from_judge_failure(self, state: State, error: Exception) -> Dict[str, Any]:
        """
        从评估失败中恢复
        
        Args:
            state: 当前状态
            error: 错误对象
            
        Returns:
            恢复结果
        """
        # 使用基本评估
        basic_evaluation = {
            "overall_score": 50,
            "evaluation_type": "basic_recovery",
            "message": "从评估失败中恢复，使用基本评估"
        }
        
        state["evaluation_result"] = basic_evaluation
        state["judge_executed"] = True
        
        return {
            "success": True,
            "strategy": "basic_evaluation",
            "message": "使用基本评估结果",
            "basic_evaluation": basic_evaluation
        }
    
    def _recover_from_memory_failure(self, state: State, error: Exception) -> Dict[str, Any]:
        """
        从记忆失败中恢复
        
        Args:
            state: 当前状态
            error: 错误对象
            
        Returns:
            恢复结果
        """
        # 跳过记忆存储
        state["memory_skipped"] = True
        state["memory_skip_reason"] = str(error)
        
        return {
            "success": True,
            "strategy": "skip_memory",
            "message": "跳过记忆存储，继续执行",
            "skip_reason": str(error)
        }
    
    def _generate_execution_summary(self) -> Dict[str, Any]:
        """
        生成执行摘要
        
        Returns:
            执行摘要
        """
        execution_time = 0
        if self.execution_state["start_time"] and self.execution_state["end_time"]:
            execution_time = self.execution_state["end_time"] - self.execution_state["start_time"]
        
        summary = {
            "execution_id": f"exec_{int(time.time())}",
            "graph_engine": "ecommerce_graph",
            "version": "1.0",
            "start_time": self.execution_state["start_time"],
            "end_time": self.execution_state["end_time"],
            "execution_time": execution_time,
            "success": self.execution_state["success"],
            "completed_steps": self.execution_state["completed_steps"],
            "failed_steps": self.execution_state["failed_steps"],
            "total_steps": len(self.workflow_steps),
            "completion_rate": len(self.execution_state["completed_steps"]) / len(self.workflow_steps) * 100 if self.workflow_steps else 0,
            "timestamp": time.time()
        }
        
        return summary
    
    def get_execution_status(self) -> Dict[str, Any]:
        """
        获取执行状态
        
        Returns:
            执行状态
        """
        return self.execution_state.copy()
    
    def reset_execution(self) -> None:
        """
        重置执行状态
        """
        self.execution_state = {
            "current_step": None,
            "completed_steps": [],
            "failed_steps": [],
            "start_time": None,
            "end_time": None,
            "success": False
        }
    
    def set_api_environment(self, environment: str) -> None:
        """
        设置API环境
        
        Args:
            environment: 环境名称 (sandbox, production, staging)
        """
        self.api_layer.set_environment(environment)
    
    def get_api_audit_log(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取API审计日志
        
        Args:
            limit: 返回条数限制
            
        Returns:
            API审计日志
        """
        return self.api_layer.get_audit_log(limit=limit)
    
    def validate_input(self, state: State) -> bool:
        """
        验证输入状态
        
        Args:
            state: 输入状态
            
        Returns:
            是否有效
        """
        # 基本验证
        if not state or not isinstance(state, State):
            return False
        
        # 检查必要字段
        required_fields = ["context", "data"]
        for field in required_fields:
            if field not in state:
                return False
        
        return True
    
    def get_agent_status(self) -> Dict[str, Any]:
        """
        获取Agent状态
        
        Returns:
            Agent状态信息
        """
        return {
            "planner": {
                "name": self.planner.name,
                "description": self.planner.description,
                "initialized": True
            },
            "analyst": {
                "name": self.analyst.name,
                "description": self.analyst.description,
                "initialized": True
            },
            "executor": {
                "name": self.executor.name,
                "description": self.executor.description,
                "initialized": True
            },
            "judge": {
                "name": self.judge.name,
                "description": self.judge.description,
                "initialized": True
            },
            "memory": {
                "name": self.memory.name,
                "description": self.memory.description,
                "initialized": True
            }
        }
    
    def execute_single_step(self, step: str, state: State) -> State:
        """
        执行单个步骤
        
        Args:
            step: 步骤名称
            state: 当前状态
            
        Returns:
            执行后的状态
        """
        step_handlers = {
            "plan": self._execute_planner,
            "analyze": self._execute_analyst,
            "decide": self._make_decision,
            "execute": self._execute_executor,
            "judge": self._execute_judge,
            "memorize": self._execute_memory
        }
        
        if step in step_handlers:
            return step_handlers[step](state)
        else:
            raise ValueError(f"不支持的步骤: {step}")
    
    def get_workflow_steps(self) -> List[str]:
        """
        获取工作流步骤
        
        Returns:
            工作流步骤列表
        """
        return self.workflow_steps.copy()
