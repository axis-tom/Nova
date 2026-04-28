"""
执行结果管理器
负责执行结果的存储、检索和管理
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import json
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from backend.models.execution_result import (
    ExecutionResult, ActionLog, OptimizationHistory, LoopExecution
)
from backend.core.database import AsyncSessionLocal


class ExecutionResultManager:
    """
    执行结果管理器
    提供执行结果的CRUD操作和查询功能
    """
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        """
        初始化执行结果管理器
        
        Args:
            db_session: 数据库会话，如果为None则创建新会话
        """
        self.db_session = db_session or AsyncSessionLocal()
    
    def create_execution_result(self, execution_data: Dict[str, Any]) -> ExecutionResult:
        """
        创建执行结果记录
        
        Args:
            execution_data: 执行数据
            
        Returns:
            创建的ExecutionResult对象
        """
        # 生成执行ID
        execution_id = execution_data.get('execution_id') or f"exec_{uuid.uuid4().hex[:16]}"
        
        # 创建执行结果记录
        execution_result = ExecutionResult(
            execution_id=execution_id,
            user_id=execution_data.get('user_id', 1),  # 默认用户ID
            graph_type=execution_data.get('graph_type', 'ecommerce_graph'),
            execution_type=execution_data.get('execution_type', 'unknown'),
            status=execution_data.get('status', 'pending'),
            input_data=execution_data.get('input_data'),
            output_data=execution_data.get('output_data'),
            execution_log=execution_data.get('execution_log'),
            execution_time=execution_data.get('execution_time'),
            api_calls=execution_data.get('api_calls'),
            success_rate=execution_data.get('success_rate'),
            roi_score=execution_data.get('roi_score'),
            conversion_score=execution_data.get('conversion_score'),
            quality_score=execution_data.get('quality_score'),
            judge_evaluation=execution_data.get('judge_evaluation'),
            optimization_suggestions=execution_data.get('optimization_suggestions'),
            iteration_number=execution_data.get('iteration_number', 1),
            parent_execution_id=execution_data.get('parent_execution_id'),
            next_execution_id=execution_data.get('next_execution_id')
        )
        
        self.db_session.add(execution_result)
        self.db_session.commit()
        
        return execution_result
    
    def update_execution_result(self, execution_id: str, update_data: Dict[str, Any]) -> Optional[ExecutionResult]:
        """
        更新执行结果记录
        
        Args:
            execution_id: 执行ID
            update_data: 更新数据
            
        Returns:
            更新后的ExecutionResult对象，如果不存在则返回None
        """
        execution_result = self.get_execution_result(execution_id)
        
        if not execution_result:
            return None
        
        # 更新字段
        for key, value in update_data.items():
            if hasattr(execution_result, key):
                setattr(execution_result, key, value)
        
        execution_result.updated_at = datetime.utcnow()
        self.db_session.commit()
        
        return execution_result
    
    def get_execution_result(self, execution_id: str) -> Optional[ExecutionResult]:
        """
        获取执行结果记录
        
        Args:
            execution_id: 执行ID
            
        Returns:
            ExecutionResult对象，如果不存在则返回None
        """
        return self.db_session.query(ExecutionResult).filter(
            ExecutionResult.execution_id == execution_id
        ).first()
    
    def get_execution_results(self, 
                             user_id: Optional[int] = None,
                             graph_type: Optional[str] = None,
                             status: Optional[str] = None,
                             limit: int = 100,
                             offset: int = 0) -> List[ExecutionResult]:
        """
        获取执行结果列表
        
        Args:
            user_id: 用户ID过滤
            graph_type: Graph类型过滤
            status: 状态过滤
            limit: 返回条数限制
            offset: 偏移量
            
        Returns:
            执行结果列表
        """
        query = self.db_session.query(ExecutionResult)
        
        # 应用过滤条件
        if user_id is not None:
            query = query.filter(ExecutionResult.user_id == user_id)
        
        if graph_type is not None:
            query = query.filter(ExecutionResult.graph_type == graph_type)
        
        if status is not None:
            query = query.filter(ExecutionResult.status == status)
        
        # 按创建时间倒序排序
        query = query.order_by(desc(ExecutionResult.created_at))
        
        # 应用分页
        query = query.offset(offset).limit(limit)
        
        return query.all()
    
    def add_action_log(self, execution_id: str, action_data: Dict[str, Any]) -> ActionLog:
        """
        添加操作日志
        
        Args:
            execution_id: 执行ID
            action_data: 操作数据
            
        Returns:
            创建的ActionLog对象
        """
        action_log = ActionLog(
            execution_id=execution_id,
            action_type=action_data.get('action_type', 'unknown'),
            action_name=action_data.get('action_name', 'unknown'),
            parameters=action_data.get('parameters'),
            result=action_data.get('result'),
            status=action_data.get('status', 'pending'),
            start_time=action_data.get('start_time'),
            end_time=action_data.get('end_time'),
            duration=action_data.get('duration'),
            error_message=action_data.get('error_message'),
            error_details=action_data.get('error_details')
        )
        
        self.db_session.add(action_log)
        self.db_session.commit()
        
        return action_log
    
    def get_action_logs(self, execution_id: str) -> List[ActionLog]:
        """
        获取执行的操作日志
        
        Args:
            execution_id: 执行ID
            
        Returns:
            操作日志列表
        """
        return self.db_session.query(ActionLog).filter(
            ActionLog.execution_id == execution_id
        ).order_by(ActionLog.created_at).all()
    
    def add_optimization_history(self, execution_id: str, optimization_data: Dict[str, Any]) -> OptimizationHistory:
        """
        添加优化历史记录
        
        Args:
            execution_id: 执行ID
            optimization_data: 优化数据
            
        Returns:
            创建的OptimizationHistory对象
        """
        optimization = OptimizationHistory(
            execution_id=execution_id,
            optimization_type=optimization_data.get('optimization_type', 'unknown'),
            previous_value=optimization_data.get('previous_value'),
            new_value=optimization_data.get('new_value'),
            improvement_score=optimization_data.get('improvement_score'),
            estimated_impact=optimization_data.get('estimated_impact'),
            actual_impact=optimization_data.get('actual_impact'),
            decision_reason=optimization_data.get('decision_reason'),
            confidence_score=optimization_data.get('confidence_score')
        )
        
        self.db_session.add(optimization)
        self.db_session.commit()
        
        return optimization
    
    def get_optimization_history(self, execution_id: str) -> List[OptimizationHistory]:
        """
        获取执行的优化历史
        
        Args:
            execution_id: 执行ID
            
        Returns:
            优化历史列表
        """
        return self.db_session.query(OptimizationHistory).filter(
            OptimizationHistory.execution_id == execution_id
        ).order_by(OptimizationHistory.created_at).all()
    
    def create_loop_execution(self, loop_data: Dict[str, Any]) -> LoopExecution:
        """
        创建循环执行记录
        
        Args:
            loop_data: 循环执行数据
            
        Returns:
            创建的LoopExecution对象
        """
        loop_id = loop_data.get('loop_id') or f"loop_{uuid.uuid4().hex[:16]}"
        
        loop_execution = LoopExecution(
            loop_id=loop_id,
            user_id=loop_data.get('user_id', 1),
            loop_type=loop_data.get('loop_type', 'continuous'),
            trigger_condition=loop_data.get('trigger_condition'),
            schedule_config=loop_data.get('schedule_config'),
            status=loop_data.get('status', 'active'),
            current_iteration=loop_data.get('current_iteration', 1),
            total_iterations=loop_data.get('total_iterations'),
            success_count=loop_data.get('success_count', 0),
            failure_count=loop_data.get('failure_count', 0),
            average_execution_time=loop_data.get('average_execution_time'),
            execution_chain=loop_data.get('execution_chain'),
            last_executed_at=loop_data.get('last_executed_at'),
            next_execution_at=loop_data.get('next_execution_at')
        )
        
        self.db_session.add(loop_execution)
        self.db_session.commit()
        
        return loop_execution
    
    def update_loop_execution(self, loop_id: str, update_data: Dict[str, Any]) -> Optional[LoopExecution]:
        """
        更新循环执行记录
        
        Args:
            loop_id: 循环ID
            update_data: 更新数据
            
        Returns:
            更新后的LoopExecution对象，如果不存在则返回None
        """
        loop_execution = self.get_loop_execution(loop_id)
        
        if not loop_execution:
            return None
        
        # 更新字段
        for key, value in update_data.items():
            if hasattr(loop_execution, key):
                setattr(loop_execution, key, value)
        
        loop_execution.updated_at = datetime.utcnow()
        self.db_session.commit()
        
        return loop_execution
    
    def get_loop_execution(self, loop_id: str) -> Optional[LoopExecution]:
        """
        获取循环执行记录
        
        Args:
            loop_id: 循环ID
            
        Returns:
            LoopExecution对象，如果不存在则返回None
        """
        return self.db_session.query(LoopExecution).filter(
            LoopExecution.loop_id == loop_id
        ).first()
    
    def get_active_loops(self, user_id: Optional[int] = None) -> List[LoopExecution]:
        """
        获取活跃的循环执行
        
        Args:
            user_id: 用户ID过滤
            
        Returns:
            活跃循环执行列表
        """
        query = self.db_session.query(LoopExecution).filter(
            LoopExecution.status == 'active'
        )
        
        if user_id is not None:
            query = query.filter(LoopExecution.user_id == user_id)
        
        return query.order_by(LoopExecution.next_execution_at).all()
    
    def add_execution_to_loop(self, loop_id: str, execution_id: str) -> bool:
        """
        将执行添加到循环执行链
        
        Args:
            loop_id: 循环ID
            execution_id: 执行ID
            
        Returns:
            是否成功添加
        """
        loop_execution = self.get_loop_execution(loop_id)
        
        if not loop_execution:
            return False
        
        # 获取当前执行链
        execution_chain = loop_execution.execution_chain or []
        
        # 添加新执行ID
        execution_chain.append(execution_id)
        
        # 更新执行链
        loop_execution.execution_chain = execution_chain
        loop_execution.current_iteration = len(execution_chain)
        loop_execution.last_executed_at = datetime.utcnow()
        
        self.db_session.commit()
        
        return True
    
    def get_execution_statistics(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        获取执行统计信息
        
        Args:
            user_id: 用户ID过滤
            
        Returns:
            执行统计信息
        """
        query = self.db_session.query(ExecutionResult)
        
        if user_id is not None:
            query = query.filter(ExecutionResult.user_id == user_id)
        
        # 获取所有执行结果
        executions = query.all()
        
        if not executions:
            return {
                "total_executions": 0,
                "success_rate": 0,
                "average_execution_time": 0,
                "total_api_calls": 0
            }
        
        # 计算统计信息
        total_executions = len(executions)
        successful_executions = sum(1 for e in executions if e.status == 'success')
        failed_executions = sum(1 for e in executions if e.status == 'failed')
        
        execution_times = [e.execution_time for e in executions if e.execution_time is not None]
        average_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        api_calls = [e.api_calls for e in executions if e.api_calls is not None]
        total_api_calls = sum(api_calls) if api_calls else 0
        
        roi_scores = [e.roi_score for e in executions if e.roi_score is not None]
        average_roi_score = sum(roi_scores) / len(roi_scores) if roi_scores else 0
        
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": (successful_executions / total_executions * 100) if total_executions > 0 else 0,
            "average_execution_time": average_execution_time,
            "total_api_calls": total_api_calls,
            "average_roi_score": average_roi_score,
            "last_execution_time": executions[0].created_at.isoformat() if executions else None
        }
    
    def get_optimization_trends(self, user_id: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取优化趋势
        
        Args:
            user_id: 用户ID过滤
            limit: 返回条数限制
            
        Returns:
            优化趋势数据
        """
        # 获取最近的执行结果
        query = self.db_session.query(ExecutionResult)
        
        if user_id is not None:
            query = query.filter(ExecutionResult.user_id == user_id)
        
        executions = query.order_by(desc(ExecutionResult.created_at)).limit(limit).all()
        
        trends = []
        for execution in executions:
            trends.append({
                "execution_id": execution.execution_id,
                "created_at": execution.created_at.isoformat() if execution.created_at else None,
                "roi_score": execution.roi_score,
                "conversion_score": execution.conversion_score,
                "quality_score": execution.quality_score,
                "status": execution.status,
                "execution_type": execution.execution_type
            })
        
        return trends
    
    def close(self):
        """关闭数据库会话"""
        if self.db_session:
            self.db_session.close()


# 全局执行结果管理器实例
_execution_result_manager = None

def get_execution_result_manager() -> ExecutionResultManager:
    """
    获取执行结果管理器实例（单例模式）
    
    Returns:
        执行结果管理器实例
    """
    global _execution_result_manager
    if _execution_result_manager is None:
        _execution_result_manager = ExecutionResultManager()
    return _execution_result_manager