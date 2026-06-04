"""
IncrementalTracker — 增量分析追踪模块

借鉴 Langfuse 的 Trace/Span 层级设计。
每轮对话创建 Trace → Span → Generation 结构。
用 tag/metadata 记录 dimensions、is_incremental 等信息。

注意：langfuse SDK 已安装（pip install langfuse），但 runtime 是否启
用取决于 LANGFUSE_ENABLE 环境变量。不启用时走内存追踪。
"""

import os
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


# ── 内存追踪（兜底方案） ──

@dataclass
class SpanRecord:
    span_id: str
    trace_id: str
    agent_name: str
    input_text: str = ""
    output_text: str = ""
    dimensions: List[str] = field(default_factory=list)
    is_incremental: bool = False
    tokens_input: int = 0
    tokens_output: int = 0
    started_at: str = ""
    ended_at: str = ""


@dataclass
class TraceRecord:
    trace_id: str
    session_id: str
    raw_query: str = ""
    spans: List[SpanRecord] = field(default_factory=list)
    created_at: str = ""


class IncrementalTracker:
    """增量分析追踪——记录每轮对话的状态变化

    支持两种模式：
    1. Langfuse 模式（LANGFUSE_ENABLE=true）：走 langfuse SDK
    2. 内存模式（默认）：走内存 dict
    """

    def __init__(self):
        self._enabled = os.getenv("LANGFUSE_ENABLE", "").lower() in ("true", "1", "yes")
        self._langfuse = None
        self._traces: Dict[str, TraceRecord] = {}
        self._current_traces: Dict[str, TraceRecord] = {}  # session_id → TraceRecord

        if self._enabled:
            try:
                from langfuse import Langfuse
                self._langfuse = Langfuse(
                    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
                    secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
                    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
                )
            except Exception:
                self._enabled = False

    # ── Trace 层级 ──

    def start_trace(self, session_id: str, raw_query: str) -> str:
        """开始一轮新的 Trace"""
        trace_id = f"trace-{session_id}-{uuid.uuid4().hex[:8]}"

        if self._enabled and self._langfuse:
            try:
                self._langfuse.trace(
                    id=trace_id,
                    name=f"nova-analysis-{session_id[:8]}",
                    session_id=session_id,
                    input=raw_query,
                    metadata={"type": "analysis"},
                )
            except Exception:
                pass

        record = TraceRecord(
            trace_id=trace_id,
            session_id=session_id,
            raw_query=raw_query,
            created_at=datetime.now().isoformat(),
        )
        self._current_traces[session_id] = record
        self._traces[trace_id] = record
        return trace_id

    def end_trace(self, session_id: str, output: str = ""):
        """结束一轮 Trace"""
        trace = self._current_traces.get(session_id)
        if not trace:
            return
        if self._enabled and self._langfuse:
            try:
                trace_obj = self._langfuse.trace(id=trace.trace_id)
                trace_obj.update(output=output)
            except Exception:
                pass

    # ── Span 层级 ──

    def start_span(
        self,
        session_id: str,
        agent_name: str,
        input_text: str = "",
        dimensions: Optional[List[str]] = None,
        is_incremental: bool = False,
    ) -> str:
        """开始一个 Agent 调用 Span"""
        trace = self._current_traces.get(session_id)
        if not trace:
            # 自动创建 Trace
            self.start_trace(session_id, input_text)
            trace = self._current_traces.get(session_id)

        span_id = f"span-{agent_name}-{uuid.uuid4().hex[:8]}"

        if self._enabled and self._langfuse:
            try:
                generation = self._langfuse.generation(
                    name=agent_name,
                    trace_id=trace.trace_id if trace else None,
                    input=input_text,
                    metadata={
                        "dimensions": dimensions or [],
                        "is_incremental": is_incremental,
                    },
                )
                # 用 generation id 作为 span_id
                if hasattr(generation, "id"):
                    span_id = generation.id
            except Exception:
                pass

        span = SpanRecord(
            span_id=span_id,
            trace_id=trace.trace_id if trace else "",
            agent_name=agent_name,
            input_text=input_text,
            dimensions=dimensions or [],
            is_incremental=is_incremental,
            started_at=datetime.now().isoformat(),
        )
        if trace:
            trace.spans.append(span)
        return span_id

    def end_span(
        self,
        session_id: str,
        span_id: str,
        output_text: str = "",
        tokens_input: int = 0,
        tokens_output: int = 0,
    ):
        """结束 Span"""
        trace = self._current_traces.get(session_id)
        if not trace:
            return
        for span in trace.spans:
            if span.span_id == span_id:
                span.output_text = output_text
                span.tokens_input = tokens_input
                span.tokens_output = tokens_output
                span.ended_at = datetime.now().isoformat()
                break

    # ── 状态查询 ──

    def get_previous_dimensions(self, session_id: str) -> List[str]:
        """获取会话中已分析过的方向（用于增量分析）"""
        trace = self._current_traces.get(session_id)
        if not trace:
            return []
        seen = set()
        for span in trace.spans:
            seen.update(span.dimensions)
        return list(seen)

    def get_session_rounds(self, session_id: str) -> int:
        """获取当前会话的轮次数"""
        trace = self._current_traces.get(session_id)
        if not trace:
            return 0
        return len(trace.spans)

    def is_incremental_possible(self, session_id: str) -> bool:
        """判断当前会话是否可以进行增量分析"""
        return self.get_session_rounds(session_id) > 0

    def get_trace_summary(self, session_id: str) -> Dict[str, Any]:
        """获取追踪摘要"""
        trace = self._current_traces.get(session_id)
        if not trace:
            return {"rounds": 0, "agents": [], "dimensions": []}
        return {
            "rounds": len(trace.spans),
            "agents": list(set(s.agent_name for s in trace.spans)),
            "dimensions": self.get_previous_dimensions(session_id),
            "raw_query": trace.raw_query,
            "trace_id": trace.trace_id,
        }