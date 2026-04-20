import client from './client.js';

/**
 * Graph API模块
 * 提供Graph相关的API调用
 */

/**
 * 获取Graph Schema
 * @param {string} scenario - 场景名称（可选）
 * @returns {Promise} Graph Schema数据
 */
export async function getGraphSchema(scenario = null) {
  const params = scenario ? { scenario } : {};
  return client.get('/graph/schema', { params });
}

/**
 * 执行Graph
 * @param {Object} request - 执行请求
 * @param {string} request.scenario - 场景名称
 * @param {Object} request.input - 输入数据
 * @param {string} request.env - 执行环境（sandbox/production）
 * @param {Object} request.graph_config - 自定义图配置（可选）
 * @returns {Promise} 执行结果
 */
export async function runGraph(request) {
  return client.post('/graph/run', request);
}

/**
 * 获取支持的场景列表
 * @returns {Promise} 场景列表
 */
export async function listScenarios() {
  return client.get('/graph/scenarios');
}

/**
 * 获取Graph健康状态
 * @returns {Promise} 健康状态
 */
export async function getGraphHealth() {
  return client.get('/graph/health');
}

/**
 * 获取Trace详情
 * @param {string} traceId - Trace ID
 * @returns {Promise} Trace详情
 */
export async function getTraceDetails(traceId) {
  return client.get(`/trace/${traceId}`);
}

/**
 * 搜索Trace会话
 * @param {Object} params - 搜索参数
 * @param {string} params.graph_id - Graph ID筛选
 * @param {string} params.status - 状态筛选
 * @param {string} params.start_date - 开始日期（YYYY-MM-DD）
 * @param {string} params.end_date - 结束日期（YYYY-MM-DD）
 * @param {string} params.tags - 标签筛选（逗号分隔）
 * @param {number} params.limit - 返回数量限制
 * @param {number} params.offset - 偏移量
 * @returns {Promise} Trace列表
 */
export async function searchTraces(params = {}) {
  return client.get('/trace/', { params });
}

/**
 * 获取Trace调试信息
 * @param {string} traceId - Trace ID
 * @returns {Promise} 调试信息
 */
export async function getTraceDebugInfo(traceId) {
  return client.get(`/trace/${traceId}/debug`);
}

/**
 * 回放Trace执行
 * @param {string} traceId - Trace ID
 * @param {Object} replayConfig - 回放配置
 * @param {string} replayConfig.replay_type - 回放类型: full, step_by_step, partial
 * @param {string} replayConfig.start_node - 起始节点（用于部分回放）
 * @param {string} replayConfig.end_node - 结束节点（用于部分回放）
 * @returns {Promise} 回放结果
 */
export async function replayTrace(traceId, replayConfig = {}) {
  return client.post(`/trace/${traceId}/replay`, replayConfig);
}

/**
 * 重试Trace执行
 * @param {string} traceId - Trace ID
 * @returns {Promise} 重试结果
 */
export async function retryTrace(traceId) {
  return client.post(`/trace/${traceId}/retry`);
}

/**
 * 获取Trace节点详情
 * @param {string} traceId - Trace ID
 * @param {string} nodeId - 节点ID
 * @returns {Promise} 节点详情
 */
export async function getTraceNodeDetail(traceId, nodeId) {
  return client.get(`/trace/${traceId}/node/${nodeId}`);
}

/**
 * 订阅Graph执行状态（WebSocket）
 * @param {string} traceId - Trace ID
 * @returns {WebSocket} WebSocket连接
 */
export function subscribeToGraphExecution(traceId) {
  const wsUrl = `${import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000'}/ws/graph/${traceId}`;
  return new WebSocket(wsUrl);
}
