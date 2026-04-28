"""
Analyst Agent - 数据分析Agent
负责分析数据、生成洞察、评估风险
"""

from typing import Dict, Any, List
from backend.core.state import State
from backend.agents.ecommerce.base import BaseEcommerceAgent


class AnalystAgent(BaseEcommerceAgent):
    """
    Analyst Agent - 数据分析Agent
    
    职责：
    1. 分析原始数据，提取有价值的信息
    2. 生成业务洞察和趋势分析
    3. 评估业务风险和机会
    4. 提供数据驱动的决策建议
    """
    
    def __init__(self):
        """初始化Analyst Agent"""
        super().__init__(
            name="ecommerce_analyst",
            description="电商数据分析Agent，负责分析数据、生成洞察、评估风险"
        )
    
    def run(self, state: State) -> State:
        """
        执行Analyst Agent逻辑
        
        Args:
            state: 输入状态
            
        Returns:
            输出状态
        """
        # 记录开始事件
        state = self.log_event(state, "start", "开始执行数据分析")
        
        try:
            # 验证输入
            if not self.validate_input(state):
                state = self.log_event(state, "error", "输入验证失败")
                state["analyst_error"] = "输入数据不完整"
                state = self.add_execution_record(state, False, {"error": "输入验证失败"})
                return state
            
            # 提取分析任务
            analysis_task = state.get("analysis_task", {})
            data = state.get("data", {})
            context = state.get("context", {})
            
            # 根据任务类型执行分析
            task_type = analysis_task.get("type", "unknown")
            
            if task_type == "market_analysis":
                result = self._perform_market_analysis(data, context)
            elif task_type == "customer_analysis":
                result = self._perform_customer_analysis(data, context)
            elif task_type == "product_analysis":
                result = self._perform_product_analysis(data, context)
            elif task_type == "sales_analysis":
                result = self._perform_sales_analysis(data, context)
            elif task_type == "competitor_analysis":
                result = self._perform_competitor_analysis(data, context)
            else:
                result = self._perform_general_analysis(data, context)
            
            # 更新状态
            state["analysis_result"] = result
            state["analyst_executed"] = True
            
            # 记录成功事件
            state = self.log_event(state, "success", f"成功完成{task_type}分析")
            state = self.add_execution_record(state, True, {
                "task_type": task_type,
                "insights_count": len(result.get("insights", [])),
                "risks_count": len(result.get("risks", []))
            })
            
        except Exception as e:
            # 记录错误事件
            state = self.log_event(state, "error", f"数据分析失败: {str(e)}")
            state["analyst_error"] = str(e)
            state["analyst_executed"] = False
            state = self.add_execution_record(state, False, {"error": str(e)})
        
        return state
    
    def get_required_fields(self) -> list:
        """
        获取必需的输入字段
        
        Returns:
            必需字段列表
        """
        return ["analysis_task", "data"]
    
    def get_output_fields(self) -> list:
        """
        获取输出的字段
        
        Returns:
            输出字段列表
        """
        return ["analysis_result", "analyst_executed", "analyst_error"]
    
    def _perform_market_analysis(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行市场分析
        
        Args:
            data: 市场数据
            context: 上下文信息
            
        Returns:
            市场分析结果
        """
        import time
        
        market_data = data.get("market_data", {})
        trends = data.get("trends", [])
        competitors = data.get("competitors", [])
        
        # 分析市场规模
        market_size = market_data.get("size", 0)
        growth_rate = market_data.get("growth_rate", 0)
        
        # 分析市场趋势
        trend_analysis = []
        for trend in trends[:5]:  # 只分析前5个趋势
            trend_analysis.append({
                "trend": trend.get("name", "未知趋势"),
                "impact": trend.get("impact", "中等"),
                "opportunity": trend.get("opportunity", "待评估")
            })
        
        # 分析竞争对手
        competitor_analysis = []
        for competitor in competitors[:5]:  # 只分析前5个竞争对手
            competitor_analysis.append({
                "name": competitor.get("name", "未知竞争对手"),
                "market_share": competitor.get("market_share", 0),
                "strengths": competitor.get("strengths", []),
                "weaknesses": competitor.get("weaknesses", [])
            })
        
        # 生成洞察
        insights = []
        
        if market_size > 0:
            insights.append({
                "type": "market_size",
                "description": f"市场规模为{market_size}，增长率为{growth_rate}%",
                "confidence": "high",
                "action": "考虑扩大市场份额"
            })
        
        if growth_rate > 10:
            insights.append({
                "type": "high_growth",
                "description": f"市场高速增长({growth_rate}%)，存在扩张机会",
                "confidence": "high",
                "action": "加速市场进入"
            })
        elif growth_rate < 0:
            insights.append({
                "type": "market_decline",
                "description": f"市场正在萎缩({growth_rate}%)，需谨慎投资",
                "confidence": "medium",
                "action": "重新评估市场策略"
            })
        
        # 识别风险
        risks = []
        
        if len(competitors) > 10:
            risks.append({
                "type": "high_competition",
                "description": f"市场竞争激烈，有{len(competitors)}个竞争对手",
                "severity": "high",
                "mitigation": "寻找差异化定位"
            })
        
        if any(trend.get("impact") == "negative" for trend in trends):
            risks.append({
                "type": "negative_trends",
                "description": "存在负面市场趋势",
                "severity": "medium",
                "mitigation": "调整产品策略"
            })
        
        return {
            "analysis_type": "market_analysis",
            "market_size": market_size,
            "growth_rate": growth_rate,
            "trend_analysis": trend_analysis,
            "competitor_analysis": competitor_analysis,
            "insights": insights,
            "risks": risks,
            "recommendations": [
                "深入分析目标细分市场",
                "监控主要竞争对手动态",
                "跟踪市场趋势变化"
            ],
            "timestamp": time.time()
        }
    
    def _perform_customer_analysis(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行客户分析
        
        Args:
            data: 客户数据
            context: 上下文信息
            
        Returns:
            客户分析结果
        """
        import time
        
        customer_data = data.get("customer_data", {})
        segments = data.get("segments", [])
        behavior = data.get("behavior", {})
        
        # 分析客户基础
        total_customers = customer_data.get("total", 0)
        active_customers = customer_data.get("active", 0)
        churn_rate = customer_data.get("churn_rate", 0)
        
        # 分析客户细分
        segment_analysis = []
        for segment in segments[:5]:  # 只分析前5个细分
            segment_analysis.append({
                "segment": segment.get("name", "未知细分"),
                "size": segment.get("size", 0),
                "value": segment.get("lifetime_value", 0),
                "characteristics": segment.get("characteristics", [])
            })
        
        # 分析客户行为
        behavior_analysis = {
            "purchase_frequency": behavior.get("purchase_frequency", 0),
            "average_order_value": behavior.get("average_order_value", 0),
            "preferred_channels": behavior.get("preferred_channels", []),
            "satisfaction_score": behavior.get("satisfaction_score", 0)
        }
        
        # 生成洞察
        insights = []
        
        if active_customers > 0:
            activation_rate = (active_customers / total_customers * 100) if total_customers > 0 else 0
            insights.append({
                "type": "customer_activation",
                "description": f"客户激活率为{activation_rate:.1f}%",
                "confidence": "high",
                "action": "优化客户激活策略"
            })
        
        if churn_rate > 10:
            insights.append({
                "type": "high_churn",
                "description": f"客户流失率较高({churn_rate}%)",
                "confidence": "high",
                "action": "实施客户留存计划"
            })
        
        # 识别高价值细分
        high_value_segments = [s for s in segments if s.get("lifetime_value", 0) > 1000]
        if high_value_segments:
            insights.append({
                "type": "high_value_segments",
                "description": f"发现{len(high_value_segments)}个高价值客户细分",
                "confidence": "medium",
                "action": "为重点细分提供个性化服务"
            })
        
        # 识别风险
        risks = []
        
        if churn_rate > 20:
            risks.append({
                "type": "critical_churn",
                "description": f"客户流失率过高({churn_rate}%)",
                "severity": "critical",
                "mitigation": "立即启动客户留存计划"
            })
        
        if behavior_analysis["satisfaction_score"] < 7:
            risks.append({
                "type": "low_satisfaction",
                "description": f"客户满意度较低({behavior_analysis['satisfaction_score']}/10)",
                "severity": "high",
                "mitigation": "改进产品和服务质量"
            })
        
        return {
            "analysis_type": "customer_analysis",
            "total_customers": total_customers,
            "active_customers": active_customers,
            "churn_rate": churn_rate,
            "segment_analysis": segment_analysis,
            "behavior_analysis": behavior_analysis,
            "insights": insights,
            "risks": risks,
            "recommendations": [
                "优化客户细分策略",
                "提升客户满意度",
                "降低客户流失率"
            ],
            "timestamp": time.time()
        }
    
    def _perform_product_analysis(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行产品分析
        
        Args:
            data: 产品数据
            context: 上下文信息
            
        Returns:
            产品分析结果
        """
        import time
        
        products = data.get("products", [])
        performance = data.get("performance", {})
        inventory = data.get("inventory", {})
        
        # 分析产品组合
        product_analysis = []
        for product in products[:10]:  # 只分析前10个产品
            product_analysis.append({
                "product_id": product.get("id", "未知"),
                "name": product.get("name", "未知产品"),
                "sales": product.get("sales", 0),
                "profit": product.get("profit", 0),
                "rating": product.get("rating", 0),
                "stock": product.get("stock", 0)
            })
        
        # 分析产品性能
        performance_analysis = {
            "total_sales": performance.get("total_sales", 0),
            "total_profit": performance.get("total_profit", 0),
            "average_rating": performance.get("average_rating", 0),
            "best_selling": performance.get("best_selling", []),
            "worst_selling": performance.get("worst_selling", [])
        }
        
        # 分析库存状况
        inventory_analysis = {
            "total_value": inventory.get("total_value", 0),
            "turnover_rate": inventory.get("turnover_rate", 0),
            "out_of_stock": inventory.get("out_of_stock", []),
            "overstock": inventory.get("overstock", [])
        }
        
        # 生成洞察
        insights = []
        
        # 识别畅销产品
        best_sellers = [p for p in products if p.get("sales", 0) > 1000]
        if best_sellers:
            insights.append({
                "type": "best_sellers",
                "description": f"发现{len(best_sellers)}个畅销产品",
                "confidence": "high",
                "action": "增加畅销产品库存和推广"
            })
        
        # 识别滞销产品
        worst_sellers = [p for p in products if p.get("sales", 0) < 10 and p.get("stock", 0) > 50]
        if worst_sellers:
            insights.append({
                "type": "worst_sellers",
                "description": f"发现{len(worst_sellers)}个滞销产品",
                "confidence": "medium",
                "action": "考虑促销或下架滞销产品"
            })
        
        # 识别库存问题
        if inventory_analysis["turnover_rate"] < 2:
            insights.append({
                "type": "low_turnover",
                "description": f"库存周转率较低({inventory_analysis['turnover_rate']})",
                "confidence": "high",
                "action": "优化库存管理"
            })
        
        # 识别风险
        risks = []
        
        # 缺货风险
        if inventory_analysis["out_of_stock"]:
            risks.append({
                "type": "out_of_stock",
                "description": f"{len(inventory_analysis['out_of_stock'])}个产品缺货",
                "severity": "high",
                "mitigation": "立即补货"
            })
        
        # 积压风险
        if inventory_analysis["overstock"]:
            risks.append({
                "type": "overstock",
                "description": f"{len(inventory_analysis['overstock'])}个产品积压",
                "severity": "medium",
                "mitigation": "制定促销计划"
            })
        
        return {
            "analysis_type": "product_analysis",
            "product_count": len(products),
            "product_analysis": product_analysis,
            "performance_analysis": performance_analysis,
            "inventory_analysis": inventory_analysis,
            "insights": insights,
            "risks": risks,
            "recommendations": [
                "优化产品组合",
                "改进库存管理",
                "提升产品利润率"
            ],
            "timestamp": time.time()
        }
    
    def _perform_sales_analysis(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行销售分析
        
        Args:
            data: 销售数据
            context: 上下文信息
            
        Returns:
            销售分析结果
        """
        import time
        
        sales_data = data.get("sales_data", {})
        trends = data.get("trends", [])
        channels = data.get("channels", [])
        
        # 分析销售表现
        sales_analysis = {
            "total_revenue": sales_data.get("total_revenue", 0),
            "total_orders": sales_data.get("total_orders", 0),
            "average_order_value": sales_data.get("average_order_value", 0),
            "conversion_rate": sales_data.get("conversion_rate", 0),
            "growth_rate": sales_data.get("growth_rate", 0)
        }
        
        # 分析销售趋势
        trend_analysis = []
        for trend in trends[:7]:  # 分析最近7天趋势
            trend_analysis.append({
                "date": trend.get("date", "未知日期"),
                "revenue": trend.get("revenue", 0),
                "orders": trend.get("orders", 0),
                "conversion": trend.get("conversion", 0)
            })
        
        # 分析销售渠道
        channel_analysis = []
        for channel in channels:
            channel_analysis.append({
                "channel": channel.get("name", "未知渠道"),
                "revenue": channel.get("revenue", 0),
                "orders": channel.get("orders", 0),
                "conversion": channel.get("conversion", 0),
                "cost": channel.get("cost", 0)
            })
        
        # 生成洞察
        insights = []
        
        # 销售增长洞察
        if sales_analysis["growth_rate"] > 20:
            insights.append({
                "type": "high_growth",
                "description": f"销售高速增长({sales_analysis['growth_rate']}%)",
                "confidence": "high",
                "action": "维持增长势头"
            })
        elif sales_analysis["growth_rate"] < 0:
            insights.append({
                "type": "sales_decline",
                "description": f"销售下滑({sales_analysis['growth_rate']}%)",
                "confidence": "high",
                "action": "分析下滑原因并采取措施"
            })
        
        # 转化率洞察
        if sales_analysis["conversion_rate"] > 5:
            insights.append({
                "type": "good_conversion",
                "description": f"转化率良好({sales_analysis['conversion_rate']}%)",
                "confidence": "medium",
                "action": "保持当前转化策略"
            })
        elif sales_analysis["conversion_rate"] < 1:
            insights.append({
                "type": "low_conversion",
                "description": f"转化率较低({sales_analysis['conversion_rate']}%)",
                "confidence": "high",
                "action": "优化网站和营销策略"
            })
        
        # 渠道表现洞察
        best_channel = max(channel_analysis, key=lambda x: x.get("revenue", 0), default=None)
        if best_channel:
            insights.append({
                "type": "best_channel",
                "description": f"最佳销售渠道: {best_channel['channel']} (收入: {best_channel['revenue']})",
                "confidence": "high",
                "action": "加大在最佳渠道的投入"
            })
        
        # 识别低效渠道
        inefficient_channels = [c for c in channel_analysis if c.get("conversion", 0) < 1 and c.get("cost", 0) > 1000]
        if inefficient_channels:
            insights.append({
                "type": "inefficient_channels",
                "description": f"发现{len(inefficient_channels)}个低效销售渠道",
                "confidence": "medium",
                "action": "优化或减少低效渠道投入"
            })
        
        # 识别风险
        risks = []
        
        # 销售下滑风险
        if sales_analysis["growth_rate"] < -10:
            risks.append({
                "type": "severe_sales_decline",
                "description": f"销售严重下滑({sales_analysis['growth_rate']}%)",
                "severity": "critical",
                "mitigation": "立即分析原因并采取紧急措施"
            })
        
        # 渠道集中风险
        if len(channel_analysis) > 0:
            top_channel_revenue = max(c.get("revenue", 0) for c in channel_analysis)
            total_revenue = sum(c.get("revenue", 0) for c in channel_analysis)
            if total_revenue > 0 and (top_channel_revenue / total_revenue) > 0.7:
                risks.append({
                    "type": "channel_concentration",
                    "description": "销售过度依赖单一渠道",
                    "severity": "high",
                    "mitigation": "拓展多元化销售渠道"
                })
        
        return {
            "analysis_type": "sales_analysis",
            "sales_analysis": sales_analysis,
            "trend_analysis": trend_analysis,
            "channel_analysis": channel_analysis,
            "insights": insights,
            "risks": risks,
            "recommendations": [
                "优化销售渠道组合",
                "提升转化率",
                "保持销售增长势头"
            ],
            "timestamp": time.time()
        }
    
    def _perform_competitor_analysis(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行竞争对手分析
        
        Args:
            data: 竞争对手数据
            context: 上下文信息
            
        Returns:
            竞争对手分析结果
        """
        import time
        
        competitors = data.get("competitors", [])
        market_data = data.get("market_data", {})
        
        # 分析竞争对手
        competitor_analysis = []
        for competitor in competitors[:10]:  # 只分析前10个竞争对手
            competitor_analysis.append({
                "name": competitor.get("name", "未知竞争对手"),
                "market_share": competitor.get("market_share", 0),
                "strengths": competitor.get("strengths", []),
                "weaknesses": competitor.get("weaknesses", []),
                "products": competitor.get("products", []),
                "pricing": competitor.get("pricing_strategy", "未知"),
                "customer_rating": competitor.get("customer_rating", 0)
            })
        
        # 分析市场竞争格局
        market_analysis = {
            "total_market_size": market_data.get("size", 0),
            "competition_intensity": market_data.get("competition_intensity", "中等"),
            "barriers_to_entry": market_data.get("barriers_to_entry", "中等"),
            "growth_potential": market_data.get("growth_potential", "中等")
        }
        
        # 生成洞察
        insights = []
        
        # 市场份额洞察
        total_share = sum(c.get("market_share", 0) for c in competitor_analysis)
        if total_share > 0:
            market_concentration = max(c.get("market_share", 0) for c in competitor_analysis) / total_share
            if market_concentration > 0.5:
                insights.append({
                    "type": "market_dominance",
                    "description": f"市场被少数竞争对手主导(集中度: {market_concentration:.1%})",
                    "confidence": "high",
                    "action": "寻找差异化竞争策略"
                })
        
        # 竞争对手优势洞察
        strong_competitors = [c for c in competitor_analysis if len(c.get("strengths", [])) > 3]
        if strong_competitors:
            insights.append({
                "type": "strong_competitors",
                "description": f"发现{len(strong_competitors)}个实力较强的竞争对手",
                "confidence": "medium",
                "action": "学习竞争对手优势，弥补自身不足"
            })
        
        # 竞争对手弱点洞察
        weak_competitors = [c for c in competitor_analysis if len(c.get("weaknesses", [])) > 3]
        if weak_competitors:
            insights.append({
                "type": "weak_competitors",
                "description": f"发现{len(weak_competitors)}个存在明显弱点的竞争对手",
                "confidence": "medium",
                "action": "针对竞争对手弱点制定竞争策略"
            })
        
        # 识别风险
        risks = []
        
        # 激烈竞争风险
        if market_analysis["competition_intensity"] == "高":
            risks.append({
                "type": "intense_competition",
                "description": "市场竞争激烈",
                "severity": "high",
                "mitigation": "加强产品差异化和品牌建设"
            })
        
        # 市场进入壁垒风险
        if market_analysis["barriers_to_entry"] == "高":
            risks.append({
                "type": "high_barriers",
                "description": "市场进入壁垒较高",
                "severity": "medium",
                "mitigation": "寻找合作伙伴或差异化进入策略"
            })
        
        return {
            "analysis_type": "competitor_analysis",
            "competitor_count": len(competitors),
            "competitor_analysis": competitor_analysis,
            "market_analysis": market_analysis,
            "insights": insights,
            "risks": risks,
            "recommendations": [
                "持续监控竞争对手动态",
                "分析竞争对手优劣势",
                "制定差异化竞争策略"
            ],
            "timestamp": time.time()
        }
    
    def _perform_general_analysis(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行通用分析
        
        Args:
            data: 通用数据
            context: 上下文信息
            
        Returns:
            通用分析结果
        """
        import time
        
        # 分析数据基本情况
        data_summary = {
            "data_points": len(data) if isinstance(data, dict) else 0,
            "data_types": list(set(type(v).__name__ for v in data.values())) if isinstance(data, dict) else [],
            "has_numeric": any(isinstance(v, (int, float)) for v in data.values()) if isinstance(data, dict) else False,
            "has_text": any(isinstance(v, str) for v in data.values()) if isinstance(data, dict) else False
        }
        
        # 提取关键指标
        key_metrics = {}
        for key, value in data.items():
            if isinstance(value, (int, float)):
                key_metrics[key] = value
            elif isinstance(value, dict):
                # 尝试从嵌套字典中提取数值
                nested_values = [v for v in value.values() if isinstance(v, (int, float))]
                if nested_values:
                    key_metrics[key] = sum(nested_values) / len(nested_values) if nested_values else 0
        
        # 生成基本洞察
        insights = []
        
        if key_metrics:
            # 识别最高和最低的指标
            if key_metrics:
                max_key = max(key_metrics, key=key_metrics.get)
                min_key = min(key_metrics, key=key_metrics.get)
                
                insights.append({
                    "type": "key_metrics",
                    "description": f"最高指标: {max_key}={key_metrics[max_key]}, 最低指标: {min_key}={key_metrics[min_key]}",
                    "confidence": "medium",
                    "action": "关注关键指标变化"
                })
        
        # 识别数据质量问题
        risks = []
        
        if data_summary["data_points"] == 0:
            risks.append({
                "type": "no_data",
                "description": "没有可分析的数据",
                "severity": "high",
                "mitigation": "收集更多数据"
            })
        
        if not data_summary["has_numeric"]:
            risks.append({
                "type": "lack_of_numeric_data",
                "description": "缺乏数值型数据，分析受限",
                "severity": "medium",
                "mitigation": "补充数值型数据"
            })
        
        return {
            "analysis_type": "general_analysis",
            "data_summary": data_summary,
            "key_metrics": key_metrics,
            "insights": insights,
            "risks": risks,
            "recommendations": [
                "收集更多结构化数据",
                "定义关键绩效指标",
                "建立定期分析机制"
            ],
            "timestamp": time.time()
        }
