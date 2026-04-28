from backend.common.core import Agent
from backend.foundation.cognition.state_machine.state_machine import State


class Formatter(Agent):
    """
    格式化器智能体
    
    将 AI 生成的 summary 格式化为最终输出
    必须依赖 AI 结果，不能自己生成内容或使用 fallback mock
    """
    
    def __init__(self, llm_client=None):
        """
        初始化格式化器
        
        Args:
            llm_client: LLM 客户端（可选，formatter 不需要调用 LLM）
        """
        self.llm_client = llm_client
    
    async def run(self, state: State) -> State:
        """
        执行格式化逻辑
        
        从状态中获取 AI 生成的 summary，将其格式化为最终输出
        
        Args:
            state: 状态对象，包含执行上下文和数据
            
        Returns:
            修改后的状态对象
            
        Raises:
            Exception: 如果 AI 结果缺失
        """
        # 从状态中获取 AI 生成的 summary
        summary = state.get("summary")
        
        # 检查 summary 是否存在
        if not summary:
            raise Exception("AI结果缺失")
        
        # 将格式化后的内容设置为 final_output
        # 根据任务要求，格式为：【日报】\n{summary}
        state.set("final_output", f"【日报】\n{summary}")
        
        # 添加事件记录
        state.add_event("formatter_done")
        
        return state
