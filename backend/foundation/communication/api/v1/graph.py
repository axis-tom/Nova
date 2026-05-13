"""
Graph API - 统一AI行为入口

实现POST /graph/run接口，所有AI行为必须通过此入口执行
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import logging

from backend.foundation.cognition.state_machine.deterministic_graph import (
    DeterministicGraphEngine,
    GraphDefinition,
    NodeDefinition,
    NodeType
)
from backend.common.core.state import State
from backend.utils.logger import logger

# 定义请求模型
class GraphRunRequest(BaseModel):
    """Graph执行请求"""
    scenario: str = Field(..., description="场景名称，如: email_briefing, daily_report等")
    input: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    env: str = Field(default="sandbox", description="执行环境: sandbox/production")
    graph_config: Optional[Dict[str, Any]] = Field(None, description="自定义图配置（可选）")

class GraphExecuteRequest(BaseModel):
    """Graph执行请求（基于SOP名称）"""
    sop_name: str = Field(..., description="SOP名称，如: product_selection")
    input: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    env: str = Field(default="sandbox", description="执行环境: sandbox/production")

class GraphRunResponse(BaseModel):
    """Graph执行响应"""
    success: bool = Field(..., description="执行是否成功")
    result: Dict[str, Any] = Field(..., description="执行结果")
    trace_id: Optional[str] = Field(None, description="追踪ID")
    execution_path: Optional[list] = Field(None, description="执行路径")
    error: Optional[str] = Field(None, description="错误信息（如果失败）")

# 创建路由器
router = APIRouter()

# 预定义的场景图配置
SCENARIO_GRAPHS = {
    "email_briefing": {
        "graph_id": "email_briefing_graph",
        "version": "1.0",
        "description": "邮件简报生成场景",
        "nodes": [
            {
                "node_id": "validate_input",
                "node_type": "data_node",
                "config": {
                    "validate": {
                        "input_data": ["required"]
                    }
                },
                "next": "analyze_content"
            },
            {
                "node_id": "analyze_content",
                "node_type": "agent_node",
                "config": {
                    "agent": "ai_analyzer",
                    "params": {
                        "task": "analyze_email_content"
                    }
                },
                "next": "generate_briefing"
            },
            {
                "node_id": "generate_briefing",
                "node_type": "agent_node",
                "config": {
                    "agent": "briefing_generator",
                    "params": {
                        "format": "standard"
                    }
                },
                "next": "output_result"
            },
            {
                "node_id": "output_result",
                "node_type": "output_node",
                "config": {
                    "output_fields": ["briefing", "summary", "key_points"]
                }
            }
        ]
    },
    "daily_report": {
        "graph_id": "daily_report_graph",
        "version": "1.0",
        "description": "每日报告生成场景",
        "nodes": [
            {
                "node_id": "collect_data",
                "node_type": "data_node",
                "config": {
                    "validate": {
                        "data_sources": ["required"]
                    }
                },
                "next": "analyze_trends"
            },
            {
                "node_id": "analyze_trends",
                "node_type": "agent_node",
                "config": {
                    "agent": "ai_analyzer",
                    "params": {
                        "task": "analyze_daily_trends"
                    }
                },
                "next": "generate_report"
            },
            {
                "node_id": "generate_report",
                "node_type": "agent_node",
                "config": {
                    "agent": "briefing_generator",
                    "params": {
                        "format": "detailed"
                    }
                },
                "next": "output_result"
            },
            {
                "node_id": "output_result",
                "node_type": "output_node",
                "config": {
                    "output_fields": ["report", "insights", "recommendations"]
                }
            }
        ]
    },
    "product_selection": {
        "graph_id": "product_selection_graph",
        "version": "1.0",
        "description": "电商选品分析场景 - 从数据采集到选品简报生成的全链路自动化",
        "nodes": [
            {
                "node_id": "data_collection",
                "node_type": "data_node",
                "config": {
                    "agent": "market_analyst",
                    "params": {
                        "task": "collect_product_data",
                        "data_source": "product_selection_data"
                    },
                    "output_fields": ["products", "competitors", "market_trends"]
                },
                "next": "market_analysis"
            },
            {
                "node_id": "market_analysis",
                "node_type": "agent_node",
                "config": {
                    "agent": "market_analyst",
                    "params": {
                        "task": "analyze_market_trends",
                        "analysis_type": "market_trends"
                    }
                },
                "next": "competitor_analysis"
            },
            {
                "node_id": "competitor_analysis",
                "node_type": "agent_node",
                "config": {
                    "agent": "competitor_analyst",
                    "params": {
                        "task": "analyze_competitors",
                        "analysis_type": "competitor_benchmark"
                    }
                },
                "next": "profitability_assessment"
            },
            {
                "node_id": "profitability_assessment",
                "node_type": "agent_node",
                "config": {
                    "agent": "market_analyst",
                    "params": {
                        "task": "assess_profitability",
                        "assessment_type": "roi_analysis"
                    }
                },
                "next": "briefing_generation"
            },
            {
                "node_id": "briefing_generation",
                "node_type": "agent_node",
                "config": {
                    "agent": "briefing_generator",
                    "params": {
                        "task": "generate_briefing",
                        "format": "markdown"
                    }
                },
                "next": "output_result"
            },
            {
                "node_id": "output_result",
                "node_type": "output_node",
                "config": {
                    "output_fields": ["briefing", "summary", "market_analysis", "competitor_analysis", "profitability"]
                }
            }
        ]
    },
    "amazon_market_monitor": {
        "graph_id": "amazon_market_monitor_graph",
        "version": "1.0",
        "description": "亚马逊实时市场监控场景 - 关键词扩展→商品采集→评论分析→流量分析→机会判断→预警通知",
        "nodes": [
            {
                "node_id": "keyword_expansion",
                "node_type": "agent_node",
                "config": {
                    "agent": "keyword_expander",
                    "params": {
                        "task": "expand_keywords",
                        "expand_count": 20,
                        "include_long_tail": true
                    }
                },
                "next": "product_collection"
            },
            {
                "node_id": "product_collection",
                "node_type": "agent_node",
                "config": {
                    "agent": "product_collector",
                    "params": {
                        "task": "collect_products",
                        "max_results": 50
                    }
                },
                "next": "review_analysis"
            },
            {
                "node_id": "review_analysis",
                "node_type": "agent_node",
                "config": {
                    "agent": "review_analyzer",
                    "params": {
                        "task": "analyze_reviews",
                        "sentiment_analysis": true
                    }
                },
                "next": "traffic_analysis"
            },
            {
                "node_id": "traffic_analysis",
                "node_type": "agent_node",
                "config": {
                    "agent": "traffic_analyzer",
                    "params": {
                        "task": "analyze_traffic",
                        "include_bsr_trend": true
                    }
                },
                "next": "opportunity_judgment"
            },
            {
                "node_id": "opportunity_judgment",
                "node_type": "agent_node",
                "config": {
                    "agent": "opportunity_judge",
                    "params": {
                        "task": "judge_opportunity",
                        "min_rating": 3.5,
                        "min_review_count": 10
                    }
                },
                "next": "alert_notification"
            },
            {
                "node_id": "alert_notification",
                "node_type": "output_node",
                "config": {
                    "output_fields": ["market_report", "price_alerts", "opportunities", "recommendations"]
                }
            }
        ]
    }
}

def create_graph_from_scenario(scenario: str, custom_config: Optional[Dict[str, Any]] = None) -> GraphDefinition:
    """
    根据场景创建图定义
    
    Args:
        scenario: 场景名称
        custom_config: 自定义配置
        
    Returns:
        GraphDefinition对象
    """
    if scenario not in SCENARIO_GRAPHS:
        raise ValueError(f"未知的场景: {scenario}")
    
    config = SCENARIO_GRAPHS[scenario]
    if custom_config:
        # 合并自定义配置
        config = {**config, **custom_config}
    
    graph = GraphDefinition(
        graph_id=config["graph_id"],
        version=config["version"],
        description=config["description"]
    )
    
    # 添加节点
    for node_config in config["nodes"]:
        node = NodeDefinition(
            node_id=node_config["node_id"],
            node_type=NodeType[node_config["node_type"].upper()],
            config=node_config["config"],
            next_node=node_config.get("next")
        )
        graph.add_node(node)
    
    return graph

@router.post("/run", response_model=GraphRunResponse, tags=["Graph"])
async def run_graph(request: GraphRunRequest):
    """
    执行Graph
    
    所有AI行为必须通过此入口执行
    输入规范:
    {
      "scenario": "email_briefing",
      "input": {},
      "env": "sandbox"
    }
    """
    try:
        logger.info(f"Graph执行请求: scenario={request.scenario}, env={request.env}")
        
        # 1. 创建图定义
        graph = create_graph_from_scenario(request.scenario, request.graph_config)
        
        # 2. 创建初始状态
        initial_state = State(
            data=request.input,
            metadata={
                "scenario": request.scenario,
                "env": request.env,
                "request_id": f"graph_{request.scenario}_{id(request)}"
            }
        )
        
        # 3. 执行Graph
        engine = DeterministicGraphEngine()
        result = await engine.run_async(graph, initial_state)
        
        # 4. 提取执行信息
        execution_metadata = result.get("execution_metadata", {})
        execution_path = execution_metadata.get("actual_path", [])
        
        # 5. 构建响应
        response = GraphRunResponse(
            success=True,
            result=result.get("data", {}),
            trace_id=execution_metadata.get("execution_id"),
            execution_path=execution_path,
            error=None
        )
        
        logger.info(f"Graph执行成功: scenario={request.scenario}, trace_id={response.trace_id}")
        return response
        
    except ValueError as e:
        logger.error(f"Graph执行参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Graph执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"Graph执行失败: {str(e)}")

@router.get("/scenarios", tags=["Graph"])
async def list_scenarios():
    """
    获取支持的场景列表
    """
    return {
        "scenarios": list(SCENARIO_GRAPHS.keys()),
        "details": SCENARIO_GRAPHS
    }

@router.get("/schema", tags=["Graph"])
async def get_graph_schema(scenario: str = None):
    """
    获取Graph Schema
    
    如果提供scenario参数，返回特定场景的Graph定义
    如果不提供scenario参数，返回所有场景的Graph定义
    """
    try:
        if scenario:
            if scenario not in SCENARIO_GRAPHS:
                raise HTTPException(status_code=404, detail=f"场景 '{scenario}' 不存在")
            
            # 创建Graph定义以获取完整结构
            graph = create_graph_from_scenario(scenario)
            
            # 转换为前端可用的格式
            schema = {
                "scenario": scenario,
                "graph_id": graph.graph_id,
                "version": graph.version,
                "description": graph.description,
                "nodes": [],
                "edges": []
            }
            
            # 添加节点
            for node in graph.nodes:
                node_data = {
                    "id": node.node_id,
                    "type": node.node_type.value,
                    "name": node.node_id,
                    "config": node.config,
                    "status": "idle"  # 默认状态
                }
                schema["nodes"].append(node_data)
                
                # 添加边（连接关系）
                if node.next_node:
                    edge = {
                        "id": f"{node.node_id}_{node.next_node}",
                        "source": node.node_id,
                        "target": node.next_node,
                        "type": "default"
                    }
                    schema["edges"].append(edge)
            
            return schema
        else:
            # 返回所有场景的概览
            scenarios_overview = []
            for scenario_name in SCENARIO_GRAPHS.keys():
                graph = create_graph_from_scenario(scenario_name)
                scenarios_overview.append({
                    "scenario": scenario_name,
                    "graph_id": graph.graph_id,
                    "version": graph.version,
                    "description": graph.description,
                    "node_count": len(graph.nodes)
                })
            
            return {
                "scenarios": scenarios_overview,
                "total": len(scenarios_overview)
            }
            
    except Exception as e:
        logger.error(f"获取Graph Schema失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Graph Schema失败: {str(e)}")

@router.post("/execute", response_model=GraphRunResponse, tags=["Graph"])
async def execute_graph(request: GraphExecuteRequest):
    """
    执行Graph（基于SOP名称）
    
    前端Workspace调用此接口执行选品分析等SOP任务
    输入规范:
    {
      "sop_name": "product_selection",
      "input": {},
      "env": "sandbox"
    }
    """
    try:
        logger.info(f"Graph执行请求: sop_name={request.sop_name}, env={request.env}")
        
        # SOP名称到场景名称的映射
        sop_to_scenario = {
            "product_selection": "product_selection",
            "email_briefing": "email_briefing",
            "daily_report": "daily_report",
            "amazon_monitor": "amazon_market_monitor",
        }
        
        scenario = sop_to_scenario.get(request.sop_name)
        if not scenario:
            raise HTTPException(status_code=400, detail=f"未知的SOP: {request.sop_name}")
        
        if scenario not in SCENARIO_GRAPHS:
            raise HTTPException(status_code=400, detail=f"SOP '{request.sop_name}' 对应的场景 '{scenario}' 未配置")
        
        # 1. 创建图定义
        graph = create_graph_from_scenario(scenario)
        
        # 2. 创建初始状态
        initial_state = State(
            data=request.input,
            metadata={
                "scenario": scenario,
                "sop_name": request.sop_name,
                "env": request.env,
                "request_id": f"graph_{scenario}_{id(request)}"
            }
        )
        
        # 3. 执行Graph
        engine = DeterministicGraphEngine()
        result = await engine.run_async(graph, initial_state)
        
        # 4. 提取执行信息
        execution_metadata = result.get("execution_metadata", {})
        execution_path = execution_metadata.get("actual_path", [])
        
        # 5. 构建响应
        response = GraphRunResponse(
            success=True,
            result=result.get("data", {}),
            trace_id=execution_metadata.get("execution_id"),
            execution_path=execution_path,
            error=None
        )
        
        logger.info(f"Graph执行成功: sop_name={request.sop_name}, trace_id={response.trace_id}")
        return response
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Graph执行参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Graph执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"Graph执行失败: {str(e)}")

@router.get("/status/{trace_id}", tags=["Graph"])
async def get_graph_status(trace_id: str):
    """
    获取Graph执行状态
    
    前端轮询此接口获取执行进度
    """
    try:
        # 从Trace系统获取执行状态
        from backend.data.models.trace import Trace
        from backend.data.database import get_session
        
        async for session in get_session():
            trace = await session.get(Trace, trace_id)
            if not trace:
                raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' 不存在")
            
            return {
                "trace_id": trace.id,
                "status": trace.status,
                "progress": trace.progress if hasattr(trace, 'progress') else None,
                "current_node": trace.current_node if hasattr(trace, 'current_node') else None,
                "result": trace.result if hasattr(trace, 'result') else None,
                "error": trace.error if hasattr(trace, 'error') else None,
                "started_at": trace.started_at.isoformat() if trace.started_at else None,
                "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Graph状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Graph状态失败: {str(e)}")

@router.get("/health", tags=["Graph"])
async def graph_health():
    """
    Graph API健康检查
    """
    return {
        "status": "healthy",
        "api": "graph",
        "version": "1.0",
        "scenarios_count": len(SCENARIO_GRAPHS)
    }
