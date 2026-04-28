"""
执行追踪系统模型
用于记录和回放Graph执行过程
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text, Float
from sqlalchemy.sql import func
from backend.data.database import Base
import uuid
from datetime import datetime


class TraceSession(Base):
    """
    追踪会话表 - 存储Graph执行的完整会话
    对应任务要求的 trace_session 结构
    """
    __tablename__ = "trace_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(36), nullable=False, index=True, unique=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    
    # Graph信息
    graph_id = Column(String(100), nullable=False, index=True)
    graph_name = Column(String(200), nullable=True)
    graph_config = Column(JSON, nullable=True)  # 完整的Graph配置
    
    # 执行信息
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="running")  # running, completed, failed, cancelled
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Float, nullable=True)  # 执行时长（秒）
    
    # 执行路径和状态
    execution_path = Column(JSON, nullable=True)  # 执行路径 [node_id1, node_id2, ...]
    errors = Column(JSON, nullable=True)  # 错误列表
    
    # 初始状态和最终状态
    initial_state = Column(JSON, nullable=True)  # 初始状态快照
    final_state = Column(JSON, nullable=True)  # 最终状态快照
    
    # 元数据
    tags = Column(JSON, nullable=True)  # 标签，用于分类和搜索
    meta_info = Column(JSON, nullable=True)  # 其他元数据（避免使用metadata保留字）
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "graph_id": self.graph_id,
            "graph_name": self.graph_name,
            "user_id": self.user_id,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "execution_path": self.execution_path or [],
            "errors": self.errors or [],
            "initial_state": self.initial_state,
            "final_state": self.final_state,
            "tags": self.tags or [],
            "metadata": self.meta_info or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def mark_completed(self, final_state=None):
        """标记会话为完成"""
        self.status = "completed"
        self.end_time = datetime.now()
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
        if final_state:
            self.final_state = final_state
    
    def mark_failed(self, error_message=None):
        """标记会话为失败"""
        self.status = "failed"
        self.end_time = datetime.now()
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
        if error_message:
            if not self.errors:
                self.errors = []
            self.errors.append({
                "timestamp": datetime.now().isoformat(),
                "message": error_message
            })


class TraceNode(Base):
    """
    追踪节点表 - 存储Graph中每个节点的执行详情
    对应任务要求的每个Graph执行必须记录的信息
    """
    __tablename__ = "trace_nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(36), ForeignKey("trace_sessions.trace_id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String(100), nullable=False, index=True)
    node_name = Column(String(200), nullable=True)
    
    # 执行顺序
    execution_order = Column(Integer, nullable=False)  # 执行顺序（从1开始）
    
    # 智能体信息
    agent_name = Column(String(100), nullable=False)
    agent_type = Column(String(50), nullable=True)
    
    # 输入输出数据（任务要求必须记录）
    input_data = Column(JSON, nullable=True)  # 输入数据
    output_data = Column(JSON, nullable=True)  # 输出数据
    context_state = Column(JSON, nullable=True)  # 上下文状态（执行时的完整状态）
    
    # 执行状态
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Float, nullable=True)  # 执行时长（秒）
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # 性能指标
    memory_usage = Column(Float, nullable=True)  # 内存使用（MB）
    cpu_usage = Column(Float, nullable=True)  # CPU使用率（%）
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "execution_order": self.execution_order,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "context_state": self.context_state,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def mark_running(self):
        """标记节点为运行中"""
        self.status = "running"
        self.start_time = datetime.now()
    
    def mark_completed(self, output_data=None, context_state=None):
        """标记节点为完成"""
        self.status = "completed"
        self.end_time = datetime.now()
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
        if output_data:
            self.output_data = output_data
        if context_state:
            self.context_state = context_state
    
    def mark_failed(self, error_message=None, error_details=None):
        """标记节点为失败"""
        self.status = "failed"
        self.end_time = datetime.now()
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
        if error_message:
            self.error_message = error_message
        if error_details:
            self.error_details = error_details


class TraceReplay(Base):
    """
    追踪回放表 - 存储回放会话信息
    """
    __tablename__ = "trace_replays"
    
    id = Column(Integer, primary_key=True, index=True)
    replay_id = Column(String(36), nullable=False, index=True, unique=True, default=lambda: str(uuid.uuid4()))
    original_trace_id = Column(String(36), ForeignKey("trace_sessions.trace_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 回放配置
    replay_type = Column(String(20), nullable=False, default="full")  # full, step_by_step, partial
    start_node = Column(String(100), nullable=True)  # 起始节点（用于部分回放）
    end_node = Column(String(100), nullable=True)  # 结束节点（用于部分回放）
    
    # 回放状态
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Float, nullable=True)  # 回放时长（秒）
    
    # 回放结果
    replay_result = Column(JSON, nullable=True)  # 回放结果
    replay_errors = Column(JSON, nullable=True)  # 回放过程中的错误
    comparison_result = Column(JSON, nullable=True)  # 与原执行的对比结果
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "replay_id": self.replay_id,
            "original_trace_id": self.original_trace_id,
            "replay_type": self.replay_type,
            "start_node": self.start_node,
            "end_node": self.end_node,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "replay_result": self.replay_result,
            "replay_errors": self.replay_errors,
            "comparison_result": self.comparison_result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def mark_completed(self, replay_result=None, comparison_result=None):
        """标记回放为完成"""
        self.status = "completed"
        self.end_time = datetime.now()
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
        if replay_result:
            self.replay_result = replay_result
        if comparison_result:
            self.comparison_result = comparison_result
    
    def mark_failed(self, error_message=None):
        """标记回放为失败"""
        self.status = "failed"
        self.end_time = datetime.now()
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
        if error_message:
            if not self.replay_errors:
                self.replay_errors = []
            self.replay_errors.append({
                "timestamp": datetime.now().isoformat(),
                "message": error_message
            })


class TraceView(Base):
    """
    追踪视图表 - 存储用户创建的追踪视图配置
    用于支持逐节点查看功能
    """
    __tablename__ = "trace_views"
    
    id = Column(Integer, primary_key=True, index=True)
    view_id = Column(String(36), nullable=False, index=True, unique=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trace_id = Column(String(36), ForeignKey("trace_sessions.trace_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 视图配置
    view_name = Column(String(200), nullable=False)
    view_type = Column(String(20), nullable=False, default="step_by_step")  # step_by_step, timeline, comparison
    view_config = Column(JSON, nullable=True)  # 视图配置
    
    # 筛选条件
    filters = Column(JSON, nullable=True)  # 筛选条件
    selected_nodes = Column(JSON, nullable=True)  # 选中的节点
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "view_id": self.view_id,
            "user_id": self.user_id,
            "trace_id": self.trace_id,
            "view_name": self.view_name,
            "view_type": self.view_type,
            "view_config": self.view_config or {},
            "filters": self.filters or {},
            "selected_nodes": self.selected_nodes or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }