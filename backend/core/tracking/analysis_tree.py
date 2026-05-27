"""
AnalysisTreeManager — 分析树生命周期管理 + Checkpoint 持久化

职责：
1. 维护每个 conversation_id 的 AnalysisTree 内存实例
2. Agent 调用前后自动追踪（记录 invocation + 保存 checkpoint + 推送 SSE 事件）
3. 回溯：恢复到指定 invocation 的 checkpoint state，清理后续节点
4. 追加维度：在 agent 分支下追加新分析维度后重跑
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from backend.common.core.analysis_trace import (
    AGENT_BRANCH_LABELS,
    AgentInvocation,
    AnalysisCheckpoint,
    AnalysisTree,
    _extract_dimensions,
)
from backend.core.memory.durable import get_durable_session

logger = logging.getLogger(__name__)


class AnalysisTreeManager:
    """分析树管理器（单例）"""

    def __init__(self):
        self._trees: Dict[str, AnalysisTree] = {}
        self._lock = threading.RLock()
        self._durable = get_durable_session()
        # SSE 事件回调：callbacks 接收 (event_dict) 并放入 asyncio.Queue
        self._event_queues: Dict[str, asyncio.Queue] = {}

    # ── 树生命周期 ──

    def get_or_create_tree(self, conv_id: str) -> AnalysisTree:
        with self._lock:
            if conv_id not in self._trees:
                self._trees[conv_id] = AnalysisTree(conversation_id=conv_id)
            return self._trees[conv_id]

    def get_tree(self, conv_id: str) -> Optional[AnalysisTree]:
        with self._lock:
            return self._trees.get(conv_id)

    def remove_tree(self, conv_id: str) -> None:
        with self._lock:
            self._trees.pop(conv_id, None)
            self._event_queues.pop(conv_id, None)

    # ── Agent 追踪 ──

    def on_agent_start(
        self, conv_id: str, agent_name: str, params: dict, conversation_round: int = 0
    ) -> AgentInvocation:
        """Agent 执行前调用：创建 invocation、推送 tree_node_status(running)"""
        tree = self.get_or_create_tree(conv_id)
        inv = tree.add_invocation(agent_name, params, conversation_round)
        tree.conversation_round = conversation_round
        self._emit(conv_id, {
            "type": "tree_node_status",
            "data": {
                "invocation_id": inv.invocation_id,
                "agent_name": agent_name,
                "branch_label": inv.branch_label,
                "status": "running",
                "dimensions": inv.dimensions,
            },
        })
        return inv

    def on_agent_end(
        self,
        conv_id: str,
        invocation_id: str,
        result_summary: str = "",
        state_dict: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> Optional[str]:
        """Agent 执行后调用：完成 invocation、保存 checkpoint、推送 tree_node_added"""
        tree = self.get_tree(conv_id)
        if not tree:
            logger.warning(f"[AnalysisTree] No tree for {conv_id}")
            return None

        tree.complete_invocation(invocation_id, result_summary, error_message=error_message)
        inv = tree.find_invocation(invocation_id)
        if not inv:
            return None

        # 保存 checkpoint
        checkpoint_id = AnalysisCheckpoint.make_id()
        dimensions_json = json.dumps(inv.dimensions, ensure_ascii=False)
        state_json = json.dumps(state_dict or {}, ensure_ascii=False)
        summary_json = json.dumps({
            "agent_name": inv.agent_name,
            "branch_label": inv.branch_label,
            "dimensions": inv.dimensions,
            "result_summary": result_summary[:500],
            "status": inv.status,
            "conversation_round": inv.conversation_round,
        }, ensure_ascii=False)

        try:
            self._durable.save_checkpoint(
                checkpoint_id=checkpoint_id,
                conversation_id=conv_id,
                invocation_id=invocation_id,
                agent_name=inv.agent_name,
                dimensions_json=dimensions_json,
                state_json=state_json,
                summary_json=summary_json,
            )
            inv.checkpoint_id = checkpoint_id
        except Exception as e:
            logger.error(f"[AnalysisTree] Failed to save checkpoint {checkpoint_id}: {e}")

        # 推送 SSE 事件
        self._emit(conv_id, {
            "type": "tree_node_added",
            "data": {
                "invocation_id": inv.invocation_id,
                "agent_name": inv.agent_name,
                "branch_label": inv.branch_label,
                "parent_invocation_id": inv.parent_invocation_id,
                "dimensions": inv.dimensions,
                "status": inv.status,
                "result_summary": result_summary[:300],
                "checkpoint_id": inv.checkpoint_id,
                "conversation_round": inv.conversation_round,
                "started_at": inv.started_at,
                "completed_at": inv.completed_at,
                "error_message": inv.error_message,
            },
        })

        return checkpoint_id

    # ── Checkpoint 操作 ──

    def restore_checkpoint(self, checkpoint_id: str) -> Optional[dict]:
        """从 SQLite 加载 checkpoint 的 state_json，返回可用于重建 State 的 dict"""
        row = self._durable.load_checkpoint(checkpoint_id)
        if not row:
            return None
        try:
            return json.loads(row["state_json"])
        except json.JSONDecodeError:
            return None

    def get_checkpoint(self, checkpoint_id: str) -> Optional[dict]:
        """获取 checkpoint 记录（含元数据）"""
        return self._durable.load_checkpoint(checkpoint_id)

    # ── 回溯 ──

    def backtrack(
        self, conv_id: str, invocation_id: str
    ) -> Optional[dict]:
        """
        回溯到指定 invocation：
        1. 找到 invocation 的 checkpoint
        2. 恢复 state
        3. 清理该 invocation 之后的所有 tree invocations
        4. 删除之后的 checkpoints
        返回恢复后的 state_dict，或 None
        """
        tree = self.get_tree(conv_id)
        if not tree:
            return None

        inv = tree.find_invocation(invocation_id)
        if not inv:
            return None

        # 恢复 state
        checkpoint_id = inv.checkpoint_id
        state_dict = None
        if checkpoint_id:
            state_dict = self.restore_checkpoint(checkpoint_id)

        # 清理该 invocation 之后的所有 invocations
        self._prune_invocations_after(tree, invocation_id)

        # 删除之后的 checkpoints
        try:
            self._durable.delete_checkpoints_after(conv_id, invocation_id)
        except Exception as e:
            logger.error(f"[AnalysisTree] Failed to delete checkpoints after {invocation_id}: {e}")

        return state_dict

    def _prune_invocations_after(self, tree: AnalysisTree, invocation_id: str) -> None:
        """清理指定 invocation 之后的所有 invocations（按 started_at 排序）"""
        target_inv = tree.find_invocation(invocation_id)
        if not target_inv or not target_inv.started_at:
            return

        cutoff = target_inv.started_at
        for branch in tree.branches.values():
            branch.invocations = [
                inv for inv in branch.invocations
                if inv.started_at and inv.started_at <= cutoff
            ]

    # ── SSE 事件 ──

    def register_queue(self, conv_id: str, queue: asyncio.Queue) -> None:
        """注册会话的 SSE 事件队列（orchestrator stream 入口调用）"""
        with self._lock:
            self._event_queues[conv_id] = queue

    def unregister_queue(self, conv_id: str) -> None:
        with self._lock:
            self._event_queues.pop(conv_id, None)

    def _emit(self, conv_id: str, event: dict) -> None:
        """向 conv_id 的事件队列推送事件（非阻塞）"""
        with self._lock:
            queue = self._event_queues.get(conv_id)
        if queue is None:
            return
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(f"[AnalysisTree] Event queue full for {conv_id}")

    # ── API 输出 ──

    def to_dict(self, conv_id: str) -> Optional[dict]:
        tree = self.get_tree(conv_id)
        if not tree:
            return None
        return tree.to_dict()

    def get_checkpoints_for_conv(self, conv_id: str) -> List[dict]:
        """获取会话的所有 checkpoints（供 API 使用）"""
        rows = self._durable.list_checkpoints(conv_id)
        for row in rows:
            if row.get("summary_json"):
                try:
                    row["summary"] = json.loads(row["summary_json"])
                except json.JSONDecodeError:
                    row["summary"] = {}
            if row.get("dimensions_json"):
                try:
                    row["dimensions"] = json.loads(row["dimensions_json"])
                except json.JSONDecodeError:
                    row["dimensions"] = []
        return rows


# 模块级单例
analysis_tree_manager = AnalysisTreeManager()