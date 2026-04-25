/**
 * Node Listener - 节点相关事件监听器
 * 
 * 监听节点相关事件：
 * - NODE_SELECT
 * - NODE_UPDATE
 * - NODE_RUN
 * 
 * 行为：eventBus.on → dispatcher → graphBridge
 */

import eventBus from '../eventBus.js'
import * as eventTypes from '../eventTypes.js'
import dispatcher from '../dispatcher.js'

/**
 * Node Listener类
 */
class NodeListener {
  constructor() {
    this.isInitialized = false
    this.unsubscribeFunctions = []
  }

  /**
   * 初始化Node Listener
   */
  initialize() {
    if (this.isInitialized) {
      return
    }
    
    // 注册事件监听
    this.registerListeners()
    
    this.isInitialized = true
    console.log('NodeListener initialized')
  }

  /**
   * 注册事件监听器
   */
  registerListeners() {
    // 监听节点选择事件
    const unsubscribeNodeSelect = eventBus.on(eventTypes.NODE_SELECT, (payload) => {
      this.handleNodeSelect(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeNodeSelect)
    
    // 监听节点更新事件
    const unsubscribeNodeUpdate = eventBus.on(eventTypes.NODE_UPDATE, (payload) => {
      this.handleNodeUpdate(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeNodeUpdate)
    
    // 监听节点运行事件
    const unsubscribeNodeRun = eventBus.on(eventTypes.NODE_RUN, (payload) => {
      this.handleNodeRun(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeNodeRun)
    
    // 监听节点状态变化事件
    const unsubscribeNodeStatusChange = eventBus.on(eventTypes.NODE_STATUS_CHANGE, (payload) => {
      this.handleNodeStatusChange(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeNodeStatusChange)
    
    // 监听节点结果就绪事件
    const unsubscribeNodeResultReady = eventBus.on(eventTypes.NODE_RESULT_READY, (payload) => {
      this.handleNodeResultReady(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeNodeResultReady)
    
    console.log('NodeListener: Registered 5 node-related event listeners')
  }

  /**
   * 处理节点选择事件
   * @param {Object} payload - 节点选择数据
   */
  async handleNodeSelect(payload) {
    console.log(`NodeListener: Node ${payload.nodeId} selected`)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.NODE_SELECT, payload)
    } catch (error) {
      console.error(`NodeListener: Error handling node select for ${payload.nodeId}:`, error)
    }
  }

  /**
   * 处理节点更新事件
   * @param {Object} payload - 节点更新数据
   */
  async handleNodeUpdate(payload) {
    console.log(`NodeListener: Node ${payload.nodeId} updated`)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.NODE_UPDATE, payload)
    } catch (error) {
      console.error(`NodeListener: Error handling node update for ${payload.nodeId}:`, error)
    }
  }

  /**
   * 处理节点运行事件
   * @param {Object} payload - 节点运行数据
   */
  async handleNodeRun(payload) {
    console.log(`NodeListener: Node ${payload.nodeId} run requested`)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.NODE_RUN, payload)
    } catch (error) {
      console.error(`NodeListener: Error handling node run for ${payload.nodeId}:`, error)
    }
  }

  /**
   * 处理节点状态变化事件
   * @param {Object} payload - 节点状态数据
   */
  async handleNodeStatusChange(payload) {
    console.log(`NodeListener: Node ${payload.nodeId} status changed to ${payload.status}`)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.NODE_STATUS_CHANGE, payload)
    } catch (error) {
      console.error(`NodeListener: Error handling node status change for ${payload.nodeId}:`, error)
    }
    
    // 如果节点状态变为完成，触发结果处理
    if (payload.status === 'done' || payload.status === 'completed') {
      eventBus.emit(eventTypes.NODE_RESULT_READY, {
        nodeId: payload.nodeId,
        timestamp: Date.now()
      })
    }
  }

  /**
   * 处理节点结果就绪事件
   * @param {Object} payload - 节点结果数据
   */
  async handleNodeResultReady(payload) {
    console.log(`NodeListener: Node ${payload.nodeId} result ready`)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.NODE_RESULT_READY, payload)
    } catch (error) {
      console.error(`NodeListener: Error handling node result ready for ${payload.nodeId}:`, error)
    }
    
    // 发送结果更新事件
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      type: 'node_result',
      nodeId: payload.nodeId,
      timestamp: Date.now()
    })
  }

  /**
   * 手动触发节点选择（用于测试或直接调用）
   * @param {string} nodeId - 节点ID
   * @param {Object} nodeData - 节点数据
   */
  async triggerNodeSelect(nodeId, nodeData = {}) {
    const payload = {
      nodeId,
      nodeType: nodeData.type,
      nodeLabel: nodeData.label,
      timestamp: Date.now(),
      source: 'manual-trigger'
    }
    
    eventBus.emit(eventTypes.NODE_SELECT, payload)
  }

  /**
   * 手动触发节点运行（用于测试或直接调用）
   * @param {string} nodeId - 节点ID
   * @param {Object} parameters - 运行参数
   */
  async triggerNodeRun(nodeId, parameters = {}) {
    const payload = {
      nodeId,
      parameters,
      timestamp: Date.now(),
      source: 'manual-trigger'
    }
    
    eventBus.emit(eventTypes.NODE_RUN, payload)
  }

  /**
   * 手动触发节点更新（用于测试或直接调用）
   * @param {string} nodeId - 节点ID
   * @param {Object} changes - 更新内容
   */
  async triggerNodeUpdate(nodeId, changes = {}) {
    const payload = {
      nodeId,
      changes,
      timestamp: Date.now(),
      source: 'manual-trigger'
    }
    
    eventBus.emit(eventTypes.NODE_UPDATE, payload)
  }

  /**
   * 销毁监听器
   */
  destroy() {
    // 取消所有事件监听
    this.unsubscribeFunctions.forEach(unsubscribe => {
      if (typeof unsubscribe === 'function') {
        unsubscribe()
      }
    })
    
    this.unsubscribeFunctions = []
    this.isInitialized = false
    
    console.log('NodeListener destroyed')
  }

  /**
   * 获取Node Listener状态
   */
  getStatus() {
    return {
      isInitialized: this.isInitialized,
      listenerType: 'node',
      activeListeners: this.unsubscribeFunctions.length
    }
  }
}

// 创建单例实例
let instance = null

/**
 * 获取NodeListener单例实例
 * @returns {NodeListener} NodeListener实例
 */
export function getNodeListener() {
  if (!instance) {
    instance = new NodeListener()
  }
  return instance
}

/**
 * 初始化Node Listener
 */
export function initializeNodeListener() {
  const listener = getNodeListener()
  listener.initialize()
  return listener
}

/**
 * 销毁Node Listener
 */
export function destroyNodeListener() {
  if (instance) {
    instance.destroy()
    instance = null
  }
}

/**
 * 重置NodeListener（主要用于测试）
 */
export function resetNodeListener() {
  destroyNodeListener()
}

// 导出默认实例
export default getNodeListener()