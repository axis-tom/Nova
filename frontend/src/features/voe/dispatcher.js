/**
 * VOE事件调度中心
 * 
 * 实现事件路由分发器，负责：
 * - 接收eventBus事件
 * - 判断事件类型
 * - 转发到对应的bridge
 * 
 * 规则：
 * - 不允许直接调用core graph执行
 * - 不允许操作DOM
 * - 只做路由转发，不包含业务逻辑
 */

import eventBus from './eventBus.js'
import * as eventTypes from './eventTypes.js'

// Bridge引用（动态导入以避免循环依赖）
let uiBridge = null
let graphBridge = null
let resultBridge = null

/**
 * 加载bridge模块
 */
async function loadBridges() {
  if (!uiBridge) {
    uiBridge = await import('./bridge/uiBridge.js')
  }
  if (!graphBridge) {
    graphBridge = await import('./bridge/graphBridge.js')
  }
  if (!resultBridge) {
    resultBridge = await import('./bridge/resultBridge.js')
  }
}

/**
 * 事件调度器类
 */
class EventDispatcher {
  constructor() {
    this.isInitialized = false
    this.eventHandlers = new Map()
    
    // 初始化事件处理器映射
    this.initializeEventHandlers()
  }

  /**
   * 初始化事件处理器映射
   */
  initializeEventHandlers() {
    // UI事件处理器
    this.eventHandlers.set(eventTypes.UI_ACTION, this.handleUIAction.bind(this))
    this.eventHandlers.set(eventTypes.NODE_SELECT, this.handleNodeSelect.bind(this))
    this.eventHandlers.set(eventTypes.NODE_UPDATE, this.handleNodeUpdate.bind(this))
    this.eventHandlers.set(eventTypes.NODE_RUN, this.handleNodeRun.bind(this))
    
    // Graph事件处理器
    this.eventHandlers.set(eventTypes.GRAPH_START, this.handleGraphStart.bind(this))
    this.eventHandlers.set(eventTypes.GRAPH_PROGRESS, this.handleGraphProgress.bind(this))
    this.eventHandlers.set(eventTypes.GRAPH_FINISH, this.handleGraphFinish.bind(this))
    
    // 结果事件处理器
    this.eventHandlers.set(eventTypes.RESULT_UPDATE, this.handleResultUpdate.bind(this))
    this.eventHandlers.set(eventTypes.RESULT_RENDER, this.handleResultRender.bind(this))
    
    // 节点状态事件处理器
    this.eventHandlers.set(eventTypes.NODE_STATUS_CHANGE, this.handleNodeStatusChange.bind(this))
    this.eventHandlers.set(eventTypes.NODE_RESULT_READY, this.handleNodeResultReady.bind(this))
    this.eventHandlers.set(eventTypes.NODE_EXECUTION_START, this.handleNodeExecutionStart.bind(this))
    this.eventHandlers.set(eventTypes.NODE_EXECUTION_COMPLETE, this.handleNodeExecutionComplete.bind(this))
    this.eventHandlers.set(eventTypes.NODE_EXECUTION_ERROR, this.handleNodeExecutionError.bind(this))
  }

  /**
   * 初始化调度器
   */
  async initialize() {
    if (this.isInitialized) {
      return
    }
    
    // 加载bridge模块
    await loadBridges()
    
    // 注册事件监听
    this.registerEventListeners()
    
    this.isInitialized = true
    console.log('EventDispatcher initialized')
  }

  /**
   * 注册事件监听器
   */
  registerEventListeners() {
    // 监听所有事件类型
    for (const eventType of this.eventHandlers.keys()) {
      eventBus.on(eventType, (payload) => {
        this.handle(eventType, payload)
      })
    }
  }

  /**
   * 处理事件（主入口）
   * @param {string} eventType - 事件类型
   * @param {any} payload - 事件数据
   */
  async handle(eventType, payload) {
    if (!this.isInitialized) {
      await this.initialize()
    }
    
    const handler = this.eventHandlers.get(eventType)
    if (!handler) {
      console.warn(`No handler found for event type: ${eventType}`)
      return
    }
    
    try {
      await handler(payload)
    } catch (error) {
      console.error(`Error handling event ${eventType}:`, error)
      // 发送错误事件
      eventBus.emit(eventTypes.SYSTEM_ERROR, {
        eventType,
        error: error.message,
        timestamp: Date.now()
      })
    }
  }

  /**
   * UI操作事件处理器
   */
  async handleUIAction(payload) {
    if (!uiBridge) {
      await loadBridges()
    }
    
    const { action, data } = payload
    switch (action) {
      case 'clickNode':
        await uiBridge.handleClickNode(data)
        break
      case 'taskSubmit':
        await uiBridge.handleTaskSubmit(data)
        break
      case 'panelAction':
        await uiBridge.handlePanelAction(data)
        break
      default:
        console.warn(`Unknown UI action: ${action}`)
    }
  }

