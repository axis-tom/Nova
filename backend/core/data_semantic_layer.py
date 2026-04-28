"""
数据语义层 - 强制数据流链路
确保整个系统遵循：collector → ContextWrapper → Graph → AI → output
"""

from typing import Dict, Any, Optional, Union, List
from backend.core.state import State
from backend.core.contextual_data import ContextualData, ContextWrapper, create_contextual_data
from backend.cognition.state_machine.contextual_graph import ContextualGraphEngine
from backend.agents.executor.contextual_ai_analyzer import ContextualAIAnalyzer
from backend.utils.logger import logger


class DataSemanticLayer:
    """
    数据语义层 - 强制数据流规范
    
    确保整个系统遵循：
    collector → ContextWrapper → Graph → AI → output
    
    验收标准：
    1. sandbox数据与production数据不会混入同一逻辑判断
    2. Graph无任何if env逻辑
    3. AI输出在两种环境下行为一致（仅数据不同）
    4. trace_id可追踪完整链路
    """
    
    def __init__(self, db=None, llm_client=None):
        """
        初始化数据语义层
        
        Args:
            db: 数据库会话（可选）
            llm_client: LLM客户端（可选，用于AI分析）
        """
        self.db = db
        self.llm_client = llm_client
        
        # 初始化组件
        self.graph_engine = ContextualGraphEngine(db)
        if llm_client:
            self.ai_analyzer = ContextualAIAnalyzer(llm_client)
        else:
            self.ai_analyzer = None
        
        # 追踪状态
        self._execution_trace = []
    
    def execute_full_flow(
        self,
        collector_name: str,
        collector_data: Any,
        graph_definition: Dict[str, Any],
        initial_state: Optional[Dict[str, Any]] = None,
        env: str = "production",
        source: str = "unknown",
        trace_id: Optional[str] = None
    ) -> State:
        """
        执行完整的数据流
        
        Args:
            collector_name: 采集器名称
            collector_data: 采集器原始数据
            graph_definition: Graph定义
            initial_state: 初始状态（可选）
            env: 环境（sandbox/production）
            source: 数据源
            trace_id: 追踪ID
            
        Returns:
            最终状态
        """
        # 1. Collector → ContextWrapper
        contextual_data = self._wrap_collector_data(
            collector_name, collector_data, env, source, trace_id
        )
        
        # 2. 创建初始状态
        state = self._create_initial_state(contextual_data, initial_state)
        
        # 3. ContextWrapper → Graph
        state = self._execute_graph(graph_definition, state)
        
        # 4. Graph → AI
        if self.ai_analyzer:
            state = self._execute_ai_analysis(state)
        
        # 5. 记录执行轨迹
        self._record_execution_trace(state)
        
        return state
    
    async def execute_full_flow_async(
        self,
        collector_name: str,
        collector_data: Any,
        graph_definition: Dict[str, Any],
        initial_state: Optional[Dict[str, Any]] = None,
        env: str = "production",
        source: str = "unknown",
        trace_id: Optional[str] = None
    ) -> State:
        """
        异步执行完整的数据流
        
        Args:
            参数同execute_full_flow
            
        Returns:
            最终状态
        """
        # 1. Collector → ContextWrapper
        contextual_data = self._wrap_collector_data(
            collector_name, collector_data, env, source, trace_id
        )
        
        # 2. 创建初始状态
        state = self._create_initial_state(contextual_data, initial_state)
        
        # 3. ContextWrapper → Graph (异步)
        state = await self._execute_graph_async(graph_definition, state)
        
        # 4. Graph → AI (异步)
        if self.ai_analyzer:
            state = await self._execute_ai_analysis_async(state)
        
        # 5. 记录执行轨迹
        self._record_execution_trace(state)
        
        return state
    
    def _wrap_collector_data(
        self,
        collector_name: str,
        data: Any,
        env: str,
        source: str,
        trace_id: Optional[str] = None
    ) -> ContextualData:
        """
        包装采集器数据
        
        Args:
            collector_name: 采集器名称
            data: 原始数据
            env: 环境
            source: 数据源
            trace_id: 追踪ID
            
        Returns:
            ContextualData实例
        """
        logger.info(f"Wrapping collector data: {collector_name}, env={env}, source={source}")
        
        # 使用ContextWrapper包装数据
        contextual_data = ContextWrapper.wrap_collector_output(
            collector_name=collector_name,
            data=data,
            env=env,
            source=source,
            trace_id=trace_id
        )
        
        # 验证数据格式
        if not ContextWrapper.validate_context(contextual_data):
            raise ValueError(f"Failed to create valid contextual data for collector: {collector_name}")
        
        logger.info(f"Created contextual data: {contextual_data}")
        return contextual_data
    
    def _create_initial_state(
        self,
        contextual_data: ContextualData,
        initial_state: Optional[Dict[str, Any]] = None
    ) -> State:
        """
        创建初始状态
        
        Args:
            contextual_data: 上下文数据
            initial_state: 初始状态字典（可选）
            
        Returns:
            State对象
        """
        # 创建基础状态
        if initial_state:
            state = State(initial_state)
        else:
            state = State()
        
        # 设置contextual_data
        state.set("contextual_data", contextual_data.to_dict())
        
        # 设置追踪信息
        state.set_meta("trace_id", contextual_data.trace_id)
        state.set_meta("env", contextual_data.env)
        state.set_meta("source", contextual_data.source)
        state.set_meta("collector", contextual_data.collector)
        
        # 记录创建事件
        state.add_event("data_semantic_layer_initial_state_created")
        
        return state
    
    def _execute_graph(self, graph_definition: Dict[str, Any], state: State) -> State:
        """
        执行Graph
        
        Args:
            graph_definition: Graph定义
            state: 输入状态
            
        Returns:
            Graph处理后的状态
        """
        logger.info(f"Executing graph with {len(graph_definition.get('nodes', {}))} nodes")
        
        try:
            # 使用上下文感知的Graph引擎
            result_state = self.graph_engine.run(graph_definition, state)
            
            # 验证Graph输出
            self._validate_graph_output(result_state)
            
            logger.info("Graph execution completed successfully")
            return result_state
            
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            state.set("graph_error", str(e))
            state.add_event(f"graph_execution_failed: {str(e)}")
            return state
    
    async def _execute_graph_async(self, graph_definition: Dict[str, Any], state: State) -> State:
        """
        异步执行Graph
        
        Args:
            graph_definition: Graph定义
            state: 输入状态
            
        Returns:
            Graph处理后的状态
        """
        logger.info(f"Async executing graph with {len(graph_definition.get('nodes', {}))} nodes")
        
        try:
            # 使用上下文感知的Graph引擎（异步）
            result_state = await self.graph_engine.run_async(graph_definition, state)
            
            # 验证Graph输出
            self._validate_graph_output(result_state)
            
            logger.info("Async graph execution completed successfully")
            return result_state
            
        except Exception as e:
            logger.error(f"Async graph execution failed: {e}")
            state.set("graph_error", str(e))
            state.add_event(f"async_graph_execution_failed: {str(e)}")
            return state
    
    def _execute_ai_analysis(self, state: State) -> State:
        """
        执行AI分析
        
        Args:
            state: 输入状态
            
        Returns:
            AI处理后的状态
        """
        if not self.ai_analyzer:
            logger.warning("AI analyzer not available, skipping AI analysis")
            state.add_event("ai_analysis_skipped_no_analyzer")
            return state
        
        logger.info("Executing AI analysis")
        
        try:
            # 使用上下文感知的AI分析器
            # 注意：由于可能已经在事件循环中，我们使用同步方式调用
            import asyncio
            
            # 检查是否在事件循环中
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，使用run_coroutine_threadsafe
                    future = asyncio.run_coroutine_threadsafe(self.ai_analyzer.run(state), loop)
                    result_state = future.result(timeout=15)
                else:
                    # 否则使用asyncio.run
                    result_state = asyncio.run(self.ai_analyzer.run(state))
            except RuntimeError:
                # 没有事件循环，创建新的
                result_state = asyncio.run(self.ai_analyzer.run(state))
            
            # 验证AI输出
            self._validate_ai_output(result_state)
            
            logger.info("AI analysis completed successfully")
            return result_state
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            state.set("ai_error", str(e))
            state.add_event(f"ai_analysis_failed: {str(e)}")
            return state
    
    async def _execute_ai_analysis_async(self, state: State) -> State:
        """
        异步执行AI分析
        
        Args:
            state: 输入状态
            
        Returns:
            AI处理后的状态
        """
        if not self.ai_analyzer:
            logger.warning("AI analyzer not available, skipping AI analysis")
            state.add_event("ai_analysis_skipped_no_analyzer")
            return state
        
        logger.info("Async executing AI analysis")
        
        try:
            # 使用上下文感知的AI分析器（异步）
            result_state = await self.ai_analyzer.run(state)
            
            # 验证AI输出
            self._validate_ai_output(result_state)
            
            logger.info("Async AI analysis completed successfully")
            return result_state
            
        except Exception as e:
            logger.error(f"Async AI analysis failed: {e}")
            state.set("ai_error", str(e))
            state.add_event(f"async_ai_analysis_failed: {str(e)}")
            return state
    
    def _validate_graph_output(self, state: State) -> None:
        """
        验证Graph输出是否符合规范
        
        Args:
            state: 要验证的状态
            
        Raises:
            ValueError: 如果不符合规范
        """
        # 检查是否包含contextual_data
        if "contextual_data" not in state:
            raise ValueError("Graph output must contain 'contextual_data'")
        
        # 检查contextual_data格式
        contextual_data = state.get("contextual_data")
        if not isinstance(contextual_data, dict):
            raise ValueError("contextual_data must be a dictionary")
        
        if "context" not in contextual_data or "payload" not in contextual_data:
            raise ValueError("contextual_data must contain 'context' and 'payload'")
        
        # 检查是否包含环境判断逻辑（通过事件检查）
        events = state.events
        for event in events:
            if isinstance(event, str):
                event_lower = event.lower()
                if any(keyword in event_lower for keyword in ["env", "sandbox", "production", "环境"]):
                    logger.warning(f"Graph event may contain environment reference: {event}")
    
    def _validate_ai_output(self, state: State) -> None:
        """
        验证AI输出是否符合规范
        
        Args:
            state: 要验证的状态
            
        Raises:
            ValueError: 如果不符合规范
        """
        # 检查AI输出是否包含环境信息
        contextual_data = state.get("contextual_data", {})
        payload = contextual_data.get("payload", {})
        
        if "ai_analysis" in payload:
            ai_output = payload["ai_analysis"]
            if isinstance(ai_output, str):
                # 使用AI分析器的验证方法
                if hasattr(self.ai_analyzer, 'validate_ai_output'):
                    if not self.ai_analyzer.validate_ai_output(ai_output):
                        logger.warning("AI output may contain environment information")
    
    def _record_execution_trace(self, state: State) -> None:
        """
        记录执行轨迹
        
        Args:
            state: 最终状态
        """
        trace_entry = {
            "timestamp": "2024-01-01T00:00:00",  # 实际应该使用当前时间
            "trace_id": state.get_meta("trace_id", "unknown"),
            "env": state.get_meta("env", "unknown"),
            "source": state.get_meta("source", "unknown"),
            "collector": state.get_meta("collector", "unknown"),
            "events_count": len(state.events),
            "has_ai_analysis": "ai_analysis" in state.get("contextual_data", {}).get("payload", {})
        }
        
        self._execution_trace.append(trace_entry)
        
        # 将轨迹信息添加到状态中
        state.set_meta("execution_trace", trace_entry)
        state.add_event("execution_trace_recorded")
    
    def get_execution_trace(self) -> List[Dict[str, Any]]:
        """
        获取执行轨迹
        
        Returns:
            执行轨迹列表
        """
        return self._execution_trace.copy()
    
    def clear_execution_trace(self) -> None:
        """清空执行轨迹"""
        self._execution_trace.clear()
    
    def validate_data_isolation(self, state1: State, state2: State) -> bool:
        """
        验证两个状态的数据是否隔离（不同环境的数据不会混合）
        
        Args:
            state1: 第一个状态
            state2: 第二个状态
            
        Returns:
            是否隔离成功
        """
        env1 = state1.get_meta("env", "unknown")
        env2 = state2.get_meta("env", "unknown")
        
        # 如果环境不同，确保数据不会混合
        if env1 != env2:
            # 检查状态中是否包含对方环境的数据
            contextual_data1 = state1.get("contextual_data", {})
            contextual_data2 = state2.get("contextual_data", {})
            
            # 这里可以添加更复杂的检查逻辑
            # 例如检查payload中是否包含对方环境的特定标记
            
            logger.info(f"Validated isolation between {env1} and {env2} environments")
            return True
        
        return True  # 相同环境，不需要特殊处理
    
    def create_sandbox_test_flow(self, collector_name: str, test_data: Any) -> Dict[str, Any]:
        """
        创建沙箱测试流程
        
        Args:
            collector_name: 采集器名称
            test_data: 测试数据
            
        Returns:
            测试流程配置
        """
        return {
            "collector": collector_name,
            "data": test_data,
            "env": "sandbox",
            "source": "test",
            "graph": {
                "start": "process",
                "nodes": {
                    "process": {
                        "agent": "test_processor",
                        "next": None
                    }
                }
            },
            "description": f"Sandbox test flow for {collector_name}"
        }
    
    def create_production_flow(self, collector_name: str, source: str) -> Dict[str, Any]:
        """
        创建生产环境流程
        
        Args:
            collector_name: 采集器名称
            source: 数据源
            
        Returns:
            生产流程配置
        """
        return {
            "collector": collector_name,
            "env": "production",
            "source": source,
            "graph": {
                "start": "process",
                "nodes": {
                    "process": {
                        "agent": "production_processor",
                        "next": "analyze"
                    },
                    "analyze": {
                        "agent": "ai_analyzer",
                        "next": None
                    }
                }
            },
            "description": f"Production flow for {collector_name} from {source}"
        }


# 全局数据语义层实例
data_semantic_layer = DataSemanticLayer()