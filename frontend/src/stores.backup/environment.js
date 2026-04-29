import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useEnvironmentStore = defineStore('environment', () => {
  // 环境状态：'sandbox' 或 'production'
  const currentEnv = ref(localStorage.getItem('nova_env') || 'sandbox');
  
  // 环境配置
  const envConfig = {
    sandbox: {
      name: '沙盒环境',
      description: '用于开发和测试',
      color: 'warning',
      icon: 'Box',
      apiBaseUrl: 'http://localhost:8000/api/v1',
      mockMode: true
    },
    production: {
      name: '生产环境',
      description: '正式运行环境',
      color: 'success',
      icon: 'Check',
      apiBaseUrl: 'https://api.nova.com/api/v1',
      mockMode: false
    }
  };

  // 当前环境配置
  const currentConfig = computed(() => envConfig[currentEnv.value]);

  // 切换环境
  const switchEnv = (env) => {
    if (env !== 'sandbox' && env !== 'production') {
      console.error('无效的环境:', env);
      return;
    }
    
    currentEnv.value = env;
    localStorage.setItem('nova_env', env);
    
    console.log(`环境已切换到: ${env}`, currentConfig.value);
    
    // 触发环境切换事件（其他组件可以监听）
    window.dispatchEvent(new CustomEvent('env-changed', { 
      detail: { env, config: currentConfig.value }
    }));
  };

  // 获取带环境参数的API调用函数
  const withEnvParam = (fn) => {
    return (...args) => {
      // 在参数中添加env参数
      const params = args.length > 0 && typeof args[args.length - 1] === 'object' 
        ? args[args.length - 1]
        : {};
      
      const newParams = {
        ...params,
        _env: currentEnv.value,
        _env_config: currentConfig.value
      };
      
      // 如果是mock模式，使用mock函数
      if (currentConfig.value.mockMode) {
        console.log(`[Mock] 调用函数 ${fn.name || 'anonymous'} 在 ${currentEnv.value} 环境`, newParams);
        return Promise.resolve({ 
          success: true, 
          message: `Mock response from ${currentEnv.value}`,
          data: { mock: true, env: currentEnv.value }
        });
      }
      
      // 否则调用原始函数
      return fn(...args);
    };
  };

  // 创建mock API函数
  const createMockApi = (name, mockData = {}) => {
    return (params = {}) => {
      console.log(`[Mock API] ${name} called with params:`, params);
      console.log(`[Mock API] Current environment: ${currentEnv.value}`);
      
      return Promise.resolve({
        success: true,
        message: `Mock ${name} response from ${currentEnv.value}`,
        data: {
          ...mockData,
          env: currentEnv.value,
          timestamp: new Date().toISOString(),
          params
        }
      });
    };
  };

  return {
    currentEnv,
    currentConfig,
    envConfig,
    switchEnv,
    withEnvParam,
    createMockApi
  };
});