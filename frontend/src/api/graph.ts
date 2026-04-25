import client from './client';

/**
 * Graph API模块
 * 提供Graph相关的API调用
 */

/**
 * 获取Graph Schema
 * @param scenario - 场景名称（可选）
 */
export async function getGraphSchema(scenario: string | null = null): Promise<unknown> {
  const params = scenario ? { scenario } : {};
  return client.get('/graph/schema', { params });
}

/**
 * 执行Graph
 * @param request - 执行请求
 */
export async function runGraph(request: {
  scenario: string;
  input: Record<string, unknown>;
  env: string;
  graph_config?: Record<string, unknown>;
}): Promise<unknown> {
  return client.post('/graph/run', request);
}

/**
 * 获取支持的场景列表
 */
export async function listScenarios(): Promise<unknown> {
  return client.get('/graph/scenarios');
}

/**
 * 获取Graph健康状态
 */
export async function getGraphHealth(): Promise<unknown> {
  return client.get('/graph/health');
}

/**
 * 获取Trace详情
 * @param traceId - Trace ID
 */
export async function getTraceDetails(traceId: string): Promise<unknown> {
  return client.get(`/trace/${traceId}`);
}

/**
 * 搜索Trace会话
 * @param params - 搜索参数
 */
export async function searchTraces(params: Record<string, unknown> = {}): Promise<unknown> {
  return client.get('/trace/', { params });
}

/**
 * 获取Trace调试信息
 * @param traceId - Trace ID
 */
export async function getTraceDebugInfo(traceId: string): Promise<unknown> {
  return client.get(`/trace/${traceId}/debug`);
}

/**
 * 回放Trace执行
 * @param traceId - Trace ID
 * @param replayConfig - 回放配置
 */
export async function replayTrace(traceId: string, replayConfig: Record<string, unknown> = {}): Promise<unknown> {
  return client.post(`/trace/${traceId}/replay`, replayConfig);
}

/**
 * 重试Trace执行
 * @param traceId - Trace ID
 */
export async function retryTrace(traceId: string): Promise<unknown> {
  return client.post(`/trace/${traceId}/retry`);
}

/**
 * 获取Trace节点详情
 * @param traceId - Trace ID
 * @param nodeId - 节点ID
 */
export async function getTraceNodeDetail(traceId: string, nodeId: string): Promise<unknown> {
  return client.get(`/trace/${traceId}/node/${nodeId}`);
}

/**
 * 订阅Graph执行状态（WebSocket）
 * @param traceId - Trace ID
 */
export function subscribeToGraphExecution(traceId: string): WebSocket {
  const wsUrl = `${import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000'}/ws/graph/${traceId}`;
  return new WebSocket(wsUrl);
}
