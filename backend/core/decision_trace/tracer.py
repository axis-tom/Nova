"""
DecisionTrace — 决策追踪

追踪 user_input → 系统回答完整链路中每个组件的"交接"细节：

  备菜员 DataLiaison → 端了什么菜到_state
  厨师长 orchestrator → 看到了什么情报, 给了什么指令
  厨师 Agent → 接到了什么食材, 实际做了什么菜, 端出什么

输出：终端打印 + runtime/traces/last.json
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TRACE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "runtime" / "traces"


# ════════════════════════════════════════════════════════════════
# 交接记录 —— 每个组件"端了什么菜"的 snapshot
# ════════════════════════════════════════════════════════════════

@dataclass
class ToolCallRecord:
    tool_name: str
    args: Dict[str, Any]
    result_preview: str       # 前 300 字符
    latency_s: float
    status: str               # ok | error
    reasoning: str = ""


@dataclass
class HandoffRecord:
    """
    一次"交接"的记录。

    from_component / to_component:
      "DataLiaison→state"
      "state→system_prompt"
      "call_nova_agent→call_agent"
      "call_agent→Agent"
      "Agent.LoadFromDB"
      "Agent.LLM"

    what_was_passed: 交接了什么内容（数据的摘要）
    detail: 关键细节（传了哪些 key、多少条、字段覆盖等）
    """
    from_to: str                # e.g. "DataLiaison→state._intel_report"
    what: str                   # "端了1个ASIN的字段覆盖率到state"
    detail: Dict[str, Any] = field(default_factory=dict)   # 关键数字/摘要


@dataclass
class AgentCallRecord:
    agent_name: str
    params: Dict[str, Any]     # 实际进入 Agent 的 params（含 intel 注入后）
    sub_task: str = ""
    custom_prompt_preview: str = ""   # PromptEngine 注入的定制指令
    result_preview: str = ""
    status: str = "ok"
    error_message: str = ""
    latency_s: float = 0.0
    products_loaded: int = 0         # 从本地表加载了多少商品
    asins_loaded: List[str] = field(default_factory=list)
    evidence_used: List[str] = field(default_factory=list)


# ════════════════════════════════════════════════════════════════
# Tracer
# ════════════════════════════════════════════════════════════════

class DecisionTracer:
    """单次请求的追踪器"""

    def __init__(self, conversation_id: str, user_input: str):
        self.trace_id = f"trace-{uuid.uuid4().hex[:12]}"
        self.conversation_id = conversation_id
        self.user_input = user_input
        self.timestamp = datetime.now(timezone.utc).isoformat()

        # 六个问题
        self.intent: Dict[str, Any] = {}
        self.data_liaison_found: Dict[str, Any] = {}   # DataLiaison 发现了什么
        self.loaded_context: Dict[str, Any] = {}        # system_prompt 拼了什么
        self.handoffs: List[HandoffRecord] = []          # 交接链
        self.tool_calls: List[ToolCallRecord] = []
        self.agent_calls: List[AgentCallRecord] = []
        self.evidence_used: List[str] = []
        self.final_answer: str = ""

        self._start_time = time.time()
        self._tool_timers: Dict[str, float] = {}
        self._agent_timers: Dict[str, float] = {}
        self._tool_args_cache: Dict[str, Dict] = {}
        self._state_data_snapshot: Dict[str, Any] = {}   # 最终 state 快照

    def capture_intent(self, intent_spec_data: Dict[str, Any]) -> None:
        """① 用户意图"""
        self.intent = intent_spec_data

    def capture_data_liaison(
        self,
        intel_report: Dict[str, Any],
        to_llm_context_text: str = "",
    ) -> None:
        """记录 DataLiaison 发现 + 端了什么到 state"""
        """
        ② DataLiaison 备菜员 —— 记录它发现了什么、端了什么到 state

        intel_report: _intel_report 原始 dict
        to_llm_context_text: to_llm_context() 生成的文本（直接给 LLM 看的）
        """
        exploration = intel_report.get("exploration", {}) or {}
        strategies = exploration.get("strategies_attempted", []) or []
        active = [s for s in strategies if s.get("matched", 0) > 0]
        brands_found = exploration.get("brands_found", {}) or {}

        self.data_liaison_found = {
            "found_asins": intel_report.get("found_asins", []),
            "missing_asins": intel_report.get("missing_asins", []),
            "category_hint": intel_report.get("category_hint", ""),
            "total_products": intel_report.get("asin_product_count", 0) or exploration.get("total_distinct_asins", 0),
            "matched_categories": intel_report.get("matched_category_names", []),
            "matched_brands": list(brands_found.keys())[:10],
            "strategies_hit": [s["column"] + "(" + s["strategy"] + ")" for s in active],
        }

        # 记录"端了什么菜到 state"
        handoff_detail = {
            "写入state位置": "state.data['_intel_report']",
            "字段数量": len(intel_report),
            "to_llm_context长度": len(to_llm_context_text),
            "to_llm_context预览": to_llm_context_text[:600],
        }
        self.handoffs.append(HandoffRecord(
            from_to="DataLiaison→state._intel_report",
            what=f"端了{len(self.data_liaison_found['found_asins'])}个ASIN+品类探索到state，to_llm_context()生成{len(to_llm_context_text)}字情报文本",
            detail=handoff_detail,
        ))

    def capture_state_to_system_prompt(self, state_summary_text: str) -> None:
        """
        ③ state → system_prompt 交接
        _build_state_summary() 把 state 中的数据拼成 system prompt 的一部分
        """
        self.handoffs.append(HandoffRecord(
            from_to="_build_state_summary→system_prompt",
            what=f"生成了{len(state_summary_text)}字state摘要注入system_prompt",
            detail={
                "state_summary_text": state_summary_text[:800],
                "长度": len(state_summary_text),
            },
        ))

    def capture_loaded_context(
        self,
        system_prompt: str,
        had_intel: bool = False,
        intel_summary: str = "",
        had_memories: bool = False,
        memory_count: int = 0,
        memory_text: str = "",
        had_state_summary: bool = False,
        state_summary: str = "",
    ) -> None:
        """
        ④ LLM / ReAct 循环拿到的完整上下文
        """
        self.loaded_context = {
            "had_intel_report": had_intel,
            "intel_summary": intel_summary[:300],
            "had_memories": had_memories,
            "memory_count": memory_count,
            "had_state_summary": had_state_summary,
            "system_prompt_preview": system_prompt[:1500],
            "agent_registry_count": system_prompt.count("input_example:"),
            "内存中_有_intel_指令": "DB 已确认包含 ASIN" in system_prompt,
            "内存中_有禁止搜索指令": "绝对不要用 search_web" in system_prompt,
        }

    def capture_call_nova_agent_handoff(
        self,
        agent_name: str,
        raw_params: Dict[str, Any],
        final_params: Dict[str, Any],     # intel 注入后的 params
        intel_report_used: bool = False,
    ) -> None:
        """
        ⑤ call_nova_agent 函数中的"交接"
        raw_params: LLM 传的原始参数
        final_params: intel 注入后的最终参数（asins/category 补全后的）
        """
        injected_keys = [k for k in final_params if final_params.get(k) != raw_params.get(k)]
        self.handoffs.append(HandoffRecord(
            from_to="call_nova_agent→Agent(params)",
            what=f"LLM传参+intel注入共{len(final_params)}个字段，其中{len(injected_keys)}个来自intel注入",
            detail={
                "agent_name": agent_name,
                "raw_params": raw_params,
                "final_params": final_params,
                "intel_注入的字段": injected_keys,
                "使用了intel报告": intel_report_used,
            },
        ))

    def capture_call_agent_handoff(
        self,
        agent_name: str,
        params: Dict[str, Any],
        custom_prompt: str,
        state_keys: List[str],
    ) -> None:
        """
        ⑥ agent_wrapper.call_agent 中的交接
        params merge 进 state → state 最终有哪些 key
        custom_prompt 被注入到 Agent._custom_system_prompt
        """
        self.handoffs.append(HandoffRecord(
            from_to="call_agent→Agent.state",
            what=f"params merge到state，state现有{len(state_keys)}个key，custom_prompt {len(custom_prompt)}字",
            detail={
                "agent_name": agent_name,
                "最终params": params,
                "custom_prompt_preview": custom_prompt[:600],
                "state_keys_after_merge": state_keys,
                "state_keys_数量": len(state_keys),
            },
        ))

    def capture_agent_load_db(
        self,
        agent_name: str,
        asins_queried: List[str],
        category_queried: str,
        products_loaded: int,
        fields_available: int = 0,
    ) -> None:
        """
        ⑦ Agent 从 amazon_products 本地表加载数据
        """
        self.handoffs.append(HandoffRecord(
            from_to=f"{agent_name}→amazon_products表",
            what=f"查了{len(asins_queried)}个ASIN/品类'{category_queried}'，加载了{products_loaded}个商品",
            detail={
                "asins_queried": asins_queried,
                "category_queried": category_queried,
                "products_loaded": products_loaded,
                "字段数": fields_available,
            },
        ))

    # ── 工具调用 ──

    def start_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> None:
        self._tool_timers[tool_name] = time.time()
        self._tool_args_cache[tool_name] = tool_args

    def end_tool_call(self, tool_name: str, result: str, status: str = "ok",
                      reasoning: str = "") -> None:
        start = self._tool_timers.pop(tool_name, self._start_time)
        self.tool_calls.append(ToolCallRecord(
            tool_name=tool_name,
            args=self._tool_args_cache.pop(tool_name, {}),
            result_preview=str(result)[:300],
            latency_s=round(time.time() - start, 2),
            status=status,
            reasoning=reasoning,
        ))

    # ── Agent 调用 ──

    def start_agent_call(self, agent_name: str, params: Dict[str, Any]) -> None:
        self._agent_timers[agent_name] = time.time()

    def end_agent_call(self, agent_name: str, result: str,
                       params: Optional[Dict] = None, sub_task: str = "",
                       custom_prompt: str = "",
                       status: str = "ok", error_message: str = "",
                       products_loaded: int = 0,
                       asins_loaded: Optional[List[str]] = None,
                       evidence_used: Optional[List[str]] = None) -> None:
        start = self._agent_timers.pop(agent_name, self._start_time)
        self.agent_calls.append(AgentCallRecord(
            agent_name=agent_name,
            params=params or {},
            sub_task=sub_task,
            custom_prompt_preview=custom_prompt[:500],
            result_preview=str(result)[:300],
            status=status,
            error_message=error_message,
            latency_s=round(time.time() - start, 2),
            products_loaded=products_loaded,
            asins_loaded=asins_loaded or [],
            evidence_used=evidence_used or [],
        ))

    # ── 证据 ──

    def add_evidence(self, evidence: str) -> None:
        self.evidence_used.append(evidence)

    # ── 最终 state 快照 ──

    def capture_state_keys(self, state_data: Dict[str, Any]) -> None:
        """记录最终 state 中有哪些 key"""
        self._state_data_snapshot = {
            "keys_数量": len(state_data),
            "keys_list": list(state_data.keys()),
            "size_of_each": {
                k: (
                    f"{len(v)}条" if isinstance(v, list) else
                    f"dict({len(v)}keys)" if isinstance(v, dict) else
                    f"{str(v)[:60]}"
                )
                for k, v in state_data.items()
                if not k.startswith("_")
            },
        }

    # ── 汇总 ──

    def finalize(self, final_answer: str) -> None:
        self.final_answer = final_answer
        elapsed = round(time.time() - self._start_time, 2)
        self._print_to_terminal(elapsed)
        self._write_to_files()

    def _print_to_terminal(self, elapsed_s: float) -> None:
        sep = "─" * 58
        print(f"\n{sep}")
        print(f"  🧠 Decision Trace [{self.trace_id}]")
        print(f"{sep}")
        print(f"  输入: {self.user_input[:80]}")
        print(f"  意图: {self.intent.get('paraphrased_intent', '?')[:80]}")

        # DataLiaison 发现了什么
        if self.data_liaison_found:
            dl = self.data_liaison_found
            print(f"\n  🥬 备菜员 DataLiaison 发现:")
            print(f"     ASIN命中 {len(dl['found_asins'])} 个: {', '.join(dl['found_asins'][:5])}")
            print(f"     缺失 {len(dl['missing_asins'])} 个: {', '.join(dl['missing_asins'][:5])}")
            print(f"     品类探索 {dl['total_products']} 商品 | 品类: {dl['matched_categories'][:3]}")
            if dl['strategies_hit']:
                print(f"     搜索策略: {', '.join(dl['strategies_hit'][:5])}")

        # 交接链
        if self.handoffs:
            print(f"\n  📦 数据交接链 ({len(self.handoffs)}次):")
            for h in self.handoffs:
                print(f"     {h.from_to}")
                print(f"       → {h.what}")

        # 上下文
        lc = self.loaded_context
        if lc:
            print(f"\n  📋 LLM 看到的上下文:")
            print(f"     {'有' if lc.get('had_intel_report') else '无'}情报"
                  f" | {'有' if lc.get('had_memories') else '无'}记忆"
                  f" | 可调Agent: {lc.get('agent_registry_count', 0)}个")
            if lc.get("内存中_有_intel_指令"):
                print(f"     ⚠ system_prompt 中有'DB 已确认包含 ASIN'指令")
            if lc.get("内存中_有禁止搜索指令"):
                print(f"     ⚠ system_prompt 中有'绝对不要用 search_web'指令")

        # 工具调用
        if self.tool_calls:
            print(f"\n  🔧 工具调用 ({len(self.tool_calls)}次):")
            for tc in self.tool_calls:
                s = "✅" if tc.status == "ok" else "❌"
                print(f"     {s} {tc.tool_name} ({tc.latency_s}s)")
                if tc.reasoning:
                    print(f"       原因: {tc.reasoning[:100]}")
                if tc.args:
                    args_preview = json.dumps(tc.args, ensure_ascii=False)[:120]
                    print(f"       参数: {args_preview}")

        # Agent 调用
        if self.agent_calls:
            print(f"\n  🧑‍🍳 Agent 调用 ({len(self.agent_calls)}次):")
            for ac in self.agent_calls:
                s = "✅" if ac.status == "ok" else "❌"
                print(f"     {s} {ac.agent_name} ({ac.latency_s}s)")
                if ac.sub_task:
                    print(f"       task: {ac.sub_task[:80]}")
                print(f"       从DB加载了 {ac.products_loaded} 个商品 | ASIN: {', '.join(ac.asins_loaded[:5])}")
                if ac.custom_prompt_preview:
                    print(f"       PromptEngine指令: {ac.custom_prompt_preview[:120]}")

        # state 最终状态
        if self._state_data_snapshot:
            print(f"\n  📊 State 最终状态 ({self._state_data_snapshot.get('keys_数量', 0)}个key):")
            for k, v in self._state_data_snapshot.get("size_of_each", {}).items():
                print(f"     {k}: {v}")

        print(f"\n  ⏱  {elapsed_s}s  |  最终回答: {len(self.final_answer)} 字符")
        print(f"{sep}\n")

    def _write_to_files(self) -> None:
        try:
            _TRACE_DIR.mkdir(parents=True, exist_ok=True)
            d = self._to_dict()
            with open(_TRACE_DIR / f"{self.trace_id}.json", "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2, default=str)
            with open(_TRACE_DIR / "last.json", "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"[DecisionTrace] 写文件失败: {e}")

    def _to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "conversation_id": self.conversation_id,
            "timestamp": self.timestamp,
            "user_input": self.user_input,

            "q1_用户想干什么": {
                "paraphrased_intent": self.intent.get("paraphrased_intent", "未识别"),
                "intent_type": self.intent.get("intent_type", "?"),
                "depth": self.intent.get("depth", "?"),
                "entities": self.intent.get("entities", []),
            },

            "q2_备菜员DataLiaison发现了什么": self.data_liaison_found or {"status": "未执行"},

            "q3_交接链": [
                {
                    "交接节点": h.from_to,
                    "交接了什么": h.what,
                    "详情": h.detail,
                }
                for h in self.handoffs
            ],

            "q4_LLM看到了什么上下文": self.loaded_context or {"status": "未记录"},

            "q5_调用了什么": {
                "tool_calls": [
                    {"tool": tc.tool_name, "耗时_s": tc.latency_s,
                     "状态": tc.status, "推理": tc.reasoning,
                     "参数": tc.args, "结果摘要": tc.result_preview}
                    for tc in self.tool_calls
                ],
                "agent_calls": [
                    {"agent": ac.agent_name, "sub_task": ac.sub_task,
                     "耗时_s": ac.latency_s, "状态": ac.status,
                     "PromptEngine指令": ac.custom_prompt_preview,
                     "从DB加载商品数": ac.products_loaded,
                     "ASIN": ac.asins_loaded,
                     "引用证据": ac.evidence_used,
                     "error": ac.error_message}
                    for ac in self.agent_calls
                ],
            },

            "q6_最终引用证据": {
                "evidence": self.evidence_used,
                "final_answer_preview": self.final_answer[:500],
            },

            "state_最终状态": self._state_data_snapshot,

            "元数据": {
                "handoff_count": len(self.handoffs),
                "tool_count": len(self.tool_calls),
                "agent_count": len(self.agent_calls),
                "total_latency_s": round(time.time() - self._start_time, 2),
            },
        }