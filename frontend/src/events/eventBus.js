/**
 * VOE事件总线 - 全局发布订阅系统
 * 
 * 实现轻量级事件总线，支持：
 * - on(event, callback) 订阅事件
 * - emit(event, payload) 发布事件
 * - off(event) 取消订阅
 * 
 * 规则：
 * - 单例模式
 * - 不包含业务逻辑
 * - 不依赖第三方库
 */

class EventBus {
  constructor() {
    // 事件监听器映射表
    this.listeners = new Map()
  }

  /**
   * 订阅事件
   * @param {string} event - 事件名称
   * @param {Function} callback - 回调函数
   * @returns {Function} 取消订阅函数
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set())
    }
    
    this.listeners.get(event).add(callback)
    
    // 返回取消订阅函数
    return () => {
      this.off(event, callback)
    }
  }

  /**
   * 发布事件
   * @param {string} event - 事件名称
   * @param {any} payload - 事件数据
   */
  emit(event, payload) {
    if (!this.listeners.has(event)) {
      return
    }
    
    const callbacks = this.listeners.get(event)
    callbacks.forEach(callback => {
      try {
        callback(payload)
      } catch (error) {
        console.error(`Error in event listener for "${event}":`, error)
      }
    })
  }

  /**
   * 取消订阅
   * @param {string} event - 事件名称
   * @param {Function} callback - 要移除的回调函数（可选）
   */
  off(event, callback) {
    if (!this.listeners.has(event)) {
      return
    }
    
    if (callback) {
      // 移除特定回调
      const callbacks = this.listeners.get(event)
      callbacks.delete(callback)
      
      // 如果没有回调了，删除事件
      if (callbacks.size === 0) {
        this.listeners.delete(event)
      }
    } else {
      // 移除所有该事件的回调
      this.listeners.delete(event)
    }
  }

  /**
   * 检查是否有事件监听器
   * @param {string} event - 事件名称
   * @returns {boolean} 是否有监听器
   */
  hasListeners(event) {
    return this.listeners.has(event) && this.listeners.get(event).size > 0
  }

  /**
   * 获取事件监听器数量
   * @param {string} event - 事件名称
   * @returns {number} 监听器数量
   */
  listenerCount(event) {
    if (!this.listeners.has(event)) {
      return 0
    }
    return this.listeners.get(event).size
  }

  /**
   * 清除所有事件监听器
   */
  clear() {
    this.listeners.clear()
  }
}

// 创建单例实例
let instance = null

/**
 * 获取EventBus单例实例
 * @returns {EventBus} EventBus实例
 */
export function getEventBus() {
  if (!instance) {
    instance = new EventBus()
  }
  return instance
}

/**
 * 重置EventBus（主要用于测试）
 */
export function resetEventBus() {
  if (instance) {
    instance.clear()
  }
  instance = null
}

// 导出默认实例
export default getEventBus()