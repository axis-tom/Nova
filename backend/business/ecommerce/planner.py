"""
Planner Agent - 任务拆解Agent
负责将高层业务目标拆解为可执行任务
"""

from typing import Dict, Any, List
from backend.foundation.cognition.state_machine.state_machine import State
from backend.business.ecommerce.base import BaseEcommerceAgent


class PlannerAgent(BaseEcommerceAgent):
    """
    Planner Agent - 任务拆解Agent
    
    职责：
    1. 将高层业务目标拆解为可执行任务
    2. 确定任务执行顺序和依赖关系
    3. 分配资源和优先级
    4. 生成任务执行计划
    """
    
    def __init__(self):
        """初始化Planner Agent"""
        super().__init__(
            name="ecommerce_planner",
            description="电商任务拆解Agent，负责将业务目标拆解为可执行任务"
        )
    
    def run(self, state: State) -> State:
        """
        执行Planner Agent逻辑
        
        Args:
            state: 输入状态
            
        Returns:
            输出状态
        """
        # 记录开始事件
        state = self.log_event(state, "start", "开始执行任务拆解")
        
        try:
            # 验证输入
            if not self.validate_input(state):
                state = self.log_event(state, "error", "输入验证失败")
                state["planner_error"] = "输入数据不完整"
                state = self.add_execution_record(state, False, {"error": "输入验证失败"})
                return state
            
            # 提取业务目标
            business_goal = state.get("business_goal", {})
            constraints = state.get("constraints", {})
            context = state.get("context", {})
            
            # 生成任务计划
            plan = self._generate_plan(business_goal, constraints, context)
            
            # 更新状态
            state["task_plan"] = plan
            state["planner_executed"] = True
            
            # 记录成功事件
            state = self.log_event(state, "success", f"成功生成任务计划，包含{len(plan.get('tasks', []))}个任务")
            state = self.add_execution_record(state, True, {
                "task_count": len(plan.get("tasks", [])),
                "plan_id": plan.get("plan_id")
            })
            
        except Exception as e:
            # 记录错误事件
            state = self.log_event(state, "error", f"任务拆解失败: {str(e)}")
            state["planner_error"] = str(e)
            state["planner_executed"] = False
            state = self.add_execution_record(state, False, {"error": str(e)})
        
        return state
    
    def get_required_fields(self) -> list:
        """
        获取必需的输入字段
        
        Returns:
            必需字段列表
        """
        return ["business_goal"]
    
    def get_output_fields(self) -> list:
        """
        获取输出的字段
        
        Returns:
            输出字段列表
        """
        return ["task_plan", "planner_executed", "planner_error"]
    
    def _generate_plan(self, business_goal: Dict[str, Any], constraints: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成任务计划
        
        Args:
            business_goal: 业务目标
            constraints: 约束条件
            context: 上下文信息
            
        Returns:
            任务计划
        """
        import uuid
        import time
        
        plan_id = f"plan_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # 根据业务目标类型生成不同的任务计划
        goal_type = business_goal.get("type", "unknown")
        
        if goal_type == "product_launch":
            plan = self._generate_product_launch_plan(business_goal, constraints, context)
        elif goal_type == "marketing_campaign":
            plan = self._generate_marketing_campaign_plan(business_goal, constraints, context)
        elif goal_type == "inventory_optimization":
            plan = self._generate_inventory_optimization_plan(business_goal, constraints, context)
        elif goal_type == "customer_retention":
            plan = self._generate_customer_retention_plan(business_goal, constraints, context)
        else:
            plan = self._generate_general_plan(business_goal, constraints, context)
        
        # 添加计划元数据
        plan["plan_id"] = plan_id
        plan["created_at"] = time.time()
        plan["goal_type"] = goal_type
        plan["constraints"] = constraints
        plan["context"] = context
        
        return plan
    
    def _generate_product_launch_plan(self, goal: Dict[str, Any], constraints: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成产品发布任务计划
        
        Args:
            goal: 业务目标
            constraints: 约束条件
            context: 上下文信息
            
        Returns:
            任务计划
        """
        product_name = goal.get("product_name", "新产品")
        launch_date = goal.get("launch_date", "尽快")
        target_audience = goal.get("target_audience", "所有用户")
        
        tasks = [
            {
                "task_id": "task_1",
                "name": "市场调研",
                "description": f"调研{product_name}的目标市场和竞争对手",
                "agent": "ecommerce_analyst",
                "dependencies": [],
                "estimated_duration": "2天",
                "priority": "high",
                "resources": ["market_data", "competitor_info"],
                "outputs": ["market_analysis_report"]
            },
            {
                "task_id": "task_2",
                "name": "产品页面设计",
                "description": f"设计{product_name}的产品页面",
                "agent": "ecommerce_executor",
                "dependencies": ["task_1"],
                "estimated_duration": "3天",
                "priority": "high",
                "resources": ["product_images", "product_description"],
                "outputs": ["product_page_design"]
            },
            {
                "task_id": "task_3",
                "name": "定价策略制定",
                "description": f"制定{product_name}的定价策略",
                "agent": "ecommerce_analyst",
                "dependencies": ["task_1"],
                "estimated_duration": "1天",
                "priority": "medium",
                "resources": ["cost_data", "market_prices"],
                "outputs": ["pricing_strategy"]
            },
            {
                "task_id": "task_4",
                "name": "营销材料准备",
                "description": f"准备{product_name}的营销材料",
                "agent": "ecommerce_executor",
                "dependencies": ["task_2", "task_3"],
                "estimated_duration": "2天",
                "priority": "medium",
                "resources": ["product_images", "pricing_strategy"],
                "outputs": ["marketing_materials"]
            },
            {
                "task_id": "task_5",
                "name": "发布前测试",
                "description": f"测试{product_name}的发布流程",
                "agent": "ecommerce_judge",
                "dependencies": ["task_2", "task_4"],
                "estimated_duration": "1天",
                "priority": "high",
                "resources": ["product_page_design", "marketing_materials"],
                "outputs": ["test_report", "launch_approval"]
            },
            {
                "task_id": "task_6",
                "name": "正式发布",
                "description": f"正式发布{product_name}",
                "agent": "ecommerce_executor",
                "dependencies": ["task_5"],
                "estimated_duration": "1天",
                "priority": "critical",
                "resources": ["launch_approval", "all_previous_outputs"],
                "outputs": ["product_live", "launch_complete"]
            }
        ]
        
        return {
            "goal": f"发布新产品: {product_name}",
            "tasks": tasks,
            "timeline": {
                "start": "立即开始",
                "end": launch_date,
                "total_duration": "10天"
            },
            "success_criteria": [
                f"{product_name}成功上线",
                "产品页面访问量达到目标",
                "首周销售额达到目标"
            ]
        }
    
    def _generate_marketing_campaign_plan(self, goal: Dict[str, Any], constraints: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成营销活动任务计划
        
        Args:
            goal: 业务目标
            constraints: 约束条件
            context: 上下文信息
            
        Returns:
            任务计划
        """
        campaign_name = goal.get("campaign_name", "营销活动")
        budget = goal.get("budget", 10000)
        target_channels = goal.get("channels", ["email", "social_media"])
        
        tasks = [
            {
                "task_id": "task_1",
                "name": "目标受众分析",
                "description": f"分析{campaign_name}的目标受众",
                "agent": "ecommerce_analyst",
                "dependencies": [],
                "estimated_duration": "1天",
                "priority": "high",
                "resources": ["customer_data", "historical_campaigns"],
                "outputs": ["audience_analysis"]
            },
            {
                "task_id": "task_2",
                "name": "渠道策略制定",
                "description": f"制定{campaign_name}的渠道策略",
                "agent": "ecommerce_analyst",
                "dependencies": ["task_1"],
                "estimated_duration": "1天",
                "priority": "high",
                "resources": ["audience_analysis", "channel_performance"],
                "outputs": ["channel_strategy"]
            },
            {
                "task_id": "task_3",
                "name": "创意内容制作",
                "description": f"制作{campaign_name}的创意内容",
                "agent": "ecommerce_executor",
                "dependencies": ["task_2"],
                "estimated_duration": "3天",
                "priority": "medium",
                "resources": ["brand_guidelines", "channel_strategy"],
                "outputs": ["creative_content"]
            },
            {
                "task_id": "task_4",
                "name": "预算分配",
                "description": f"分配{campaign_name}的预算",
                "agent": "ecommerce_analyst",
                "dependencies": ["task_2"],
                "estimated_duration": "1天",
                "priority": "medium",
                "resources": ["budget_constraints", "channel_strategy"],
                "outputs": ["budget_allocation"]
            },
            {
                "task_id": "task_5",
                "name": "活动执行",
                "description": f"执行{campaign_name}",
                "agent": "ecommerce_executor",
                "dependencies": ["task_3", "task_4"],
                "estimated_duration": "7天",
                "priority": "critical",
                "resources": ["creative_content", "budget_allocation"],
                "outputs": ["campaign_live", "performance_data"]
            },
            {
                "task_id": "task_6",
                "name": "效果评估",
                "description": f"评估{campaign_name}的效果",
                "agent": "ecommerce_judge",
                "dependencies": ["task_5"],
                "estimated_duration": "2天",
                "priority": "medium",
                "resources": ["performance_data", "campaign_goals"],
                "outputs": ["campaign_report", "roi_analysis"]
            }
        ]
        
        return {
            "goal": f"执行营销活动: {campaign_name}",
            "tasks": tasks,
            "timeline": {
                "start": "立即开始",
                "end": "活动结束后2天",
                "total_duration": "15天"
            },
            "success_criteria": [
                f"活动ROI达到{goal.get('target_roi', 3)}倍",
                f"覆盖{goal.get('target_reach', 10000)}名用户",
                f"转化率达到{goal.get('target_conversion', 5)}%"
            ]
        }
    
    def _generate_inventory_optimization_plan(self, goal: Dict[str, Any], constraints: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成库存优化任务计划
        
        Args:
            goal: 业务目标
            constraints: 约束条件
            context: 上下文信息
            
        Returns:
            任务计划
        """
        optimization_target = goal.get("target", "库存周转率")
        current_level = goal.get("current_level", "未知")
        target_level = goal.get("target_level", "提升20%")
        
        tasks = [
            {
                "task_id": "task_1",
                "name": "库存数据分析",
                "description": f"分析当前库存数据",
                "agent": "ecommerce_analyst",
                "dependencies": [],
                "estimated_duration": "2天",
                "priority": "high",
                "resources": ["inventory_data", "sales_data"],
                "outputs": ["inventory_analysis"]
            },
            {
                "task_id": "task_2",
                "name": "需求预测",
                "description": f"预测未来产品需求",
                "agent": "ecommerce_analyst",
                "dependencies": ["task_1"],
                "estimated_duration": "2天",
                "priority": "high",
                "resources": ["historical_sales", "market_trends"],
                "outputs": ["demand_forecast"]
            },
            {
                "task_id": "task_3",
                "name": "优化策略制定",
                "description": f"制定库存优化策略",
                "agent": "ecommerce_analyst",
                "dependencies": ["task_1", "task_2"],
                "estimated_duration": "2天",
                "priority": "medium",
                "resources": ["inventory_analysis", "demand_forecast"],
                "outputs": ["optimization_strategy"]
            },
            {
                "task_id": "task_4",
                "name": "采购计划调整",
                "description": f"调整采购计划",
                "agent": "ecommerce_executor",
                "dependencies": ["task_3"],
                "estimated_duration": "1天",
                "priority": "medium",
                "resources": ["optimization_strategy", "supplier_info"],
                "outputs": ["updated_purchase_plan"]
            },
            {
                "task_id": "task_5",
                "name": "库存调整执行",
                "description": f"执行库存调整",
                "agent": "ecommerce_executor",
                "dependencies": ["task_4"],
                "estimated_duration": "3天",
                "priority": "high",
                "resources": ["updated_purchase_plan", "warehouse_capacity"],
                "outputs": ["inventory_adjusted"]
            },
            {
                "task_id": "task_6",
                "name": "效果监控",
                "description": f"监控优化效果",
                "agent": "ecommerce_judge",
                "dependencies": ["task_5"],
                "estimated_duration": "7天",
                "priority": "low",
                "resources": ["inventory_adjusted", "sales_data"],
                "outputs": ["optimization_report", "kpi_tracking"]
            }
        ]
        
        return {
            "goal": f"优化库存: {optimization_target}从{current_level}提升到{target_level}",
            "tasks": tasks,
            "timeline": {
                "start": "立即开始",
                "end": "调整后7天",
                "total_duration": "17天"
            },
            "success_criteria": [
                f"库存周转率提升{target_level}",
                "缺货率降低50%",
                "库存成本降低15%"
            ]
        }
    
    def _generate_customer_retention_plan(self, goal: Dict[str, Any], constraints: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成客户留存任务计划
        
        Args:
            goal: 业务目标
            constraints: 约束条件
            context: 上下文信息
            
        Returns:
            任务计划
        """
        retention_target = goal.get("target", "客户留存率")
        current_rate = goal.get("current_rate", "未知")
        target_rate = goal.get("target_rate", "提升10%")
        
        tasks = [
            {
                "task_id": "task_1",
                "name": "客户流失分析",
                "description": "分析客户流失原因",
                "agent": "ecommerce_analyst",
                "dependencies": [],
                "estimated_duration": "3天",
                "priority": "high",
                "resources": ["customer_data", "churn_data"],
                "outputs": ["churn_analysis"]
            },
            {
                "task_id": "task_2",
                "name": "留存策略研究",
                "description": "研究客户留存策略",
                "agent": "ecommerce_analyst",
                "dependencies": ["task_1"],
                "estimated_duration": "2天",
                "priority": "high",
                "resources": ["industry_best_practices", "churn_analysis"],
                "outputs": ["retention_strategies"]
            },
            {
                "task_id": "task_3",
                "name": "个性化方案设计",
                "description": "设计个性化留存方案",
                "agent": "ecommerce_analyst",
                "dependencies": ["task_2"],
                "estimated_duration": "3天",
                "priority": "medium",
                "resources": ["retention_strategies", "customer_segments"],
                "outputs": ["personalized_plans"]
            },
            {
                "task_id": "task_4",
                "name": "留存活动执行",
                "description": "执行客户留存活动",
                "agent": "ecommerce_executor",
                "dependencies": ["task_3"],
                "estimated_duration": "5天",
                "priority": "high",
                "resources": ["personalized_plans", "customer_segments"],
                "outputs": ["retention_campaign_live"]
            },
            {
                "task_id": "task_5",
                "name": "效果跟踪",
                "description": "跟踪留存活动效果",
                "agent": "ecommerce_judge",
                "dependencies": ["task_4"],
                "estimated_duration": "7天",
                "priority": "medium",
                "resources": ["retention_campaign_live", "customer_behavior"],
                "outputs": ["retention_report", "effectiveness_analysis"]
            },
            {
                "task_id": "task_6",
                "name": "策略优化",
                "description": "优化留存策略",
                "agent": "ecommerce_analyst",
                "dependencies": ["task_5"],
                "estimated_duration": "2天",
                "priority": "low",
                "resources": ["retention_report", "effectiveness_analysis"],
                "outputs": ["optimized_retention_strategy"]
            }
        ]
        
        return {
            "goal": f"提升客户留存率: 从{current_rate}提升到{target_rate}",
            "tasks": tasks,
            "timeline": {
                "start": "立即开始",
                "end": "活动后7天",
                "total_duration": "22天"
            },
            "success_criteria": [
                f"客户留存率提升{target_rate}",
                "客户满意度提升15%",
                "复购率提升20%"
            ]
        }
    
    def _generate_general_plan(self, goal: Dict[str, Any], constraints: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成通用任务计划
        
        Args:
            goal: 业务目标
            constraints: 约束条件
            context: 上下文信息
            
        Returns:
            任务计划
        """
        goal_description = goal.get("description", "未指定目标")
        
        tasks = [
            {
                "task_id": "task_1",
                "name": "需求分析",
                "description": f"分析{goal_description}的需求",
                "agent": "ecommerce_analyst",
                "dependencies": [],
                "estimated_duration": "2天",
                "priority": "high",
                "resources": ["business_context", "requirements"],
                "outputs": ["requirements_analysis"]
            },
            {
                "task_id": "task_2",
                "name": "方案设计",
                "description": f"设计{goal_description}的解决方案",
                "agent": "ecommerce_analyst",
                "dependencies": ["task_1"],
                "estimated_duration": "3天",
                "priority": "high",
                "resources": ["requirements_analysis", "best_practices"],
                "outputs": ["solution_design"]
            },
            {
                "task_id": "task_3",
                "name": "方案评估",
                "description": f"评估{goal_description}的解决方案",
                "agent": "ecommerce_judge",
                "dependencies": ["task_2"],
                "estimated_duration": "2天",
                "priority": "medium",
                "resources": ["solution_design", "evaluation_criteria"],
                "outputs": ["evaluation_report", "approval"]
            },
            {
                "task_id": "task_4",
                "name": "方案执行",
                "description": f"执行{goal_description}的解决方案",
                "agent": "ecommerce_executor",
                "dependencies": ["task_3"],
                "estimated_duration": "5天",
                "priority": "critical",
                "resources": ["approval", "solution_design"],
                "outputs": ["solution_implemented"]
            },
            {
                "task_id": "task_5",
                "name": "效果验证",
                "description": f"验证{goal_description}的效果",
                "agent": "ecommerce_judge",
                "dependencies": ["task_4"],
                "estimated_duration": "3天",
                "priority": "medium",
                "resources": ["solution_implemented", "success_metrics"],
                "outputs": ["verification_report", "success_confirmation"]
            }
        ]
        
        return {
            "goal": goal_description,
            "tasks": tasks,
            "timeline": {
                "start": "立即开始",
                "end": "执行后3天",
                "total_duration": "15天"
            },
            "success_criteria": [
                "目标达成",
                "解决方案有效",
                "用户满意度高"
            ]
        }
