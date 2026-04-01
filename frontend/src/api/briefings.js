import client from './client';

/**
 * 获取简报列表（支持分页）
 * @param {Object} params - { page, limit, sort }
 * @returns {Promise} { items: [], total, page, limit }
 */
export function getBriefings(params = {}) {
  // 将前端常用的 page/limit 转换为后端需要的 skip/limit
  let { page, limit, skip, ...rest } = params;

  // 如果传入了 page 和 limit，则自动计算 skip
  if (page !== undefined && limit !== undefined) {
    skip = (page - 1) * limit;
    // 保留 limit 用于后端
  } else if (skip === undefined) {
    skip = 0;
  }
  if (limit === undefined) limit = 10;

  // 使用带斜杠的 URL，避免重定向丢失认证头
  return client.get('/briefings/', { params: { skip, limit, ...rest } });
}

/**
 * 获取单个简报详情
 * @param {string|number} id
 * @returns {Promise} { briefing }
 */
export function getBriefing(id) {
  return client.get(`/briefings/${id}`);
}

/**
 * 生成新的简报（异步任务，返回 task_id 或直接返回结果）
 * @param {Object} data - 生成参数（如时间范围、数据源等）
 * @returns {Promise} { taskId, briefing? }
 */
export function generateBriefing(data) {
  return client.post('/briefings/generate', data);
}

/**
 * 删除简报
 * @param {string|number} id
 * @returns {Promise}
 */
export function deleteBriefing(id) {
  return client.delete(`/briefings/${id}`);
}

/**
 * 获取简报生成任务状态（若生成是异步的）
 * @param {string} taskId
 * @returns {Promise} { status, briefing? }
 */
export function getBriefingTaskStatus(taskId) {
  return client.get(`/briefings/tasks/${taskId}`);
}
