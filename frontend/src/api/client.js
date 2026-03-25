import axios from 'axios';

// 从环境变量获取 API 基础路径，默认为 /api/v1
const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// 创建 axios 实例
const client = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：自动添加 JWT token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('nova_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器：统一处理错误
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      // 后端返回的错误信息
      const { status, data } = error.response;
      let message = data?.message || '请求失败';
      if (status === 401) {
        // 未授权，清除 token 并跳转登录页
        localStorage.removeItem('nova_token');
        // 注意：若在 Vue Router 中，可调用 router.push('/login')，但这里不引入 router 避免循环依赖
        window.location.href = '/login';
      }
      return Promise.reject({ status, message, data });
    } else if (error.request) {
      // 网络错误
      return Promise.reject({ status: 0, message: '网络错误，请检查连接', data: null });
    } else {
      return Promise.reject({ status: -1, message: error.message, data: null });
    }
  }
);

export default client;