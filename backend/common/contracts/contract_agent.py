"""
Contract Agent - 支持契约验证的智能体基类

这个基类提供了契约验证功能，确保所有智能体遵循单一职责原则，
输入输出均为结构化JSON格式。
"""

import json
from typing import Dict, Any, Optional, Type
from abc import ABC, abstractmethod
from pydantic import BaseModel, ValidationError
from backend.foundation.cognition.state_machine.state_machine import State


class AgentContract(BaseModel):
    """智能体契约模型"""
    name: str
    description: str
    single_responsibility: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    prohibited_actions: list[str]


class ContractAgent(ABC):
    """
    支持契约验证的智能体基类
    
    所有智能体应该继承这个类，并实现以下功能：
    1. 定义契约（通过get_contract方法）
    2. 实现run方法执行核心逻辑
    3. 确保输入输出符合契约规范
    """
    
    def __init__(self):
        """初始化契约智能体"""
        self.contract = self.get_contract()
        self._validate_contract()
    
    @abstractmethod
    def get_contract(self) -> AgentContract:
        """
        获取智能体契约
        
        子类必须实现此方法，返回智能体的契约定义
        """
        raise NotImplementedError
    
    @abstractmethod
    def run(self, state: State) -> State:
        """
        执行智能体逻辑
        
        子类必须实现此方法，执行智能体的核心逻辑
        """
        raise NotImplementedError
    
    def _validate_contract(self):
        """验证契约定义是否有效"""
        if not self.contract.name:
            raise ValueError("契约必须包含name字段")
        if not self.contract.single_responsibility:
            raise ValueError("契约必须包含single_responsibility字段")
        if not self.contract.input_schema:
            raise ValueError("契约必须包含input_schema字段")
        if not self.contract.output_schema:
            raise ValueError("契约必须包含output_schema字段")
    
    def validate_input(self, input_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证输入数据是否符合契约
        
        Args:
            input_data: 输入数据
            
        Returns:
            tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        try:
            # 检查必需字段
            required_fields = self.contract.input_schema.get("required", [])
            for field in required_fields:
                if field not in input_data:
                    return False, f"缺少必需字段: {field}"
            
            # 验证字段类型（简化验证）
            properties = self.contract.input_schema.get("properties", {})
            for field, schema in properties.items():
                if field in input_data:
                    field_type = schema.get("type")
                    if field_type:
                        value = input_data[field]
                        if field_type == "string" and not isinstance(value, str):
                            return False, f"字段 {field} 应该是字符串类型"
                        elif field_type == "integer" and not isinstance(value, int):
                            return False, f"字段 {field} 应该是整数类型"
                        elif field_type == "number" and not isinstance(value, (int, float)):
                            return False, f"字段 {field} 应该是数字类型"
                        elif field_type == "boolean" and not isinstance(value, bool):
                            return False, f"字段 {field} 应该是布尔类型"
                        elif field_type == "array" and not isinstance(value, list):
                            return False, f"字段 {field} 应该是数组类型"
                        elif field_type == "object" and not isinstance(value, dict):
                            return False, f"字段 {field} 应该是对象类型"
            
            return True, None
            
        except Exception as e:
            return False, f"输入验证失败: {str(e)}"
    
    def validate_output(self, output_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证输出数据是否符合契约
        
        Args:
            output_data: 输出数据
            
        Returns:
            tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        try:
            # 检查必需字段
            required_fields = self.contract.output_schema.get("required", [])
            for field in required_fields:
                if field not in output_data:
                    return False, f"缺少必需输出字段: {field}"
            
            # 验证字段类型（简化验证）
            properties = self.contract.output_schema.get("properties", {})
            for field, schema in properties.items():
                if field in output_data:
                    field_type = schema.get("type")
                    if field_type:
                        value = output_data[field]
                        if field_type == "string" and not isinstance(value, str):
                            return False, f"输出字段 {field} 应该是字符串类型"
                        elif field_type == "integer" and not isinstance(value, int):
                            return False, f"输出字段 {field} 应该是整数类型"
                        elif field_type == "number" and not isinstance(value, (int, float)):
                            return False, f"输出字段 {field} 应该是数字类型"
                        elif field_type == "boolean" and not isinstance(value, bool):
                            return False, f"输出字段 {field} 应该是布尔类型"
                        elif field_type == "array" and not isinstance(value, list):
                            return False, f"输出字段 {field} 应该是数组类型"
                        elif field_type == "object" and not isinstance(value, dict):
                            return False, f"输出字段 {field} 应该是对象类型"
            
            return True, None
            
        except Exception as e:
            return False, f"输出验证失败: {str(e)}"
    
    def execute_with_validation(self, state: State) -> State:
        """
        执行智能体逻辑并进行契约验证
        
        Args:
            state: 输入状态
            
        Returns:
            输出状态
        """
        # 记录开始事件
        state.add_event(f"{self.contract.name}_start")
        
        try:
            # 验证输入
            input_data = state.to_plain_dict()
            is_valid, error = self.validate_input(input_data)
            if not is_valid:
                state.set("error", f"输入验证失败: {error}")
                state.add_event(f"{self.contract.name}_input_validation_failed")
                return state
            
            # 执行核心逻辑
            result_state = self.run(state)
            
            # 验证输出
            output_data = result_state.to_plain_dict()
            is_valid, error = self.validate_output(output_data)
            if not is_valid:
                result_state.set("error", f"输出验证失败: {error}")
                result_state.add_event(f"{self.contract.name}_output_validation_failed")
                return result_state
            
            # 记录成功事件
            result_state.add_event(f"{self.contract.name}_success")
            
            return result_state
            
        except Exception as e:
            # 记录错误事件
            state.set("error", f"执行失败: {str(e)}")
            state.add_event(f"{self.contract.name}_execution_failed")
            return state
    
    def get_single_responsibility(self) -> str:
        """获取单一职责描述"""
        return self.contract.single_responsibility
    
    def get_prohibited_actions(self) -> list[str]:
        """获取禁止行为列表"""
        return self.contract.prohibited_actions
    
    def check_prohibited_action(self, action: str) -> bool:
        """检查某个行为是否被禁止"""
        return action in self.contract.prohibited_actions


class BriefingGeneratorAgent(ContractAgent):
    """简报生成器 - 示例实现"""
    
    def get_contract(self) -> AgentContract:
        return AgentContract(
            name="briefing_generator",
            description="生成简报 - 从分析结果生成结构化简报",
            single_responsibility="将分析结果转换为结构化简报",
            input_schema={
                "type": "object",
                "required": ["analysis_result"],
                "properties": {
                    "analysis_result": {
                        "type": "object",
                        "description": "分析结果，包含总结和关键信息"
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "用户ID"
                    }
                }
            },
            output_schema={
                "type": "object",
                "required": ["briefing"],
                "properties": {
                    "briefing": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "简报标题"
                            },
                            "content": {
                                "type": "string",
                                "description": "简报内容"
                            },
                            "summary": {
                                "type": "string",
                                "description": "简报摘要"
                            }
                        }
                    }
                }
            },
            prohibited_actions=[
                "分析数据",
                "评估质量",
                "判断风险",
                "执行其他Agent的职责"
            ]
        )
    
    def run(self, state: State) -> State:
        """执行简报生成逻辑"""
        analysis_result = state.get("analysis_result", {})
        user_id = state.get("user_id", 0)
        
        # 生成简报（简化实现）
        briefing = {
            "title": f"用户{user_id}的简报",
            "content": analysis_result.get("summary", "无内容"),
            "summary": analysis_result.get("summary", "无摘要")
        }
        
        state.set("briefing", briefing)
        return state


