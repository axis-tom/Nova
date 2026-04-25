import client from './client';
import type { AuthResponse, User } from '@/types';

/**
 * 用户登录
 * @param data - { email, password }
 */
export async function login(data: { email: string; password: string }): Promise<AuthResponse> {
  const response = await client.post('/auth/login', data);
  // 后端返回 { access_token, token_type }
  const responseData = response.data as { access_token: string; user?: User };
  return {
    token: responseData.access_token,
    user: responseData.user || (null as unknown as User),
  };
}

/**
 * 用户注册
 * @param data - { name, email, password }
 */
export async function register(data: { name: string; email: string; password: string }): Promise<AuthResponse> {
  const response = await client.post('/auth/register', data);
  const responseData = response.data as { access_token: string; user?: User };
  return {
    token: responseData.access_token,
    user: responseData.user || (null as unknown as User),
  };
}

/**
 * 获取当前用户信息
 */
export async function getCurrentUser(): Promise<{ user: User }> {
  const response = await client.get('/auth/me');
  return response.data as { user: User };
}

/**
 * 修改密码
 * @param data - { oldPassword, newPassword }
 */
export async function changePassword(data: { oldPassword: string; newPassword: string }): Promise<unknown> {
  const response = await client.post('/auth/change-password', data);
  return response.data;
}

/**
 * 退出登录
 */
export async function logout(): Promise<unknown> {
  const response = await client.post('/auth/logout');
  return response.data;
}
