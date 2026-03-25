import client from './client';

/**
 * 用户登录
 * @param {Object} data - { email, password }
 * @returns {Promise} { token, user }
 */
export async function login(data) {
  const response = await client.post('/auth/login', data);
  // 后端返回 { access_token, token_type }
  return {
    token: response.access_token,
    user: null,  // 如果后端返回用户信息，可在此提取
  };
}

/**
 * 用户注册
 * @param {Object} data - { name, email, password }
 * @returns {Promise} { token, user }
 */
export async function register(data) {
  const response = await client.post('/auth/register', data);
  return {
    token: response.access_token,
    user: null,
  };
}

/**
 * 获取当前用户信息
 * @returns {Promise} { user }
 */
export function getCurrentUser() {
  return client.get('/auth/me');
}

/**
 * 修改密码
 * @param {Object} data - { oldPassword, newPassword }
 * @returns {Promise}
 */
export function changePassword(data) {
  return client.post('/auth/change-password', data);
}

/**
 * 退出登录
 * @returns {Promise}
 */
export function logout() {
  return client.post('/auth/logout');
}