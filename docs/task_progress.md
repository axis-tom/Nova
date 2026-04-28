# TASK 4 & TASK 5 实施计划

## TASK 4 - API入口统一化（系统收口）
**目标**: 所有AI行为必须走Graph入口

### 实施步骤:
- [ ] 1. 创建统一的Graph API入口 `/graph/run`
- [ ] 2. 实现输入规范: `{"scenario": "email_briefing", "input": {}, "env": "sandbox"}`
- [ ] 3. 集成现有的确定性Graph引擎
- [ ] 4. 禁用直接Agent API调用
- [ ] 5. 验证所有业务调用统一入口

## TASK 5 - F5稳定性验证系统（收尾）
**目标**: 验证系统是否真的"稳定"

### 实施步骤:
- [ ] 1. 创建F5稳定性测试套件
- [ ] 2. 实现10次重复执行测试
- [ ] 3. 实现graph path一致性检测
- [ ] 4. 实现agent output一致性检测
- [ ] 5. 生成f5_test_report.json
- [ ] 6. 验证10次运行结构一致率 = 100%
- [ ] 7. 验证无Graph漂移
- [ ] 8. 验证无Agent职责越界

## F5完成判定标准:
- [ ] Graph固定
- [ ] Agent收敛
- [ ] Trace可回放
- [ ] API唯一入口
- [ ] 稳定性测试通过