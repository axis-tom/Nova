"""
增强版电商Graph引擎
支持循环执行和闭环流程
"""

from typing import Dict, Any, List, Optional
from backend.core.state import State
from backend.workflow.graph_engine import GraphEngine
from backend.agents.ecommerce.planner import PlannerAgent
from backend.agents.ecommerce.analyst import AnalystAgent
from backend.agents.ecommerce.executor import ExecutorAgent
from backend.agents.ecommerce.judge_enhanced_complete import JudgeEnhancedAgentComplete
from backend.agents.ecommerce.memory import MemoryAgent
from backend.agents.ecommerce.api_layer import APILayer, get_api_layer
from backend.core.execution_result_manager import get_execution_result_manager
import time
import json
import uuid


class EcommerceGraphEnhanced(GraphEngine):
    """
    增强版电商Graph引擎
    
    新增功能：
    1. 执行结果回流到数据库
    2. 支持循环执行
    3. 集成增强版Judge Agent
    4. 实现完整闭环流程
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化增强版电商Graph引擎
        
        Args:
            config: 配置参数
        """
        super().__init__(config)
        
        # 初始化Agent
        self.planner = PlannerAgent()
        self.analyst = AnalystAgent()
        self.executor = ExecutorAgent()
        self.judge = JudgeEnhancedAgentComplete()  # 使用增强版Judge Agent
        self.memory = MemoryAgent()
        
        # 初始化API层
        self.api_layer = get_api_layer()
        
        # 初始化执行结果管理器
        self.result_manager = get_execution_result_manager()
        
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
            "success": False,
            "execution_id": None,
            "iteration_number": 1,
            "loop_id": None
        }
        
        # 循环执行配置
        self.loop_config = {
            "enabled": False,
            "type": "conditional",  # conditional, timed, continuous
            "max_iterations": 10,
            "condition": None,
            "interval_seconds": 3600  # 默认1小时
        }
    
    def run(self, initial_state: State) -> State:
        """
        执行完整电商闭环流程
        
        Args:
            initial_state: 初始状态
            
        Returns:
            最终状态
        """
        # 生成执行ID
        execution_id = f"exec_{uuid.uuid4().hex[:16]}"
        self.execution_state["execution_id"] = execution_id
        
        # 记录开始时间
        self.execution_state["start_time"] = time.time()
        self.execution_state["current_step"] = "initialize"
        
        # 初始化状态
        state = self._initialize_state(initial_state, execution_id)
        
        try:
            # 创建执行结果记录
            self._create_execution_record(state, execution_id)
            
            # 步骤1: 规划 (Planner Agent)
            self.execution_state["current_step"] = "plan"
            state = self._execute_planner(state)
            self.execution_state["completed_steps"].append("plan")
            self._add_action_log(execution_id, "planner", state.get("planner_executed", False))
            
            # 步骤2: 分析 (Analyst Agent)
            self.execution_state["current_step"] = "analyze"
            state = self._execute_analyst(state)
            self.execution_state["completed_steps"].append("analyze")
            self._add_action_log(execution_id, "analyst", state.get("analyst_executed", False))
            
            # 步骤3: 决策 (Graph决策)
            self.execution_state["current_step"] = "decide"
            state = self._make_decision(state)
            self.execution_state["completed_steps"].append("decide")
            self._add_action_log(execution_id, "decision", True)
            
            # 步骤4: 执行 (Executor Agent)
            self.execution_state["current_step"] = "execute"
            state = self._execute_executor(state)
            self.execution_state["completed_steps"].append("execute")
            self._add_action_log(execution_id, "executor", state.get("executor_executed", False))
            
            # 步骤5: 评估 (增强版Judge Agent)
            self.execution_state["current_step"] = "judge"
            state = self._execute_judge_enhanced(state)
            self.execution_state["completed_steps"].append("judge")
            self._add_action_log(execution_id, "judge", state.get("judge_executed", False))
            
            # 步骤6: 记忆 (Memory Agent)
            self.execution_state["current_step"] = "memorize"
            state = self._execute_memory(state)
            self.execution_state["completed_steps"].append("memorize")
            self._add_action_log(execution_id, "memory", state.get("memory_executed", False))
            
            # 步骤7: 完成
            self.execution_state["current_step"] = "finalize"
            state = self._finalize_execution(state)
            self.execution_state["completed_steps"].append("finalize")
            
            # 标记执行成功
            self.execution_state["success"] = True
            
            # 更新执行结果记录
            self._update_execution_record(execution_id, state, True)
            
            # 检查是否需要循环执行
            if self.loop_config["enabled"]:
                state = self._check_loop_condition(state, execution_id)
            
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
            
            # 更新执行结果记录
            self._update_execution_record(execution_id, state, False)
            
            # 执行错误处理
            state = self._handle_execution_error(state, e)
        
        # 记录结束时间
        self.execution_state["end_time"] = time.time()
        
        # 添加执行摘要
        state["execution_summary"] = self._generate_execution_summary()
        
        return state
    
    def _initialize_state(self, initial_state: State, execution_id: str) -> State:
        """
        初始化执行状态
        
        Args:
            initial_state: 初始状态
            execution_id: 执行ID
            
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
                "execution_id": execution_id,
                "start_time": time.time(),
                "graph_engine": "ecommerce_graph_enhanced",
                "version": "2.0",
                "iteration": self.execution_state["iteration_number"]
            }
        
        # 添加执行跟踪信息
        initial_state["execution_tracking"] = {
            "execution_id": execution_id,
            "steps_completed": [],
            "steps_failed": [],
            "current_step": "initialize",
            "start_time": time.time(),
            "iteration": self.execution_state["iteration_number"]
        }
        
        # 添加循环执行信息
        if self.loop_config["enabled"]:
            initial_state["loop_info"] = {
                "loop_id": self.execution_state.get("loop_id"),
                "iteration": self.execution_state["iteration_number"],
                "max_iterations": self.loop_config["max_iterations"],
                "loop_type": self.loop_config["type"]
            }
        
        return initial_state
    
    def _create_execution_record(self, state: State, execution_id: str):
        """
        创建执行结果记录
        
        Args:
            state: 状态
            execution_id: 执行ID
        """
        try:
            execution_data = {
                "execution_id": execution_id,
                "user_id": state.get("context", {}).get("user_id", 1),
                "graph_type": "ecommerce_graph_enhanced",
                "execution_type": state.get("execution_type", "unknown"),
                "status": "running",
                "input_data": {
                    "context": state.get("context", {}),
                    "data": state.get("data", {}),
                    "goal": state.get("goal", "unknown")
                },
                "iteration_number": self.execution_state["iteration_number"],
                "parent_execution_id": state.get("parent_execution_id"),
                "loop_id": self.execution_state.get("loop_id")
            }
            
            self.result_manager.create_execution_result(execution_data)
            
        except Exception as e:
            print(f"创建执行记录失败: {str(e)}")
    
    def _update_execution_record(self, execution_id: str, state: State, success: bool):
        """
        更新执行结果记录
        
        Args:
            execution_id: 执行ID
            state: 状态
            success: 是否成功
        """
        try:
            update_data = {
                "status": "success" if success else "failed",
                "output_data": {
                    "execution_result": state.get("execution_result", {}),
                    "evaluation_result": state.get("evaluation_result", {}),
                    "decision": state.get("decision", {})
                },
                "execution_log": state.get("execution_tracking", {}),
                "execution_time": time.time() - self.execution_state["start_time"],
                "api_calls": state.get("execution_result", {}).get("api_calls", 0),
                "success_rate": 100 if success else 0
            }
            
            # 添加评估分数
            if "evaluation_result" in state:
                eval_result = state["evaluation_result"]
                update_data["roi_score"] = eval_result.get("roi_score")
                update_data["conversion_score"] = eval_result.get("conversion_score")
                update_data["quality_score"] = eval_result.get("overall_score")
                update_data["judge_evaluation"] = eval_result
                update_data["optimization_suggestions"] = eval_result.get("optimization_suggestions", [])
            
            self.result_manager.update_execution_result(execution_id, update_data)
            
        except Exception as e:
            print(f"更新执行记录失败: {str(e)}")
    
    def _add_action_log(self, execution_id: str, action_type: str, success: bool):
        """
        添加操作日志
        
        Args:
            execution_id: 执行ID
            action_type: 操作类型
            success: 是否成功
        """
        try:
            action_data = {
                "action_type": "agent_execution",
                "action_name": action_type,
                "status": "success" if success else "failed",
                "timestamp": time.time()
            }
            
            self.result_manager.add_action_log(execution_id, action_data)
            
        except Exception as e:
            print(f"添加操作日志失败: {str(e)}")
    
    def _execute_judge_enhanced(self, state: State) -> State:
        """
        执行增强版Judge Agent
        
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
                "type": "comprehensive_evaluation",
                "scope": "full"
            }),
            "execution_result": state.get("execution_result", {}),
            "context": state.get("context", {})
        }
        
        # 添加业务数据
        if "business_data" not in judge_input["context"]:
            judge_input["context"]["business_data"] = {
                "api_cost_per_call": 0.01,
                "hourly_rate": 50,
                "infrastructure_cost": 0.1,
                "base_price": state.get("data", {}).get("base_price", 100),
                "estimated_quantity": state.get("data", {}).get("estimated_quantity", 100),
                "base_conversion_rate": 0.02,
                "estimated_visitors": 1000,
                "average_order_value": 100,
                "lost_sale_value": 50
            }
        
        # 更新状态
        state["judge_input"] = judge_input
        
        # 执行增强版Judge Agent
        judge_state = State(judge_input)
        judge_result = self.judge.run(judge_state)
        
        # 合并结果到状态
        state["evaluation_result"] = judge_result.get("evaluation_result", {})
        state["judge_executed"] = judge_result.get("judge_executed", False)
        state["judge_error"] = judge_result.get("judge_error")
        
        # 提取关键指标
        if "evaluation_result" in state:
            eval_result = state["evaluation_result"]
            state["roi_score"] = eval_result.get("roi_score", 0)
            state["conversion_score"] = eval_result.get("conversion_score", 0)
            state["optimization_decision"] = eval_result.get("optimization_decision", "unknown")
            state["optimization_suggestions"] = eval_result.get("optimization_suggestions", [])
        
        # 更新执行跟踪
        state["execution_tracking"]["steps_completed"].append("judge")
        
        return state
    
    def _check_loop_condition(self, state: State, execution_id: str) -> State:
        """
        检查循环执行条件
        
        Args:
            state: 当前状态
            execution_id: 当前执行ID
            
        Returns:
            更新后的状态
        """
        loop_type = self.loop_config["type"]
        max_iterations = self.loop_config["max_iterations"]
        current_iteration = self.execution_state["iteration_number"]
        
        # 检查是否达到最大迭代次数
        if max_iterations and current_iteration >= max_iterations:
            state["loop_completed"] = True
            state["loop_completion_reason"] = f"达到最大迭代次数: {max_iterations}"
            return state
        
        should_continue = False
        
        if loop_type == "conditional":
            # 条件循环：基于评估结果决定是否继续
            optimization_decision = state.get("optimization_decision", "")
            roi_score = state.get("roi_score", 0)
            
            if optimization_decision in ["continue_optimization", "adjust_and_continue", "accelerate_optimization"]:
                should_continue = True
            elif roi_score > 20:  # ROI大于20%继续
                should_continue = True
        
        elif loop_type == "timed":
            # 定时循环：基于时间间隔
            should_continue = True
        
        elif loop_type == "continuous":
            # 连续循环：一直继续直到手动停止
            should_continue = True
        
        if should_continue:
            # 准备下一次执行
            next_iteration = current_iteration + 1
            state["should_continue_loop"] = True
            state["next_iteration"] = next_iteration
            state["loop_continuation_reason"] = f"{loop_type}循环条件满足"
            
            # 更新循环执行记录
            if self.execution_state.get("loop_id"):
                self.result_manager.add_execution_to_loop(
                    self.execution_state["loop_id"],
                    execution_id
                )
        
        else:
            state["loop_completed"] = True
            state["loop_completion_reason"] = f"{loop_type}循环条件不满足"
        
        return state
    
    def enable_loop(self, loop_config: Dict[str, Any] = None):
        """
        启用循环执行
        
        Args:
            loop_config: 循环配置
        """
        self.loop_config["enabled"] = True
        
        if loop_config:
            self.loop_config.update(loop_config)
        
        # 生成循环ID
        if not self.execution_state.get("loop_id"):
            self.execution_state["loop_id"] = f"loop_{uuid.uuid4().hex[:16]}"
            
            # 创建循环执行记录
            loop_data = {
                "loop_id": self.execution_state["loop_id"],
                "user_id": 1,  # 默认用户ID
                "loop_type": self.loop_config["type"],
                "trigger_condition": self.loop_config.get("condition"),
                "schedule_config": {
                    "interval_seconds": self.loop_config.get("interval_seconds", 3600),
                    "max_iterations": self.loop_config.get("max_iterations", 10)
                },
                "status": "active",
                "current_iteration": 1,
                "total_iterations": self.loop_config.get("max_iterations", 10)
            }
            
            self.result_manager.create_loop_execution(loop_data)
    
    def disable_loop(self):
        """禁用循环执行"""
        self.loop_config["enabled"] = False
        
        # 更新循环执行记录状态
        if self.execution_state.get("loop_id"):
            self.result_manager.update_loop_execution(
                self.execution_state["loop_id"],
                {"status": "completed"}
            )
    
    def get_loop_info(self) -> Dict[str, Any]:
        """
        获取循环执行信息
        
        Returns:
            循环执行信息
        """
        return {
            "loop_enabled": self.loop_config["enabled"],
            "loop_type": self.loop_config["type"],
            "loop_id": self.execution_state.get("loop_id"),
            "current_iteration": self.execution_state["iteration_number"],
            "max_iterations": self.loop_config["max_iterations"],
            "completed_steps": self.execution_state["completed_steps"],
            "failed_steps": self.execution_state["failed_steps"],
            "success": self.execution_state["success"]
        }
    
    def _execute_planner(self, state: State) -> State:
        """
        执行Planner Agent
        
        Args:
            state: 当前状态
            
        Returns:
            Planner执行后的状态
        """
        # 简化实现，实际应该调用Planner Agent
        state["planner_executed"] = True
        state["plan"] = {
            "strategy": "price_optimization",
            "actions": ["analyze_market", "calculate_optimal_price", "update_price"],
            "priority": "high"
        }
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
        # 简化实现，实际应该调用Analyst Agent
        state["analyst_executed"] = True
        state["analysis_result"] = {
            "market_analysis": {
                "competitor_prices": [85.99, 92.50, 87.75, 94.99],
                "market_average": 90.31,
                "recommended_price": 91.50
            },
            "inventory_analysis": {
                "current_stock": 150,
                "optimal_stock": 180,
                "reorder_point": 30
            }
        }
        state["execution_tracking"]["steps_completed"].append("analyst")
        return state
    
    def _make_decision(self, state: State) -> State:
        """
        做出决策
        
        Args:
            state: 当前状态
            
        Returns:
            决策后的状态
        """
        # 基于分析结果做出决策
        analysis_result = state.get("analysis_result", {})
        market_analysis = analysis_result.get("market_analysis", {})
        
        state["decision"] = {
            "action": "adjust_price",
            "target_price": market_analysis.get("recommended_price", 89.99),
            "reason": "基于市场分析优化价格",
            "confidence": 0.85
        }
        state["execution_task"] = {
            "type": "update_product_price",
            "parameters": {
                "product_id": state.get("data", {}).get("product_id", "unknown"),
                "new_price": market_analysis.get("recommended_price", 89.99)
            }
        }
        state["execution_tracking"]["steps_completed"].append("decision")
        return state
    
    def _execute_executor(self, state: State) -> State:
        """
        执行Executor Agent
        
        Args:
            state: 当前状态
            
        Returns:
            Executor执行后的状态
        """
        # 简化实现，实际应该调用Executor Agent
        state["executor_executed"] = True
        state["execution_result"] = {
            "success": True,
            "api_calls": 2,
            "execution_time": 1.5,
            "data": {
                "price_adjustment": {
                    "old_price": 89.99,
                    "new_price": 91.50,
                    "change_percentage": 1.68
                },
                "conversion_data": {
                    "conversion_lift": 0.12
                }
            },
            "timestamp": time.time()
        }
        state["execution_tracking"]["steps_completed"].append("executor")
        return state
    
    def _execute_memory(self, state: State) -> State:
        """
        执行Memory Agent
        
        Args:
            state: 当前状态
            
        Returns:
            Memory执行后的状态
        """
        # 简化实现，实际应该调用Memory Agent
        state["memory_executed"] = True
        state["memory_result"] = {
            "learnings": [
                "价格调整1.68%可能带来12%的转化提升",
                "市场平均价格为90.31，新价格91.50具有竞争力"
            ],
            "recommendations": [
                "监控未来7天的销售数据",
                "考虑库存优化策略"
            ]
        }
        state["execution_tracking"]["steps_completed"].append("memory")
        return state
    
    def _finalize_execution(self, state: State) -> State:
        """
        完成执行
        
        Args:
            state: 当前状态
            
        Returns:
            完成后的状态
        """
        state["execution_completed"] = True
        state["execution_success"] = True
        state["execution_summary"] = {
            "total_steps": len(self.workflow_steps),
            "completed_steps": len(self.execution_state["completed_steps"]),
            "failed_steps": len(self.execution_state["failed_steps"]),
            "execution_time": time.time() - self.execution_state["start_time"],
            "success": self.execution_state["success"]
        }
        state["execution_tracking"]["steps_completed"].append("finalize")
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
        state["execution_error_handled"] = True
        state["error_recovery"] = {
            "action": "retry_later",
            "reason": str(error),
            "suggestions": ["检查网络连接", "验证API密钥", "重试执行"]
        }
        state["execution_tracking"]["steps_failed"].append(self.execution_state["current_step"])
        return state
    
    def _generate_execution_summary(self) -> Dict[str, Any]:
        """
        生成执行摘要
        
        Returns:
            执行摘要
        """
        execution_time = 0
        if self.execution_state["start_time"] and self.execution_state["end_time"]:
            execution_time = self.execution_state["end_time"] - self.execution_state["start_time"]
        
        return {
            "execution_id": self.execution_state["execution_id"],
            "loop_id": self.execution_state.get("loop_id"),
            "iteration": self.execution_state["iteration_number"],
            "start_time": self.execution_state["start_time"],
            "end_time": self.execution_state["end_time"],
            "execution_time": execution_time,
            "success": self.execution_state["success"],
            "completed_steps": self.execution_state["completed_steps"],
            "failed_steps": self.execution_state["failed_steps"],
            "current_step": self.execution_state["current_step"]
        }
