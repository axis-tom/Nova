import client from './client';

/**
 * 获取审计日志列表（支持分页和筛选）
 * @param params - { page, limit, startDate, endDate, level, agent }
 */
export function getLogs(params: Record<string, unknown> = {}): Promise<{ items: unknown[]; total: number; page: number; limit: number }> {
  return client.get('/logs', { params });
}

/**
 * 获取日志详情
 * @param id - 日志ID
 */
export function getLog(id: string | number): Promise<{ log: unknown }> {
  return client.get(`/logs/${id}`);
}

/**
 * 导出日志（返回 Blob）
 * @param params - 筛选条件
 */
export function exportLogs(params: Record<string, unknown> = {}): Promise<Blob> {
  return client.get('/logs/export', { params, responseType: 'blob' });
}
