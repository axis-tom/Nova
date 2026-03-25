import client from './client';

/**
 * 获取单个优先级事项详情
 * @param {string|number} id
 * @returns {Promise} { priority }
 */
export function getPriority(id) {
  return client.get(`/priority/${id}`);
}

/**
 * 更新优先级事项
 * @param {string|number} id
 * @param {Object} data
 * @returns {Promise} { priority }
 */
export function updatePriority(id, data) {
  return client.put(`/priority/${id}`, data);
}

/**
 * 删除优先级事项
 * @param {string|number} id
 * @returns {Promise}
 */
export function deletePriority(id) {
  return client.delete(`/priority/${id}`);
}

/**
 * 获取优先级事项列表
 * @param {Object} params - { page, limit, status }
 * @returns {Promise} { items: [], total }
 */
export function getPriorities(params = {}) {
  return client.get('/priority', { params });
}