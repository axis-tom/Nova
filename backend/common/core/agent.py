from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import json
import logging
from pydantic import BaseModel, Field
from backend.common.core.state import State

logger = logging.getLogger(__name__)

# ── LLM 调用重试（引用 config.py 中的统一降级函数） ──

from backend.core.llm.config import llm_invoke_with_fallback as _llm_invoke_with_fallback

class AgentInput(BaseModel):
    """智能体输入模型（向后兼容）"""
    data: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    user_id: int = Field(..., description="用户ID")
    trace_id: Optional[str] = Field(None, description="链路追踪ID")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="运行时配置")

    class Config:
        arbitrary_types_allowed = True

class AgentOutput(BaseModel):
    """智能体输出模型（向后兼容）"""
    result: Any = Field(..., description="执行结果")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据（耗时、模型等）")
    error: Optional[str] = Field(None, description="错误信息（如果失败）")

class Agent(ABC):
    """智能体抽象基类，所有智能体必须继承并实现 run 方法"""
    name: str = "base_agent"
    description: str = "Base agent for all agents"
    llm: Optional[Any] = None
    fallback_llm: Optional[Any] = None  # 502 降级用备用模型
    # Prompt Engine 支持：Agent 调用前由外层注入定制指令
    _custom_system_prompt: Optional[str] = None

    async def llm_invoke(self, prompt: str, system: str = "") -> Optional[str]:
        """调用内嵌 LLM，失败返回 None（调用方自行 fallback 到规则引擎）"""
        if not self.llm:
            return None
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            messages: List[Any] = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))
            response = await _llm_invoke_with_fallback(
                self.llm, messages, fallback_llm=getattr(self, "fallback_llm", None),
            )
            # 记录 token 用量
            self._record_usage(response)
            return response.content
        except Exception as e:
            logger.warning(f"[{self.name}] LLM invoke failed, falling back to rules: {e}")
            return None

    def _record_usage(self, response: Any):
        """从 LLM response 中提取 token 用量并记录"""
        try:
            usage = getattr(response, "usage_metadata", None) or {}
            if isinstance(usage, dict):
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
            else:
                input_tokens = getattr(usage, "input_tokens", 0)
                output_tokens = getattr(usage, "output_tokens", 0)
            if input_tokens or output_tokens:
                from backend.core.llm.config import record_token_usage
                record_token_usage(self.name, input_tokens, output_tokens)
        except Exception:
            pass

    @abstractmethod
    def run(self, state: State) -> State:
        """
        执行智能体逻辑（新规范）
        
        新规范要求：
        1. 接受 State 对象作为输入
        2. 在方法开始和结束时添加事件
        3. 通过 state.set() 设置结果
        4. 返回修改后的 State 对象
        
        :param state: 状态对象，包含执行上下文和数据
        :return: 修改后的状态对象
        """
        raise NotImplementedError

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """
        向后兼容的 execute 方法（已弃用）
        
        注意：新代码应该使用 run(state) 方法
        此方法仅为向后兼容保留，会调用 run 方法并转换接口
        
        转换规则：
        1. 如果state中有"result"键，则使用它作为结果
        2. 否则，返回整个state的data部分作为结果
        3. 从state.meta中提取metadata
        4. 从state中提取error信息
        """
        # 将 AgentInput 转换为 State
        state = State(input_data.data)
        state.set_meta("user_id", input_data.user_id)
        if input_data.trace_id:
            state.set_meta("trace_id", input_data.trace_id)
        if input_data.config:
            state.set_meta("config", input_data.config)
        
        # 执行 run 方法（支持同步和异步）
        run_method = self.run
        if asyncio.iscoroutinefunction(run_method):
            result_state = await run_method(state)
        else:
            result_state = run_method(state)
        
        # 将 State 转换为 AgentOutput
        # 优先使用"result"键，否则使用整个data部分
        if "result" in result_state:
            result = result_state.get("result")
        else:
            # 返回整个data部分，但排除一些内部键
            result = result_state.to_plain_dict()
            # 移除可能不需要的键
            for key in ["error", "metadata", "executed"]:
                if key in result:
                    del result[key]
        
        # 从meta中提取metadata
        metadata = {}
        for key in result_state.meta:
            if key not in ["user_id", "trace_id", "config", "step"]:
                metadata[key] = result_state.meta[key]
        
        # 提取error信息
        error = result_state.get("error")
        
        return AgentOutput(
            result=result,
            metadata=metadata,
            error=error
        )

    async def _call_model(self, prompt: str, model: Optional[str] = None) -> str:
        return ""

    # ════════════════════════════════════════════════════════════════
    # LLM 驱动的分析循环框架（Phase 6 Part B 大手术）
    # Agent 从固定函数管道 → LLM 决定分析路径
    # ════════════════════════════════════════════════════════════════

    def _tool_fn(self, fn, products: List[Dict]):
        """
        将分析函数包装为可调用的闭包。
        子类在 _build_analysis_tools 中调用此方法。
        """
        return lambda: fn(products)

    async def _execute_tool_call(
        self, tool_call: Dict, tools_map: Dict[str, Any],
    ) -> Tuple[str, Any]:
        """执行单个工具调用，返回 (tool_name, result)"""
        name = tool_call.get("name", "")
        raw_args = tool_call.get("args", {})
        tool = tools_map.get(name)
        if not tool:
            logger.warning(f"[{self.name}] 未知工具: {name}")
            return name, {"error": f"未知工具: {name}"}
        try:
            result = await tool.ainvoke(raw_args)
            return name, result
        except Exception as e:
            logger.warning(f"[{self.name}] 工具 {name} 执行失败: {e}")
            return name, {"error": str(e)}

    async def _run_analysis_loop(
        self,
        products: List[Dict],
        system_prompt: str,
        analysis_question: str = "",
        max_turns: int = 15,
    ) -> str:
        """
        通用的 LLM 驱动分析循环。

        流程：
        1. 子类通过 _build_analysis_tools() 提供工具
        2. 绑定工具到 LLM
        3. 循环：LLM 思考 → 调工具 → 看结果 → 直到 LLM 主动结束
        4. 返回 LLM 最终输出（JSON 字符串）

        子类无需重写此方法，只需实现 _build_analysis_tools()。
        """
        tools = self._build_analysis_tools(products)
        tools_map = {t.name: t for t in tools}

        from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

        llm_with_tools = self.llm.bind_tools(tools)

        # Prompt Engine 支持：如果有定制 system_prompt，优先使用
        effective_system_prompt = system_prompt
        if self._custom_system_prompt:
            effective_system_prompt = self._custom_system_prompt
            self._custom_system_prompt = None  # 一次性消费

        messages = [SystemMessage(content=effective_system_prompt)]
        messages.append(HumanMessage(
            content=analysis_question or (
                f"请分析以下 {len(products)} 个商品的市场情况。\n"
                f"你有 {len(tools)} 个分析工具可用，按需调用。\n"
                f"商品摘要：{len(products)} 个商品，"
                f"包含 asin/title/brand/price/rating/bsr/review_count/monthly_sold 等字段。\n\n"
                f"请逐步分析，每次调用工具后思考结果，再决定下一步。"
                f"当信息足够时，请输出完整分析报告（JSON 格式）。"
            )
        ))

        for turn in range(max_turns):
            try:
                response = await _llm_invoke_with_fallback(
                    llm_with_tools, messages,
                    fallback_llm=getattr(self, "fallback_llm", None),
                )
            except Exception as e:
                logger.error(f"[{self.name}] LLM 调用失败 (turn {turn}): {e}")
                break

            messages.append(response)

            if not response.tool_calls:
                # LLM 主动结束 → 这就是最终输出
                logger.info(f"[{self.name}] LLM 在 {turn+1} 轮后主动结束分析")
                return response.content

            for tc in response.tool_calls:
                name, result = await self._execute_tool_call(tc, tools_map)
                result_str = json.dumps(result, ensure_ascii=False, default=str)
                messages.append(ToolMessage(
                    content=result_str,
                    tool_call_id=tc.get("id", ""),
                ))

        # 超时安全阀：最后一次 assistant 输出（如果有）或空
        logger.warning(f"[{self.name}] 分析循环达到最大轮次 {max_turns}，强制结束")
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content and isinstance(msg, type(response)):
                return msg.content
        return ""

    def _build_analysis_tools(self, products: List[Dict]) -> List:
        """
        子类重写此方法，将 _analyze_* 方法转为 @tool 列表。
        默认返回空列表（Agent 不使用工具）。
        """
        return []

    def _parse_json_output(self, content: str) -> Dict[str, Any]:
        """从 LLM 输出中提取 JSON，兼容 ```json ... ``` 包裹"""
        if not content:
            return {}
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"[{self.name}] LLM 输出不是合法 JSON，原样返回")
        return {"llm_raw_output": content}
