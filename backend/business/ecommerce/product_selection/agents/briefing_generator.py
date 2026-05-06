
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from backend.common.core.agent import Agent, AgentInput, AgentOutput
from backend.common.core.state import State

class BriefingGeneratorAgent(Agent):
    """简报生成 Agent — 汇总所有分析结果，生成最终的选品简报"""

    def __init__(self):
        super().__init__(name="briefing_generator")

    def run(self, state: State) -> State:
        """执行简报生成"""
        try:
            # 1. 从 State 中收集所有分析结果
            market_analysis = state.get("market_analysis_result") or {}
            competitor_analysis = state.get("competitor_analysis_result") or {}
            profitability = state.get("profitability_result") or {}
            
            # 2. 生成 Markdown 和 JSON 格式的简报
            markdown_briefing = self._generate_markdown_briefing(
                market_analysis, competitor_analysis, profitability
            )
            json_briefing = self._generate_json_briefing(
                market_analysis, competitor_analysis, profitability
            )
            
            # 3. 组装最终简报对象
            briefing = {
                "title": "电商选品分析简报",
                "generated_at": datetime.now().isoformat(),
                "market_analysis": market_analysis,
                "competitor_analysis": competitor_analysis,
                "profitability": profitability,
                "markdown": markdown_briefing,
                "json": json_briefing
            }
            
            # 4. 将简报对象存入 State
            state.set("briefing", briefing)
            
            # 5. 【关键修复】将 Markdown 字符串放到 'result' 字段中，供前端渲染
            state.set("result", markdown_briefing)
            state.add_event("briefing_generation_done")
            
            return state
            
        except Exception as e:
            state.set("error", f"简报生成失败: {str(e)}")
            state.add_event(f"briefing_generation_failed: {str(e)}")
            return state

    def execute(self, input_data: AgentInput) -> AgentOutput:
        """实现基类的 execute 方法"""
        state = State()
        state.data = input_data.data or {}
        
        state = self.run(state)
        
        # 返回 AgentOutput，包含简报内容
        return AgentOutput(
            result=state.get("result", {}),
            metadata={
                "agent": self.name,
                "status": "completed",
                "briefing_data": state.get("briefing", {})
            }
        )

    def _generate_markdown_briefing(
        self,
        market_analysis: Dict[str, Any],
        competitor_analysis: Dict[str, Any],
        profitability: Dict[str, Any]
    ) -> str:
        """生成 Markdown 格式的选品简报"""
        lines = [
            "# 📊 电商选品分析简报",
            f"\n> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "\n---",
            "\n## 一、市场概况",
        ]
        
        # 市场分析部分
        if market_analysis:
            summary = market_analysis.get("summary", "暂无市场分析数据")
            lines.append(f"\n{summary}")
            
            # 机会点
            opportunities = market_analysis.get("opportunities", [])
            if opportunities:
                lines.append("\n### 🟢 市场机会")
                for opp in opportunities[:5]:
                    lines.append(f"- {opp}")
            
            # 风险点
            risks = market_analysis.get("risks", [])
            if risks:
                lines.append("\n### 🔴 风险提示")
                for risk in risks[:5]:
                    lines.append(f"- {risk}")
        
        # 竞品分析部分
        if competitor_analysis:
            lines.append("\n---\n## 二、竞品分析")
            summary = competitor_analysis.get("summary", "暂无竞品数据")
            lines.append(f"\n{summary}")
            
            benchmark = competitor_analysis.get("benchmark", {})
            if benchmark:
                lines.append("\n### 竞品对比")
                for key, value in benchmark.items():
                    lines.append(f"- **{key}**：{value}")
        
        # 盈利评估部分
        if profitability:
            lines.append("\n---\n## 三、盈利评估")
            summary = profitability.get("summary", "暂无盈利数据")
            lines.append(f"\n{summary}")
            
            recommendations = profitability.get("recommendations", [])
            if recommendations:
                lines.append("\n### 💡 选品建议")
                for rec in recommendations[:5]:
                    lines.append(f"- {rec}")
        
        lines.append("\n---\n*本简报由 Nova AI 智能体自动生成*")
        return "\n".join(lines)

    def _generate_json_briefing(
        self,
        market_analysis: Dict[str, Any],
        competitor_analysis: Dict[str, Any],
        profitability: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成 JSON 格式的选品简报数据"""
        return {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "generator": self.name,
                "version": "1.0.0"
            },
            "sections": {
                "market_analysis": market_analysis,
                "competitor_analysis": competitor_analysis,
                "profitability_assessment": profitability
            }
        }