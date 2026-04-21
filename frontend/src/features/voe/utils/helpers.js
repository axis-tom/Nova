/**
 * VOE工具函数
 * 
 * 提供VOE系统常用的工具函数
 */

/**
 * 生成唯一ID
 * @returns {string} 唯一ID
 */
export function generateId() {
  return 'id_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
}

/**
 * 验证事件数据格式
 * @param {Object} data - 事件数据
 * @param {Array} requiredFields - 必需字段数组
 * @returns {Object} 验证结果 { isValid: boolean, errors: Array }
 */
export function validateEventData(data, requiredFields = []) {
  const errors = []
  
  if (!data || typeof data !== 'object') {
    errors.push('事件数据必须是一个对象')
    return { isValid: false, errors }
  }
  
  // 检查必需字段
  for (const field of requiredFields) {
    if (!(field in data)) {
      errors.push(`缺少必需字段: ${field}`)
    }
  }
  
  // 检查timestamp字段
  if (!data.timestamp) {
    errors.push('事件数据必须包含timestamp字段')
  } else if (typeof data.timestamp !== 'number') {
    errors.push('timestamp字段必须是数字')
  }
  
  return {
    isValid: errors.length === 0,
    errors
  }
}

/**
 * 标准化事件数据
 * @param {string} eventType - 事件类型
 * @param {Object} data - 原始数据
 * @param {string} source - 事件来源
 * @returns {Object} 标准化的事件数据
 */
export function normalizeEventData(eventType, data = {}, source = 'unknown') {
  return {
    eventType,
    ...data,
    timestamp: data.timestamp || Date.now(),
    source: data.source || source,
    eventId: data.eventId || generateId()
  }
}

/**
 * 安全执行函数，捕获错误并记录
 * @param {Function} fn - 要执行的函数
 * @param {string} context - 执行上下文描述
 * @param {any} defaultValue - 出错时的默认返回值
 * @returns {any} 函数执行结果或默认值
 */
export function safeExecute(fn, context = 'unknown', defaultValue = null) {
  try {
    return fn()
  } catch (error) {
    console.error(`Error in ${context}:`, error)
    return defaultValue
  }
}

/**
 * 异步安全执行函数
 * @param {Function} fn - 要执行的异步函数
 * @param {string} context - 执行上下文描述
 * @param {any} defaultValue - 出错时的默认返回值
 * @returns {Promise<any>} 函数执行结果或默认值
 */
export async function safeExecuteAsync(fn, context = 'unknown', defaultValue = null) {
  try {
    return await fn()
  } catch (error) {
    console.error(`Error in ${context}:`, error)
    return defaultValue
  }
}

/**
 * 防抖函数
 * @param {Function} fn - 要防抖的函数
 * @param {number} delay - 延迟时间（毫秒）
 * @returns {Function} 防抖后的函数
 */
export function debounce(fn, delay = 300) {
  let timer = null
  return function(...args) {
    if (timer) {
      clearTimeout(timer)
    }
    timer = setTimeout(() => {
      fn.apply(this, args)
      timer = null
    }, delay)
  }
}

/**
 * 节流函数
 * @param {Function} fn - 要节流的函数
 * @param {number} interval - 时间间隔（毫秒）
 * @returns {Function} 节流后的函数
 */
export function throttle(fn, interval = 300) {
  let lastTime = 0
  return function(...args) {
    const now = Date.now()
    if (now - lastTime >= interval) {
      fn.apply(this, args)
      lastTime = now
    }
  }
}

/**
 * 深度合并对象
 * @param {Object} target - 目标对象
 * @param {Object} source - 源对象
 * @returns {Object} 合并后的对象
 */
export function deepMerge(target, source) {
  const result = { ...target }
  
  for (const key in source) {
    if (source.hasOwnProperty(key)) {
      if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
        result[key] = deepMerge(result[key] || {}, source[key])
      } else {
        result[key] = source[key]
      }
    }
  }
  
  return result
}

