import client from './client';

/**
 * 获取用户设置
 * @returns {Promise} { settings }
 */
export function getSettings() {
  return client.get('/settings');
}

/**
 * 更新用户设置
 * @param {Object} data - 要更新的设置字段
 * @returns {Promise} { settings }
 */
export function updateSettings(data) {
  return client.put('/settings', data);
}

/**
 * 获取通知偏好
 * @returns {Promise} { notifications }
 */
export function getNotificationPreferences() {
  return client.get('/settings/notifications');
}

/**
 * 更新通知偏好
 * @param {Object} data
 * @returns {Promise}
 */
export function updateNotificationPreferences(data) {
  return client.put('/settings/notifications', data);
}

/**
 * 获取个人资料
 * @returns {Promise} { profile }
 */
export function getProfile() {
  return client.get('/settings/profile');
}

/**
 * 更新个人资料
 * @param {Object} data - { name, avatar, ... }
 * @returns {Promise}
 */
export function updateProfile(data) {
  return client.put('/settings/profile', data);
}

export const getCurrentUser = getProfile; // 别名导出