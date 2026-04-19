"""
支持Trace的Graph Engine
在原有Graph Engine基础上集成执行追踪功能
"""

from typing import Dict, Any, Union
from backend.agents.registry import AgentRegistry
from backend.core.state import State
from backend.core.trace_manager import get_trace_manager
import asyncio


class TraceGraphEngine:
    """
    支持Trace的Graph Engine
    
    特性：
    1. 完整记录Graph执行过程
    2. 支持执行回放
    3. 支持逐节点查看
    4. 与原有Graph Engine兼容
    """
    
    def __init__(self, db=None, user_id=None, enable_trace=True):
        """
        初始化TraceGraphEngine
        
        Args:
            db: 数据库会话（可选）
            user_id: 用户ID（可选，用于追踪）
            enable_trace: 是否启用追踪（默认启用）
        """
        self.db = db
        self.user_id = user_id
        self.enable_trace = enable_trace
        self.trace_manager = None
        self.current_trace_id = None
        
        if self.db and self.enable_trace:
            self.trace_manager = get_trace_manager(self.db)
    
    def run(self, graph: Dict[str, Any], state: Union[Dict[str, Any], State]) -> Dict[str, Any]:
        """
        执行线性图（支持Trace）
        
        Args:
            graph: 图定义
            state: 初始状态
            
        Returns:
            最终状态字典
        """
        # 确保状态是 State 对象
        if not isinstance(state, State):
            state = State(state)
        
        # 开始追踪会话
        if self.enable_trace and self.trace_manager and self.user_id:
            try:
                self.current_trace_id = self.trace_manager.start_trace_session(
                    graph_id=graph.get("graph_id", "unknown"),
                    graph_config=graph,
                    user_id=self.user_id,
                    initial_state=state,
                    graph_name=graph.get("graph_name"),
                    tags=graph.get("tags", []),
                    metadata={
                        "engine": "TraceGraphEngine",
                        "execution_mode": "sync"
                    }
                )
                state.set_meta("trace_id", self.current_trace_id)
            except Exception as e:
                # 追踪失败不影响主流程
                print(f"Warning: Failed to start trace session: {e}")
        
        # 获取起始节点
        current_node_id = graph.get("start")
        if not current_node_id:
            raise ValueError("Graph must have a 'start' node")
        
        nodes = graph.get("nodes", {})
        if not nodes:
            raise ValueError("Graph must have at least one node")
        
        # 线性遍历节点
        while current_node_id:
            node_config = nodes.get(current_node_id)
            if not node_config:
                raise ValueError(f"Node '{current_node_id}' not found in graph")
            
            agent_name = node_config.get("agent")
            if not agent_name or not isinstance(agent_name, str):
                raise ValueError(f"Node '{current_node_id}' must have an 'agent' that is a string (agent name)")
            
            # 记录节点开始执行
            node_record_id = None
            if self.enable_trace and self.trace_manager and self.current_trace_id:
                try:
                    node_record_id = self.trace_manager.record_node_start(
                        node_id=current_node_id,
                        node_name=node_config.get("node_name", current_node_id),
                        agent_name=agent_name,
                        agent_type=node_config.get("agent_type"),
                        input_data=state.to_plain_dict(),
                        context_state=state
                    )
                except Exception as e:
                    print(f"Warning: Failed to record node start: {e}")
            
            # 使用AgentRegistry获取智能体实例
            try:
                if self.db is not None:
                    agent = AgentRegistry.get(agent_name, self.db)
                else:
                    agent = AgentRegistry.get(agent_name)
            except Exception as e:
                error_msg = f"Failed to get agent '{agent_name}' from registry: {e}"
                
                # 记录节点失败
                if node_record_id and self.trace_manager:
                    try:
                        self.trace_manager.record_node_failed(
                            node_record_id=node_record_id,
                            error_message=error_msg,
                            context_state=state
                        )
                    except:
                        pass
                
                # 记录错误但继续执行（线性图要求）
                state[f"{current_node_id}_error"] = error_msg
                state[f"{current_node_id}_executed"] = False
                state[f"{current_node_id}_status"] = "error"
                state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 获取失败: {e}")
                
                # 获取下一个节点
                current_node_id = node_config.get("next")
                continue
            
            # 适配 Agent 到统一接口
            adapted_agent = self._adapt_agent(agent)
            
            # 执行智能体
            try:
                result = adapted_agent.run(state)
                
                # 处理规范格式：{"state": state_dict, "events": [], "status": "ok"}
                if isinstance(result, dict) and "state" in result:
                    # 新的规范格式
                    state_dict = result["state"]
                    status = result.get("status", "ok")
                    events = result.get("events", [])
                    
                    # 更新状态
                    state = State(state_dict)
                    
                    # 记录执行状态
                    state[f"{current_node_id}_executed"] = True
                    state[f"{current_node_id}_status"] = status
                    if events:
                        state[f"{current_node_id}_events"] = events
                    state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行成功，状态: {status}")
                    
                    # 如果状态是错误，记录但不抛出
                    if status == "error":
                        error_msg = result.get("error", "Unknown error")
                        state[f"{current_node_id}_error"] = error_msg
                        state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行出错: {error_msg}")
                        
                        # 记录节点失败
                        if node_record_id and self.trace_manager:
                            try:
                                self.trace_manager.record_node_failed(
                                    node_record_id=node_record_id,
                                    error_message=error_msg,
                                    context_state=state
                                )
                            except:
                                pass
                    else:
                        # 记录节点完成
                        if node_record_id and self.trace_manager:
                            try:
                                self.trace_manager.record_node_complete(
                                    node_record_id=node_record_id,
                                    output_data=result.get("output"),
                                    context_state=state
                                )
                            except:
                                pass
                else:
                    # 兼容旧格式：直接返回状态字典
                    state_dict = result
                    state = State(state_dict)
                    state[f"{current_node_id}_executed"] = True
                    state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行成功（旧格式）")
                    
                    # 记录节点完成
                    if node_record_id and self.trace_manager:
                        try:
                            self.trace_manager.record_node_complete(
                                node_record_id=node_record_id,
                                output_data=result,
                                context_state=state
                            )
                        except:
                            pass
                
            except Exception as e:
                error_msg = str(e)
                
                # 记录节点失败
                if node_record_id and self.trace_manager:
                    try:
                        self.trace_manager.record_node_failed(
                            node_record_id=node_record_id,
                            error_message=error_msg,
                            context_state=state
                        )
                    except:
                        pass
                
                # 记录错误但继续执行（线性图要求）
                state[f"{current_node_id}_error"] = error_msg
                state[f"{current_node_id}_executed"] = False
                state[f"{current_node_id}_status"] = "error"
                state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 执行失败: {e}")
            
            # 获取下一个节点
            current_node_id = node_config.get("next")
        
        # 结束追踪会话
        if self.enable_trace and self.trace_manager and self.current_trace_id:
            try:
                self.trace_manager.end_trace_session(
                    final_state=state,
                    status="completed"
                )
            except Exception as e:
                print(f"Warning: Failed to end trace session: {e}")
            finally:
                self.current_trace_id = None
        
        return state.to_plain_dict()
    
    async def run_async(self, graph: Dict[str, Any], state: Union[Dict[str, Any], State]) -> Dict[str, Any]:
        """
        异步执行线性图（支持Trace）
        
        Args:
            graph: 图定义
            state: 初始状态
            
        Returns:
            最终状态字典
        """
        # 确保状态是 State 对象
        if not isinstance(state, State):
            state = State(state)
        
        # 开始追踪会话
        if self.enable_trace and self.trace_manager and self.user_id:
            try:
                self.current_trace_id = self.trace_manager.start_trace_session(
                    graph_id=graph.get("graph_id", "unknown"),
                    graph_config=graph,
                    user_id=self.user_id,
                    initial_state=state,
                    graph_name=graph.get("graph_name"),
                    tags=graph.get("tags", []),
                    metadata={
                        "engine": "TraceGraphEngine",
                        "execution_mode": "async"
                    }
                )
                state.set_meta("trace_id", self.current_trace_id)
            except Exception as e:
                # 追踪失败不影响主流程
                print(f"Warning: Failed to start trace session: {e}")
        
        # 获取起始节点
        current_node_id = graph.get("start")
        if not current_node_id:
            raise ValueError("Graph must have a 'start' node")
        
        nodes = graph.get("nodes", {})
        if not nodes:
            raise ValueError("Graph must have at least one node")
        
        # 线性遍历节点
        while current_node_id:
            node_config = nodes.get(current_node_id)
            if not node_config:
                raise ValueError(f"Node '{current_node_id}' not found in graph")
            
            agent_name = node_config.get("agent")
            if not agent_name or not isinstance(agent_name, str):
                raise ValueError(f"Node '{current_node_id}' must have an 'agent' that is a string (agent name)")
            
            # 记录节点开始执行
            node_record_id = None
            if self.enable_trace and self.trace_manager and self.current_trace_id:
                try:
                    node_record_id = self.trace_manager.record_node_start(
                        node_id=current_node_id,
                        node_name=node_config.get("node_name", current_node_id),
                        agent_name=agent_name,
                        agent_type=node_config.get("agent_type"),
                        input_data=state.to_plain_dict(),
                        context_state=state
                    )
                except Exception as e:
                    print(f"Warning: Failed to record node start: {e}")
            
            # 使用AgentRegistry获取智能体实例
            try:
                if self.db is not None:
                    agent = AgentRegistry.get(agent_name, self.db)
                else:
                    agent = AgentRegistry.get(agent_name)
            except Exception as e:
                error_msg = f"Failed to get agent '{agent_name}' from registry: {e}"
                
                # 记录节点失败
                if node_record_id and self.trace_manager:
                    try:
                        self.trace_manager.record_node_failed(
                            node_record_id=node_record_id,
                            error_message=error_msg,
                            context_state=state
                        )
                    except:
                        pass
                
                # 记录错误但继续执行（线性图要求）
                state[f"{current_node_id}_error"] = error_msg
                state[f"{current_node_id}_executed"] = False
                state[f"{current_node_id}_status"] = "error"
                state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 获取失败: {e}")
                
                # 获取下一个节点
                current_node_id = node_config.get("next")
                continue
            
            # 适配 Agent 到统一接口
            adapted_agent = self._adapt_agent_async(agent)
            
            # 执行智能体
            try:
                if hasattr(adapted_agent, 'run_async'):
                    # 使用异步版本
                    result = await adapted_agent.run_async(state)
                else:
                    # 使用同步版本（在线程中运行）
                    result = await asyncio.to_thread(adapted_agent.run, state)
                
                # 处理规范格式：{"state": state_dict, "events": [], "status": "ok"}
                if isinstance(result, dict) and "state" in result:
                    # 新的规范格式
                    state_dict = result["state"]
                    status = result.get("status", "ok")
                    events = result.get("events", [])
                    
                    # 更新状态
                    state = State(state_dict)
                    
                    # 记录执行状态
                    state[f"{current_node_id}_executed"] = True
                    state[f"{current_node_id}_status"] = status
                    if events:
                        state[f"{current_node_id}_events"] = events
                    state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 异步执行成功，状态: {status}")
                    
                    # 如果状态是错误，记录但不抛出
                    if status == "error":
                        error_msg = result.get("error", "Unknown error")
                        state[f"{current_node_id}_error"] = error_msg
                        state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 异步执行出错: {error_msg}")
                        
                        # 记录节点失败
                        if node_record_id and self.trace_manager:
                            try:
                                self.trace_manager.record_node_failed(
                                    node_record_id=node_record_id,
                                    error_message=error_msg,
                                    context_state=state
                                )
                            except:
                                pass
                    else:
                        # 记录节点完成
                        if node_record_id and self.trace_manager:
                            try:
                                self.trace_manager.record_node_complete(
                                    node_record_id=node_record_id,
                                    output_data=result.get("output"),
                                    context_state=state
                                )
                            except:
                                pass
                else:
                    # 兼容旧格式：直接返回状态字典
                    state_dict = result
                    state = State(state_dict)
                    state[f"{current_node_id}_executed"] = True
                    state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 异步执行成功（旧格式）")
                    
                    # 记录节点完成
                    if node_record_id and self.trace_manager:
                        try:
                            self.trace_manager.record_node_complete(
                                node_record_id=node_record_id,
                                output_data=result,
                                context_state=state
                            )
                        except:
                            pass
                
            except Exception as e:
                error_msg = str(e)
                
                # 记录节点失败
                if node_record_id and self.trace_manager:
                    try:
                        self.trace_manager.record_node_failed(
                            node_record_id=node_record_id,
                            error_message=error_msg,
                            context_state=state
                        )
                    except:
                        pass
                
                # 记录错误但继续执行（线性图要求）
                state[f"{current_node_id}_error"] = error_msg
                state[f"{current_node_id}_executed"] = False
                state[f"{current_node_id}_status"] = "error"
                state.log(f"Node '{current_node_id}' (Agent: {agent_name}) 异步执行失败: {e}")
            
            # 获取下一个节点
            current_node_id = node_config.get("next")
        
        # 结束追踪会话
        if self.enable_trace and self.trace_manager and self.current_trace_id:
            try:
                self.trace_manager.end_trace_session(
                    final_state=state,
                    status="completed"
                )
            except Exception as e:
                print(f"Warning: Failed to end trace session: {e}")
            finally:
                self.current_trace_id = None
        
        return state.to_plain_dict()
    
    def _adapt_agent(self, agent):
        """
        适配 Agent 到统一接口（同步版本）
        
        Args:
            agent: 从 Registry 获取的 Agent 实例
            
        Returns:
            适配后的 Agent 实例
        """
        from backend.workflow.agent_adapter import adapt_agent
        from backend.agents.standard_base import BaseAgent
        
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
        from backend.agents.standard_base import BaseAgent
        
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
    
    def get_trace_id(self) -> str:
        """
        获取当前追踪会话ID
        
        Returns:
            追踪会话ID，如果没有则返回None
        """
        return self.current_trace_id
    
    def get_trace_summary(self, trace_id: str = None) -> Dict[str, Any]:
        """
        获取追踪摘要
        
        Args:
            trace_id: 追踪会话ID，如果为None则使用当前会话
            
        Returns:
            追踪摘要字典
        """
        if not self.trace_manager:
            raise ValueError("Trace manager not initialized")
        
        trace_id_to_use = trace_id or self.current_trace_id
        if not trace_id_to_use:
            raise ValueError("No trace ID provided and no active trace session")
        
        return self.trace_manager.get_execution_summary(trace_id_to_use)
    
    def get_trace_detail(self, trace_id: str = None) -> Dict[str, Any]:
        """
        获取追踪详情
        
        Args:
            trace_id: 追踪会话ID，如果为None则使用当前会话
            
        Returns:
            追踪详情字典，包含会话和节点信息
        """
        if not self.trace_manager:
            raise ValueError("Trace manager not initialized")
        
        trace_id_to_use = trace_id or self.current_trace_id
        if not trace_id_to_use:
            raise ValueError("No trace ID provided and no active trace session")
        
        session_detail = self.trace_manager.get_trace_session(trace_id_to_use)
        if not session_detail:
            raise ValueError(f"Trace session with id {trace_id_to_use} not found")
        
        nodes_detail = self.trace_manager.get_trace_nodes(trace_id_to_use)
        
        return {
            "session": session_detail,
            "nodes": nodes_detail
        }
    
    def search_traces(
        self,
        user_id: int = None,
        graph_id: str = None,
        status: str = None,
        start_date: str = None,
        end_date: str = None,
        tags: List[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        搜索追踪会话
        
        Args:
            user_id: 用户ID（可选）
            graph_id: Graph ID（可选）
            status: 状态（可选）
            start_date: 开始日期字符串（ISO格式，可选）
            end_date: 结束日期字符串（ISO格式，可选）
            tags: 标签列表（可选）
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            搜索结果字典
        """
        if not self.trace_manager:
            raise ValueError("Trace manager not initialized")
        
        from datetime import datetime
        
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            try:
                start_date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError(f"Invalid start_date format: {start_date}")
        
        if end_date:
            try:
                end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError(f"Invalid end_date format: {end_date}")
        
        return self.trace_manager.search_trace_sessions(
            user_id=user_id or self.user_id,
            graph_id=graph_id,
            status=status,
            start_date=start_date_obj,
            end_date=end_date_obj,
            tags=tags,
            limit=limit,
            offset=offset
        )
        