/**
 * 创建事件监听器包装器
 * @param {Function} callback - 原始回调函数
 * @param {Object} options - 配置选项
 * @returns {Function} 包装后的回调函数
 */
export function createEventListenerWrapper(callback, options = {}) {
  const {
    logEvent = false,
    validateData = false,
    requiredFields = [],
    errorHandler = null
  } = options
  
  return function(payload) {
    // 验证数据
    if (validateData) {
      const validation = validateEventData(payload, requiredFields)
      if (!validation.isValid) {
        console.error('事件数据验证失败:', validation.errors)
        if (errorHandler) {
          errorHandler(new Error(`事件数据验证失败: ${validation.errors.join(', ')}`))
        }
        return
      }
    }
    
    // 记录事件
    if (logEvent) {
      console.log(`事件处理: ${payload.eventType || 'unknown'}`, payload)
    }
    
    // 执行回调
    try {
      return callback(payload)
    } catch (error) {
      console.error('事件处理错误:', error)
      if (errorHandler) {
        errorHandler(error)
      }
    }
  }
}

/**
 * 创建事件发射器包装器
 * @param {Function} emitter - 原始发射器函数
 * @param {Object} options - 配置选项
 * @returns {Function} 包装后的发射器函数
 */
export function createEventEmitterWrapper(emitter, options = {}) {
  const {
    logEvent = false,
    validateData = false,
    requiredFields = [],
    normalizeData = false
  } = options
  
  return function(eventType, payload = {}) {
    let finalPayload = { ...payload }
    
    // 标准化数据
    if (normalizeData) {
      finalPayload = normalizeEventData(eventType, finalPayload, 'wrapped-emitter')
    }
    
    // 验证数据
    if (validateData) {
      const validation = validateEventData(finalPayload, requiredFields)
      if (!validation.isValid) {
        console.error('事件数据验证失败:', validation.errors)
        return
      }
    }
    
    // 记录事件
    if (logEvent) {
      console.log(`事件发射: ${eventType}`, finalPayload)
    }
    
    // 发射事件
    return emitter(eventType, finalPayload)
  }
}

/**
 * 计算执行时间
 * @param {Function} fn - 要计时的函数
 * @param {string} label - 计时标签
 * @returns {any} 函数执行结果
 */
export function measureExecutionTime(fn, label = 'Execution') {
  const start = performance.now()
  const result = fn()
  const end = performance.now()
  console.log(`${label} took ${(end - start).toFixed(2)}ms`)
  return result
}

/**
 * 异步计算执行时间
 * @param {Function} fn - 要计时的异步函数
 * @param {string} label - 计时标签
 * @returns {Promise<any>} 函数执行结果
 */
export async function measureExecutionTimeAsync(fn, label = 'Execution') {
  const start = performance.now()
  const result = await fn()
  const end = performance.now()
  console.log(`${label} took ${(end - start).toFixed(2)}ms`)
  return result
}

/**
 * 创建事件追踪器
 * @param {string} eventType - 事件类型
 * @returns {Object} 事件追踪器
 */
export function createEventTracker(eventType) {
  const startTime = Date.now()
  let endTime = null
  let success = false
  let error = null
  
  return {
    markSuccess() {
      endTime = Date.now()
      success = true
      return this
    },
    
    markError(err) {
      endTime = Date.now()
      success = false
      error = err
      return this
    },
    
    getResult() {
      const duration = endTime ? endTime - startTime : null
      return {
        eventType,
        startTime,
        endTime,
        duration,
        success,
        error: error ? error.message : null
      }
    },
    
    log() {
      const result = this.getResult()
      if (success) {
        console.log(`✅ ${eventType} completed in ${result.duration}ms`)
      } else {
        console.error(`❌ ${eventType} failed: ${result.error}`)
      }
      return result
    }
  }
}

export default {
  generateId,
  validateEventData,
  normalizeEventData,
  safeExecute,
  safeExecuteAsync,
  debounce,
  throttle,
  deepMerge,
  createEventListenerWrapper,
  createEventEmitterWrapper,
  measureExecutionTime,
  measureExecutionTimeAsync,
  createEventTracker
}