import client from './client';

/**
 * 获取所有数据源
 * @returns {Promise} { sources: [] }
 */
export function getDataSources() {
  return client.get('/data-sources');
}

/**
 * 获取单个数据源详情
 * @param {string|number} id
 * @returns {Promise} { source }
 */
export function getDataSource(id) {
  return client.get(`/data-sources/${id}`);
}

/**
 * 创建数据源
 * @param {Object} data - { name, type, config, ... }
 * @returns {Promise} { source }
 */
export function createDataSource(data) {
  return client.post('/data-sources', data);
}

/**
 * 更新数据源
 * @param {string|number} id
 * @param {Object} data
 * @returns {Promise} { source }
 */
export function updateDataSource(id, data) {
  return client.put(`/data-sources/${id}`, data);
}

/**
 * 删除数据源
 * @param {string|number} id
 * @returns {Promise}
 */
export function deleteDataSource(id) {
  return client.delete(`/data-sources/${id}`);
}

/**
 * 测试数据源连接
 * @param {Object} config - 数据源配置
 * @returns {Promise} { success, message }
 */
export function testDataSource(config) {
  return client.post('/data-sources/test', config);
}