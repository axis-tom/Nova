"""
执行追踪管理器
负责记录Graph执行过程，支持回放和查看
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.models.trace import TraceSession, TraceNode, TraceReplay, TraceView
from backend.cognition.state_machine.state_machine import State
import json
import copy


class TraceManager:
    """
    执行追踪管理器
    负责：
    1. 创建和管理追踪会话
    2. 记录节点执行详情
    3. 支持执行回放
    4. 提供逐节点查看功能
    """
    
    def __init__(self, db_session: Session):
        """
        初始化TraceManager
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session
        self.current_trace_id = None
        self.current_session = None
        self.execution_order = 0
    
    def start_trace_session(
        self,
        graph_id: str,
        graph_config: Dict[str, Any],
        user_id: int,
        initial_state: Union[Dict[str, Any], State],
        graph_name: str = None,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        开始一个新的追踪会话
        
        Args:
            graph_id: Graph ID
            graph_config: Graph配置
            user_id: 用户ID
            initial_state: 初始状态
            graph_name: Graph名称（可选）
            tags: 标签列表（可选）
            metadata: 其他元数据（可选）
            
        Returns:
            trace_id: 追踪会话ID
        """
        # 创建追踪会话
        trace_session = TraceSession(
            graph_id=graph_id,
            graph_name=graph_name,
            graph_config=graph_config,
            user_id=user_id,
            initial_state=self._serialize_state(initial_state),
            tags=tags or [],
            metadata=metadata or {}
        )
        
        self.db.add(trace_session)
        self.db.commit()
        self.db.refresh(trace_session)
        
        self.current_trace_id = trace_session.trace_id
        self.current_session = trace_session
        self.execution_order = 0
        
        return trace_session.trace_id
    
    def record_node_start(
        self,
        node_id: str,
        node_name: str,
        agent_name: str,
        agent_type: str = None,
        input_data: Dict[str, Any] = None,
        context_state: Union[Dict[str, Any], State] = None
    ) -> int:
        """
        记录节点开始执行
        
        Args:
            node_id: 节点ID
            node_name: 节点名称
            agent_name: 智能体名称
            agent_type: 智能体类型（可选）
            input_data: 输入数据（可选）
            context_state: 上下文状态（可选）
            
        Returns:
            node_record_id: 节点记录ID
        """
        if not self.current_trace_id:
            raise ValueError("No active trace session. Call start_trace_session first.")
        
        self.execution_order += 1
        
        trace_node = TraceNode(
            trace_id=self.current_trace_id,
            node_id=node_id,
            node_name=node_name,
            execution_order=self.execution_order,
            agent_name=agent_name,
            agent_type=agent_type,
            input_data=input_data,
            context_state=self._serialize_state(context_state)
        )
        
        trace_node.mark_running()
        
        self.db.add(trace_node)
        self.db.commit()
        self.db.refresh(trace_node)
        
        # 更新执行路径
        if self.current_session:
            execution_path = self.current_session.execution_path or []
            execution_path.append(node_id)
            self.current_session.execution_path = execution_path
            self.db.commit()
        
        return trace_node.id
    
    def record_node_complete(
        self,
        node_record_id: int,
        output_data: Dict[str, Any] = None,
        context_state: Union[Dict[str, Any], State] = None,
        memory_usage: float = None,
        cpu_usage: float = None
    ):
        """
        记录节点执行完成
        
        Args:
            node_record_id: 节点记录ID
            output_data: 输出数据（可选）
            context_state: 上下文状态（可选）
            memory_usage: 内存使用（MB，可选）
            cpu_usage: CPU使用率（%，可选）
        """
        trace_node = self.db.query(TraceNode).filter(TraceNode.id == node_record_id).first()
        if not trace_node:
            raise ValueError(f"Trace node with id {node_record_id} not found")
        
        trace_node.mark_completed(
            output_data=output_data,
            context_state=self._serialize_state(context_state)
        )
        
        if memory_usage is not None:
            trace_node.memory_usage = memory_usage
        if cpu_usage is not None:
            trace_node.cpu_usage = cpu_usage
        
        self.db.commit()
    
    def record_node_failed(
        self,
        node_record_id: int,
        error_message: str,
        error_details: Dict[str, Any] = None,
        context_state: Union[Dict[str, Any], State] = None
    ):
        """
        记录节点执行失败
        
        Args:
            node_record_id: 节点记录ID
            error_message: 错误消息
            error_details: 错误详情（可选）
            context_state: 上下文状态（可选）
        """
        trace_node = self.db.query(TraceNode).filter(TraceNode.id == node_record_id).first()
        if not trace_node:
            raise ValueError(f"Trace node with id {node_record_id} not found")
        
        trace_node.mark_failed(
            error_message=error_message,
            error_details=error_details
        )
        
        if context_state:
            trace_node.context_state = self._serialize_state(context_state)
        
        # 更新会话错误列表
        if self.current_session:
            errors = self.current_session.errors or []
            errors.append({
                "node_id": trace_node.node_id,
                "node_name": trace_node.node_name,
                "timestamp": datetime.now().isoformat(),
                "message": error_message,
                "details": error_details
            })
            self.current_session.errors = errors
            self.db.commit()
    
    def end_trace_session(
        self,
        final_state: Union[Dict[str, Any], State] = None,
        status: str = "completed"
    ):
        """
        结束追踪会话
        
        Args:
            final_state: 最终状态（可选）
            status: 结束状态（completed, failed, cancelled）
        """
        if not self.current_session:
            raise ValueError("No active trace session")
        
        if status == "completed":
            self.current_session.mark_completed(
                final_state=self._serialize_state(final_state)
            )
        elif status == "failed":
            self.current_session.mark_failed()
        else:
            self.current_session.status = status
            self.current_session.end_time = datetime.now()
            if self.current_session.start_time:
                self.current_session.duration = (
                    self.current_session.end_time - self.current_session.start_time
                ).total_seconds()
        
        if final_state:
            self.current_session.final_state = self._serialize_state(final_state)
        
        self.db.commit()
        
        # 重置当前会话
        self.current_trace_id = None
        self.current_session = None
        self.execution_order = 0
    
    def get_trace_session(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        获取追踪会话详情
        
        Args:
            trace_id: 追踪会话ID
            
        Returns:
            追踪会话详情字典，如果不存在则返回None
        """
        trace_session = self.db.query(TraceSession).filter(
            TraceSession.trace_id == trace_id
        ).first()
        
        if not trace_session:
            return None
        
        return trace_session.to_dict()
    
    def get_trace_nodes(self, trace_id: str) -> List[Dict[str, Any]]:
        """
        获取追踪会话的所有节点记录
        
        Args:
            trace_id: 追踪会话ID
            
        Returns:
            节点记录列表
        """
        trace_nodes = self.db.query(TraceNode).filter(
            TraceNode.trace_id == trace_id
        ).order_by(TraceNode.execution_order).all()
        
        return [node.to_dict() for node in trace_nodes]
    
    def get_trace_node_detail(self, node_record_id: int) -> Optional[Dict[str, Any]]:
        """
        获取节点记录详情
        
        Args:
            node_record_id: 节点记录ID
            
        Returns:
            节点记录详情字典，如果不存在则返回None
        """
        trace_node = self.db.query(TraceNode).filter(
            TraceNode.id == node_record_id
        ).first()
        
        if not trace_node:
            return None
        
        return trace_node.to_dict()
    
    def replay_trace(
        self,
        trace_id: str,
        replay_type: str = "full",
        start_node: str = None,
        end_node: str = None
    ) -> str:
        """
        创建回放会话
        
        Args:
            trace_id: 原始追踪会话ID
            replay_type: 回放类型（full, step_by_step, partial）
            start_node: 起始节点（用于部分回放）
            end_node: 结束节点（用于部分回放）
            
        Returns:
            replay_id: 回放会话ID
        """
        # 验证原始追踪会话存在
        trace_session = self.db.query(TraceSession).filter(
            TraceSession.trace_id == trace_id
        ).first()
        
        if not trace_session:
            raise ValueError(f"Trace session with id {trace_id} not found")
        
        # 创建回放记录
        trace_replay = TraceReplay(
            original_trace_id=trace_id,
            replay_type=replay_type,
            start_node=start_node,
            end_node=end_node
        )
        
        self.db.add(trace_replay)
        self.db.commit()
        self.db.refresh(trace_replay)
        
        return trace_replay.replay_id
    
    def get_replay_result(self, replay_id: str) -> Optional[Dict[str, Any]]:
        """
        获取回放结果
        
        Args:
            replay_id: 回放会话ID
            
        Returns:
            回放结果字典，如果不存在则返回None
        """
        trace_replay = self.db.query(TraceReplay).filter(
            TraceReplay.replay_id == replay_id
        ).first()
        
        if not trace_replay:
            return None
        
        return trace_replay.to_dict()
    
    def create_trace_view(
        self,
        trace_id: str,
        user_id: int,
        view_name: str,
        view_type: str = "step_by_step",
        view_config: Dict[str, Any] = None,
        filters: Dict[str, Any] = None,
        selected_nodes: List[str] = None
    ) -> str:
        """
        创建追踪视图
        
        Args:
            trace_id: 追踪会话ID
            user_id: 用户ID
            view_name: 视图名称
            view_type: 视图类型（step_by_step, timeline, comparison）
            view_config: 视图配置（可选）
            filters: 筛选条件（可选）
            selected_nodes: 选中的节点（可选）
            
        Returns:
            view_id: 视图ID
        """
        # 验证追踪会话存在
        trace_session = self.db.query(TraceSession).filter(
            TraceSession.trace_id == trace_id
        ).first()
        
        if not trace_session:
            raise ValueError(f"Trace session with id {trace_id} not found")
        
        # 创建视图
        trace_view = TraceView(
            trace_id=trace_id,
            user_id=user_id,
            view_name=view_name,
            view_type=view_type,
            view_config=view_config or {},
            filters=filters or {},
            selected_nodes=selected_nodes or []
        )
        
        self.db.add(trace_view)
        self.db.commit()
        self.db.refresh(trace_view)
        
        return trace_view.view_id
    
    def get_trace_view(self, view_id: str) -> Optional[Dict[str, Any]]:
        """
        获取追踪视图
        
        Args:
            view_id: 视图ID
            
        Returns:
            视图详情字典，如果不存在则返回None
        """
        trace_view = self.db.query(TraceView).filter(
            TraceView.view_id == view_id
        ).first()
        
        if not trace_view:
            return None
        
        return trace_view.to_dict()
    
    def search_trace_sessions(
        self,
        user_id: int = None,
        graph_id: str = None,
        status: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
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
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            tags: 标签列表（可选）
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            搜索结果字典，包含会话列表和总数
        """
        query = self.db.query(TraceSession)
        
        if user_id:
            query = query.filter(TraceSession.user_id == user_id)
        
        if graph_id:
            query = query.filter(TraceSession.graph_id == graph_id)
        
        if status:
            query = query.filter(TraceSession.status == status)
        
        if start_date:
            query = query.filter(TraceSession.created_at >= start_date)
        
        if end_date:
            query = query.filter(TraceSession.created_at <= end_date)
        
        if tags:
            # 使用JSON包含查询
            for tag in tags:
                query = query.filter(TraceSession.tags.contains([tag]))
        
        total = query.count()
        
        sessions = query.order_by(desc(TraceSession.created_at)).offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "sessions": [session.to_dict() for session in sessions],
            "limit": limit,
            "offset": offset
        }
    
    def _serialize_state(self, state: Union[Dict[str, Any], State, None]) -> Optional[Dict[str, Any]]:
        """
        序列化状态对象
        
        Args:
            state: 状态对象，可以是字典、State对象或None
            
        Returns:
            序列化后的字典，如果输入为None则返回None
        """
        if state is None:
            return None
        
        if isinstance(state, State):
            # 使用State的to_dict方法获取完整表示
            return state.to_dict()
        elif isinstance(state, dict):
            # 如果是字典，直接返回
            return copy.deepcopy(state)
        else:
            # 其他类型，尝试转换为字典
            try:
                return dict(state)
            except:
                # 如果无法转换，返回字符串表示
                return {"_raw": str(state)}
    
    def get_execution_summary(self, trace_id: str) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Args:
            trace_id: 追踪会话ID
            
        Returns:
            执行摘要字典
        """
        trace_session = self.db.query(TraceSession).filter(
            TraceSession.trace_id == trace_id
        ).first()
        
        if not trace_session:
            raise ValueError(f"Trace session with id {trace_id} not found")
        
        trace_nodes = self.db.query(TraceNode).filter(
            TraceNode.trace_id == trace_id
        ).all()
        
        # 统计节点执行情况
        total_nodes = len(trace_nodes)
        completed_nodes = sum(1 for node in trace_nodes if node.status == "completed")
        failed_nodes = sum(1 for node in trace_nodes if node.status == "failed")
        running_nodes = sum(1 for node in trace_nodes if node.status == "running")
        
        # 计算总执行时间
        total_duration = sum(node.duration or 0 for node in trace_nodes if node.duration)
        
        return {
            "trace_id": trace_id,
            "graph_id": trace_session.graph_id,
            "graph_name": trace_session.graph_name,
            "status": trace_session.status,
            "start_time": trace_session.start_time.isoformat() if trace_session.start_time else None,
            "end_time": trace_session.end_time.isoformat() if trace_session.end_time else None,
            "duration": trace_session.duration,
            "node_statistics": {
                "total": total_nodes,
                "completed": completed_nodes,
                "failed": failed_nodes,
                "running": running_nodes,
                "success_rate": completed_nodes / total_nodes if total_nodes > 0 else 0
            },
            "performance": {
                "total_duration": total_duration,
                "average_node_duration": total_duration / total_nodes if total_nodes > 0 else 0
            },
            "errors": trace_session.errors or []
        }


# 全局TraceManager实例工厂
def get_trace_manager(db_session: Session) -> TraceManager:
    """
    获取TraceManager实例
    
    Args:
        db_session: 数据库会话
        
    Returns:
        TraceManager实例
    """
    return TraceManager(db_session)
