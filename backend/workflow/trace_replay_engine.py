"""
Trace回放引擎
用于回放已记录的Graph执行过程
支持完整回放、逐节点回放和部分回放
"""

from typing import Dict, Any, Union, List, Optional
from backend.core.state import State
from backend.core.trace_manager import get_trace_manager
from backend.agents.registry import AgentRegistry
import asyncio
import copy


class TraceReplayEngine:
    """
    Trace回放引擎
    
    特性：
    1. 完整回放：完全按照原始执行过程重新执行
    2. 逐节点回放：可以单步执行每个节点
    3. 部分回放：只回放指定范围的节点
    4. 对比分析：比较回放结果与原始结果
    """
    
    def __init__(self, db=None, user_id=None):
        """
        初始化TraceReplayEngine
        
        Args:
            db: 数据库会话（可选）
            user_id: 用户ID（可选）
        """
        self.db = db
        self.user_id = user_id
        self.trace_manager = None
        
        if self.db:
            self.trace_manager = get_trace_manager(self.db)
    
    def replay_trace(
        self,
        trace_id: str,
        replay_type: str = "full",
        start_node: str = None,
        end_node: str = None,
        step_by_step: bool = False
    ) -> Dict[str, Any]:
        """
        回放追踪会话
        
        Args:
            trace_id: 追踪会话ID
            replay_type: 回放类型（full, partial）
            start_node: 起始节点（用于部分回放）
            end_node: 结束节点（用于部分回放）
            step_by_step: 是否逐节点回放
            
        Returns:
            回放结果字典
        """
        if not self.trace_manager:
            raise ValueError("Trace manager not initialized")
        
        # 获取原始追踪会话
        trace_session = self.trace_manager.get_trace_session(trace_id)
        if not trace_session:
            raise ValueError(f"Trace session with id {trace_id} not found")
        
        # 获取原始节点记录
        trace_nodes = self.trace_manager.get_trace_nodes(trace_id)
        if not trace_nodes:
            raise ValueError(f"No nodes found for trace session {trace_id}")
        
        # 创建回放记录
        replay_id = self.trace_manager.replay_trace(
            trace_id=trace_id,
            replay_type=replay_type,
            start_node=start_node,
            end_node=end_node
        )
        
        try:
            # 准备初始状态
            initial_state = trace_session.get("initial_state", {})
            if isinstance(initial_state, dict) and "data" in initial_state:
                # 如果是State对象的字典表示
                state = State.from_dict(initial_state)
            else:
                # 如果是普通字典
                state = State(initial_state)
            
            # 设置追踪ID
            state.set_meta("original_trace_id", trace_id)
            state.set_meta("replay_id", replay_id)
            state.set_meta("replay_type", replay_type)
            
            # 获取Graph配置
            graph_config = trace_session.get("graph_config", {})
            if not graph_config:
                raise ValueError("Graph configuration not found in trace session")
            
            # 筛选要回放的节点
            nodes_to_replay = self._filter_nodes_for_replay(
                trace_nodes, replay_type, start_node, end_node
            )
            
            replay_results = []
            replay_errors = []
            
            # 执行回放
            for node_record in nodes_to_replay:
                node_id = node_record["node_id"]
                agent_name = node_record["agent_name"]
                
                # 记录回放开始
                state.log(f"开始回放节点: {node_id} (Agent: {agent_name})")
                
                if step_by_step:
                    # 逐节点回放：等待用户确认
                    # 在实际应用中，这里可以添加等待用户交互的逻辑
                    pass
                
                try:
                    # 获取智能体实例
                    if self.db is not None:
                        agent = AgentRegistry.get(agent_name, self.db)
                    else:
                        agent = AgentRegistry.get(agent_name)
                    
                    # 适配智能体
                    adapted_agent = self._adapt_agent(agent)
                    
                    # 执行智能体
                    result = adapted_agent.run(state)
                    
                    # 处理执行结果
                    if isinstance(result, dict) and "state" in result:
                        # 新的规范格式
                        state_dict = result["state"]
                        status = result.get("status", "ok")
                        
                        # 更新状态
                        state = State(state_dict)
                        
                        # 记录回放结果
                        replay_result = {
                            "node_id": node_id,
                            "agent_name": agent_name,
                            "status": status,
                            "original_status": node_record.get("status"),
                            "match": status == node_record.get("status", "completed")
                        }
                        
                        if status == "error":
                            error_msg = result.get("error", "Unknown error")
                            replay_result["error"] = error_msg
                            replay_errors.append({
                                "node_id": node_id,
                                "error": error_msg
                            })
                        
                        replay_results.append(replay_result)
                        
                    else:
                        # 兼容旧格式
                        state = State(result)
                        
                        replay_result = {
                            "node_id": node_id,
                            "agent_name": agent_name,
                            "status": "completed",
                            "original_status": node_record.get("status"),
                            "match": node_record.get("status") == "completed"
                        }
                        replay_results.append(replay_result)
                    
                    state.log(f"节点回放完成: {node_id} (Agent: {agent_name})")
                    
                except Exception as e:
                    # 记录回放错误
                    error_msg = str(e)
                    replay_result = {
                        "node_id": node_id,
                        "agent_name": agent_name,
                        "status": "error",
                        "original_status": node_record.get("status"),
                        "match": node_record.get("status") == "error",
                        "error": error_msg
                    }
                    replay_results.append(replay_result)
                    replay_errors.append({
                        "node_id": node_id,
                        "error": error_msg
                    })
                    
                    state.log(f"节点回放失败: {node_id} (Agent: {agent_name}): {error_msg}")
            
            # 计算回放统计
            total_nodes = len(replay_results)
            successful_nodes = sum(1 for r in replay_results if r["status"] == "completed")
            matching_nodes = sum(1 for r in replay_results if r.get("match", False))
            
            # 准备回放结果
            replay_result = {
                "replay_id": replay_id,
                "original_trace_id": trace_id,
                "replay_type": replay_type,
                "start_node": start_node,
                "end_node": end_node,
                "step_by_step": step_by_step,
                "statistics": {
                    "total_nodes": total_nodes,
                    "successful_nodes": successful_nodes,
                    "failed_nodes": total_nodes - successful_nodes,
                    "matching_nodes": matching_nodes,
                    "mismatching_nodes": total_nodes - matching_nodes,
                    "success_rate": successful_nodes / total_nodes if total_nodes > 0 else 0,
                    "match_rate": matching_nodes / total_nodes if total_nodes > 0 else 0
                },
                "results": replay_results,
                "errors": replay_errors,
                "final_state": state.to_dict()
            }
            
            # 更新回放记录
            self._update_replay_record(replay_id, replay_result, replay_errors)
            
            return replay_result
            
        except Exception as e:
            # 记录回放失败
            error_msg = str(e)
            replay_errors.append({
                "stage": "replay_execution",
                "error": error_msg
            })
            
            replay_result = {
                "replay_id": replay_id,
                "original_trace_id": trace_id,
                "status": "failed",
                "error": error_msg,
                "errors": replay_errors
            }
            
            self._update_replay_record(replay_id, replay_result, replay_errors)
            
            raise
    
    async def replay_trace_async(
        self,
        trace_id: str,
        replay_type: str = "full",
        start_node: str = None,
        end_node: str = None,
        step_by_step: bool = False
    ) -> Dict[str, Any]:
        """
        异步回放追踪会话
        
        Args:
            trace_id: 追踪会话ID
            replay_type: 回放类型（full, partial）
            start_node: 起始节点（用于部分回放）
            end_node: 结束节点（用于部分回放）
            step_by_step: 是否逐节点回放
            
        Returns:
            回放结果字典
        """
        if not self.trace_manager:
            raise ValueError("Trace manager not initialized")
        
        # 获取原始追踪会话
        trace_session = self.trace_manager.get_trace_session(trace_id)
        if not trace_session:
            raise ValueError(f"Trace session with id {trace_id} not found")
        
        # 获取原始节点记录
        trace_nodes = self.trace_manager.get_trace_nodes(trace_id)
        if not trace_nodes:
            raise ValueError(f"No nodes found for trace session {trace_id}")
        
        # 创建回放记录
        replay_id = self.trace_manager.replay_trace(
            trace_id=trace_id,
            replay_type=replay_type,
            start_node=start_node,
            end_node=end_node
        )
        
        try:
            # 准备初始状态
            initial_state = trace_session.get("initial_state", {})
            if isinstance(initial_state, dict) and "data" in initial_state:
                # 如果是State对象的字典表示
                state = State.from_dict(initial_state)
            else:
                # 如果是普通字典
                state = State(initial_state)
            
            # 设置追踪ID
            state.set_meta("original_trace_id", trace_id)
            state.set_meta("replay_id", replay_id)
            state.set_meta("replay_type", replay_type)
            
            # 获取Graph配置
            graph_config = trace_session.get("graph_config", {})
            if not graph_config:
                raise ValueError("Graph configuration not found in trace session")
            
            # 筛选要回放的节点
            nodes_to_replay = self._filter_nodes_for_replay(
                trace_nodes, replay_type, start_node, end_node
            )
            
            replay_results = []
            replay_errors = []
            
            # 执行回放
            for node_record in nodes_to_replay:
                node_id = node_record["node_id"]
                agent_name = node_record["agent_name"]
                
                # 记录回放开始
                state.log(f"开始异步回放节点: {node_id} (Agent: {agent_name})")
                
                if step_by_step:
                    # 逐节点回放：等待用户确认
                    # 在实际应用中，这里可以添加等待用户交互的逻辑
                    pass
                
                try:
                    # 获取智能体实例
                    if self.db is not None:
                        agent = AgentRegistry.get(agent_name, self.db)
                    else:
                        agent = AgentRegistry.get(agent_name)
                    
                    # 适配智能体
                    adapted_agent = self._adapt_agent_async(agent)
                    
                    # 执行智能体
                    if hasattr(adapted_agent, 'run_async'):
                        result = await adapted_agent.run_async(state)
                    else:
                        result = await asyncio.to_thread(adapted_agent.run, state)
                    
                    # 处理执行结果
                    if isinstance(result, dict) and "state" in result:
                        # 新的规范格式
                        state_dict = result["state"]
                        status = result.get("status", "ok")
                        
                        # 更新状态
                        state = State(state_dict)
                        
                        # 记录回放结果
                        replay_result = {
                            "node_id": node_id,
                            "agent_name": agent_name,
                            "status": status,
                            "original_status": node_record.get("status"),
                            "match": status == node_record.get("status", "completed")
                        }
                        
                        if status == "error":
                            error_msg = result.get("error", "Unknown error")
                            replay_result["error"] = error_msg
                            replay_errors.append({
                                "node_id": node_id,
                                "error": error_msg
                            })
                        
                        replay_results.append(replay_result)
                        
                    else:
                        # 兼容旧格式
                        state = State(result)
                        
                        replay_result = {
                            "node_id": node_id,
                            "agent_name": agent_name,
                            "status": "completed",
                            "original_status": node_record.get("status"),
                            "match": node_record.get("status") == "completed"
                        }
                        replay_results.append(replay_result)
                    
                    state.log(f"节点异步回放完成: {node_id} (Agent: {agent_name})")
                    
                except Exception as e:
                    # 记录回放错误
                    error_msg = str(e)
                    replay_result = {
                        "node_id": node_id,
                        "agent_name": agent_name,
                        "status": "error",
                        "original_status": node_record.get("status"),
                        "match": node_record.get("status") == "error",
                        "error": error_msg
                    }
                    replay_results.append(replay_result)
                    replay_errors.append({
                        "node_id": node_id,
                        "error": error_msg
                    })
                    
                    state.log(f"节点异步回放失败: {node_id} (Agent: {agent_name}): {error_msg}")
            
            # 计算回放统计
            total_nodes = len(replay_results)
            successful_nodes = sum(1 for r in replay_results if r["status"] == "completed")
            matching_nodes = sum(1 for r in replay_results if r.get("match", False))
            
            # 准备回放结果
            replay_result = {
                "replay_id": replay_id,
                "original_trace_id": trace_id,
                "replay_type": replay_type,
                "start_node": start_node,
                "end_node": end_node,
                "step_by_step": step_by_step,
                "statistics": {
                    "total_nodes": total_nodes,
                    "successful_nodes": successful_nodes,
                    "failed_nodes": total_nodes - successful_nodes,
                    "matching_nodes": matching_nodes,
                    "mismatching_nodes": total_nodes - matching_nodes,
                    "success_rate": successful_nodes / total_nodes if total_nodes > 0 else 0,
                    "match_rate": matching_nodes / total_nodes if total_nodes > 0 else 0
                },
                "results": replay_results,
                "errors": replay_errors,
                "final_state": state.to_dict()
            }
            
            # 更新回放记录
            self._update_replay_record(replay_id, replay_result, replay_errors)
            
            return replay_result
            
        except Exception as e:
            # 记录回放失败
            error_msg = str(e)
            replay_errors.append({
                "stage": "replay_execution",
                "error": error_msg
            })
            
            replay_result = {
                "replay_id": replay_id,
                "original_trace_id": trace_id,
                "status": "failed",
                "error": error_msg,
                "errors": replay_errors
            }
            
            self._update_replay_record(replay_id, replay_result, replay_errors)
            
            raise
    
    def step_replay(
        self,
        trace_id: str,
        current_node: str = None,
        state: Union[Dict[str, Any], State] = None
    ) -> Dict[str, Any]:
        """
        单步回放
        
        Args:
            trace_id: 追踪会话ID
            current_node: 当前节点ID，如果为None则从第一个节点开始
            state: 当前状态，如果为None则使用初始状态
            
        Returns:
            单步回放结果
        """
        if not self.trace_manager:
            raise ValueError("Trace manager not initialized")
        
        # 获取原始追踪会话
        trace_session = self.trace_manager.get_trace_session(trace_id)
        if not trace_session:
            raise ValueError(f"Trace session with id {trace_id} not found")
        
        # 获取原始节点记录
        trace_nodes = self.trace_manager.get_trace_nodes(trace_id)
        if not trace_nodes:
            raise ValueError(f"No nodes found for trace session {trace_id}")
        
        # 确定要执行的节点
        if current_node:
            # 查找指定节点
            node_to_execute = None
            for node in trace_nodes:
                if node["node_id"] == current_node:
                    node_to_execute = node
                    break
            
            if not node_to_execute:
                raise ValueError(f"Node {current_node} not found in trace session {trace_id}")
            
            next_nodes = []
        else:
            # 从第一个节点开始
            node_to_execute = trace_nodes[0]
            
            # 确定下一个节点
            if len(trace_nodes) > 1:
                next_nodes = trace_nodes[1:]
            else:
                next_nodes = []
        
        # 准备状态
        if state is None:
            initial_state = trace_session.get("initial_state", {})
            if isinstance(initial_state, dict) and "data" in initial_state:
                state = State.from_dict(initial_state)
            else:
                state = State(initial_state)
        elif not isinstance(state, State):
            state = State(state)
        
        # 设置追踪ID
        state.set_meta("original_trace_id", trace_id)
        state.set_meta("step_replay", True)
        
        # 执行节点
        node_id = node_to_execute["node_id"]
        agent_name = node_to_execute["agent_name"]
        
        try:
            # 获取智能体实例
            if self.db is not None:
                agent = AgentRegistry.get(agent_name, self.db)
            else:
                agent = AgentRegistry.get(agent_name)
            
            # 适配智能体
            adapted_agent = self._adapt_agent(agent)
            
            # 执行智能体
            result = adapted_agent.run(state)
            
            # 处理执行结果
            if isinstance(result, dict) and "state" in result:
                # 新的规范格式
                state_dict = result["state"]
                status = result.get("status", "ok")
                
                # 更新状态
                state = State(state_dict)
                
                # 准备结果
                step_result = {
                    "node_id": node_id,
                    "agent_name": agent_name,
                    "status": status,
                    "original_status": node_to_execute.get("status"),
                    "match": status == node_to_execute.get("status", "completed"),
                    "has_next": len(next_nodes) > 0,
                    "next_node": next_nodes[0]["node_id"] if next_nodes else None
                }
                
                if status == "error":
                    error_msg = result.get("error", "Unknown error")
                    step_result["error"] = error_msg
                
                return {
                    "success": True,
                    "step_result": step_result,
                    "state": state.to_dict(),
                    "next_nodes": [node["node_id"] for node in next_nodes]
                }
                
            else:
                # 兼容旧格式
                state = State(result)
                
                step_result = {
                    "node_id": node_id,
                    "agent_name": agent_name,
                    "status": "completed",
                    "original_status": node_to_execute.get("status"),
                    "match": node_to_execute.get("status") == "completed",
                    "has_next": len(next_nodes) > 0,
                    "next_node": next_nodes[0]["node_id"] if next_nodes else None
                }
                
                return {
                    "success": True,
                    "step_result": step_result,
                    "state": state.to_dict(),
                    "next_nodes": [node["node_id"] for node in next_nodes]
                }
                
        except Exception as e:
            # 记录执行错误
            error_msg = str(e)
            step_result = {
                "node_id": node_id,
                "agent_name": agent_name,
                "status": "error",
                "original_status": node_to_execute.get("status"),
                "match": node_to_execute.get("status") == "error",
                "error": error_msg,
                "has_next": len(next_nodes) > 0,
                "next_node": next_nodes[0]["node_id"] if next_nodes else None
            }
            
            return {
                "success": False,
                "step_result": step_result,
                "error": error_msg,
                "state": state.to_dict(),
                "next_nodes": [node["node_id"] for node in next_nodes]
            }
    
    def _filter_nodes_for_replay(
        self,
        trace_nodes: List[Dict[str, Any]],
        replay_type: str,
        start_node: str,
        end_node: str
    ) -> List[Dict[str, Any]]:
        """
        筛选要回放的节点
        
        Args:
            trace_nodes: 原始节点记录列表
            replay_type: 回放类型
            start_node: 起始节点
            end_node: 结束节点
            
        Returns:
            筛选后的节点列表
        """
        if replay_type == "full":
            # 完整回放：返回所有节点
            return trace_nodes
        
        elif replay_type == "partial":
            # 部分回放：返回指定范围内的节点
            if not start_node:
                raise ValueError("start_node is required for partial replay")
            
            start_index = -1
            end_index = len(trace_nodes)
            
            # 查找起始节点
            for i, node in enumerate(trace_nodes):
                if node["node_id"] == start_node:
                    start_index = i
                    break
            
            if start_index == -1:
                raise ValueError(f"Start node '{start_node}' not found in trace")
            
            # 查找结束节点
            if end_node:
                for i, node in enumerate(trace_nodes):
                    if node["node_id"] == end_node:
                        end_index = i + 1  # 包含结束节点
                        break
                
                if end_index == len(trace_nodes):
                    raise ValueError(f"End node '{end_node}' not found in trace")
                
                if end_index <= start_index:
                    raise ValueError(f"End node must come after start node")
            
            return trace_nodes[start_index:end_index]
        
        else:
            raise ValueError(f"Unsupported replay type: {replay_type}")
    
    def _adapt_agent(self, agent):
        """
        适配 Agent 到统一接口（同步版本）
        
        Args:
            agent: 从 Registry 获取的 Agent 实例
            
        Returns:
            适配后的 Agent 实例
        """
        from backend.workflow.agent_adapter import adapt_agent
        
        if hasattr(agent, 'run'):
            # 如果有 run 方法，直接使用
            return agent
        else:
            # 使用适配器
            return adapt_agent(agent)
    
    def _adapt_agent_async(self, agent):
        """
        适配 Agent 到统一接口（异步版本）
        
        Args:
            agent: 从 Registry 获取的 Agent 实例
            
        Returns:
            适配后的支持异步的 Agent 实例
        """
        from backend.workflow.agent_adapter import adapt_agent_async
        
        if hasattr(agent, 'run_async'):
            # 如果有 run_async 方法，直接使用
            return agent
        elif hasattr(agent, 'run'):
            # 只有 run 方法，创建异步包装器
            class AsyncWrapper:
                def __init__(self, agent):
                    self.agent = agent
                
                async def run_async(self, state):
                    import asyncio
                    return await asyncio.to_thread(self.agent.run, state)
                
                def run(self, state):
                    return self.agent.run(state)
            
            return AsyncWrapper(agent)
        else:
            # 使用异步适配器
            return adapt_agent_async(agent)
    
    def _update_replay_record(self, replay_id: str, replay_result: Dict[str, Any], replay_errors: List[Dict[str, Any]]):
        """
        更新回放记录
        
        Args:
            replay_id: 回放ID
            replay_result: 回放结果
            replay_errors: 回放错误列表
        """
        if not self.trace_manager:
            return
        
        try:
            # 获取回放记录
            replay_record = self.trace_manager.get_replay_result(replay_id)
            if not replay_record:
                return
            
            # 更新回放记录状态
            # 注意：这里需要直接操作数据库，因为TraceManager没有提供更新方法
            # 在实际应用中，需要在TraceManager中添加更新方法
            pass
            
        except Exception as e:
            # 更新失败不影响主流程
            print(f"Warning: Failed to update replay record: {e}")
    
    def get_replay_result(self, replay_id: str) -> Optional[Dict[str, Any]]:
        """
        获取回放结果
        
        Args:
            replay_id: 回放ID
            
        Returns:
            回放结果字典，如果不存在则返回None
        """
        if not self.trace_manager:
            raise ValueError("Trace manager not initialized")
        
        return self.trace_manager.get_replay_result(replay_id)
    
    def compare_replay_with_original(self, replay_id: str) -> Dict[str, Any]:
        """
        比较回放结果与原始执行
        
        Args:
            replay_id: 回放ID
            
        Returns:
            比较结果字典
        """
        if not self.trace_manager:
            raise ValueError("Trace manager not initialized")
        
        # 获取回放结果
        replay_result = self.trace_manager.get_replay_result(replay_id)
        if not replay_result:
            raise ValueError(f"Replay result with id {replay_id} not found")
        
        original_trace_id = replay_result.get("original_trace_id")
        if not original_trace_id:
            raise ValueError("Original trace ID not found in replay result")
        
        # 获取原始追踪会话
        original_session = self.trace_manager.get_trace_session(original_trace_id)
        if not original_session:
            raise ValueError(f"Original trace session with id {original_trace_id} not found")
        
        # 获取原始节点记录
        original_nodes = self.trace_manager.get_trace_nodes(original_trace_id)
        
        # 获取回放节点结果
        replay_results = replay_result.get("results", [])
        
        # 比较节点执行结果
        comparison_results = []
        
        for i, (original_node, replay_result_node) in enumerate(zip(original_nodes, replay_results)):
            comparison = {
                "node_id": original_node["node_id"],
                "agent_name": original_node["agent_name"],
                "original_status": original_node.get("status"),
                "replay_status": replay_result_node.get("status"),
                "status_match": original_node.get("status") == replay_result_node.get("status"),
                "execution_order": i + 1
            }
            
            # 比较执行时间（如果可用）
            if original_node.get("duration") and replay_result_node.get("duration"):
                original_duration = original_node.get("duration", 0)
                replay_duration = replay_result_node.get("duration", 0)
                comparison["duration_original"] = original_duration
                comparison["duration_replay"] = replay_duration
                comparison["duration_diff"] = replay_duration - original_duration
                comparison["duration_diff_percent"] = (replay_duration - original_duration) / original_duration * 100 if original_duration > 0 else 0
            
            comparison_results.append(comparison)
        
        # 计算统计信息
        total_nodes = len(comparison_results)
        matching_nodes = sum(1 for c in comparison_results if c["status_match"])
        
        return {
            "replay_id": replay_id,
            "original_trace_id": original_trace_id,
            "comparison_results": comparison_results,
            "statistics": {
                "total_nodes": total_nodes,
                "matching_nodes": matching_nodes,
                "mismatching_nodes": total_nodes - matching_nodes,
                "match_rate": matching_nodes / total_nodes if total_nodes > 0 else 0
            },
            "summary": {
                "replay_successful": replay_result.get("status") == "completed",
                "original_successful": original_session.get("status") == "completed",
                "overall_match": matching_nodes == total_nodes
            }
        }
    
    def create_step_by_step_view(self, trace_id: str, view_name: str = None) -> str:
        """
        创建逐节点查看视图
        
        Args:
            trace_id: 追踪会话ID
            view_name: 视图名称
            
        Returns:
            视图ID
        """
        if not self.trace_manager:
            raise ValueError("Trace manager not initialized")
        
        if not self.user_id:
            raise ValueError("User ID is required to create view")
        
        view_name = view_name or f"Step-by-Step View for Trace {trace_id[:8]}..."
        
        view_id = self.trace_manager.create_trace_view(
            trace_id=trace_id,
            user_id=self.user_id,
            view_name=view_name,
            view_type="step_by_step",
            view_config={
                "enable_step_control": True,
                "show_input_output": True,
                "show_context_state": True,
                "highlight_differences": True
            }
        )
        
        return view_id
    
    def get_step_by_step_view(self, view_id: str) -> Dict[str, Any]:
        """
        获取逐节点查看视图
        
        Args:
            view_id: 视图ID
            
        Returns:
            视图详情
        """
        if not self.trace_manager:
            raise ValueError("Trace manager not initialized")
        
        view_detail = self.trace_manager.get_trace_view(view_id)
        if not view_detail:
            raise ValueError(f"View with id {view_id} not found")
        
        trace_id = view_detail.get("trace_id")
        if not trace_id:
            raise ValueError("Trace ID not found in view")
        
        # 获取追踪详情
        trace_detail = self.trace_manager.get_trace_session(trace_id)
        trace_nodes = self.trace_manager.get_trace_nodes(trace_id)
        
        # 准备逐节点查看数据
        step_data = []
        for node in trace_nodes:
            step = {
                "node_id": node["node_id"],
                "node_name": node.get("node_name", node["node_id"]),
                "agent_name": node["agent_name"],
                "agent_type": node.get("agent_type"),
                "status": node.get("status"),
                "execution_order": node.get("execution_order"),
                "start_time": node.get("start_time"),
                "end_time": node.get("end_time"),
                "duration": node.get("duration"),
                "has_input": node.get("input_data") is not None,
                "has_output": node.get("output_data") is not None,
                "has_context": node.get("context_state") is not None,
                "has_error": node.get("error_message") is not None
            }
            step_data.append(step)
        
        return {
            "view": view_detail,
            "trace": trace_detail,
            "steps": step_data,
            "total_steps": len(step_data),
            "current_step": 0  # 从第一步开始
        }
