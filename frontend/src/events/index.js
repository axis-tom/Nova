/**
 * VOE事件交互层 - 主入口文件
 * 
 * 导出所有VOE模块，提供统一的初始化接口
 * 实现UI操作 → eventBus → dispatcher → graph → result的完整通信链路
 */

// 导出核心模块
export { default as eventBus } from './eventBus.js'
export * from './eventTypes.js'
export { default as dispatcher, initializeEventDispatcher } from './dispatcher.js'

// 导出Bridge模块
export { default as uiBridge, initializeUIBridge } from './bridge/uiBridge.js'
export { default as graphBridge, initializeGraphBridge } from './bridge/graphBridge.js'
export { default as resultBridge, initializeResultBridge } from './bridge/resultBridge.js'

// 导出Listener模块
export { default as nodeListener, initializeNodeListener } from './listeners/nodeListener.js'
export { default as uiListener, initializeUIListener } from './listeners/uiListener.js'
export { default as graphListener, initializeGraphListener } from './listeners/graphListener.js'

/**
 * VOE系统状态
 */
class VOESystem {
  constructor() {
    this.isInitialized = false
    this.initializationPromise = null
  }

  /**
   * 初始化整个VOE系统
   * @returns {Promise<VOESystem>} 初始化后的VOE系统
   */
  async initialize() {
    if (this.isInitialized) {
      return this
    }
    
    // 防止重复初始化
    if (this.initializationPromise) {
      return this.initializationPromise
    }
    
    this.initializationPromise = this._initializeInternal()
    return this.initializationPromise
  }

  /**
   * 内部初始化逻辑
   */
  async _initializeInternal() {
    try {
      console.log('Initializing VOE Event Interaction Layer...')
      
      // 1. 初始化Bridge
      console.log('Step 1: Initializing bridges...')
      initializeUIBridge()
      await initializeGraphBridge()
      initializeResultBridge()
      
      // 2. 初始化Dispatcher
      console.log('Step 2: Initializing dispatcher...')
      await initializeEventDispatcher()
      
      // 3. 初始化Listeners
      console.log('Step 3: Initializing listeners...')
      initializeNodeListener()
      initializeUIListener()
      initializeGraphListener()
      
      this.isInitialized = true
      console.log('✅ VOE Event Interaction Layer initialized successfully!')
      
      // 发送系统初始化完成事件
      eventBus.emit('SYSTEM_INIT', {
        type: 'voe_system',
        message: 'VOE事件交互层初始化完成',
        timestamp: Date.now()
      })
      
      return this
    } catch (error) {
      console.error('❌ Failed to initialize VOE system:', error)
      throw error
    }
  }

  /**
   * 获取系统状态
   */
  getStatus() {
    return {
      isInitialized: this.isInitialized,
      components: {
        eventBus: eventBus.listenerCount ? Object.keys(eventBus.listeners || {}).length : 'unknown',
        dispatcher: dispatcher.getStatus ? dispatcher.getStatus() : 'available',
        uiBridge: uiBridge.getStatus ? uiBridge.getStatus() : 'available',
        graphBridge: graphBridge.getStatus ? graphBridge.getStatus() : 'available',
        resultBridge: resultBridge.getStatus ? resultBridge.getStatus() : 'available',
        nodeListener: nodeListener.getStatus ? nodeListener.getStatus() : 'available',
        uiListener: uiListener.getStatus ? uiListener.getStatus() : 'available',
        graphListener: graphListener.getStatus ? graphListener.getStatus() : 'available'
      }
    }
  }

  /**
   * 触发UI点击节点事件（示例）
   */
  triggerNodeClick(node) {
    if (!this.isInitialized) {
      console.warn('VOE system not initialized. Call initialize() first.')
      return
    }
    
    uiBridge.handleClickNode(node)
  }

  /**
   * 触发节点运行事件（示例）
   */
  triggerNodeRun(nodeId, parameters = {}) {
    if (!this.isInitialized) {
      console.warn('VOE system not initialized. Call initialize() first.')
      return
    }
    
    uiBridge.triggerNodeRun({ nodeId, parameters })
  }

  /**
   * 触发Graph开始事件（示例）
   */
  triggerGraphStart() {
    if (!this.isInitialized) {
      console.warn('VOE system not initialized. Call initialize() first.')
      return
    }
    
    uiBridge.triggerGraphStart()
  }

  /**
   * 重置VOE系统（主要用于测试）
   */
  reset() {
    // 注意：这里只是标记为未初始化，实际组件需要单独重置
    this.isInitialized = false
    this.initializationPromise = null
    console.log('VOE system reset (marked as uninitialized)')
  }
}

// 创建单例实例
let instance = null

/**
 * 获取VOE系统单例实例
 * @returns {VOESystem} VOE系统实例
 */
export function getVOESystem() {
  if (!instance) {
    instance = new VOESystem()
  }
  return instance
}

/**
 * 初始化VOE系统（便捷函数）
 */
export async function initializeVOESystem() {
  const system = getVOESystem()
  return await system.initialize()
}

/**
 * 获取VOE系统状态（便捷函数）
 */
export function getVOEStatus() {
  const system = getVOESystem()
  return system.getStatus()
}

// 导出默认实例
export default getVOESystem()