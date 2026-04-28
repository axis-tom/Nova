"""
上下文感知的AI分析器
确保AI只能消费state.payload，不得访问context.env
AI输出不得携带数据来源信息
"""

from typing import Dict, Any, List, Optional
from backend.common.core import Agent
from backend.core.state import State
from backend.core.contextual_data import ContextWrapper
from backend.utils.logger import logger


class ContextualAIAnalyzer(Agent):
    """
    上下文感知的AI分析器
    
    强制规范：
    1. AI只能消费state.payload中的数据
    2. AI不得访问context.env或任何上下文信息
    3. AI输出不得携带数据来源信息
    4. AI在sandbox和production环境下的行为必须一致（仅数据不同）
    """
    
    def __init__(self, llm_client):
        """
        初始化ContextualAIAnalyzer
        
        Args:
            llm_client: LLM客户端实例
        """
        self.llm_client = llm_client
        self._strict_mode = True  # 严格模式，强制遵守规范
    
    async def run(self, state: State) -> State:
        """
        执行AI分析（上下文感知版本）
        
        Args:
            state: 输入状态，必须包含contextual_data
            
        Returns:
            包含AI分析结果的状态
        """
        # 验证输入状态
        if self._strict_mode:
            self._validate_input_state(state)
        
        # 提取payload数据（AI只能访问payload）
        payload = self._extract_payload_for_ai(state)
        
        if not payload:
            state.set("error", "未找到有效的数据供AI分析")
            state.add_event("contextual_ai_analyzer_skipped_no_payload")
            return state
        
        # 准备AI输入（只包含payload数据）
        ai_input = self._prepare_ai_input(payload)
        
        try:
            # 调用LLM生成分析结果
            import asyncio
            ai_output = await asyncio.wait_for(
                self._call_llm_safely(ai_input),
                timeout=10
            )
            
            # 处理AI输出（确保不携带来源信息）
            processed_output = self._process_ai_output(ai_output, state)
            
            # 将AI输出整合回状态
            state = self._integrate_ai_output(state, processed_output)
            
            state.add_event("contextual_ai_analyzer_done")
            
        except asyncio.TimeoutError:
            state.set("ai_error", "AI调用超时")
            state.add_event("contextual_ai_analyzer_timeout")
        except Exception as e:
            state.set("ai_error", f"AI分析失败: {str(e)}")
            state.add_event(f"contextual_ai_analyzer_failed: {str(e)}")
        
        return state
    
    def _validate_input_state(self, state: State) -> None:
        """
        验证输入状态是否符合规范
        
        Args:
            state: 要验证的状态
            
        Raises:
            ValueError: 如果状态不符合规范
        """
        # 检查是否有contextual_data字段
        if "contextual_data" not in state:
            raise ValueError("AI分析器只能处理包含contextual_data的状态")
        
        # 验证contextual_data格式
        contextual_data = state.get("contextual_data")
        if not isinstance(contextual_data, dict):
            raise ValueError("contextual_data必须是字典")
        
        if "context" not in contextual_data or "payload" not in contextual_data:
            raise ValueError("contextual_data必须包含'context'和'payload'")
        
        # 记录验证通过（但不暴露环境信息）
        state.add_event("ai_input_validated")
    
    def _extract_payload_for_ai(self, state: State) -> Dict[str, Any]:
        """
        为AI提取payload数据
        
        Args:
            state: 输入状态
            
        Returns:
            供AI使用的payload数据
        """
        contextual_data = state.get("contextual_data", {})
        payload = contextual_data.get("payload", {})
        
        # 记录提取的信息（不包含环境信息）
        extracted_keys = list(payload.keys())
        state.add_event(f"ai_payload_extracted_keys: {extracted_keys}")
        
        return payload
    
    def _prepare_ai_input(self, payload: Dict[str, Any]) -> List[str]:
        """
        准备AI输入数据
        
        Args:
            payload: 从状态中提取的payload数据
            
        Returns:
            供LLM使用的消息列表
        """
        messages = []
        
        # 处理邮件数据
        if "emails" in payload:
            emails = payload["emails"]
            if isinstance(emails, list):
                for email in emails:
                    if isinstance(email, dict):
                        content = f"主题：{email.get('subject', '无主题')}\n发件人：{email.get('from', '未知发件人')}\n内容预览：{email.get('body_preview', '无内容预览')}"
                        messages.append(content)
                    else:
                        messages.append(str(email))
        
        # 处理其他类型的数据
        for key, value in payload.items():
            if key != "emails":
                if isinstance(value, list):
                    for item in value:
                        messages.append(f"{key}: {str(item)}")
                elif isinstance(value, dict):
                    messages.append(f"{key}: {str(value)}")
                else:
                    messages.append(f"{key}: {str(value)}")
        
        # 添加系统提示（确保AI不知道数据来源）
        system_prompt = """你是一个数据分析助手。请分析提供的数据并生成简洁的总结。
注意：你不需要知道数据的来源或环境，只需专注于数据内容本身。"""
        
        return [system_prompt] + messages
    
    async def _call_llm_safely(self, messages: List[str]) -> str:
        """
        安全调用LLM（确保不传递上下文信息）
        
        Args:
            messages: 消息列表
            
        Returns:
            LLM生成的文本
        """
        # 确保消息中不包含环境信息
        sanitized_messages = []
        for msg in messages:
            # 移除可能的环境标识
            sanitized_msg = msg
            for env_keyword in ["sandbox", "production", "test", "env:", "environment:"]:
                if env_keyword in msg.lower():
                    # 替换或移除环境关键词
                    sanitized_msg = sanitized_msg.replace(env_keyword, "[数据]")
            sanitized_messages.append(sanitized_msg)
        
        # 调用LLM
        return await self.llm_client.generate_briefing(sanitized_messages)
    
    def _process_ai_output(self, ai_output: str, state: State) -> Dict[str, Any]:
        """
        处理AI输出，确保不携带来源信息
        
        Args:
            ai_output: AI原始输出
            state: 当前状态（用于记录但不使用环境信息）
            
        Returns:
            处理后的AI输出
        """
        # 检查AI输出是否包含环境信息
        output_lower = ai_output.lower()
        forbidden_keywords = ["sandbox", "production", "测试环境", "生产环境", "数据来源", "来自"]
        
        contains_forbidden_info = any(keyword in output_lower for keyword in forbidden_keywords)
        
        if contains_forbidden_info:
            # 记录警告但不修改输出（在实际生产中可能需要更严格的处理）
            logger.warning("AI输出可能包含环境信息，但为了保持输出完整性，未进行修改")
            state.add_event("ai_output_may_contain_context_info_warning")
        
        # 返回处理后的输出
        return {
            "ai_analysis": ai_output,
            "analysis_timestamp": "2024-01-01T00:00:00",  # 固定时间戳，不暴露真实时间
            "analysis_version": "1.0"
        }
    
    def _integrate_ai_output(self, state: State, ai_output: Dict[str, Any]) -> State:
        """
        将AI输出整合回状态
        
        Args:
            state: 当前状态
            ai_output: AI处理结果
            
        Returns:
            更新后的状态
        """
        # 获取当前contextual_data
        contextual_data = state.get("contextual_data", {})
        
        # 将AI输出添加到payload中
        if "payload" in contextual_data:
            contextual_data["payload"].update(ai_output)
        else:
            contextual_data["payload"] = ai_output
        
        # 更新contextual_data
        state.set("contextual_data", contextual_data)
        
        # 添加AI处理事件（不包含环境信息）
        state.add_event("ai_analysis_integrated")
        
        return state
    
    def enforce_ai_isolation(self, state: State) -> State:
        """
        强制AI隔离：确保AI只能访问payload，不能访问context
        
        Args:
            state: 要处理的状态
            
        Returns:
            隔离后的状态
        """
        # 创建AI专用的状态副本
        ai_state = state.copy()
        
        # 移除context信息，只保留payload
        contextual_data = ai_state.get("contextual_data", {})
        if "payload" in contextual_data:
            # 只保留payload数据
            ai_state.data = {"payload": contextual_data["payload"]}
            
            # 清空可能包含环境信息的元数据
            ai_state.meta = {
                "ai_isolated": True,
                "timestamp": "2024-01-01T00:00:00"  # 固定时间戳
            }
            
            # 保留事件但添加隔离标记
            ai_state.add_event("ai_isolation_enforced")
        
        return ai_state
    
    def validate_ai_output(self, ai_output: str) -> bool:
        """
        验证AI输出是否符合规范（不包含环境信息）
        
        Args:
            ai_output: AI输出文本
            
        Returns:
            是否通过验证
        """
        output_lower = ai_output.lower()
        
        # 禁止的关键词
        forbidden_patterns = [
            "sandbox",
            "production", 
            "测试环境",
            "生产环境",
            "数据来源",
            "来自.*环境",
            "env:",
            "environment:"
        ]
        
        import re
        for pattern in forbidden_patterns:
            if re.search(pattern, output_lower):
                return False
        
        return True
    
    def create_context_free_prompt(self, task_description: str) -> str:
        """
        创建无上下文的AI提示
        
        Args:
            task_description: 任务描述
            
        Returns:
            无上下文的提示文本
        """
        base_prompt = f"""请分析以下数据并完成任务：{task_description}

要求：
1. 只基于提供的数据进行分析
2. 不要猜测数据的来源或环境
3. 不要使用"测试"、"生产"、"sandbox"、"production"等词语
4. 专注于数据内容本身

数据："""
        
        return base_prompt


# 兼容性包装器，用于逐步迁移
class LegacyAIAnalyzerAdapter:
    """
    旧版AIAnalyzer的适配器，使其符合上下文感知规范
    """
    
    def __init__(self, legacy_ai_analyzer):
        """
        初始化适配器
        
        Args:
            legacy_ai_analyzer: 旧版AIAnalyzer实例
        """
        self.legacy_analyzer = legacy_ai_analyzer
        self.contextual_analyzer = ContextualAIAnalyzer(legacy_ai_analyzer.llm_client)
    
    async def run(self, state: State) -> State:
        """
        运行适配器，确保符合上下文感知规范
        
        Args:
            state: 输入状态
            
        Returns:
            输出状态
        """
        # 首先使用上下文感知分析器
        try:
            return await self.contextual_analyzer.run(state)
        except Exception as e:
            logger.warning(f"Contextual AI analyzer failed, falling back to legacy: {e}")
            
            # 回退到旧版分析器，但先进行隔离
            isolated_state = self.contextual_analyzer.enforce_ai_isolation(state)
            result = await self.legacy_analyzer.run(isolated_state)
            
            # 将结果整合回原始状态
            return self.contextual_analyzer._integrate_ai_output(state, result.get("ai_analysis", {}))