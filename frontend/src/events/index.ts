/**
 * VOE事件交互层 - 主入口文件
 * 导出所有VOE模块，提供统一的初始化接口
 */

// 核心模块
export { default as eventBus } from './eventBus'
export * from './eventTypes'
export { default as dispatcher, initializeEventDispatcher } from './dispatcher'

// Bridge 模块
export { default as uiBridge, initializeUIBridge } from './bridge/uiBridge'
export { default as graphBridge, initializeGraphBridge } from './bridge/graphBridge'
export { default as resultBridge, initializeResultBridge } from './bridge/resultBridge'

// Listener 模块
export { default as nodeListener, initializeNodeListener } from './listeners/nodeListener'
export { default as uiListener, initializeUIListener } from './listeners/uiListener'
export { default as graphListener, initializeGraphListener } from './listeners/graphListener'

// 在文件内部使用这些函数时，需要直接导入
import { initializeUIBridge } from './bridge/uiBridge'
import { initializeGraphBridge } from './bridge/graphBridge'
import { initializeResultBridge } from './bridge/resultBridge'
import { initializeEventDispatcher } from './dispatcher'
import { initializeNodeListener } from './listeners/nodeListener'
import { initializeUIListener } from './listeners/uiListener'
import { initializeGraphListener } from './listeners/graphListener'

import eventBus from './eventBus'
import dispatcher from './dispatcher'
import uiBridge from './bridge/uiBridge'
import graphBridge from './bridge/graphBridge'
import resultBridge from './bridge/resultBridge'
import nodeListener from './listeners/nodeListener'
import uiListener from './listeners/uiListener'
import graphListener from './listeners/graphListener'

interface VOEStatus {
  isInitialized: boolean
  components: Record<string, unknown>
}

class VOESystem {
  isInitialized: boolean = false
  initializationPromise: Promise<VOESystem> | null = null

  async initialize(): Promise<VOESystem> {
    if (this.isInitialized) return this
    if (this.initializationPromise) return this.initializationPromise
    this.initializationPromise = this._initializeInternal()
    return this.initializationPromise
  }

  private async _initializeInternal(): Promise<VOESystem> {
    try {
      console.log('Initializing VOE Event Interaction Layer...')
      console.log('Step 1: Initializing bridges...')
      initializeUIBridge()
      await initializeGraphBridge()
      initializeResultBridge()

      console.log('Step 2: Initializing dispatcher...')
      await initializeEventDispatcher()

      console.log('Step 3: Initializing listeners...')
      initializeNodeListener()
      initializeUIListener()
      initializeGraphListener()

      this.isInitialized = true
      console.log('✅ VOE Event Interaction Layer initialized successfully!')

      eventBus.emit('SYSTEM_INIT', {
        type: 'voe_system',
        message: 'VOE事件交互层初始化完成',
        timestamp: Date.now(),
      })
      return this
    } catch (error) {
      console.error('❌ Failed to initialize VOE system:', error)
      throw error
    }
  }

  getStatus(): VOEStatus {
    return {
      isInitialized: this.isInitialized,
      components: {
        // eventBus.hasListeners 需要传入一个事件名作为参数
        eventBus: eventBus.hasListeners('SYSTEM_INIT') ? 'active' : 'unknown',
        dispatcher: dispatcher.getStatus ? dispatcher.getStatus() : 'available',
        uiBridge: uiBridge.getStatus ? uiBridge.getStatus() : 'available',
        graphBridge: graphBridge.getStatus ? graphBridge.getStatus() : 'available',
        resultBridge: resultBridge.getStatus ? resultBridge.getStatus() : 'available',
        nodeListener: nodeListener.getStatus ? nodeListener.getStatus() : 'available',
        uiListener: uiListener.getStatus ? uiListener.getStatus() : 'available',
        graphListener: graphListener.getStatus ? graphListener.getStatus() : 'available',
      },
    }
  }

  triggerNodeClick(node: { id: string; type?: string; label?: string }): void {
    if (!this.isInitialized) {
      console.warn('VOE system not initialized. Call initialize() first.')
      return
    }
    uiBridge.handleClickNode(node)
  }

  triggerNodeRun(nodeId: string, parameters: Record<string, unknown> = {}): void {
    if (!this.isInitialized) {
      console.warn('VOE system not initialized. Call initialize() first.')
      return
    }
    uiBridge.triggerNodeRun({ nodeId, parameters })
  }

  triggerGraphStart(): void {
    if (!this.isInitialized) {
      console.warn('VOE system not initialized. Call initialize() first.')
      return
    }
    uiBridge.triggerGraphStart()
  }

  reset(): void {
    this.isInitialized = false
    this.initializationPromise = null
    console.log('VOE system reset (marked as uninitialized)')
  }
}

let instance: VOESystem | null = null

export function getVOESystem(): VOESystem {
  if (!instance) instance = new VOESystem()
  return instance
}

export async function initializeVOESystem(): Promise<VOESystem> {
  return getVOESystem().initialize()
}

export function getVOEStatus(): VOEStatus {
  return getVOESystem().getStatus()
}

export default getVOESystem()