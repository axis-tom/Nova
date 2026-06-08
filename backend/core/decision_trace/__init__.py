"""
Decision Trace — 决策追踪

两个输出路径：
1. 后端终端打印结构化追踪信息（每次执行完后自动打印）
2. 写入 runtime/traces/last.json（六问格式，随时 cat 查看）

用法：
    tracer = DecisionTracer(conv_id, user_input)
    tracer.capture_intent(intent_spec_data)
    tracer.capture_data_liaison(intel_report)
    tracer.capture_loaded_context(system_prompt, had_intel=True, intel_summary=...)
    tracer.start_tool_call(name, args)
    tracer.end_tool_call(name, result, reasoning=...)
    tracer.start_agent_call(agent_name, params)
    tracer.end_agent_call(agent_name, result, sub_task=...)
    tracer.add_decision(step="data_source", question="用什么数据？", ...)
    tracer.add_evidence("DB 中有 ASIN B0XXX 的数据")
    tracer.finalize(final_answer)
"""

from backend.core.decision_trace.tracer import DecisionTracer

__all__ = [
    "DecisionTracer",
]