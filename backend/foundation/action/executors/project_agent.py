import json
from typing import List, Dict, Any
from backend.common.core import Agent, AgentInput, AgentOutput

class ProjectAgent(Agent):
    """
    项目拆解智能体：
    将大任务拆分为子任务，并生成可执行清单。
    """
    name = "project_agent"
    description = "将复杂项目拆解为可执行子任务"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        project_description = input_data.data.get("description", "")
        if not project_description:
            return AgentOutput(
                result=[],
                metadata={"error": "No project description"},
                error="No description"
            )

        use_model = input_data.config.get("use_model", True)  # 默认使用模型
        if use_model:
            subtasks = await self._decompose_by_model(project_description)
        else:
            subtasks = self._decompose_by_rules(project_description)

        return AgentOutput(
            result=subtasks,
            metadata={"method": "model" if use_model else "rules", "count": len(subtasks)}
        )

    def _decompose_by_rules(self, description: str) -> List[Dict[str, Any]]:
        """基于规则的简单拆解（示例）"""
        # 根据关键词生成典型任务
        tasks = []
        if "开发" in description:
            tasks.append({"title": "需求分析", "estimated_hours": 2})
            tasks.append({"title": "技术方案设计", "estimated_hours": 4})
            tasks.append({"title": "编码实现", "estimated_hours": 8})
            tasks.append({"title": "测试", "estimated_hours": 4})
        elif "营销" in description:
            tasks.append({"title": "市场调研", "estimated_hours": 3})
            tasks.append({"title": "内容制作", "estimated_hours": 5})
            tasks.append({"title": "渠道投放", "estimated_hours": 2})
            tasks.append({"title": "数据复盘", "estimated_hours": 2})
        else:
            tasks.append({"title": "理解需求", "estimated_hours": 1})
            tasks.append({"title": "执行计划", "estimated_hours": 2})
            tasks.append({"title": "验收交付", "estimated_hours": 1})
        return tasks

    async def _decompose_by_model(self, description: str) -> List[Dict[str, Any]]:
        """调用模型进行拆解"""
        prompt = f"""请将以下项目描述拆解为具体的子任务列表，输出JSON格式，每个任务包含 title（标题）和 estimated_hours（预估小时数）。

项目描述：{description}

输出（JSON列表）："""
        try:
            response = await self._call_model(prompt)
            json_str = self._extract_json(response)
            if json_str:
                tasks = json.loads(json_str)
                if isinstance(tasks, list):
                    return tasks
            return self._decompose_by_rules(description)
        except Exception as e:
            print(f"Model call failed: {e}")
            return self._decompose_by_rules(description)

    def _extract_json(self, text: str) -> str:
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return ""