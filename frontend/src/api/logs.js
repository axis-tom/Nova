import client from './client';

/**
 * 获取审计日志列表（支持分页和筛选）
 * @param {Object} params - { page, limit, startDate, endDate, level, agent }
 * @returns {Promise} { items: [], total, page, limit }
 */
export function getLogs(params = {}) {
  return client.get('/logs', { params });
}

/**
 * 获取日志详情
 * @param {string|number} id
 * @returns {Promise} { log }
 */
export function getLog(id) {
  return client.get(`/logs/${id}`);
}

/**
 * 导出日志（返回 Blob）
 * @param {Object} params - 筛选条件
 * @returns {Promise<Blob>}
 */
export function exportLogs(params = {}) {
  return client.get('/logs/export', { params, responseType: 'blob' });
}