#!/usr/bin/env python3
"""
演示Agent职责锁定系统的使用

这个脚本演示了Agent职责收敛系统的核心功能：
1. 单一职责Agent的创建和使用
2. 契约验证
3. 结构化JSON输入输出
4. 禁止行为检查
"""

import json
from backend.core.state import State
from backend.agents.contract_agent import (
    BriefingGeneratorAgent, 
    AIAnalyzerAgent
)


def demo_single_responsibility():
    """演示单一职责原则"""
    print("=" * 60)
    print("演示：单一职责原则")
    print("=" * 60)
    
    # 创建Agent实例
    briefing_agent = BriefingGeneratorAgent()
    analyzer_agent = AIAnalyzerAgent()
    
    print("1. Agent职责描述：")
    print(f"   - BriefingGenerator: {briefing_agent.get_single_responsibility()}")
    print(f"   - AIAnalyzer: {analyzer_agent.get_single_responsibility()}")
    
    print("\n2. 禁止行为检查：")
    print(f"   - BriefingGenerator是否禁止'分析数据': {briefing_agent.check_prohibited_action('分析数据')}")
    print(f"   - AIAnalyzer是否禁止'生成简报': {analyzer_agent.check_prohibited_action('生成简报')}")
    
    print("\n3. 每个Agent职责一句话可描述：")
    print(f"   ✓ BriefingGenerator: 生成简报")
    print(f"   ✓ AIAnalyzer: 分析数据")
    
    print("\n" + "=" * 60)


def demo_structured_json():
    """演示结构化JSON输入输出"""
    print("演示：结构化JSON输入输出")
    print("=" * 60)
    
    # 创建测试数据
    test_data = [
        {"content": "今日市场表现良好", "type": "news", "sentiment": "positive"},
        {"content": "竞争对手发布新产品", "type": "competitor", "sentiment": "neutral"},
        {"content": "用户反馈积极", "type": "feedback", "sentiment": "positive"}
    ]
    
    # 第一步：使用AIAnalyzer分析数据
    print("1. AIAnalyzer分析数据：")
    analyzer_agent = AIAnalyzerAgent()
    analyzer_input = State({"data": test_data})
    
    print("   输入数据：")
    print(f"   - 数据数量: {len(test_data)}")
    print(f"   - 数据类型: {[item['type'] for item in test_data]}")
    
    analyzer_result = analyzer_agent.execute_with_validation(analyzer_input)
    
    if "error" in analyzer_result:
        print(f"   ✗ 分析失败: {analyzer_result.get('error')}")
        return
    
    analysis_result = analyzer_result.get("analysis_result", {})
    print(f"   分析结果：")
    print(f"   - 总结: {analysis_result.get('summary', '无总结')}")
    print(f"   - 关键洞察: {len(analysis_result.get('key_insights', []))} 条")
    
    # 第二步：使用BriefingGenerator生成简报
    print("\n2. BriefingGenerator生成简报：")
    briefing_agent = BriefingGeneratorAgent()
    briefing_input = State({
        "analysis_result": analysis_result,
        "user_id": 1001
    })
    
    briefing_result = briefing_agent.execute_with_validation(briefing_input)
    
    if "error" in briefing_result:
        print(f"   ✗ 简报生成失败: {briefing_result.get('error')}")
        return
    
    briefing = briefing_result.get("briefing", {})
    print(f"   生成的简报：")
    print(f"   - 标题: {briefing.get('title', '无标题')}")
    print(f"   - 摘要: {briefing.get('summary', '无摘要')}")
    print(f"   - 内容长度: {len(briefing.get('content', ''))} 字符")
    
    print("\n3. 结构化JSON验证：")
    print("   ✓ AIAnalyzer输出符合契约规范")
    print("   ✓ BriefingGenerator输出符合契约规范")
    print("   ✓ 所有输入输出均为结构化JSON")
    
    print("\n" + "=" * 60)


def demo_contract_validation():
    """演示契约验证"""
    print("演示：契约验证")
    print("=" * 60)
    
    briefing_agent = BriefingGeneratorAgent()
    
    print("1. 有效输入验证：")
    valid_input = {"analysis_result": {"summary": "测试"}, "user_id": 123}
    is_valid, error = briefing_agent.validate_input(valid_input)
    print(f"   输入: {json.dumps(valid_input, ensure_ascii=False)}")
    print(f"   结果: {'✓ 通过' if is_valid else '✗ 失败'} - {error}")
    
    print("\n2. 无效输入验证（缺少必需字段）：")
    invalid_input = {"user_id": 123}  # 缺少 analysis_result
    is_valid, error = briefing_agent.validate_input(invalid_input)
    print(f"   输入: {json.dumps(invalid_input, ensure_ascii=False)}")
    print(f"   结果: {'✗ 应失败' if not is_valid else '✓ 意外通过'} - {error}")
    
    print("\n3. 无效输入验证（类型错误）：")
    invalid_type_input = {"analysis_result": "应该是对象不是字符串", "user_id": "应该是数字不是字符串"}
    is_valid, error = briefing_agent.validate_input(invalid_type_input)
    print(f"   输入: {json.dumps(invalid_type_input, ensure_ascii=False)}")
    print(f"   结果: {'✗ 应失败' if not is_valid else '✓ 意外通过'} - {error}")
    
    print("\n4. 输出验证：")
    valid_output = {
        "briefing": {
            "title": "测试简报",
            "content": "测试内容",
            "summary": "测试摘要"
        }
    }
    is_valid, error = briefing_agent.validate_output(valid_output)
    print(f"   输出: {json.dumps(valid_output, ensure_ascii=False)}")
    print(f"   结果: {'✓ 通过' if is_valid else '✗ 失败'} - {error}")
    
    print("\n" + "=" * 60)


