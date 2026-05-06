"""
市场分析 Agent - 电商选品分析场景

职责：
1. 读取商品、市场趋势模拟数据
2. 调用 foundation/cognition/ 的分析能力进行市场趋势分析
3. 识别市场机会点和风险点
4. 进行盈利评估（ROI 分析）

继承自 common/core/agent.py 的 Agent 基类
"""

import json
import os
from typing import Any, Dict, Optional

from backend.common.core.agent import Agent, AgentInput, AgentOutput
from backend.common.core.state import State


class MarketAnalystAgent(Agent):
    """市场分析 Agent - 负责市场趋势分析和盈利评估"""

    name = "market_analyst"
    description = "电商选品市场分析 Agent，负责市场趋势分析和盈利评估"

    def __init__(self):
        """初始化市场分析 Agent"""
        self._data_cache = {}

    def _load_mock_data(self) -> Dict[str, Any]:
        """
        加载模拟数据
        从 product_selection/data/ 目录读取 JSON 文件
        
        Returns:
            Dict 包含 products, market_trends 等数据
        """
        if self._data_cache:
            return self._data_cache

        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data"
        )

        # 加载商品数据
        products_path = os.path.join(data_dir, "mock_products.json")
        if os.path.exists(products_path):
            with open(products_path, "r", encoding="utf-8") as f:
                self._data_cache["products"] = json.load(f).get("products", [])
        else:
            self._data_cache["products"] = []

        # 加载市场趋势数据
        trends_path = os.path.join(data_dir, "mock_market_trends.json")
        if os.path.exists(trends_path):
            with open(trends_path, "r", encoding="utf-8") as f:
                self._data_cache["market_trends"] = json.load(f).get("market_trends", {})
        else:
            self._data_cache["market_trends"] = {}

        return self._data_cache

    def run(self, state: State) -> State:
        """
        执行市场分析逻辑
        
        根据 state 中的 analysis_type 参数决定执行：
        - "market_trends": 市场趋势分析
        - "roi_analysis": 盈利评估（ROI 分析）
        
        Args:
            state: 状态对象，包含 analysis_type 等参数
            
        Returns:
            修改后的状态对象，包含分析结果
        """
        state.add_event("market_analyst_start")

        # 获取分析类型
        analysis_type = state.get("analysis_type", "market_trends")
        state.set_meta("analysis_type", analysis_type)

        try:
            # 加载数据
            data = self._load_mock_data()

            if analysis_type == "market_trends":
                result = self._analyze_market_trends(data, state)
            elif analysis_type == "roi_analysis":
                result = self._analyze_profitability(data, state)
            else:
                result = {
                    "error": f"未知的分析类型: {analysis_type}",
                    "available_types": ["market_trends", "roi_analysis"]
                }

            state.set("result", result)
            state.set_meta("analysis_completed", True)
            state.add_event("market_analyst_success")

        except Exception as e:
            state.set("error", str(e))
            state.set_meta("analysis_completed", False)
            state.add_event(f"market_analyst_error: {str(e)}")

        return state

    def _analyze_market_trends(self, data: Dict[str, Any], state: State) -> Dict[str, Any]:
        """
        市场趋势分析
        
        分析商品数据和市场趋势数据，识别：
        - 市场总体概况
        - 月度趋势变化
        - 品类洞察
        - 机会点
        - 风险点
        
        Args:
            data: 加载的模拟数据
            state: 状态对象
            
        Returns:
            市场分析结果
        """
        products = data.get("products", [])
        market_trends = data.get("market_trends", {})

        # 1. 商品基础统计
        total_products = len(products)
        avg_price = sum(p["price"] for p in products) / total_products if total_products > 0 else 0
        total_sales = sum(p["sales_volume"] for p in products)
        avg_rating = sum(p["rating"] for p in products) / total_products if total_products > 0 else 0

        # 2. 品类分布分析
        category_stats = {}
        for p in products:
            cat = p["category"]
            if cat not in category_stats:
                category_stats[cat] = {
                    "product_count": 0,
                    "total_sales": 0,
                    "total_reviews": 0,
                    "avg_price": 0,
                    "avg_rating": 0,
                    "products": []
                }
            stats = category_stats[cat]
            stats["product_count"] += 1
            stats["total_sales"] += p["sales_volume"]
            stats["total_reviews"] += p["review_count"]
            stats["avg_price"] = (stats["avg_price"] * (stats["product_count"] - 1) + p["price"]) / stats["product_count"]
            stats["avg_rating"] = (stats["avg_rating"] * (stats["product_count"] - 1) + p["rating"]) / stats["product_count"]
            stats["products"].append(p["name"])

        # 3. 趋势分析
        monthly_trends = market_trends.get("monthly_trends", [])
        category_insights = market_trends.get("category_insights", [])
        overview = market_trends.get("overview", {})

        # 计算搜索量趋势
        search_volumes = [m["search_volume"] for m in monthly_trends]
        avg_search_volume = sum(search_volumes) / len(search_volumes) if search_volumes else 0
        peak_month = max(monthly_trends, key=lambda m: m["search_volume"]) if monthly_trends else {}
        low_month = min(monthly_trends, key=lambda m: m["search_volume"]) if monthly_trends else {}

        # 4. 识别机会点
        opportunities = []
        for insight in category_insights:
            if insight["recommendation"] in ["重点关注", "持续投入"]:
                opportunities.append({
                    "category": insight["category"],
                    "annual_growth": insight["annual_growth"],
                    "avg_margin": insight["avg_margin"],
                    "competition_level": insight["competition_level"],
                    "reason": f"{insight['category']}品类年增长率{insight['annual_growth']*100:.0f}%，"
                              f"平均利润率{insight['avg_margin']*100:.0f}%，"
                              f"竞争{insight['competition_level']}，建议{insight['recommendation']}"
                })

        # 5. 识别风险点
        risks = []
        for insight in category_insights:
            if insight["competition_level"] == "高":
                risks.append({
                    "category": insight["category"],
                    "risk_type": "竞争激烈",
                    "detail": f"{insight['category']}品类竞争程度高，需差异化策略"
                })
        # 低增长品类风险
        for insight in category_insights:
            if insight["annual_growth"] < 0.15:
                risks.append({
                    "category": insight["category"],
                    "risk_type": "增长放缓",
                    "detail": f"{insight['category']}品类年增长率仅{insight['annual_growth']*100:.0f}%，市场增长空间有限"
                })

        # 6. 热门关键词提取
        hot_keywords = []
        for month in monthly_trends:
            hot_keywords.extend(month.get("hot_keywords", []))
        # 去重并统计频率
        keyword_freq = {}
        for kw in hot_keywords:
            keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "analysis_type": "market_trends",
            "summary": {
                "total_products_analyzed": total_products,
                "average_price": round(avg_price, 2),
                "total_sales_volume": total_sales,
                "average_rating": round(avg_rating, 2),
                "market_size": overview.get("total_market_size", "未知"),
                "market_growth_rate": overview.get("growth_rate", 0),
                "active_buyers": overview.get("active_buyers", "未知")
            },
            "category_distribution": {
                cat: {
                    "product_count": stats["product_count"],
                    "total_sales": stats["total_sales"],
                    "avg_price": round(stats["avg_price"], 2),
                    "avg_rating": round(stats["avg_rating"], 2)
                }
                for cat, stats in sorted(
                    category_stats.items(),
                    key=lambda x: x[1]["total_sales"],
                    reverse=True
                )
            },
            "trend_analysis": {
                "avg_monthly_search_volume": int(avg_search_volume),
                "peak_month": {
                    "month": peak_month.get("month"),
                    "search_volume": peak_month.get("search_volume"),
                    "hot_keywords": peak_month.get("hot_keywords", [])
                } if peak_month else {},
                "low_month": {
                    "month": low_month.get("month"),
                    "search_volume": low_month.get("search_volume")
                } if low_month else {},
                "sales_index_trend": [
                    {"month": m["month"], "sales_index": m["sales_index"]}
                    for m in monthly_trends
                ]
            },
            "opportunities": opportunities,
            "risks": risks,
            "hot_keywords": [{"keyword": kw, "frequency": freq} for kw, freq in top_keywords],
            "category_insights": category_insights
        }

    def _analyze_profitability(self, data: Dict[str, Any], state: State) -> Dict[str, Any]:
        """
        盈利评估（ROI 分析）
        
        基于商品数据和竞品分析结果，评估各商品的盈利能力
        
        Args:
            data: 加载的模拟数据
            state: 状态对象
            
        Returns:
            盈利评估结果
        """
        products = data.get("products", [])

        # 获取竞品分析结果（如果已存在）
        competitor_result = state.get("competitor_analysis_result", {})

        # 对每个商品进行盈利评估
        profitability_results = []
        for p in products:
            # 计算月均收入
            monthly_revenue = p["price"] * p["sales_volume"]
            # 计算月均利润
            monthly_profit = monthly_revenue * p["profit_margin"]
            # 估算库存成本（假设库存周转周期为30天）
            inventory_cost = p["stock"] * p["price"] * 0.02  # 2% 库存持有成本
            # 净月利润
            net_monthly_profit = monthly_profit - inventory_cost
            # ROI（月化）
            monthly_roi = net_monthly_profit / (p["stock"] * p["price"]) if p["stock"] > 0 else 0

            profitability_results.append({
                "product_id": p["id"],
                "product_name": p["name"],
                "category": p["category"],
                "price": p["price"],
                "monthly_sales": p["sales_volume"],
                "monthly_revenue": round(monthly_revenue, 2),
                "profit_margin": p["profit_margin"],
                "monthly_profit": round(monthly_profit, 2),
                "inventory_cost": round(inventory_cost, 2),
                "net_monthly_profit": round(net_monthly_profit, 2),
                "monthly_roi": round(monthly_roi, 4),
                "annualized_roi": round(monthly_roi * 12, 4),
                "rating": p["rating"],
                "review_count": p["review_count"]
            })

        # 按 ROI 排序
        profitability_results.sort(key=lambda x: x["monthly_roi"], reverse=True)

        # 计算整体统计
        total_revenue = sum(r["monthly_revenue"] for r in profitability_results)
        total_profit = sum(r["net_monthly_profit"] for r in profitability_results)
        avg_roi = sum(r["monthly_roi"] for r in profitability_results) / len(profitability_results) if profitability_results else 0

        # 按品类汇总
        category_profitability = {}
        for r in profitability_results:
            cat = r["category"]
            if cat not in category_profitability:
                category_profitability[cat] = {
                    "product_count": 0,
                    "total_revenue": 0,
                    "total_profit": 0,
                    "avg_roi": 0,
                    "avg_margin": 0
                }
            cp = category_profitability[cat]
            cp["product_count"] += 1
            cp["total_revenue"] += r["monthly_revenue"]
            cp["total_profit"] += r["net_monthly_profit"]
            cp["avg_roi"] = (cp["avg_roi"] * (cp["product_count"] - 1) + r["monthly_roi"]) / cp["product_count"]
            cp["avg_margin"] = (cp["avg_margin"] * (cp["product_count"] - 1) + r["profit_margin"]) / cp["product_count"]

        # 推荐 Top 5 选品
        top_picks = profitability_results[:5]

        return {
            "analysis_type": "roi_analysis",
            "summary": {
                "total_products_evaluated": len(profitability_results),
                "total_monthly_revenue": round(total_revenue, 2),
                "total_monthly_profit": round(total_profit, 2),
                "average_monthly_roi": round(avg_roi, 4),
                "average_annualized_roi": round(avg_roi * 12, 4)
            },
            "category_profitability": {
                cat: {
                    "product_count": cp["product_count"],
                    "total_revenue": round(cp["total_revenue"], 2),
                    "total_profit": round(cp["total_profit"], 2),
                    "avg_roi": round(cp["avg_roi"], 4),
                    "avg_margin": round(cp["avg_margin"], 4)
                }
                for cat, cp in sorted(
                    category_profitability.items(),
                    key=lambda x: x[1]["total_profit"],
                    reverse=True
                )
            },
            "product_profitability": profitability_results,
            "top_picks": [
                {
                    "rank": i + 1,
                    "product_name": tp["product_name"],
                    "category": tp["category"],
                    "price": tp["price"],
                    "monthly_roi": tp["monthly_roi"],
                    "annualized_roi": tp["annualized_roi"],
                    "net_monthly_profit": tp["net_monthly_profit"],
                    "rating": tp["rating"],
                    "reason": f"月化ROI {tp['monthly_roi']*100:.2f}%，"
                              f"年化ROI {tp['annualized_roi']*100:.2f}%，"
                              f"月净利 ¥{tp['net_monthly_profit']:.0f}，"
                              f"评分 {tp['rating']}"
                }
                for i, tp in enumerate(top_picks)
            ]
        }

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """
        向后兼容的 execute 方法
        
        Args:
            input_data: AgentInput 对象
            
        Returns:
            AgentOutput 对象
        """
        return await super().execute(input_data)
