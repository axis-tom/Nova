"""
Prompt Engine — Agent System Prompt 动态定制引擎

对外只暴露 PromptEngine 类。
用法：
    engine = PromptEngine()
    spec = engine.translate("分析蓝牙耳机，重点看定价", session_id="conv_xxx")
    system_prompt = engine.customize("market_analyst", spec)
"""

from backend.core.prompt_engine.prompt_engine import PromptEngine

__all__ = ["PromptEngine"]