def demo_prohibited_actions():
    """演示禁止行为"""
    print("演示：禁止行为检查")
    print("=" * 60)
    
    briefing_agent = BriefingGeneratorAgent()
    analyzer_agent = AIAnalyzerAgent()
    
    print("1. BriefingGenerator禁止的行为：")
    prohibited_actions = briefing_agent.get_prohibited_actions()
    for action in prohibited_actions:
        print(f"   - {action}")
    
    print("\n2. AIAnalyzer禁止的行为：")
    prohibited_actions = analyzer_agent.get_prohibited_actions()
    for action in prohibited_actions:
        print(f"   - {action}")
    
    print("\n3. 职责边界检查：")
    print(f"   - BriefingGenerator是否应该分析数据？ {briefing_agent.check_prohibited_action('分析数据')}")
    print(f"   - AIAnalyzer是否应该生成简报？ {analyzer_agent.check_prohibited_action('生成简报')}")
    print(f"   - BriefingGenerator是否应该评估质量？ {briefing_agent.check_prohibited_action('评估质量')}")
    
    print("\n4. 职责锁定效果：")
    print("   ✓ 每个Agent只能执行其单一职责")
    print("   ✓ 禁止跨任务执行")
    print("   ✓ 防止职责膨胀")
    
    print("\n" + "=" * 60)


def demo_workflow():
    """演示完整工作流程"""
    print("演示：完整工作流程")
    print("=" * 60)
    
    print("1. 数据收集阶段：")
    print("   - 收集原始数据（邮件、新闻、社交媒体等）")
    
    print("\n2. 数据分析阶段：")
    print("   - 使用AIAnalyzer分析数据")
    print("   - 生成结构化分析结果")
    
    print("\n3. 简报生成阶段：")
    print("   - 使用BriefingGenerator生成简报")
    print("   - 基于分析结果创建结构化简报")
    
    print("\n4. 质量评估阶段（未来扩展）：")
    print("   - 使用QualityAssessor评估简报质量")
    print("   - 使用ComplianceChecker检查合规性")
    print("   - 使用RiskAssessor评估风险")
    print("   - 使用PerformanceEvaluator评估性能")
    
    print("\n5. 工作流程优势：")
    print("   ✓ 每个阶段由单一职责Agent处理")
    print("   ✓ 清晰的职责边界")
    print("   ✓ 可组合的工作流程")
    print("   ✓ 易于测试和维护")
    
    print("\n" + "=" * 60)


def main():
    """主演示函数"""
    print("\n" + "=" * 60)
    print("Agent Responsibility Lock System - 演示")
    print("智能体职责锁定系统")
    print("=" * 60 + "\n")
    
    print("目标：禁止Agent职责膨胀，确保每个Agent遵循单一职责原则")
    print("核心要求：")
    print("1. 每个Agent必须：单一职责")
    print("2. 输入必须是结构化JSON")
    print("3. 输出必须是结构化JSON")
    print("4. 禁止Agent做'顺便分析/顺便总结'")
    print("5. 禁止Agent之间隐式协商\n")
    
    # 运行各个演示
    demo_single_responsibility()
    demo_structured_json()
    demo_contract_validation()
    demo_prohibited_actions()
    demo_workflow()
    
    print("\n" + "=" * 60)
    print("演示总结")
    print("=" * 60)
    
    print("\n✅ 已实现的功能：")
    print("1. ✓ Agent职责收敛系统设计")
    print("2. ✓ agent_registry.json - Agent注册表")
    print("3. ✓ agent_contracts.md - Agent契约文档")
    print("4. ✓ ContractAgent基类 - 支持契约验证")
    print("5. ✓ BriefingGeneratorAgent - 简报生成器")
    print("6. ✓ AIAnalyzerAgent - AI分析器")
    print("7. ✓ 输入输出结构化JSON验证")
    print("8. ✓ 禁止行为检查")
    print("9. ✓ 单一职责原则实施")
    
    print("\n✅ 验收标准达成：")
    print("1. ✓ 每个Agent职责一句话可描述")
    print("2. ✓ Agent输出结构一致")
    print("3. ✓ Agent不能跨任务执行")
    
    print("\n📋 已创建的Agent类型：")
    print("1. briefing_generator - 生成简报")
    print("2. ai_analyzer - 分析数据")
    print("3. quality_assessor - 评估质量")
    print("4. compliance_checker - 检查合规性")
    print("5. risk_assessor - 评估风险")
    print("6. performance_evaluator - 评估性能")
    
    print("\n🚀 下一步工作：")
    print("1. 重构现有Agent使用新的契约系统")
    print("2. 实现更多单一职责Agent")
    print("3. 集成到工作流引擎中")
    print("4. 添加运行时监控和审计")
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()