"""
Judge Agent - 结果评估Agent
负责评估执行结果、质量检查、合规验证
"""

from typing import Dict, Any, List
from backend.foundation.cognition.state_machine.state_machine import State
from backend.business.ecommerce.base import BaseEcommerceAgent


class JudgeAgent(BaseEcommerceAgent):
    """
    Judge Agent - 结果评估Agent
    
    职责：
    1. 评估执行结果的质量和效果
    2. 检查合规性和安全性
    3. 识别异常和风险
    4. 提供改进建议
    """
    
    def __init__(self):
        """初始化Judge Agent"""
        super().__init__(
            name="ecommerce_judge",
            description="电商结果评估Agent，负责评估执行结果、质量检查、合规验证"
        )
    
    def run(self, state: State) -> State:
        """
        执行Judge Agent逻辑
        
        Args:
            state: 输入状态
            
        Returns:
            输出状态
        """
        # 记录开始事件
        state = self.log_event(state, "start", "开始执行结果评估")
        
        try:
            # 验证输入
            if not self.validate_input(state):
                state = self.log_event(state, "error", "输入验证失败")
                state["judge_error"] = "输入数据不完整"
                state = self.add_execution_record(state, False, {"error": "输入验证失败"})
                return state
            
            # 提取评估任务
            evaluation_task = state.get("evaluation_task", {})
            execution_result = state.get("execution_result", {})
            context = state.get("context", {})
            
            # 根据任务类型执行评估
            task_type = evaluation_task.get("type", "unknown")
            
            if task_type == "quality_assessment":
                result = self._assess_quality(execution_result, context)
            elif task_type == "compliance_check":
                result = self._check_compliance(execution_result, context)
            elif task_type == "risk_assessment":
                result = self._assess_risk(execution_result, context)
            elif task_type == "performance_evaluation":
                result = self._evaluate_performance(execution_result, context)
            else:
                result = self._general_evaluation(execution_result, context)
            
            # 更新状态
            state["evaluation_result"] = result
            state["judge_executed"] = True
            
            # 记录成功事件
            state = self.log_event(state, "success", f"成功完成{task_type}评估")
            state = self.add_execution_record(state, True, {
                "task_type": task_type,
                "overall_score": result.get("overall_score", 0),
                "issues_found": len(result.get("issues", []))
            })
            
        except Exception as e:
            # 记录错误事件
            state = self.log_event(state, "error", f"结果评估失败: {str(e)}")
            state["judge_error"] = str(e)
            state["judge_executed"] = False
            state = self.add_execution_record(state, False, {"error": str(e)})
        
        return state
    
    def get_required_fields(self) -> list:
        """
        获取必需的输入字段
        
        Returns:
            必需字段列表
        """
        return ["evaluation_task", "execution_result"]
    
    def get_output_fields(self) -> list:
        """
        获取输出的字段
        
        Returns:
            输出字段列表
        """
        return ["evaluation_result", "judge_executed", "judge_error"]
    
    def _assess_quality(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估执行结果质量
        
        Args:
            execution_result: 执行结果
            context: 上下文信息
            
        Returns:
            质量评估结果
        """
        import time
        
        # 提取质量评估标准
        quality_standards = context.get("quality_standards", {})
        
        # 初始化评估结果
        assessment = {
            "overall_score": 0,
            "dimensions": {},
            "issues": [],
            "recommendations": [],
            "passed": True
        }
        
        # 检查执行是否成功
        if not execution_result.get("success", False):
            assessment["overall_score"] = 0
            assessment["issues"].append({
                "type": "execution_failed",
                "severity": "critical",
                "description": "执行失败",
                "details": execution_result.get("error", "未知错误")
            })
            assessment["passed"] = False
            assessment["recommendations"].append("修复执行错误后重新执行")
            return assessment
        
        # 评估维度1: 执行时间
        execution_time = execution_result.get("execution_time", 0)
        max_allowed_time = quality_standards.get("max_execution_time", 30)
        
        time_score = 100
        if execution_time > max_allowed_time:
            time_score = max(0, 100 - (execution_time - max_allowed_time) * 10)
            assessment["issues"].append({
                "type": "slow_execution",
                "severity": "warning",
                "description": f"执行时间过长: {execution_time:.2f}秒",
                "details": f"超过最大允许时间{max_allowed_time}秒"
            })
            assessment["recommendations"].append("优化API调用或增加超时时间")
        
        assessment["dimensions"]["execution_time"] = {
            "score": time_score,
            "value": execution_time,
            "threshold": max_allowed_time
        }
        
        # 评估维度2: API调用次数
        api_calls = execution_result.get("api_calls", 0)
        optimal_calls = quality_standards.get("optimal_api_calls", 1)
        
        calls_score = 100
        if api_calls > optimal_calls * 2:
            calls_score = max(0, 100 - (api_calls - optimal_calls) * 20)
            assessment["issues"].append({
                "type": "excessive_api_calls",
                "severity": "warning",
                "description": f"API调用次数过多: {api_calls}次",
                "details": f"最优调用次数为{optimal_calls}次"
            })
            assessment["recommendations"].append("合并API调用或使用批量操作")
        
        assessment["dimensions"]["api_calls"] = {
            "score": calls_score,
            "value": api_calls,
            "threshold": optimal_calls
        }
        
        # 评估维度3: 数据完整性
        data_completeness = self._assess_data_completeness(execution_result)
        assessment["dimensions"]["data_completeness"] = {
            "score": data_completeness["score"],
            "value": data_completeness["completeness"],
            "missing_fields": data_completeness["missing_fields"]
        }
        
        if data_completeness["score"] < 80:
            assessment["issues"].append({
                "type": "incomplete_data",
                "severity": "medium",
                "description": "返回数据不完整",
                "details": f"缺失字段: {', '.join(data_completeness['missing_fields'])}"
            })
            assessment["recommendations"].append("确保API返回所有必要字段")
        
        # 评估维度4: 错误处理
        error_handling = self._assess_error_handling(execution_result)
        assessment["dimensions"]["error_handling"] = {
            "score": error_handling["score"],
            "has_error_details": error_handling["has_error_details"],
            "has_retry_mechanism": error_handling["has_retry_mechanism"]
        }
        
        if error_handling["score"] < 70:
            assessment["issues"].append({
                "type": "poor_error_handling",
                "severity": "medium",
                "description": "错误处理不完善",
                "details": "缺少错误详情或重试机制"
            })
            assessment["recommendations"].append("改进错误处理和重试逻辑")
        
        # 计算总体得分
        dimension_scores = [dim["score"] for dim in assessment["dimensions"].values()]
        if dimension_scores:
            assessment["overall_score"] = sum(dimension_scores) / len(dimension_scores)
        
        # 确定是否通过
        min_pass_score = quality_standards.get("min_pass_score", 70)
        assessment["passed"] = assessment["overall_score"] >= min_pass_score
        
        if not assessment["passed"]:
            assessment["issues"].append({
                "type": "below_threshold",
                "severity": "critical",
                "description": f"总体得分低于阈值: {assessment['overall_score']:.1f}/{min_pass_score}",
                "details": "需要改进执行质量"
            })
        
        assessment["timestamp"] = time.time()
        return assessment
    
    def _assess_data_completeness(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估数据完整性
        
        Args:
            execution_result: 执行结果
            
        Returns:
            数据完整性评估
        """
        # 定义期望的字段
        expected_fields = [
            "success",
            "api_calls",
            "execution_time"
        ]
        
        # 根据执行类型添加特定字段
        if "product_id" in execution_result:
            expected_fields.extend(["product_id", "platform", "product_data"])
        elif "order_id" in execution_result:
            expected_fields.extend(["order_id", "platform", "order_data"])
        elif "updated_items" in execution_result:
            expected_fields.extend(["updated_items", "platform", "inventory_updates"])
        
        # 检查字段存在性
        missing_fields = []
        for field in expected_fields:
            if field not in execution_result:
                missing_fields.append(field)
        
        # 计算完整性得分
        completeness = 1.0 - (len(missing_fields) / len(expected_fields)) if expected_fields else 1.0
        score = completeness * 100
        
        return {
            "score": score,
            "completeness": completeness,
            "missing_fields": missing_fields,
            "expected_fields": expected_fields
        }
    
    def _assess_error_handling(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估错误处理
        
        Args:
            execution_result: 执行结果
            
        Returns:
            错误处理评估
        """
        score = 100
        
        # 检查是否有错误详情
        has_error_details = "error" in execution_result or "error_message" in execution_result
        
        # 检查是否有重试机制
        has_retry_mechanism = "retry_count" in execution_result or "retry_attempts" in execution_result
        
        # 计算得分
        if not has_error_details:
            score -= 30
        
        if not has_retry_mechanism:
            score -= 20
        
        # 检查错误消息质量
        error_message = execution_result.get("error") or execution_result.get("error_message")
        if error_message and len(error_message) < 10:
            score -= 10  # 错误消息太简短
        
        return {
            "score": max(0, score),
            "has_error_details": has_error_details,
            "has_retry_mechanism": has_retry_mechanism,
            "error_message_quality": "good" if error_message and len(error_message) >= 10 else "poor"
        }
    
    def _check_compliance(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查合规性
        
        Args:
            execution_result: 执行结果
            context: 上下文信息
            
        Returns:
            合规性检查结果
        """
        import time
        
        # 提取合规性要求
        compliance_rules = context.get("compliance_rules", {})
        
        # 初始化检查结果
        compliance_check = {
            "overall_compliant": True,
            "rules_checked": [],
            "violations": [],
            "warnings": [],
            "recommendations": []
        }
        
        # 规则1: 数据隐私合规
        if compliance_rules.get("check_data_privacy", True):
            data_privacy_compliant = self._check_data_privacy(execution_result)
            compliance_check["rules_checked"].append({
                "rule": "data_privacy",
                "compliant": data_privacy_compliant["compliant"],
                "details": data_privacy_compliant["details"]
            })
            
            if not data_privacy_compliant["compliant"]:
                compliance_check["overall_compliant"] = False
                compliance_check["violations"].append({
                    "rule": "data_privacy",
                    "severity": "high",
                    "description": "数据隐私合规问题",
                    "details": data_privacy_compliant["details"]
                })
                compliance_check["recommendations"].append("确保不传输或存储敏感个人信息")
        
        # 规则2: API使用合规
        if compliance_rules.get("check_api_usage", True):
            api_usage_compliant = self._check_api_usage(execution_result)
            compliance_check["rules_checked"].append({
                "rule": "api_usage",
                "compliant": api_usage_compliant["compliant"],
                "details": api_usage_compliant["details"]
            })
            
            if not api_usage_compliant["compliant"]:
                compliance_check["overall_compliant"] = False
                compliance_check["violations"].append({
                    "rule": "api_usage",
                    "severity": "medium",
                    "description": "API使用合规问题",
                    "details": api_usage_compliant["details"]
                })
                compliance_check["recommendations"].append("遵守API使用条款和限制")
        
        # 规则3: 业务规则合规
        if compliance_rules.get("check_business_rules", True):
            business_rules_compliant = self._check_business_rules(execution_result, context)
            compliance_check["rules_checked"].append({
                "rule": "business_rules",
                "compliant": business_rules_compliant["compliant"],
                "details": business_rules_compliant["details"]
            })
            
            if not business_rules_compliant["compliant"]:
                compliance_check["overall_compliant"] = False
                compliance_check["violations"].append({
                    "rule": "business_rules",
                    "severity": "high",
                    "description": "业务规则合规问题",
                    "details": business_rules_compliant["details"]
                })
                compliance_check["recommendations"].append("遵守业务规则和流程")
        
        # 规则4: 安全合规
        if compliance_rules.get("check_security", True):
            security_compliant = self._check_security(execution_result)
            compliance_check["rules_checked"].append({
                "rule": "security",
                "compliant": security_compliant["compliant"],
                "details": security_compliant["details"]
            })
            
            if not security_compliant["compliant"]:
                compliance_check["overall_compliant"] = False
                compliance_check["violations"].append({
                    "rule": "security",
                    "severity": "critical",
                    "description": "安全合规问题",
                    "details": security_compliant["details"]
                })
                compliance_check["recommendations"].append("加强安全措施和验证")
        
        # 添加时间戳
        compliance_check["timestamp"] = time.time()
        
        return compliance_check
    
    def _check_data_privacy(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查数据隐私合规
        
        Args:
            execution_result: 执行结果
            
        Returns:
            数据隐私合规检查结果
        """
        # 敏感数据字段
        sensitive_fields = ["email", "phone", "address", "credit_card", "password", "ssn"]
        
        # 检查执行结果中是否包含敏感数据
        violations = []
        
        def check_dict_for_sensitive(data, path=""):
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
                    # 检查键名是否敏感
                    if any(sensitive in key.lower() for sensitive in sensitive_fields):
                        violations.append({
                            "field": current_path,
                            "reason": "包含敏感数据字段名"
                        })
                    # 递归检查值
                    check_dict_for_sensitive(value, current_path)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    check_dict_for_sensitive(item, f"{path}[{i}]")
            elif isinstance(data, str):
                # 简单检查字符串是否包含敏感模式
                import re
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
                
                if re.search(email_pattern, data):
                    violations.append({
                        "field": path,
                        "reason": "包含电子邮件地址"
                    })
                elif re.search(phone_pattern, data):
                    violations.append({
                        "field": path,
                        "reason": "包含电话号码"
                    })
        
        # 检查整个执行结果
        check_dict_for_sensitive(execution_result)
        
        return {
            "compliant": len(violations) == 0,
            "details": {
                "sensitive_fields_checked": sensitive_fields,
                "violations_found": len(violations),
                "violations": violations
            }
        }
    
    def _check_api_usage(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查API使用合规
        
        Args:
            execution_result: 执行结果
            
        Returns:
            API使用合规检查结果
        """
        # 检查API调用次数
        api_calls = execution_result.get("api_calls", 0)
        max_allowed_calls = 100  # 假设最大允许调用次数
        
        violations = []
        
        if api_calls > max_allowed_calls:
            violations.append({
                "type": "excessive_api_calls",
                "description": f"API调用次数过多: {api_calls}次",
                "threshold": max_allowed_calls
            })
        
        # 检查API响应时间
        execution_time = execution_result.get("execution_time", 0)
        max_allowed_time = 30  # 假设最大允许时间
        
        if execution_time > max_allowed_time:
            violations.append({
                "type": "slow_api_response",
                "description": f"API响应时间过长: {execution_time:.2f}秒",
                "threshold": max_allowed_time
            })
        
        # 检查错误率
        success = execution_result.get("success", True)
        if not success:
            violations.append({
                "type": "api_failure",
                "description": "API调用失败",
                "details": execution_result.get("error", "未知错误")
            })
        
        return {
            "compliant": len(violations) == 0,
            "details": {
                "api_calls": api_calls,
                "execution_time": execution_time,
                "success": success,
                "violations_found": len(violations),
                "violations": violations
            }
        }
    
    def _check_business_rules(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查业务规则合规
        
        Args:
            execution_result: 执行结果
            context: 上下文信息
            
        Returns:
            业务规则合规检查结果
        """
        business_rules = context.get("business_rules", {})
        violations = []
        
        # 检查价格规则
        if "min_price" in business_rules and "max_price" in business_rules:
            # 检查产品价格
            if "product_data" in execution_result:
                product_data = execution_result.get("product_data", {})
                price = product_data.get("price", 0)
                min_price = business_rules["min_price"]
                max_price = business_rules["max_price"]
                
                if price < min_price or price > max_price:
                    violations.append({
                        "type": "price_violation",
                        "description": f"产品价格{price}超出允许范围({min_price}-{max_price})"
                    })
        
        # 检查库存规则
        if "min_stock" in business_rules:
            # 检查库存数量
            if "inventory_updates" in execution_result:
                inventory_updates = execution_result.get("inventory_updates", [])
                min_stock = business_rules["min_stock"]
                
                for update in inventory_updates:
                    if update.get("new_quantity", 0) < min_stock:
                        violations.append({
                            "type": "low_stock",
                            "description": f"产品{update.get('product_id')}库存低于最小值{min_stock}"
                        })
        
        # 检查订单规则
        if "min_order_value" in business_rules:
            # 检查订单金额
            if "order_data" in execution_result:
                order_data = execution_result.get("order_data", {})
                total_price = order_data.get("total_price", 0)
                min_order_value = business_rules["min_order_value"]
                
                if total_price < min_order_value:
                    violations.append({
                        "type": "low_order_value",
                        "description": f"订单金额{total_price}低于最小值{min_order_value}"
                    })
        
        return {
            "compliant": len(violations) == 0,
            "details": {
                "business_rules_checked": list(business_rules.keys()),
                "violations_found": len(violations),
                "violations": violations
            }
        }
    
    def _check_security(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查安全合规
        
        Args:
            execution_result: 执行结果
            
        Returns:
            安全合规检查结果
        """
        violations = []
        
        # 检查是否包含敏感信息
        metadata = execution_result.get("metadata", {})
        
        # 检查API密钥或令牌
        sensitive_keys = ["api_key", "token", "secret", "password"]
        for key in sensitive_keys:
            if key in str(execution_result).lower():
                violations.append({
                    "type": "sensitive_info_exposure",
                    "description": f"可能包含敏感信息: {key}",
                    "severity": "high"
                })
        
        # 检查HTTPS使用
        if "api_config" in execution_result:
            api_config = execution_result.get("api_config", {})
            endpoint = api_config.get("endpoint", "")
            if endpoint.startswith("http://") and not endpoint.startswith("https://"):
                violations.append({
                    "type": "insecure_protocol",
                    "description": "使用不安全的HTTP协议",
                    "severity": "medium"
                })
        
        return {
            "compliant": len(violations) == 0,
            "details": {
                "security_checks_performed": ["sensitive_info", "protocol_security"],
                "violations_found": len(violations),
                "violations": violations
            }
        }
    
    def _assess_risk(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估风险
        
        Args:
            execution_result: 执行结果
            context: 上下文信息
            
        Returns:
            风险评估结果
        """
        import time
        
        risk_assessment = {
            "overall_risk_level": "low",
            "risk_factors": [],
            "mitigation_strategies": [],
            "recommendations": []
        }
        
        # 风险因素1: 执行失败风险
        if not execution_result.get("success", False):
            risk_assessment["risk_factors"].append({
                "factor": "execution_failure",
                "risk_level": "high",
                "description": "执行失败",
                "impact": "业务操作无法完成",
                "probability": "certain"
            })
            risk_assessment["mitigation_strategies"].append("实施重试机制和错误处理")
            risk_assessment["overall_risk_level"] = "high"
        
        # 风险因素2: 性能风险
        execution_time = execution_result.get("execution_time", 0)
        if execution_time > 10:  # 超过10秒
            risk_assessment["risk_factors"].append({
                "factor": "performance_degradation",
                "risk_level": "medium",
                "description": f"执行时间过长: {execution_time:.2f}秒",
                "impact": "用户体验下降，系统响应慢",
                "probability": "likely"
            })
            risk_assessment["mitigation_strategies"].append("优化API调用和缓存策略")
            if risk_assessment["overall_risk_level"] != "high":
                risk_assessment["overall_risk_level"] = "medium"
        
        # 风险因素3: 数据风险
        data_completeness = self._assess_data_completeness(execution_result)
        if data_completeness["score"] < 70:
            risk_assessment["risk_factors"].append({
                "factor": "data_incompleteness",
                "risk_level": "medium",
                "description": "数据不完整",
                "impact": "决策基于不完整信息",
                "probability": "possible"
            })
            risk_assessment["mitigation_strategies"].append("加强数据验证和完整性检查")
            if risk_assessment["overall_risk_level"] != "high":
                risk_assessment["overall_risk_level"] = "medium"
        
        # 风险因素4: 合规风险
        compliance_check = self._check_compliance(execution_result, context)
        if not compliance_check.get("overall_compliant", True):
            risk_assessment["risk_factors"].append({
                "factor": "compliance_violation",
                "risk_level": "high",
                "description": "合规性问题",
                "impact": "法律和监管风险",
                "probability": "possible"
            })
            risk_assessment["mitigation_strategies"].append("加强合规性检查和审计")
            risk_assessment["overall_risk_level"] = "high"
        
        # 风险因素5: 安全风险
        security_check = self._check_security(execution_result)
        if not security_check.get("compliant", True):
            risk_assessment["risk_factors"].append({
                "factor": "security_vulnerability",
                "risk_level": "critical",
                "description": "安全漏洞",
                "impact": "数据泄露和系统攻击",
                "probability": "unlikely"
            })
            risk_assessment["mitigation_strategies"].append("加强安全措施和监控")
            risk_assessment["overall_risk_level"] = "critical"
        
        # 生成总体建议
        if risk_assessment["overall_risk_level"] in ["high", "critical"]:
            risk_assessment["recommendations"].append("立即采取风险缓解措施")
        elif risk_assessment["overall_risk_level"] == "medium":
            risk_assessment["recommendations"].append("制定风险缓解计划")
        else:
            risk_assessment["recommendations"].append("继续监控风险状况")
        
        risk_assessment["timestamp"] = time.time()
        return risk_assessment
    
    def _evaluate_performance(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估性能
        
        Args:
            execution_result: 执行结果
            context: 上下文信息
            
        Returns:
            性能评估结果
        """
        import time
        
        performance_metrics = {
            "execution_time": execution_result.get("execution_time", 0),
            "api_calls": execution_result.get("api_calls", 0),
            "success_rate": 100 if execution_result.get("success", False) else 0,
            "data_volume": len(str(execution_result))  # 简单估算数据量
        }
        
        # 性能基准
        performance_benchmarks = context.get("performance_benchmarks", {
            "execution_time": {"good": 5, "acceptable": 10, "poor": 30},
            "api_calls": {"good": 1, "acceptable": 3, "poor": 10},
            "success_rate": {"good": 95, "acceptable": 90, "poor": 80}
        })
        
        # 评估每个指标
        evaluations = {}
        
        # 执行时间评估
        exec_time = performance_metrics["execution_time"]
        time_bench = performance_benchmarks["execution_time"]
        if exec_time <= time_bench["good"]:
            time_eval = "good"
        elif exec_time <= time_bench["acceptable"]:
            time_eval = "acceptable"
        else:
            time_eval = "poor"
        
        evaluations["execution_time"] = {
            "value": exec_time,
            "evaluation": time_eval,
            "benchmark": time_bench
        }
        
        # API调用次数评估
        api_calls = performance_metrics["api_calls"]
        calls_bench = performance_benchmarks["api_calls"]
        if api_calls <= calls_bench["good"]:
            calls_eval = "good"
        elif api_calls <= calls_bench["acceptable"]:
            calls_eval = "acceptable"
        else:
            calls_eval = "poor"
        
        evaluations["api_calls"] = {
            "value": api_calls,
            "evaluation": calls_eval,
            "benchmark": calls_bench
        }
        
        # 成功率评估
        success_rate = performance_metrics["success_rate"]
        success_bench = performance_benchmarks["success_rate"]
        if success_rate >= success_bench["good"]:
            success_eval = "good"
        elif success_rate >= success_bench["acceptable"]:
            success_eval = "acceptable"
        else:
            success_eval = "poor"
        
        evaluations["success_rate"] = {
            "value": success_rate,
            "evaluation": success_eval,
            "benchmark": success_bench
        }
        
        # 计算总体性能得分
        eval_scores = {"good": 100, "acceptable": 70, "poor": 30}
        dimension_scores = [eval_scores[eval["evaluation"]] for eval in evaluations.values()]
        overall_score = sum(dimension_scores) / len(dimension_scores) if dimension_scores else 0
        
        # 性能改进建议
        recommendations = []
        if evaluations["execution_time"]["evaluation"] == "poor":
            recommendations.append("优化执行时间，考虑异步处理或缓存")
        if evaluations["api_calls"]["evaluation"] == "poor":
            recommendations.append("减少API调用次数，使用批量操作")
        if evaluations["success_rate"]["evaluation"] == "poor":
            recommendations.append("提高成功率，加强错误处理和重试机制")
        
        return {
            "performance_metrics": performance_metrics,
            "evaluations": evaluations,
            "overall_score": overall_score,
            "overall_evaluation": "good" if overall_score >= 80 else "acceptable" if overall_score >= 60 else "poor",
            "recommendations": recommendations,
            "timestamp": time.time()
        }
    
    def _general_evaluation(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        通用评估
        
        Args:
            execution_result: 执行结果
            context: 上下文信息
            
        Returns:
            通用评估结果
        """
        import time
        
        # 执行基本评估
        evaluation = {
            "execution_successful": execution_result.get("success", False),
            "has_errors": "error" in execution_result or "error_message" in execution_result,
            "execution_time": execution_result.get("execution_time", 0),
            "api_calls": execution_result.get("api_calls", 0),
            "data_returned": bool(execution_result.get("data") or execution_result.get("response")),
            "metadata_present": "metadata" in execution_result,
            "timestamp": execution_result.get("timestamp") or time.time()
        }
        
        # 生成简单评分
        score = 0
        if evaluation["execution_successful"]:
            score += 40
        if not evaluation["has_errors"]:
            score += 30
        if evaluation["data_returned"]:
            score += 20
        if evaluation["metadata_present"]:
            score += 10
        
        evaluation["overall_score"] = score
        
        # 生成基本建议
        recommendations = []
        if not evaluation["execution_successful"]:
            recommendations.append("修复执行错误")
        if evaluation["has_errors"]:
            recommendations.append("改进错误处理")
        if not evaluation["data_returned"]:
            recommendations.append("确保返回有效数据")
        if not evaluation["metadata_present"]:
            recommendations.append("添加执行元数据")
        
        evaluation["recommendations"] = recommendations
        
        return evaluation
