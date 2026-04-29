import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { login as apiLogin, register as apiRegister, getCurrentUser, logout as apiLogout, changePassword } from '@/api/auth';
import type { User, AuthResponse } from '@/types';
// import client from './client';

const MOCK_USER: User = {
  id: 'dev-user',
  name: '开发者模式',
  email: 'dev@nova.local'
};

export const useAuthStore = defineStore('auth', () => {
  // 状态
  // const token = ref(localStorage.getItem('nova_token') || null);
  // const user = ref(null);
  const token = ref<string | null>(localStorage.getItem('nova_token') || 'mock-token-for-dev'); // 强制有 token
  const user = ref<User | null>(MOCK_USER); // 强制有用户信息
  const loading = ref<boolean>(false);
  const error = ref<string | null>(null);

  // 计算属性
  // const isAuthenticated = computed(() => !!token.value);
  const isAuthenticated = computed<boolean>(() => true); // 直接返回 true
  const userName = computed<string>(() => user.value?.name || '');
  const userEmail = computed<string>(() => user.value?.email || '');

  // 初始化：从本地存储恢复 token 并获取用户信息
  const init = async (): Promise<void> => {
    if (token.value) {
      try {
        const res = await getCurrentUser();
        user.value = res.user;
      } catch (err) {
        // token 无效，清除
        token.value = null;
        localStorage.removeItem('nova_token');
      }
    }
  };

  // 登录
  const login = async (credentials: { email: string; password: string }): Promise<AuthResponse> => {
    loading.value = true;
    error.value = null;
    try {
      const res = await apiLogin(credentials);
      token.value = res.token;
      user.value = res.user;
      localStorage.setItem('nova_token', res.token);
      return res;
    } catch (err) {
      error.value = (err as Error).message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 注册
  const register = async (userData: { name: string; email: string; password: string }): Promise<AuthResponse> => {
    loading.value = true;
    error.value = null;
    try {
      const res = await apiRegister(userData);
      token.value = res.token;
      user.value = res.user;
      localStorage.setItem('nova_token', res.token);
      return res;
    } catch (err) {
      error.value = (err as Error).message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 退出
  const logout = async (): Promise<void> => {
    loading.value = true;
    try {
      await apiLogout();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      token.value = null;
      user.value = null;
      localStorage.removeItem('nova_token');
      loading.value = false;
    }
  };

  // 修改密码
  const updatePassword = async (data: { oldPassword: string; newPassword: string }): Promise<void> => {
    loading.value = true;
    try {
      await changePassword(data);
    } finally {
      loading.value = false;
    }
  };

  return {
    token,
    user,
    loading,
    error,
    isAuthenticated,
    userName,
    userEmail,
    init,
    login,
    register,
    logout,
    updatePassword,
  };
});