  /**
   * 节点选择事件处理器
   */
  async handleNodeSelect(payload) {
    if (!uiBridge) {
      await loadBridges()
    }
    
    // 转发到UI Bridge处理
    await uiBridge.handleNodeSelect(payload)
  }

  /**
   * 节点更新事件处理器
   */
  async handleNodeUpdate(payload) {
    if (!graphBridge) {
      await loadBridges()
    }
    
    // 转发到Graph Bridge处理
    await graphBridge.handleNodeUpdate(payload)
  }

  /**
   * 节点运行事件处理器
   */
  async handleNodeRun(payload) {
    if (!graphBridge) {
      await loadBridges()
    }
    
    // 转发到Graph Bridge处理
    await graphBridge.handleNodeRun(payload)
  }

  /**
   * Graph开始事件处理器
   */
  async handleGraphStart(payload) {
    if (!graphBridge) {
      await loadBridges()
    }
    
    // 转发到Graph Bridge处理
    await graphBridge.handleGraphStart(payload)
  }

  /**
   * Graph进度事件处理器
   */
  async handleGraphProgress(payload) {
    if (!graphBridge) {
      await loadBridges()
    }
    
    // 转发到Graph Bridge处理
    await graphBridge.handleGraphProgress(payload)
  }

  /**
   * Graph完成事件处理器
   */
  async handleGraphFinish(payload) {
    if (!graphBridge) {
      await loadBridges()
    }
    
    // 转发到Graph Bridge处理
    await graphBridge.handleGraphFinish(payload)
  }

  /**
   * 结果更新事件处理器
   */
  async handleResultUpdate(payload) {
    if (!resultBridge) {
      await loadBridges()
    }
    
    // 转发到Result Bridge处理
    await resultBridge.handleResultUpdate(payload)
  }

  /**
   * 结果渲染事件处理器
   */
  async handleResultRender(payload) {
    if (!resultBridge) {
      await loadBridges()
    }
    
    // 转发到Result Bridge处理
    await resultBridge.handleResultRender(payload)
  }

  /**
   * 节点状态变化事件处理器
   */
  async handleNodeStatusChange(payload) {
    if (!graphBridge) {
      await loadBridges()
    }
    
    // 转发到Graph Bridge处理
    await graphBridge.handleNodeStatusChange(payload)
  }

  /**
   * 节点结果就绪事件处理器
   */
  async handleNodeResultReady(payload) {
    if (!graphBridge) {
      await loadBridges()
    }
    
    // 转发到Graph Bridge处理
    await graphBridge.handleNodeResultReady(payload)
  }

  /**
   * 节点执行开始事件处理器
   */
  async handleNodeExecutionStart(payload) {
    if (!graphBridge) {
      await loadBridges()
    }
    
    // 转发到Graph Bridge处理
    await graphBridge.handleNodeExecutionStart(payload)
  }

  /**
   * 节点执行完成事件处理器
   */
  async handleNodeExecutionComplete(payload) {
    if (!graphBridge) {
      await loadBridges()
    }
    
    // 转发到Graph Bridge处理
    await graphBridge.handleNodeExecutionComplete(payload)
  }

  /**
   * 节点执行错误事件处理器
   */
  async handleNodeExecutionError(payload) {
    if (!graphBridge) {
      await loadBridges()
    }
    
    // 转发到Graph Bridge处理
    await graphBridge.handleNodeExecutionError(payload)
  }

  /**
   * 手动触发事件处理（用于测试或直接调用）
   */
  async trigger(eventType, payload) {
    await this.handle(eventType, payload)
  }

  /**
   * 获取调度器状态
   */
  getStatus() {
    return {
      isInitialized: this.isInitialized,
      eventHandlerCount: this.eventHandlers.size,
      bridgesLoaded: {
        ui: !!uiBridge,
        graph: !!graphBridge,
        result: !!resultBridge
      }
    }
  }
}

// 创建单例实例
let instance = null

/**
 * 获取EventDispatcher单例实例
 * @returns {EventDispatcher} EventDispatcher实例
 */
export function getEventDispatcher() {
  if (!instance) {
    instance = new EventDispatcher()
  }
  return instance
}

/**
 * 初始化事件调度器
 */
export async function initializeEventDispatcher() {
  const dispatcher = getEventDispatcher()
  await dispatcher.initialize()
  return dispatcher
}

/**
 * 重置EventDispatcher（主要用于测试）
 */
export function resetEventDispatcher() {
  instance = null
}

// 导出默认实例
export default getEventDispatcher()