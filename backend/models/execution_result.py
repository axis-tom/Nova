"""
执行结果存储模型
用于电商业务闭环系统的执行结果回流
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float, Text, ForeignKey
from sqlalchemy.sql import func
from backend.core.database import Base


class ExecutionResult(Base):
    """
    执行结果表 - 存储电商执行结果
    """
    __tablename__ = "execution_results"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(String(100), nullable=False, index=True, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 执行信息
    graph_type = Column(String(50), nullable=False)  # ecommerce_graph, etc.
    execution_type = Column(String(50), nullable=False)  # price_adjustment, inventory_update, etc.
    status = Column(String(20), nullable=False)  # success, failed, partial_success
    
    # 执行数据
    input_data = Column(JSON, nullable=True)  # 输入数据
    output_data = Column(JSON, nullable=True)  # 输出数据
    execution_log = Column(JSON, nullable=True)  # 执行日志
    
    # 性能指标
    execution_time = Column(Float, nullable=True)  # 执行时间（秒）
    api_calls = Column(Integer, nullable=True)  # API调用次数
    success_rate = Column(Float, nullable=True)  # 成功率
    
    # 业务指标
    roi_score = Column(Float, nullable=True)  # ROI评分
    conversion_score = Column(Float, nullable=True)  # 转化评分
    quality_score = Column(Float, nullable=True)  # 质量评分
    
    # 评估结果
    judge_evaluation = Column(JSON, nullable=True)  # Judge Agent评估结果
    optimization_suggestions = Column(JSON, nullable=True)  # 优化建议
    
    # 循环执行信息
    iteration_number = Column(Integer, default=1)  # 迭代次数
    parent_execution_id = Column(String(100), nullable=True, index=True)  # 父执行ID
    next_execution_id = Column(String(100), nullable=True, index=True)  # 下一次执行ID
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "user_id": self.user_id,
            "graph_type": self.graph_type,
            "execution_type": self.execution_type,
            "status": self.status,
            "execution_time": self.execution_time,
            "api_calls": self.api_calls,
            "success_rate": self.success_rate,
            "roi_score": self.roi_score,
            "conversion_score": self.conversion_score,
            "quality_score": self.quality_score,
            "iteration_number": self.iteration_number,
            "parent_execution_id": self.parent_execution_id,
            "next_execution_id": self.next_execution_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ActionLog(Base):
    """
    操作日志表 - 存储详细的操作记录
    """
    __tablename__ = "action_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(String(100), ForeignKey("execution_results.execution_id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # api_call, decision, analysis, etc.
    action_name = Column(String(100), nullable=False)
    
    # 操作详情
    parameters = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False)  # success, failed, pending
    
    # 性能数据
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Float, nullable=True)  # 持续时间（秒）
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "action_type": self.action_type,
            "action_name": self.action_name,
            "status": self.status,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class OptimizationHistory(Base):
    """
    优化历史表 - 存储策略优化历史
    """
    __tablename__ = "optimization_history"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(String(100), ForeignKey("execution_results.execution_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 优化信息
    optimization_type = Column(String(50), nullable=False)  # price, inventory, marketing, etc.
    previous_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    improvement_score = Column(Float, nullable=True)  # 改进评分
    
    # 业务影响
    estimated_impact = Column(JSON, nullable=True)  # 预估影响
    actual_impact = Column(JSON, nullable=True)  # 实际影响（后续更新）
    
    # 决策信息
    decision_reason = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)  # 置信度
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "optimization_type": self.optimization_type,
            "improvement_score": self.improvement_score,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class LoopExecution(Base):
    """
    循环执行表 - 存储循环执行信息
    """
    __tablename__ = "loop_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    loop_id = Column(String(100), nullable=False, index=True, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 循环配置
    loop_type = Column(String(50), nullable=False)  # timed, conditional, continuous
    trigger_condition = Column(JSON, nullable=True)  # 触发条件
    schedule_config = Column(JSON, nullable=True)  # 调度配置
    
    # 执行状态
    status = Column(String(20), nullable=False)  # active, paused, completed, failed
    current_iteration = Column(Integer, default=1)
    total_iterations = Column(Integer, nullable=True)  # None表示无限循环
    
    # 性能统计
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    average_execution_time = Column(Float, nullable=True)
    
    # 执行链
    execution_chain = Column(JSON, nullable=True)  # 执行ID链
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_executed_at = Column(DateTime(timezone=True), nullable=True)
    next_execution_at = Column(DateTime(timezone=True), nullable=True)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "loop_id": self.loop_id,
            "user_id": self.user_id,
            "loop_type": self.loop_type,
            "status": self.status,
            "current_iteration": self.current_iteration,
            "total_iterations": self.total_iterations,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None,
            "next_execution_at": self.next_execution_at.isoformat() if self.next_execution_at else None
        }