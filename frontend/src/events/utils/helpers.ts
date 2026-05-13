export function generateId(): string {
  return 'id_' + Date.now() + '_' + Math.random().toString(36).substring(2, 11)
}

interface ValidationResult {
  isValid: boolean
  errors: string[]
}

export function validateEventData(
  data: unknown,
  requiredFields: string[] = []
): ValidationResult {
  const errors: string[] = []
  if (!data || typeof data !== 'object') {
    errors.push('事件数据必须是一个对象')
    return { isValid: false, errors }
  }
  const obj = data as Record<string, unknown>
  for (const field of requiredFields) {
    if (!(field in obj)) errors.push(`缺少必需字段: ${field}`)
  }
  if (!obj.timestamp) {
    errors.push('事件数据必须包含timestamp字段')
  } else if (typeof obj.timestamp !== 'number') {
    errors.push('timestamp字段必须是数字')
  }
  return { isValid: errors.length === 0, errors }
}

export function normalizeEventData(
  eventType: string,
  data: Record<string, unknown> = {},
  source: string = 'unknown'
): Record<string, unknown> {
  return {
    eventType,
    ...data,
    timestamp: data.timestamp || Date.now(),
    source: data.source || source,
    eventId: data.eventId || generateId(),
  }
}

export function safeExecute<T>(
  fn: () => T,
  context: string = 'unknown',
  defaultValue: T | null = null
): T | null {
  try {
    return fn()
  } catch (error) {
    console.error(`Error in ${context}:`, error)
    return defaultValue
  }
}

export async function safeExecuteAsync<T>(
  fn: () => Promise<T>,
  context: string = 'unknown',
  defaultValue: T | null = null
): Promise<T | null> {
  try {
    return await fn()
  } catch (error) {
    console.error(`Error in ${context}:`, error)
    return defaultValue
  }
}

export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  delay: number = 300
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null
  return (...args: Parameters<T>): void => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      fn(...args)
      timer = null
    }, delay)
  }
}

export function throttle<T extends (...args: unknown[]) => void>(
  fn: T,
  interval: number = 300
): (...args: Parameters<T>) => void {
  let lastTime = 0
  return (...args: Parameters<T>): void => {
    const now = Date.now()
    if (now - lastTime >= interval) {
      fn(...args)
      lastTime = now
    }
  }
}

export function deepMerge(
  target: Record<string, unknown>,
  source: Record<string, unknown>
): Record<string, unknown> {
  const result = { ...target }
  for (const key in source) {
    if (Object.prototype.hasOwnProperty.call(source, key)) {
      const val = source[key]
      if (val && typeof val === 'object' && !Array.isArray(val)) {
        result[key] = deepMerge(
          (result[key] as Record<string, unknown>) || {},
          val as Record<string, unknown>
        )
      } else {
        result[key] = val
      }
    }
  }
  return result
}

interface EventListenerWrapperOptions {
  logEvent?: boolean
  validateData?: boolean
  requiredFields?: string[]
  errorHandler?: ((err: Error) => void) | null
}

export function createEventListenerWrapper(
  callback: (payload: unknown) => void,
  options: EventListenerWrapperOptions = {}
): (payload: unknown) => void {
  const { logEvent = false, validateData: vd = false, requiredFields = [], errorHandler = null } = options
  return (payload: unknown): void => {
    if (vd) {
      const validation = validateEventData(payload, requiredFields)
      if (!validation.isValid) {
        console.error('事件数据验证失败:', validation.errors)
        errorHandler?.(new Error(`事件数据验证失败: ${validation.errors.join(', ')}`))
        return
      }
    }
    if (logEvent) {
      const p = payload as Record<string, unknown>
      console.log(`事件处理: ${p.eventType || 'unknown'}`, payload)
    }
    try {
      callback(payload)
    } catch (error) {
      console.error('事件处理错误:', error)
      errorHandler?.(error as Error)
    }
  }
}

interface EventEmitterWrapperOptions {
  logEvent?: boolean
  validateData?: boolean
  requiredFields?: string[]
  normalizeData?: boolean
}

export function createEventEmitterWrapper(
  emitter: (event: string, payload: unknown) => void,
  options: EventEmitterWrapperOptions = {}
): (eventType: string, payload?: Record<string, unknown>) => void {
  const { logEvent = false, validateData: vd = false, requiredFields = [], normalizeData: nd = false } = options
  return (eventType: string, payload: Record<string, unknown> = {}): void => {
    let finalPayload: Record<string, unknown> = { ...payload }
    if (nd) finalPayload = normalizeEventData(eventType, finalPayload, 'wrapped-emitter')
    if (vd) {
      const validation = validateEventData(finalPayload, requiredFields)
      if (!validation.isValid) {
        console.error('事件数据验证失败:', validation.errors)
        return
      }
    }
    if (logEvent) console.log(`事件发射: ${eventType}`, finalPayload)
    emitter(eventType, finalPayload)
  }
}

export function measureExecutionTime<T>(fn: () => T, label: string = 'Execution'): T {
  const start = performance.now()
  const result = fn()
  const end = performance.now()
  console.log(`${label} took ${(end - start).toFixed(2)}ms`)
  return result
}

export async function measureExecutionTimeAsync<T>(
  fn: () => Promise<T>,
  label: string = 'Execution'
): Promise<T> {
  const start = performance.now()
  const result = await fn()
  const end = performance.now()
  console.log(`${label} took ${(end - start).toFixed(2)}ms`)
  return result
}

interface EventTracker {
  markSuccess: () => EventTracker
  markError: (err: Error) => EventTracker
  getResult: () => {
    eventType: string
    startTime: number
    endTime: number | null
    duration: number | null
    success: boolean
    error: string | null
  }
  log: () => {
    eventType: string
    startTime: number
    endTime: number | null
    duration: number | null
    success: boolean
    error: string | null
  }
}

export function createEventTracker(eventType: string): EventTracker {
  const startTime = Date.now()
  let endTime: number | null = null
  let success = false
  let error: Error | null = null
  return {
    markSuccess() {
      endTime = Date.now()
      success = true
      return this
    },
    markError(err: Error) {
      endTime = Date.now()
      success = false
      error = err
      return this
    },
    getResult() {
      const duration = endTime ? endTime - startTime : null
      return { eventType, startTime, endTime, duration, success, error: error ? error.message : null }
    },
    log() {
      const result = this.getResult()
      if (success) console.log(`✅ ${eventType} completed in ${result.duration}ms`)
      else console.error(`❌ ${eventType} failed: ${result.error}`)
      return result
    },
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
  createEventTracker,
}