import client from './client';
import type { AuthResponse, User } from '@/types';

/**
 * 用户登录
 * @param data - { email, password }
 */
export async function login(data: { email: string; password: string }): Promise<AuthResponse> {
  const response = await client.post('/auth/login', data) as unknown as { access_token: string; user?: User };
  return {
    token: response.access_token,
    user: response.user || (null as unknown as User),
  };
}

/**
 * 用户注册
 * @param data - { name, email, password }
 */
export async function register(data: { name: string; email: string; password: string }): Promise<AuthResponse> {
  const response = await client.post('/auth/register', data) as unknown as { access_token: string; user?: User };
  return {
    token: response.access_token,
    user: response.user || (null as unknown as User),
  };
}

/**
 * 获取当前用户信息
 */
export async function getCurrentUser(): Promise<{ user: User }> {
  const response = await client.get('/auth/me') as unknown as User;
  return { user: response };
}

/**
 * 修改密码
 * @param data - { oldPassword, newPassword }
 */
export async function changePassword(data: { oldPassword: string; newPassword: string }): Promise<unknown> {
  return client.post('/auth/change-password', data);
}

/**
 * 退出登录
 */
export async function logout(): Promise<unknown> {
  return client.post('/auth/logout');
}
