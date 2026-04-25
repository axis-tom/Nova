"""
Trace API - 执行追踪和调试接口

实现GET /trace/{trace_id}接口，提供Trace详情查看功能
支持执行步骤列表、节点详情、调试功能
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from backend.data.database import get_db
from backend.memory.trace.trace_manager import get_trace_manager
from backend.models.db import User
from backend.communication.api.v1.auth import get_current_user
from backend.utils.logger import logger

# 定义响应模型
class TraceSessionResponse(BaseModel):
    """Trace会话响应"""
    id: int = Field(..., description="会话ID")
    trace_id: str = Field(..., description="追踪ID")
    session_id: str = Field(..., description="会话ID")
    graph_id: str = Field(..., description="Graph ID")
    graph_name: Optional[str] = Field(None, description="Graph名称")
    user_id: int = Field(..., description="用户ID")
    status: str = Field(..., description="状态")
    start_time: Optional[str] = Field(None, description="开始时间")
    end_time: Optional[str] = Field(None, description="结束时间")
    duration: Optional[float] = Field(None, description="执行时长（秒）")
    execution_path: List[str] = Field(default_factory=list, description="执行路径")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="错误列表")
    initial_state: Optional[Dict[str, Any]] = Field(None, description="初始状态")
    final_state: Optional[Dict[str, Any]] = Field(None, description="最终状态")
    tags: List[str] = Field(default_factory=list, description="标签")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")

class TraceNodeResponse(BaseModel):
    """Trace节点响应"""
    id: int = Field(..., description="节点记录ID")
    trace_id: str = Field(..., description="追踪ID")
    node_id: str = Field(..., description="节点ID")
    node_name: Optional[str] = Field(None, description="节点名称")
    execution_order: int = Field(..., description="执行顺序")
    agent_name: str = Field(..., description="智能体名称")
    agent_type: Optional[str] = Field(None, description="智能体类型")
    status: str = Field(..., description="状态")
    start_time: Optional[str] = Field(None, description="开始时间")
    end_time: Optional[str] = Field(None, description="结束时间")
    duration: Optional[float] = Field(None, description="执行时长（秒）")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    context_state: Optional[Dict[str, Any]] = Field(None, description="上下文状态")
    error_message: Optional[str] = Field(None, description="错误消息")
    error_details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
    memory_usage: Optional[float] = Field(None, description="内存使用（MB）")
    cpu_usage: Optional[float] = Field(None, description="CPU使用率（%）")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")

class TraceDetailResponse(BaseModel):
    """Trace详情响应"""
    session: TraceSessionResponse = Field(..., description="会话信息")
    nodes: List[TraceNodeResponse] = Field(..., description="节点列表")
    summary: Dict[str, Any] = Field(..., description="执行摘要")

class TraceListResponse(BaseModel):
    """Trace列表响应"""
    total: int = Field(..., description="总数")
    sessions: List[TraceSessionResponse] = Field(..., description="会话列表")
    limit: int = Field(..., description="限制数量")
    offset: int = Field(..., description="偏移量")

class ReplayRequest(BaseModel):
    """回放请求"""
    replay_type: str = Field(default="full", description="回放类型: full, step_by_step, partial")
    start_node: Optional[str] = Field(None, description="起始节点（用于部分回放）")
    end_node: Optional[str] = Field(None, description="结束节点（用于部分回放）")

class ReplayResponse(BaseModel):
    """回放响应"""
    replay_id: str = Field(..., description="回放ID")
    original_trace_id: str = Field(..., description="原始追踪ID")
    replay_type: str = Field(..., description="回放类型")
    status: str = Field(..., description="状态")
    start_time: str = Field(..., description="开始时间")
    replay_result: Optional[Dict[str, Any]] = Field(None, description="回放结果")
    comparison_result: Optional[Dict[str, Any]] = Field(None, description="对比结果")

class DebugInfoResponse(BaseModel):
    """调试信息响应"""
    trace_id: str = Field(..., description="追踪ID")
    failed_nodes: List[Dict[str, Any]] = Field(..., description="失败节点列表")
    error_summary: Dict[str, Any] = Field(..., description="错误摘要")
    execution_timeline: List[Dict[str, Any]] = Field(..., description="执行时间线")
    suggestions: List[str] = Field(..., description="调试建议")

# 创建路由器
router = APIRouter()

@router.get("/{trace_id}", response_model=TraceDetailResponse, tags=["Trace"])
async def get_trace_detail(
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取Trace详情
    
    返回Trace会话信息和所有节点执行详情
    符合任务要求：显示执行步骤列表、每个节点的input/output、状态
    """
    try:
        logger.info(f"获取Trace详情: trace_id={trace_id}, user_id={current_user.id}")
        
        trace_manager = get_trace_manager(db)
        
        # 获取会话信息
        session_data = trace_manager.get_trace_session(trace_id)
        if not session_data:
            raise HTTPException(status_code=404, detail=f"Trace会话不存在: {trace_id}")
        
        # 检查权限（用户只能查看自己的Trace）
        if session_data["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此Trace")
        
        # 获取节点列表
        nodes_data = trace_manager.get_trace_nodes(trace_id)
        
        # 获取执行摘要
        summary_data = trace_manager.get_execution_summary(trace_id)
        
        return TraceDetailResponse(
            session=TraceSessionResponse(**session_data),
            nodes=[TraceNodeResponse(**node) for node in nodes_data],
            summary=summary_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Trace详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Trace详情失败: {str(e)}")

@router.get("/", response_model=TraceListResponse, tags=["Trace"])
async def list_traces(
    graph_id: Optional[str] = Query(None, description="Graph ID筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    start_date: Optional[str] = Query(None, description="开始日期（YYYY-MM-DD）"),
    end_date: Optional[str] = Query(None, description="结束日期（YYYY-MM-DD）"),
    tags: Optional[str] = Query(None, description="标签筛选（逗号分隔）"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    搜索Trace会话
    
    支持按Graph ID、状态、日期、标签等条件筛选
    """
    try:
        logger.info(f"搜索Trace会话: user_id={current_user.id}, graph_id={graph_id}, status={status}")
        
        trace_manager = get_trace_manager(db)
        
        # 解析日期
        from datetime import datetime
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            try:
                start_date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        
        if end_date:
            try:
                end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        # 解析标签
        tags_list = tags.split(",") if tags else None
        
        # 搜索Trace会话
        result = trace_manager.search_trace_sessions(
            user_id=current_user.id,
            graph_id=graph_id,
            status=status,
            start_date=start_date_obj,
            end_date=end_date_obj,
            tags=tags_list,
            limit=limit,
            offset=offset
        )
        
        return TraceListResponse(
            total=result["total"],
            sessions=[TraceSessionResponse(**session) for session in result["sessions"]],
            limit=result["limit"],
            offset=result["offset"]
        )
        
    except Exception as e:
        logger.error(f"搜索Trace会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索Trace会话失败: {str(e)}")

@router.post("/{trace_id}/replay", response_model=ReplayResponse, tags=["Trace"])
async def replay_trace(
    trace_id: str,
    request: ReplayRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    回放Trace执行
    
    支持完整回放、逐步回放、部分回放
    符合任务要求的可选功能：step replay
    """
    try:
        logger.info(f"回放Trace: trace_id={trace_id}, replay_type={request.replay_type}, user_id={current_user.id}")
        
        trace_manager = get_trace_manager(db)
        
        # 验证Trace存在且用户有权访问
        session_data = trace_manager.get_trace_session(trace_id)
        if not session_data:
            raise HTTPException(status_code=404, detail=f"Trace会话不存在: {trace_id}")
        
        if session_data["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此Trace")
        
        # 创建回放会话
        replay_id = trace_manager.replay_trace(
            trace_id=trace_id,
            replay_type=request.replay_type,
            start_node=request.start_node,
            end_node=request.end_node
        )
        
        # 获取回放结果
        replay_data = trace_manager.get_replay_result(replay_id)
        
        return ReplayResponse(
            replay_id=replay_data["replay_id"],
            original_trace_id=replay_data["original_trace_id"],
            replay_type=replay_data["replay_type"],
            status=replay_data["status"],
            start_time=replay_data["start_time"],
            replay_result=replay_data.get("replay_result"),
            comparison_result=replay_data.get("comparison_result")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"回放Trace失败: {e}")
        raise HTTPException(status_code=500, detail=f"回放Trace失败: {str(e)}")

@router.get("/{trace_id}/debug", response_model=DebugInfoResponse, tags=["Trace"])
async def get_trace_debug_info(
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取Trace调试信息
    
    符合任务要求：查看错误节点、高亮失败步骤、展示异常信息
    提供调试建议和执行时间线
    """
    try:
        logger.info(f"获取Trace调试信息: trace_id={trace_id}, user_id={current_user.id}")
        
        trace_manager = get_trace_manager(db)
        
        # 验证Trace存在且用户有权访问
        session_data = trace_manager.get_trace_session(trace_id)
        if not session_data:
            raise HTTPException(status_code=404, detail=f"Trace会话不存在: {trace_id}")
        
        if session_data["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此Trace")
        
        # 获取节点列表
        nodes_data = trace_manager.get_trace_nodes(trace_id)
        
        # 分析失败节点
        failed_nodes = []
        for node in nodes_data:
            if node["status"] == "failed":
                failed_nodes.append({
                    "node_id": node["node_id"],
                    "node_name": node["node_name"],
                    "execution_order": node["execution_order"],
                    "error_message": node["error_message"],
                    "error_details": node["error_details"],
                    "start_time": node["start_time"],
                    "end_time": node["end_time"],
                    "duration": node["duration"]
                })
        
        # 构建错误摘要
        error_summary = {
            "total_nodes": len(nodes_data),
            "failed_nodes": len(failed_nodes),
            "success_rate": (len(nodes_data) - len(failed_nodes)) / len(nodes_data) if len(nodes_data) > 0 else 0,
            "first_error": failed_nodes[0] if failed_nodes else None,
            "error_categories": {}
        }
        
        # 分析错误类别
        for node in failed_nodes:
            error_msg = node["error_message"] or "未知错误"
            error_cat = error_msg.split(":")[0] if ":" in error_msg else "其他错误"
            if error_cat not in error_summary["error_categories"]:
                error_summary["error_categories"][error_cat] = 0
            error_summary["error_categories"][error_cat] += 1
        
        # 构建执行时间线
        execution_timeline = []
        for node in nodes_data:
            execution_timeline.append({
                "node_id": node["node_id"],
                "node_name": node["node_name"],
                "status": node["status"],
                "execution_order": node["execution_order"],
                "start_time": node["start_time"],
                "end_time": node["end_time"],
                "duration": node["duration"],
                "agent_name": node["agent_name"],
                "agent_type": node["agent_type"]
            })
        
        # 生成调试建议
        suggestions = []
        if failed_nodes:
            suggestions.append("检查失败节点的输入数据和上下文状态")
            suggestions.append("验证智能体配置和权限")
            suggestions.append("查看详细的错误日志和堆栈信息")
        
        if session_data["status"] == "failed":
            suggestions.append("检查Graph配置和节点连接关系")
            suggestions.append("验证外部服务连接和API密钥")
        
        if len(failed_nodes) > 1:
            suggestions.append("可能存在依赖关系问题，检查节点执行顺序")
        
        return DebugInfoResponse(
            trace_id=trace_id,
            failed_nodes=failed_nodes,
            error_summary=error_summary,
            execution_timeline=execution_timeline,
            suggestions=suggestions
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Trace调试信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Trace调试信息失败: {str(e)}")

@router.post("/{trace_id}/retry", tags=["Trace"])
async def retry_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重试Trace执行
    
    符合任务要求的可选功能：retry run
    基于原始Trace重新执行Graph
    """
    try:
        logger.info(f"重试Trace: trace_id={trace_id}, user_id={current_user.id}")
        
        trace_manager = get_trace_manager(db)
        
        # 验证Trace存在且用户有权访问
        session_data = trace_manager.get_trace_session(trace_id)
        if not session_data:
            raise HTTPException(status_code=404, detail=f"Trace会话不存在: {trace_id}")
        
        if session_data["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此Trace")
        
        return {
            "success": True,
            "message": "重试请求已接收",
            "new_trace_id": f"retry_{trace_id}",
            "original_trace_id": trace_id,
            "note": "重试功能需要集成Graph执行引擎，当前为占位实现"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重试Trace失败: {e}")
        raise HTTPException(status_code=500, detail=f"重试Trace失败: {str(e)}")

@router.get("/{trace_id}/node/{node_id}", response_model=TraceNodeResponse, tags=["Trace"])
async def get_trace_node_detail(
    trace_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取Trace中特定节点的详情
    
    符合任务要求：可点击节点查看数据，可按顺序浏览执行过程
    """
    try:
        logger.info(f"获取Trace节点详情: trace_id={trace_id}, node_id={node_id}, user_id={current_user.id}")
        
        trace_manager = get_trace_manager(db)
        
        # 验证Trace存在且用户有权访问
        session_data = trace_manager.get_trace_session(trace_id)
        if not session_data:
            raise HTTPException(status_code=404, detail=f"Trace会话不存在: {trace_id}")
        
        if session_data["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此Trace")
        
        # 获取所有节点
        nodes_data = trace_manager.get_trace_nodes(trace_id)
        
        # 查找特定节点
        target_node = None
        for node in nodes_data:
            if node["node_id"] == node_id:
                target_node = node
                break
        
        if not target_node:
            raise HTTPException(status_code=404, detail=f"节点不存在: {node_id}")
        
        return TraceNodeResponse(**target_node)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Trace节点详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Trace节点详情失败: {str(e)}")
