import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { login as apiLogin, register as apiRegister, getCurrentUser, logout as apiLogout, changePassword } from '@/api/auth';
// import client from './client';

const MOCK_USER = {
  id: 'dev-user',
  name: '开发者模式',
  email: 'dev@nova.local'
};

export const useAuthStore = defineStore('auth', () => {
  // 状态
  // const token = ref(localStorage.getItem('nova_token') || null);
  // const user = ref(null);
  const token = ref(localStorage.getItem('nova_token') || 'mock-token-for-dev'); // 强制有 token
  const user = ref(MOCK_USER); // 强制有用户信息
  const loading = ref(false);
  const error = ref(null);

  // 计算属性
  // const isAuthenticated = computed(() => !!token.value);
  const isAuthenticated = computed(() => true); // 直接返回 true
  const userName = computed(() => user.value?.name || '');
  const userEmail = computed(() => user.value?.email || '');

  // 初始化：从本地存储恢复 token 并获取用户信息
  const init = async () => {
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
  const login = async (credentials) => {
    loading.value = true;
    error.value = null;
    try {
      const res = await apiLogin(credentials);
      token.value = res.token;
      user.value = res.user;
      localStorage.setItem('nova_token', res.token);
      return res;
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 注册
  const register = async (userData) => {
    loading.value = true;
    error.value = null;
    try {
      const res = await apiRegister(userData);
      token.value = res.token;
      user.value = res.user;
      localStorage.setItem('nova_token', res.token);
      return res;
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 退出
  const logout = async () => {
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
  const updatePassword = async (data) => {
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