# Agent Contracts - 智能体契约

## 概述

本文档定义了所有智能体的契约规范，确保每个智能体遵循单一职责原则，输入输出均为结构化JSON格式，禁止职责膨胀和隐式协商。

## 核心原则

1. **单一职责原则**：每个智能体只能有一个明确的职责
2. **结构化输入输出**：所有输入输出必须是结构化JSON
3. **禁止职责膨胀**：智能体不能做"顺便分析/顺便总结"
4. **禁止隐式协商**：智能体之间不能进行隐式协商

## 智能体契约列表

### 1. Briefing Generator (简报生成器)

**职责描述**：将分析结果转换为结构化简报

**单一职责**：生成简报

**输入契约**：
```json
{
  "analysis_result": {
    "type": "object",
    "description": "分析结果，包含总结和关键信息"
  },
  "user_id": {
    "type": "integer",
    "description": "用户ID"
  }
}
```

**输出契约**：
```json
{
  "briefing": {
    "title": "string - 简报标题",
    "content": "string - 简报内容",
    "summary": "string - 简报摘要"
  }
}
```

**禁止行为**：
- 分析数据
- 评估质量
- 判断风险
- 执行其他Agent的职责

### 2. AI Analyzer (AI分析器)

**职责描述**：分析输入数据并生成结构化分析结果

**单一职责**：分析数据

**输入契约**：
```json
{
  "data": {
    "type": "array",
    "items": {
      "type": "object"
    },
    "description": "要分析的数据列表"
  }
}
```

**输出契约**：
```json
{
  "analysis_result": {
    "summary": "string - 分析总结",
    "key_insights": ["string - 关键洞察"]
  }
}
```

**禁止行为**：
- 生成简报
- 评估质量
- 判断风险
- 执行其他Agent的职责

### 3. Quality Assessor (质量评估器)

**职责描述**：评估执行结果的质量并提供质量评分

**单一职责**：评估质量

**输入契约**：
```json
{
  "execution_result": {
    "type": "object",
    "description": "执行结果"
  }
}
```

**输出契约**：
```json
{
  "quality_assessment": {
    "overall_score": "number (0-100) - 总体质量得分",
    "passed": "boolean - 是否通过质量检查"
  }
}
```

**禁止行为**：
- 检查合规性
- 评估风险
- 分析数据
- 生成简报

### 4. Compliance Checker (合规检查器)

**职责描述**：检查执行结果是否符合合规要求

**单一职责**：检查合规性

**输入契约**：
```json
{
  "execution_result": {
    "type": "object",
    "description": "执行结果"
  }
}
```

**输出契约**：
```json
{
  "compliance_check": {
    "overall_compliant": "boolean - 总体是否合规"
  }
}
```

**禁止行为**：
- 评估质量
- 评估风险
- 分析数据
- 生成简报

### 5. Risk Assessor (风险评估器)

**职责描述**：评估执行结果的风险等级和风险因素

**单一职责**：评估风险

**输入契约**：
```json
{
  "execution_result": {
    "type": "object",
    "description": "执行结果"
  }
}
```

**输出契约**：
```json
{
  "risk_assessment": {
    "overall_risk_level": "string - 总体风险等级 (critical/high/medium/low)"
  }
}
```

**禁止行为**：
- 评估质量
- 检查合规性
- 分析数据
- 生成简报

### 6. Performance Evaluator (性能评估器)

**职责描述**：评估执行结果的性能指标

**单一职责**：评估性能

**输入契约**：
```json
{
  "execution_result": {
    "type": "object",
    "description": "执行结果"
  }
}
```

**输出契约**：
```json
{
  "performance_evaluation": {
    "overall_score": "number (0-100) - 总体性能得分"
  }
}
```

**禁止行为**：
- 评估质量
- 检查合规性
- 评估风险
- 分析数据
- 生成简报

## 执行规范

### 输入验证
每个智能体在开始执行前必须验证输入是否符合契约规范：
1. 检查必需字段是否存在
2. 验证字段类型是否符合预期
3. 验证数据格式是否正确

### 输出标准化
每个智能体必须确保输出符合契约规范：
1. 必须包含所有必需字段
2. 字段类型必须符合规范
3. 数据格式必须标准化

### 错误处理
1. 输入验证失败时，必须返回明确的错误信息
2. 执行过程中发生错误，必须记录错误详情
3. 错误信息必须结构化，便于后续处理

## 职责锁定机制

### 1. 契约注册
所有智能体必须在`agent_registry.json`中注册，明确其职责、输入输出契约和禁止行为。

### 2. 运行时检查
系统在运行时检查智能体是否遵守契约：
- 输入是否符合契约规范
- 输出是否符合契约规范
- 是否执行了禁止行为

### 3. 审计日志
记录每个智能体的执行情况：
- 输入数据
- 输出数据
- 执行时间
- 是否违反契约

## 重构指南

### 现有智能体重构
1. **briefing_agent** → **briefing_generator**
   - 移除所有分析逻辑
   - 只保留简报生成功能

2. **analyzer_agent** → **ai_analyzer**
   - 移除所有评估逻辑
   - 只保留数据分析功能

3. **judge_agent** → 拆分为多个单一职责智能体：
   - **quality_assessor** - 质量评估
   - **compliance_checker** - 合规检查
   - **risk_assessor** - 风险评估
   - **performance_evaluator** - 性能评估

### 新智能体开发规范
1. 明确单一职责
2. 定义输入输出契约
3. 注册到agent_registry.json
4. 实现契约验证
5. 确保不执行禁止行为

## 验收标准

### 每个智能体职责一句话可描述
- briefing_generator: 生成简报
- ai_analyzer: 分析数据
- quality_assessor: 评估质量
- compliance_checker: 检查合规性
- risk_assessor: 评估风险
- performance_evaluator: 评估性能

### Agent输出结构一致
所有智能体输出都遵循统一的结构化JSON格式，包含明确的字段和类型定义。

### Agent不能跨任务执行
每个智能体只能执行其契约定义的单一职责，不能执行其他智能体的职责。

## 实施时间表

1. **第一阶段**：创建契约文档和注册表
2. **第二阶段**：重构现有智能体
3. **第三阶段**：实现运行时检查机制
4. **第四阶段**：全面测试和验证

## 维护和更新

1. 智能体契约变更必须更新`agent_registry.json`和本文档
2. 新增智能体必须遵循本规范
3. 定期审计智能体是否遵守契约

---

*最后更新：2026-04-19*
*版本：1.0.0*