"""
竞品分析 Agent - 电商选品分析场景

职责：
1. 读取竞品模拟数据
2. 进行竞品对比分析
3. 评估竞争优势和劣势
4. 提出差异化建议

继承自 common/core/agent.py 的 Agent 基类
"""

import json
import os
from typing import Any, Dict, List

from backend.common.core.agent import Agent, AgentInput, AgentOutput
from backend.common.core.state import State


class CompetitorAnalystAgent(Agent):
    """竞品分析 Agent - 负责竞品对比分析和差异化策略建议"""

    name = "competitor_analyst"
    description = "电商竞品分析 Agent，负责竞品对比分析和差异化策略建议"

    def __init__(self):
        """初始化竞品分析 Agent"""
        self._data_cache = {}

    def _load_mock_data(self) -> Dict[str, Any]:
        """
        加载竞品模拟数据
        
        Returns:
            Dict 包含 competitors 数据
        """
        if self._data_cache:
            return self._data_cache

        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data"
        )

        competitors_path = os.path.join(data_dir, "mock_competitors.json")
        if os.path.exists(competitors_path):
            with open(competitors_path, "r", encoding="utf-8") as f:
                self._data_cache["competitors"] = json.load(f).get("competitors", [])
        else:
            self._data_cache["competitors"] = []

        return self._data_cache

    def run(self, state: State) -> State:
        """
        执行竞品分析逻辑
        
        Args:
            state: 状态对象，包含 competitors 数据或 analysis_type 参数
            
        Returns:
            修改后的状态对象，包含竞品分析结果
        """
        state.add_event("competitor_analyst_start")

        try:
            # 加载数据
            data = self._load_mock_data()
            competitors = data.get("competitors", [])

            # 获取市场分析结果（如果已存在）
            market_result = state.get("market_analysis_result", {})

            # 执行竞品分析
            result = self._analyze_competitors(competitors, market_result)

            state.set("result", result)
            state.set_meta("analysis_completed", True)
            state.add_event("competitor_analyst_success")

        except Exception as e:
            state.set("error", str(e))
            state.set_meta("analysis_completed", False)
            state.add_event(f"competitor_analyst_error: {str(e)}")

        return state

    def _analyze_competitors(
        self,
        competitors: List[Dict[str, Any]],
        market_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        竞品对比分析
        
        分析维度：
        1. 市场份额分布
        2. 价格区间对比
        3. 品牌优劣势对比
        4. 品类覆盖分析
        5. 差异化机会识别
        
        Args:
            competitors: 竞品列表
            market_result: 市场分析结果（可选）
            
        Returns:
            竞品分析结果
        """
        total_competitors = len(competitors)

        # 1. 市场份额分析
        total_market_share = sum(c["market_share"] for c in competitors)
        market_leaders = sorted(competitors, key=lambda c: c["market_share"], reverse=True)

        # 2. 价格区间分析
        price_ranges = []
        for c in competitors:
            price_ranges.append({
                "brand": c["brand_name"],
                "min_price": c["price_range"]["min"],
                "max_price": c["price_range"]["max"],
                "price_span": c["price_range"]["max"] - c["price_range"]["min"]
            })

        # 3. 评分对比
        rating_comparison = sorted(
            [{"brand": c["brand_name"], "avg_rating": c["avg_rating"]} for c in competitors],
            key=lambda x: x["avg_rating"],
            reverse=True
        )

        # 4. 品类覆盖分析
        category_coverage = {}
        for c in competitors:
            for cat in c["target_categories"]:
                if cat not in category_coverage:
                    category_coverage[cat] = []
                category_coverage[cat].append(c["brand_name"])

        # 5. 优劣势汇总
        strengths_summary = {}
        weaknesses_summary = {}
        for c in competitors:
            for s in c["strengths"]:
                strengths_summary[s] = strengths_summary.get(s, 0) + 1
            for w in c["weaknesses"]:
                weaknesses_summary[w] = weaknesses_summary.get(w, 0) + 1

        # 6. 差异化机会识别
        differentiation_opportunities = self._identify_differentiation(
            competitors, category_coverage, market_result
        )

        # 7. 竞争格局总结
        competitive_landscape = self._analyze_competitive_landscape(
            competitors, market_leaders
        )

        return {
            "analysis_type": "competitor_benchmark",
            "summary": {
                "total_competitors_analyzed": total_competitors,
                "total_market_share_covered": total_market_share,
                "market_concentration": "高" if market_leaders[0]["market_share"] > 0.2 else "中",
                "top_3_market_share": round(
                    sum(c["market_share"] for c in market_leaders[:3]), 4
                )
            },
            "market_share_distribution": [
                {
                    "rank": i + 1,
                    "brand": c["brand_name"],
                    "market_share": c["market_share"],
                    "market_share_percent": f"{c['market_share']*100:.1f}%",
                    "monthly_sales_estimate": c["monthly_sales_estimate"]
                }
                for i, c in enumerate(market_leaders)
            ],
            "price_comparison": price_ranges,
            "rating_comparison": rating_comparison,
            "category_coverage": {
                cat: {
                    "competitor_count": len(brands),
                    "competitors": brands
                }
                for cat, brands in sorted(
                    category_coverage.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )
            },
            "strengths_analysis": sorted(
                [{"strength": k, "frequency": v} for k, v in strengths_summary.items()],
                key=lambda x: x["frequency"],
                reverse=True
            ),
            "weaknesses_analysis": sorted(
                [{"weakness": k, "frequency": v} for k, v in weaknesses_summary.items()],
                key=lambda x: x["frequency"],
                reverse=True
            ),
            "differentiation_opportunities": differentiation_opportunities,
            "competitive_landscape": competitive_landscape
        }

    def _identify_differentiation(
        self,
        competitors: List[Dict[str, Any]],
        category_coverage: Dict[str, List[str]],
        market_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        识别差异化机会
        
        Args:
            competitors: 竞品列表
            category_coverage: 品类覆盖情况
            market_result: 市场分析结果
            
        Returns:
            差异化机会列表
        """
        opportunities = []

        # 1. 品类空白机会
        all_categories = set()
        for c in competitors:
            all_categories.update(c["target_categories"])

        # 检查市场分析中的推荐品类是否已有竞品覆盖
        category_insights = market_result.get("category_insights", [])
        for insight in category_insights:
            cat = insight["category"]
            if cat not in all_categories:
                opportunities.append({
                    "type": "品类空白",
                    "category": cat,
                    "description": f"{cat}品类尚无主要竞品覆盖，存在先发优势机会",
                    "potential": "高",
                    "action": f"优先布局{cat}品类，抢占市场空白"
                })
            elif len(category_coverage.get(cat, [])) <= 2:
                opportunities.append({
                    "type": "品类竞争不足",
                    "category": cat,
                    "description": f"{cat}品类仅有{len(category_coverage.get(cat, []))}家竞品，竞争格局尚未固化",
                    "potential": "中高",
                    "action": f"差异化进入{cat}品类，避免与头部竞品正面竞争"
                })

        # 2. 价格带空白机会
        price_bands = [(0, 99), (100, 299), (300, 599), (600, 999), (1000, 1999), (2000, 5000)]
        for band_min, band_max in price_bands:
            brands_in_band = []
            for c in competitors:
                if c["price_range"]["min"] <= band_max and c["price_range"]["max"] >= band_min:
                    brands_in_band.append(c["brand_name"])
            if len(brands_in_band) <= 1:
                opportunities.append({
                    "type": "价格带空白",
                    "price_band": f"¥{band_min}-{band_max}",
                    "competitors_in_band": brands_in_band,
                    "description": f"¥{band_min}-{band_max} 价格带竞品较少，存在差异化定价机会",
                    "potential": "中",
                    "action": f"针对 ¥{band_min}-{band_max} 价格带开发高性价比产品"
                })

        # 3. 竞品弱点利用
        common_weaknesses = {}
        for c in competitors:
            for w in c["weaknesses"]:
                if w not in common_weaknesses:
                    common_weaknesses[w] = []
                common_weaknesses[w].append(c["brand_name"])

        for weakness, brands in common_weaknesses.items():
            if len(brands) >= 2:
                opportunities.append({
                    "type": "竞品弱点利用",
                    "weakness": weakness,
                    "affected_brands": brands,
                    "description": f"多家竞品({', '.join(brands)})存在「{weakness}」问题，可作为差异化突破口",
                    "potential": "高",
                    "action": f"在产品设计和营销中突出解决「{weakness}」问题"
                })

        return opportunities

    def _analyze_competitive_landscape(
        self,
        competitors: List[Dict[str, Any]],
        market_leaders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析竞争格局
        
        Args:
            competitors: 竞品列表
            market_leaders: 按市场份额排序的竞品列表
            
        Returns:
            竞争格局分析
        """
        # 分层分析
        tiers = {"第一梯队": [], "第二梯队": [], "第三梯队": []}
        for c in market_leaders:
            if c["market_share"] >= 0.15:
                tiers["第一梯队"].append(c["brand_name"])
            elif c["market_share"] >= 0.08:
                tiers["第二梯队"].append(c["brand_name"])
            else:
                tiers["第三梯队"].append(c["brand_name"])

        # 竞争策略总结
        strategies = []
        for c in competitors:
            if "性价比" in str(c["strengths"]) or "价格" in str(c["strengths"]):
                strategies.append({
                    "brand": c["brand_name"],
                    "strategy": "性价比策略",
                    "detail": "以价格优势获取市场份额"
                })
            if "品牌" in str(c["strengths"]) or "技术" in str(c["strengths"]):
                strategies.append({
                    "brand": c["brand_name"],
                    "strategy": "品牌/技术驱动",
                    "detail": "依靠品牌影响力和技术实力获取溢价"
                })
            if "渠道" in str(c["strengths"]) or "流量" in str(c["strengths"]):
                strategies.append({
                    "brand": c["brand_name"],
                    "strategy": "渠道/流量驱动",
                    "detail": "依托渠道优势和流量资源获取销量"
                })

        return {
            "tiers": tiers,
            "market_leaders": [c["brand_name"] for c in market_leaders[:3]],
            "competitive_strategies": strategies,
            "entry_barrier": "中",
            "recommended_strategy": "差异化竞争，避免与头部品牌正面价格战，"
                                    "聚焦细分品类和价格带空白"
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
