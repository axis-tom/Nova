import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

interface EnvironmentConfig {
  name: string
  description: string
  color: string
  icon: string
  apiBaseUrl: string
  mockMode: boolean
}

type EnvType = 'sandbox' | 'production'

export const useEnvironmentStore = defineStore('environment', () => {
  const currentEnv = ref<EnvType>(
    (localStorage.getItem('nova_env') as EnvType) || 'sandbox'
  )

  const envConfig: Record<EnvType, EnvironmentConfig> = {
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
  }

  const currentConfig = computed<EnvironmentConfig>(() => envConfig[currentEnv.value])

  const switchEnv = (env: EnvType): void => {
    if (env !== 'sandbox' && env !== 'production') {
      console.error('无效的环境:', env)
      return
    }
    currentEnv.value = env
    localStorage.setItem('nova_env', env)
    console.log(`环境已切换到: ${env}`, currentConfig.value)
    window.dispatchEvent(
      new CustomEvent('env-changed', {
        detail: { env, config: currentConfig.value }
      })
    )
  }

  // 修正类型：让包装函数返回正确的类型
  const withEnvParam = <T extends (...args: any[]) => any>(fn: T): T => {
    return ((...args: any[]) => {
      const lastArg = args.length > 0 && typeof args[args.length - 1] === 'object'
        ? (args[args.length - 1] as Record<string, unknown>)
        : {}

      const newParams = {
        ...lastArg,
        _env: currentEnv.value,
        _env_config: currentConfig.value
      }

      if (currentConfig.value.mockMode) {
        const name = (fn as any).name || 'anonymous'
        console.log(`[Mock] 调用函数 ${name} 在 ${currentEnv.value} 环境`, newParams)
        return Promise.resolve({
          success: true,
          message: `Mock response from ${currentEnv.value}`,
          data: { mock: true, env: currentEnv.value }
        })
      }

      return fn(...args)
    }) as T
  }

  const createMockApi = (
    name: string,
    mockData: Record<string, unknown> = {}
  ) => {
    return (params: Record<string, unknown> = {}): Promise<unknown> => {
      console.log(`[Mock API] ${name} called with params:`, params)
      console.log(`[Mock API] Current environment: ${currentEnv.value}`)
      return Promise.resolve({
        success: true,
        message: `Mock ${name} response from ${currentEnv.value}`,
        data: {
          ...mockData,
          env: currentEnv.value,
          timestamp: new Date().toISOString(),
          params
        }
      })
    }
  }

  return {
    currentEnv,
    currentConfig,
    envConfig,
    switchEnv,
    withEnvParam,
    createMockApi
  }
})