class AIAnalyzerAgent(ContractAgent):
    """AI分析器 - 示例实现"""
    
    def get_contract(self) -> AgentContract:
        return AgentContract(
            name="ai_analyzer",
            description="分析数据 - 使用AI分析输入数据并生成总结",
            single_responsibility="分析输入数据并生成结构化分析结果",
            input_schema={
                "type": "object",
                "required": ["data"],
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object"
                        },
                        "description": "要分析的数据列表"
                    }
                }
            },
            output_schema={
                "type": "object",
                "required": ["analysis_result"],
                "properties": {
                    "analysis_result": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "分析总结"
                            },
                            "key_insights": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "关键洞察"
                            }
                        }
                    }
                }
            },
            prohibited_actions=[
                "生成简报",
                "评估质量",
                "判断风险",
                "执行其他Agent的职责"
            ]
        )
    
    def run(self, state: State) -> State:
        """执行数据分析逻辑"""
        data = state.get("data", [])
        
        # 分析数据（简化实现）
        summary = f"分析了{len(data)}条数据"
        key_insights = []
        
        for i, item in enumerate(data[:3]):  # 只取前3条作为关键洞察
            if isinstance(item, dict):
                key_insights.append(f"数据{i+1}: {str(item)[:50]}...")
            else:
                key_insights.append(f"数据{i+1}: {str(item)[:50]}...")
        
        analysis_result = {
            "summary": summary,
            "key_insights": key_insights
        }
        
        state.set("analysis_result", analysis_result)
        return state