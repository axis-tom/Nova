"""
增强版Judge Agent
添加ROI/转化评分和优化决策功能
"""

from typing import Dict, Any, List, Optional
from backend.common.core.state import State
from backend.business.ecommerce.base import BaseEcommerceAgent
import time
import json


class JudgeEnhancedAgent(BaseEcommerceAgent):
    """
    增强版Judge Agent - 电商结果评估Agent
    
    新增功能：
    1. ROI评分计算
    2. 转化率评估
    3. 优化决策建议
    4. 是否继续优化判断
    """
    
    def __init__(self):
        """初始化增强版Judge Agent"""
        super().__init__(
            name="ecommerce_judge_enhanced",
            description="增强版电商结果评估Agent，负责ROI/转化评分和优化决策"
        )
    
    def run(self, state: State) -> State:
        """
        执行增强版Judge Agent逻辑
        
        Args:
            state: 输入状态
            
        Returns:
            输出状态
        """
        # 记录开始事件
        state = self.log_event(state, "start", "开始执行增强版结果评估")
        
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
            
            if task_type == "roi_assessment":
                result = self._assess_roi(execution_result, context)
            elif task_type == "conversion_analysis":
                result = self._analyze_conversion(execution_result, context)
            elif task_type == "optimization_decision":
                result = self._make_optimization_decision(execution_result, context)
            elif task_type == "business_impact":
                result = self._evaluate_business_impact(execution_result, context)
            else:
                # 默认执行综合评估
                result = self._comprehensive_evaluation(execution_result, context)
            
            # 更新状态
            state["evaluation_result"] = result
            state["judge_executed"] = True
            
            # 记录成功事件
            state = self.log_event(state, "success", f"成功完成{task_type}评估")
            state = self.add_execution_record(state, True, {
                "task_type": task_type,
                "overall_score": result.get("overall_score", 0),
                "roi_score": result.get("roi_score", 0),
                "conversion_score": result.get("conversion_score", 0),
                "optimization_decision": result.get("optimization_decision", "unknown")
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
        return [
            "evaluation_result", 
            "judge_executed", 
            "judge_error",
            "roi_score",
            "conversion_score",
            "optimization_decision"
        ]
    
    def _assess_roi(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估ROI（投资回报率）
        
        Args:
            execution_result: 执行结果
            context: 上下文信息
            
        Returns:
            ROI评估结果
        """
        import time
        
        # 提取业务数据
        business_data = context.get("business_data", {})
        
        # 计算成本
        execution_cost = self._calculate_execution_cost(execution_result, business_data)
        
        # 计算收益
        revenue_impact = self._estimate_revenue_impact(execution_result, business_data)
        
        # 计算ROI
        roi_score = 0
        if execution_cost > 0:
            roi_score = (revenue_impact - execution_cost) / execution_cost * 100
        
        # ROI评估
        roi_assessment = {
            "roi_score": roi_score,
            "execution_cost": execution_cost,
            "revenue_impact": revenue_impact,
            "net_profit": revenue_impact - execution_cost,
            "break_even_point": self._calculate_break_even_point(execution_cost, revenue_impact),
            "roi_category": self._categorize_roi(roi_score),
            "recommendations": self._generate_roi_recommendations(roi_score, execution_cost, revenue_impact),
            "timestamp": time.time()
        }
        
        return roi_assessment
    
    def _calculate_execution_cost(self, execution_result: Dict[str, Any], business_data: Dict[str, Any]) -> float:
        """
        计算执行成本
        
        Args:
            execution_result: 执行结果
            business_data: 业务数据
            
        Returns:
            执行成本
        """
        # API调用成本
        api_calls = execution_result.get("api_calls", 0)
        api_cost_per_call = business_data.get("api_cost_per_call", 0.01)
        api_cost = api_calls * api_cost_per_call
        
        # 时间成本
        execution_time = execution_result.get("execution_time", 0)
        hourly_rate = business_data.get("hourly_rate", 50)
        time_cost = (execution_time / 3600) * hourly_rate
        
        # 基础设施成本
        infrastructure_cost = business_data.get("infrastructure_cost", 0.1)
        
        # 总成本
        total_cost = api_cost + time_cost + infrastructure_cost
        
        return total_cost
    
    def _estimate_revenue_impact(self, execution_result: Dict[str, Any], business_data: Dict[str, Any]) -> float:
        """
        预估收益影响
        
        Args:
            execution_result: 执行结果
            business_data: 业务数据
            
        Returns:
            预估收益
        """
        # 提取执行结果中的业务指标
        execution_data = execution_result.get("data", {})
        
        # 价格调整收益
        price_impact = 0
        if "price_adjustment" in execution_data:
            price_change = execution_data["price_adjustment"].get("change_percentage", 0)
            base_price = business_data.get("base_price", 100)
            quantity = business_data.get("estimated_quantity", 100)
            price_impact = base_price * (price_change / 100) * quantity
        
        # 库存优化收益
        inventory_impact = 0
        if "inventory_optimization" in execution_data:
            stockout_reduction = execution_data["inventory_optimization"].get("stockout_reduction", 0)
            lost_sale_value = business_data.get("lost_sale_value", 50)
            inventory_impact = stockout_reduction * lost_sale_value
        
        # 营销活动收益
        marketing_impact = 0
        if "marketing_campaign" in execution_data:
            conversion_lift = execution_data["marketing_campaign"].get("conversion_lift", 0)
            base_conversion = business_data.get("base_conversion_rate", 0.02)
            visitors = business_data.get("estimated_visitors", 1000)
            average_order_value = business_data.get("average_order_value", 100)
            marketing_impact = visitors * (base_conversion * (1 + conversion_lift)) * average_order_value
        
        # 总收益
        total_revenue = price_impact + inventory_impact + marketing_impact
        
        return total_revenue
    
    def _calculate_break_even_point(self, cost: float, revenue_per_period: float) -> Dict[str, Any]:
        """
        计算盈亏平衡点
        
        Args:
            cost: 成本
            revenue_per_period: 每期收益
            
        Returns:
            盈亏平衡点信息
        """
        if revenue_per_period <= 0:
            return {
                "break_even_periods": float('inf'),
                "break_even_time": "无法达到",
                "feasible": False
            }
        
        break_even_periods = cost / revenue_per_period
        
        return {
            "break_even_periods": break_even_periods,
            "break_even_time": f"{break_even_periods:.1f}个周期",
            "feasible": break_even_periods <= 12  # 假设12个周期内达到为可行
        }
    
    def _categorize_roi(self, roi_score: float) -> str:
        """
        分类ROI
        
        Args:
            roi_score: ROI评分
            
        Returns:
            ROI分类
        """
        if roi_score >= 100:
            return "excellent"
        elif roi_score >= 50:
            return "good"
        elif roi_score >= 20:
            return "acceptable"
        elif roi_score >= 0:
            return "marginal"
        else:
            return "negative"
    
    def _generate_roi_recommendations(self, roi_score: float, cost: float, revenue: float) -> List[str]:
        """
        生成ROI建议
        
        Args:
            roi_score: ROI评分
            cost: 成本
            revenue: 收益
            
        Returns:
            建议列表
        """
        recommendations = []
        
        if roi_score < 0:
            recommendations.append("立即停止执行，ROI为负")
            recommendations.append("重新评估执行策略")
            recommendations.append("考虑降低执行成本")
        elif roi_score < 20:
            recommendations.append("ROI较低，需要优化")
            recommendations.append("尝试降低执行成本")
            recommendations.append("探索提高收益的方法")
        elif roi_score < 50:
            recommendations.append("ROI可接受，但有改进空间")
            recommendations.append("优化执行效率")
            recommendations.append("监控实际业务影响")
        elif roi_score < 100:
            recommendations.append("ROI良好，继续执行")
            recommendations.append("考虑扩大执行规模")
            recommendations.append("定期评估ROI变化")
        else:
            recommendations.append("ROI优秀，强烈推荐继续")
            recommendations.append("考虑自动化执行")
            recommendations.append("扩展到其他业务领域")
        
        return recommendations
    
    def _analyze_conversion(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析转化率
        
        Args:
            execution_result: 执行结果
            context: 上下文信息
            
        Returns:
            转化分析结果
        """
        import time
        
        # 提取转化数据
        conversion_data = execution_result.get("conversion_data", {})
        business_data = context.get("business_data", {})
        
        # 基础转化率
        base_conversion_rate = business_data.get("base_conversion_rate", 0.02)
        
        # 计算转化提升
        conversion_lift = conversion_data.get("conversion_lift", 0)
        new_conversion_rate = base_conversion_rate * (1 + conversion_lift)
        
        # 计算转化评分
        conversion_score = self._calculate_conversion_score(
            base_conversion_rate, 
            new_conversion_rate, 
            conversion_lift
        )
        
        # 业务影响分析
        visitors = business_data.get("estimated_visitors", 1000)
        average_order_value = business_data.get("average_order_value", 100)
        
        additional_conversions = visitors * (new_conversion_rate - base_conversion_rate)
        additional_revenue = additional_conversions * average_order_value
        
        conversion_analysis = {
            "conversion_score": conversion_score,
            "base_conversion_rate": base_conversion_rate,
            "new_conversion_rate": new_conversion_rate,
            "conversion_lift": conversion_lift,
            "additional_conversions": additional_conversions,
            "additional_revenue": additional_revenue,
            "conversion_category": self._categorize_conversion(conversion_lift),
            "recommendations": self._generate_conversion_recommendations(conversion_lift, new_conversion_rate),
            "timestamp": time.time()
        }
        
        return conversion_analysis
    
    def _calculate_conversion_score(self, base_rate: float, new_rate: float, lift: float) -> float:
        """
        计算转化评分
        
        Args:
            base_rate: 基础转化率
            new_rate: 新转化率
            lift: 提升比例
            
        Returns:
            转化评分
        """
        # 基础评分
        score = 50
        
        # 提升比例加分
        if lift > 0:
            score += min(lift * 100, 30)  # 最多加30分
        
        # 绝对转化率加分
        if new_rate >= 0.05:  # 5%以上
            score += 10
        elif new_rate >= 0.03:  # 3%以上
            score += 5
        
        # 确保评分在0-100之间
        return max(0, min(100, score))
    
    def _categorize_conversion(self, conversion_lift: float) -> str:
        """
        分类转化提升
        
        Args:
            conversion_lift: 转化提升比例
            
        Returns:
            转化分类
        """
        if conversion_lift >= 0.5:
            return "exceptional"
        elif conversion_lift >= 0.2:
            return "excellent"
        elif conversion_lift >= 0.1:
            return "good"
        elif conversion_lift >= 0.05:
            return "moderate"
        elif conversion_lift >= 0:
            return "slight"
        else:
            return "negative"
    
    def _generate_conversion_recommendations(self, conversion_lift: float, new_rate: float) -> List[str]:
        """
        生成转化建议
        
        Args:
            conversion_lift: 转化提升比例
            new_rate: 新转化率
            
        Returns:
            建议列表
        """
        recommendations = []
        
        if conversion_lift < 0:
            recommendations.append("转化率下降，需要立即调查原因")
            recommendations.append("恢复原有策略或测试新方法")
            recommendations.append("检查执行过程中的问题")
        elif conversion_lift < 0.05:
            recommendations.append("转化提升不明显，需要优化")
            recommendations.append("A/B测试不同策略")
            recommendations.append("分析用户行为数据")
        elif conversion_lift < 0.1:
            recommendations.append("转化有提升，继续优化")
            recommendations.append("扩大测试范围")
            recommendations.append("监控长期效果")
        elif conversion_lift < 0.2:
            recommendations.append("转化提升显著，效果良好")
            recommendations.append("考虑全面推广")
            recommendations.append("持续监控和优化")
        else:
            recommendations.append("转化提升非常显著，优秀表现")
            recommendations.append("立即全面推广")
            recommendations.append("作为最佳实践记录")
        
        # 基于绝对转化率的建议
        if new_rate < 0.02:
            recommendations.append("整体转化率偏低，需要系统性优化")
        elif new_rate < 0.05:
            recommendations.append("转化率处于行业平均水平，有提升空间")
        else:
            recommendations.append("转化率优秀，保持并寻求进一步优化")
        
        return recommendations
    
    def _make_optimization_decision(self, execution_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        做出优化决策
        
        Args:
            execution_result: 执行结果
            context: 上下文信息
            
        Returns:
            优化决策结果
        """
        import time
        
        # 提取评估数据
        evaluation_data = execution_result.get("evaluation_data", {})
        
        # 计算优化评分
        optimization_score = self._calculate_optimization_score(evaluation_data)
        
        # 做出决策
        decision = self._determine_optimization_action(optimization_score, evaluation_data)
        
        # 生成优化建议
        optimization_suggestions = self._generate_optimization_suggestions(decision, evaluation_data)
        
        optimization_decision = {
            "optimization_score": optimization_score,
            "optimization_decision": decision["action"],
            "decision_reason": decision["reason"],
            "confidence_level": decision["confidence"],
            "next_steps": decision["next_steps"],
            "optimization_suggestions": optimization_suggestions,
            "estimated_improvement": self._estimate_improvement_potential(evaluation_data),
            "risk_assessment": self._assess_optimization_risk(evaluation_data),
            "timestamp": time.time()
        }
        
        return optimization_decision
    
    def _calculate_optimization_score(self, evaluation_data: Dict[str, Any]) -> float:
        """
        计算优化评分
        
        Args:
            evaluation_data: 评估数据
            
        Returns:
            优化评分
        """
        score = 50  # 基础分
        
        # ROI贡献
        roi_score = evaluation_data.get("roi_score", 0)
        if roi_score > 0:
            score += min(roi_score / 10, 20)  # 最多加20分
        
        # 转化贡献
        conversion_lift = evaluation_data.get("conversion_lift", 0)
        if conversion_lift > 0:
            score += min(conversion_lift * 100, 15)  # 最多加15分
        
        # 执行效率贡献
        execution_time = evaluation_data.get("execution_time", 0)
        if execution_time < 5:  # 5秒以内
            score += 10
        elif execution_time < 10:  # 10秒以内
            score += 5
        
        # 成功率贡献
        success_rate = evaluation_data.get("success_rate", 0)
        if success_rate >= 90:
            score += 10
        elif success_rate >= 80:
            score += 5
        
        # 确保评分在0-100之间
        return max(0, min(100, score))
