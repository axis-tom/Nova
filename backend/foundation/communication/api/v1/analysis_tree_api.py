"""
Analysis Tree API — 选品分析树查询 / 回溯 / 追加维度
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from nova_agent_system.analysis_tree import analysis_tree_manager
from nova_agent_system.session_store import session_store
from backend.common.core.state import State
from backend.data.database import get_db
from backend.data.models.db import AgentConversation
from backend.foundation.communication.api.v1.auth import get_current_user

router = APIRouter(prefix="/agent", tags=["分析树"])


class BacktrackRequest(BaseModel):
    invocation_id: str


class AppendDimensionRequest(BaseModel):
    agent_name: str
    dimension_label: str
    dimension_params: dict = {}


# ── 获取分析树 ──

@router.get("/conversations/{conv_id}/tree")
async def get_analysis_tree(
    conv_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前分析树完整结构"""
    conv = await db.get(AgentConversation, conv_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="对话不存在")

    tree_dict = analysis_tree_manager.to_dict(conv_id)
    checkpoints = analysis_tree_manager.get_checkpoints_for_conv(conv_id)

    return {
        "conversation_id": conv_id,
        "tree": tree_dict,
        "checkpoints": checkpoints,
    }


# ── 回溯 ──

@router.post("/conversations/{conv_id}/tree/backtrack")
async def backtrack_analysis(
    conv_id: str,
    req: BacktrackRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    恢复到指定 invocation 的 checkpoint state，
    清理该 invocation 之后的所有 tree node，
    然后 LLM 可从此位置继续自由执行。
    """
    conv = await db.get(AgentConversation, conv_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="对话不存在")

    # 检查 invocation 是否存在
    tree = analysis_tree_manager.get_tree(conv_id)
    if not tree:
        raise HTTPException(status_code=404, detail="该对话没有分析树")

    inv = tree.find_invocation(req.invocation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="未找到指定的分析节点")

    # 执行回溯
    state_dict = analysis_tree_manager.backtrack(conv_id, req.invocation_id)

    # 恢复 SessionStore 中的 State
    if state_dict:
        current_state = session_store.get_or_create(conv_id)
        current_state.data = state_dict.get("data", {})
        current_state.events = state_dict.get("events", [])
        current_state.meta = state_dict.get("meta", {"trace_id": None, "step": 0})
        session_store.save(conv_id)

    return {
        "ok": True,
        "invocation_id": req.invocation_id,
        "agent_name": inv.agent_name,
        "branch_label": inv.branch_label,
        "checkpoint_id": inv.checkpoint_id,
        "restored_state_keys": list(state_dict.get("data", {}).keys()) if state_dict else [],
        "message": f"已回溯到 [{inv.branch_label}]，可发送新消息让 LLM 从此继续分析",
    }


# ── 追加维度 ──

@router.post("/conversations/{conv_id}/tree/append_dimension")
async def append_dimension(
    conv_id: str,
    req: AppendDimensionRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    在指定 agent 分支下追加新分析维度：
    1. 找到该 agent 最近一次 invocation 的 checkpoint
    2. 恢复到该 checkpoint
    3. 把新维度参数合并到 state
    4. 返回就绪，前端可发送新消息触发重跑
    """
    conv = await db.get(AgentConversation, conv_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="对话不存在")

    tree = analysis_tree_manager.get_tree(conv_id)
    if not tree:
        raise HTTPException(status_code=404, detail="该对话没有分析树")

    branch = tree.branches.get(req.agent_name)
    if not branch:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 agent [{req.agent_name}] 的分析分支",
        )

    last_inv = branch.last_invocation()
    if not last_inv:
        raise HTTPException(status_code=404, detail=f"Agent [{req.agent_name}] 暂无调用记录")

    # 回溯到该 agent 最近一次 invocation
    state_dict = analysis_tree_manager.backtrack(conv_id, last_inv.invocation_id)

    # 把新维度参数合并到 state
    if state_dict:
        current_state = session_store.get_or_create(conv_id)
        current_state.data = state_dict.get("data", {})
        current_state.events = state_dict.get("events", [])
        current_state.meta = state_dict.get("meta", {"trace_id": None, "step": 0})

        # 合并新维度参数
        for k, v in req.dimension_params.items():
            current_state.set(k, v)

        # 记录追加的维度标签
        appended_dims = current_state.get("appended_dimensions") or []
        appended_dims.append({
            "agent_name": req.agent_name,
            "dimension_label": req.dimension_label,
            "params": req.dimension_params,
        })
        current_state.set("appended_dimensions", appended_dims)

        session_store.save(conv_id)

    return {
        "ok": True,
        "agent_name": req.agent_name,
        "dimension_label": req.dimension_label,
        "checkpoint_id": last_inv.checkpoint_id,
        "restored_state_keys": list(state_dict.get("data", {}).keys()) if state_dict else [],
        "message": f"已准备就绪，维度 [{req.dimension_label}] 将追加到 [{branch.label}] 分支，请发送新消息触发重跑",
    }