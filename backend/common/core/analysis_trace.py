"""
分析树数据模型：系统层追踪 LLM → Agent 调用，归约为分析维度树

LLM 侧: ReAct 自由思考，自由选 agent
系统侧: 观察每次调用 → 记录 → 归纳为树 → SSE 推前端
用户侧: 看到实时更新的分析树，可回溯 / 追加维度
"""

from __future__ import annotations

import uuid
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── 维度标签映射 ─────────────────────────────────────────────────────
# 从 agent 的 params 中自动提取分析维度标签

def _extract_dimensions(agent_name: str, params: Dict[str, Any]) -> List[str]:
    """从 agent 调用参数中提取用户友好的维度标签"""
    dims = []

    if agent_name == "market_analyst":
        atype = params.get("analysis_type", "market_trends")
        if atype == "market_trends":
            dims.append("市场体量与趋势")
        if atype == "roi_analysis":
            dims.append("盈利评估")

    elif agent_name == "competitor_analyst":
        dims.append("品牌竞争分析")
        if params.get("include_head_to_head"):
            dims.append("产品细节对比")

    elif agent_name == "product_collector":
        if params.get("watchlist_asins"):
            dims.append(f"指定ASIN采集 ({len(params['watchlist_asins'])}个)")
        if params.get("expanded_keywords"):
            dims.append(f"关键词搜索采集 ({len(params['expanded_keywords'])}个词)")

    elif agent_name == "keyword_expander":
        dims.append("关键词扩展")

    elif agent_name == "review_analyzer":
        dims.append("评论洞察")

    elif agent_name == "traffic_analyzer":
        dims.append("流量竞争分析")

    elif agent_name == "opportunity_judge":
        dims.append("机会评分与推荐")

    elif agent_name == "briefing_generator":
        dims.append("选品简报")

    return dims


# ── Agent → 分支标签映射 ─────────────────────────────────────────────

AGENT_BRANCH_LABELS: Dict[str, str] = {
    "keyword_expander": "搜索准备",
    "product_collector": "数据采集",
    "market_analyst": "市场分析",
    "competitor_analyst": "竞品分析",
    "review_analyzer": "需求挖掘",
    "traffic_analyzer": "流量分析",
    "opportunity_judge": "综合评估",
    "briefing_generator": "报告生成",
}


# ── 数据模型 ─────────────────────────────────────────────────────────


@dataclass
class AgentInvocation:
    """系统追踪到的每次 agent 调用"""
    invocation_id: str
    agent_name: str
    branch_label: str               # "市场分析"
    params: dict
    dimensions: list
    result_summary: str
    status: str                     # "running" | "completed" | "error"
    conversation_round: int
    parent_invocation_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "invocation_id": self.invocation_id,
            "agent_name": self.agent_name,
            "branch_label": self.branch_label,
            "params": self.params,
            "dimensions": self.dimensions,
            "result_summary": self.result_summary,
            "status": self.status,
            "conversation_round": self.conversation_round,
            "parent_invocation_id": self.parent_invocation_id,
            "checkpoint_id": self.checkpoint_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
        }


@dataclass
class TreeBranch:
    """一个 agent 分支 = 所有对该 agent 的调用记录"""
    branch_id: str                  # agent_name
    agent_name: str
    label: str                      # "市场分析"
    invocations: List[AgentInvocation] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.invocations:
            return "pending"
        statuses = {inv.status for inv in self.invocations}
        if "running" in statuses:
            return "running"
        if all(s == "completed" for s in statuses):
            return "completed"
        if all(s == "error" for s in statuses):
            return "error"
        # mixed: some completed, some error
        if "completed" in statuses:
            return "partial"
        return "pending"

    def last_invocation(self) -> Optional[AgentInvocation]:
        return self.invocations[-1] if self.invocations else None

    def to_dict(self) -> dict:
        return {
            "branch_id": self.branch_id,
            "agent_name": self.agent_name,
            "label": self.label,
            "status": self.status,
            "invocations": [inv.to_dict() for inv in self.invocations],
        }


@dataclass
class AnalysisTree:
    """系统维护的分析树（LLM 无感知）"""
    conversation_id: str
    branches: Dict[str, TreeBranch] = field(default_factory=dict)
    conversation_round: int = 0

    def add_invocation(
        self,
        agent_name: str,
        params: dict,
        conversation_round: int,
    ) -> AgentInvocation:
        """创建新的 invocation 并归入对应分支"""
        branch_id = agent_name
        if branch_id not in self.branches:
            self.branches[branch_id] = TreeBranch(
                branch_id=branch_id,
                agent_name=agent_name,
                label=AGENT_BRANCH_LABELS.get(agent_name, agent_name),
            )

        branch = self.branches[branch_id]
        parent_id = branch.last_invocation().invocation_id if branch.invocations else None

        invocation = AgentInvocation(
            invocation_id=f"inv-{uuid.uuid4().hex[:12]}",
            agent_name=agent_name,
            branch_label=branch.label,
            params=params,
            dimensions=_extract_dimensions(agent_name, params),
            result_summary="",
            status="running",
            conversation_round=conversation_round,
            parent_invocation_id=parent_id,
            started_at=datetime.now().isoformat(),
        )
        branch.invocations.append(invocation)
        return invocation

    def complete_invocation(
        self,
        invocation_id: str,
        result_summary: str = "",
        checkpoint_id: str = None,
        error_message: str = None,
    ):
        """标记 invocation 完成或失败"""
        for branch in self.branches.values():
            for inv in branch.invocations:
                if inv.invocation_id == invocation_id:
                    inv.status = "error" if error_message else "completed"
                    inv.result_summary = result_summary
                    inv.checkpoint_id = checkpoint_id
                    inv.completed_at = datetime.now().isoformat()
                    inv.error_message = error_message
                    return

    @property
    def ordered_branches(self) -> List[TreeBranch]:
        """按首次调用时间排序的分支列表"""
        ordered = []
        for branch in self.branches.values():
            first_ts = branch.invocations[0].started_at if branch.invocations else ""
            ordered.append((first_ts, branch))
        ordered.sort(key=lambda x: x[0])
        return [b for _, b in ordered]

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "conversation_round": self.conversation_round,
            "branches": [b.to_dict() for b in self.ordered_branches],
        }

    def find_invocation(self, invocation_id: str) -> Optional[AgentInvocation]:
        for branch in self.branches.values():
            for inv in branch.invocations:
                if inv.invocation_id == invocation_id:
                    return inv
        return None


# ── Checkpoint ───────────────────────────────────────────────────────


@dataclass
class AnalysisCheckpoint:
    """agent 调用完成后的 State 快照"""
    checkpoint_id: str
    conversation_id: str
    invocation_id: str
    agent_name: str
    dimensions: list
    state_json: str                 # 完整 state.to_dict() JSON
    summary_json: str               # 摘要 JSON
    created_at: str

    @staticmethod
    def make_id() -> str:
        return f"ck-{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "conversation_id": self.conversation_id,
            "invocation_id": self.invocation_id,
            "agent_name": self.agent_name,
            "dimensions": self.dimensions,
            "summary": json.loads(self.summary_json) if self.summary_json else {},
            "created_at": self.created_at,
        }