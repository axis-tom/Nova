"""
PromptCustomizer — 自定义 prompt 渲染模块

借鉴 Prompty 的 Load→Render 管道。
用 Jinja2 渲染 .prompty 模板 + 注入 orchestrator 分配的子任务。
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from backend.core.prompt_engine.dimension_registry import get_dimension_registry

# .prompty 模板目录
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptCustomizer:
    """Prompt 定制器——加载 .prompty 模板 + 注入 orchestrator 分配的子任务

    不再从 dimension_registry 注入预设分析方向。
    Agent 的分析方向由 orchestrator 在 ReAct 循环中动态分配（自然语言 sub_task）。
    """

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.registry = get_dimension_registry()

    def customize(
        self,
        agent_name: str,
        dimensions: Optional[list] = None,
        primary_dim: str = "",
        is_incremental: bool = False,
        extra_vars: Optional[Dict[str, Any]] = None,
        # ── 新参数 ──
        sub_task: str = "",
    ) -> str:
        """为指定 Agent 生成定制 system prompt

        流程：
        1. 加载 agent.prompty 模板
        2. 如果有 sub_task（推荐），注入 orchestrator 分配的自然语言子任务
        3. 否则向后兼容：从 DimensionRegistry 读（已废弃，返回空）
        4. Jinja2 渲染 → 返回完整 system prompt

        Args:
            agent_name: Agent 名称
            dimensions: 旧参数（已废弃，留空即可）
            primary_dim: 旧参数（已废弃，留空即可）
            is_incremental: 是否为增量分析
            extra_vars: 额外模板变量
            sub_task: ★ 新参数 — orchestrator 分配给该 Agent 的子任务描述（自然语言）
        """
        # 构建模板变量
        focus_directions = ""
        if sub_task:
            # ★ 新路径：自然语言子任务直接注入
            focus_directions = f"【Orchestrator 分配的任务】\n{sub_task}"
        elif primary_dim:
            # 旧路径（向后兼容）：从 registry 读（已废弃，返回空）
            agent_prompt = self.registry.get_agent_prompt(primary_dim, agent_name)
            if agent_prompt:
                focus_directions = f"【主线方向】{self.registry.get_dim_name(primary_dim)}\n{agent_prompt}"

        # 弱化方向（旧字段，已废弃）
        downgrade_directions = ""
        if not sub_task and primary_dim:
            downgraded = self.registry.get_downgraded_directions(primary_dim)
            if downgraded:
                names = [self.registry.get_dim_name(d) for d in downgraded]
                downgrade_directions = f"【弱化方向】本次非重点：{', '.join(names)}。分析时简要带过即可。"

        # 其他辅助方向（旧字段，已废弃）
        other_directions = ""
        if not sub_task and dimensions:
            other_dims = [d for d in dimensions if d != primary_dim]
            if other_dims:
                other_parts = []
                for d in other_dims:
                    agent_prompt = self.registry.get_agent_prompt(d, agent_name)
                    if agent_prompt:
                        other_parts.append(f"- {self.registry.get_dim_name(d)}: {agent_prompt}")
                if other_parts:
                    other_directions = "【辅助方向】\n" + "\n".join(other_parts)

        # 渲染模板
        vars_dict = {
            "focus_directions": focus_directions,
            "downgrade_directions": downgrade_directions,
            "other_directions": other_directions,
            "is_incremental": is_incremental,
            "agent_name": agent_name,
        }
        if extra_vars:
            vars_dict.update(extra_vars)

        return self._render(agent_name, vars_dict)

    def _render(self, agent_name: str, vars_dict: Dict[str, Any]) -> str:
        """渲染 Agent 的 .prompty 模板"""
        # 尝试精确匹配 agent 名称
        template_name = f"{agent_name}.prompty"
        try:
            template = self.env.get_template(template_name)
            return template.render(**vars_dict)
        except TemplateNotFound:
            # 回退到 base_agent.prompty
            try:
                template = self.env.get_template("base_agent.prompty")
                return template.render(**vars_dict)
            except TemplateNotFound:
                return self._default_prompt(agent_name, vars_dict)

    def _default_prompt(self, agent_name: str, vars_dict: Dict[str, Any]) -> str:
        """兜底：没有模板文件时生成通用 prompt"""
        parts = [f"你是 Amazon {agent_name.replace('_', ' ')} 分析专家。"]

        if vars_dict.get("focus_directions"):
            parts.append(vars_dict["focus_directions"])

        if vars_dict.get("other_directions"):
            parts.append(vars_dict["other_directions"])

        if vars_dict.get("downgrade_directions"):
            parts.append(vars_dict["downgrade_directions"])

        if vars_dict.get("is_incremental"):
            parts.append("注意：本轮是增量分析。已有数据不重复采集，聚焦未覆盖的方向。")

        parts.append("请逐步分析，输出结构化中文报告。")
        return "\n\n".join(parts)

    def list_available_templates(self) -> list:
        """列出可用的 .prompty 模板"""
        if not _PROMPTS_DIR.exists():
            return []
        return sorted(
            f.stem for f in _PROMPTS_DIR.iterdir()
            if f.suffix == ".prompty"
        )