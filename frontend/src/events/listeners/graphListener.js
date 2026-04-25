/**
 * Graph Listener - Graph执行状态监听器
 * 
 * 监听graph执行状态：
 * - GRAPH_START
 * - GRAPH_PROGRESS
 * - GRAPH_FINISH
 * 
 * 行为：graph状态变化 → resultBridge → UI更新
 */

import eventBus from '../eventBus.js'
import * as eventTypes from '../eventTypes.js'
import dispatcher from '../dispatcher.js'

/**
 * Graph Listener类
 */
class GraphListener {
  constructor() {
    this.isInitialized = false
    this.unsubscribeFunctions = []
    this.executionHistory = []
    this.maxHistorySize = 100
  }

  /**
   * 初始化Graph Listener
   */
  initialize() {
    if (this.isInitialized) {
      return
    }
    
    // 注册事件监听
    this.registerListeners()
    
    this.isInitialized = true
    console.log('GraphListener initialized')
  }

  /**
   * 注册事件监听器
   */
  registerListeners() {
    // 监听Graph开始事件
    const unsubscribeGraphStart = eventBus.on(eventTypes.GRAPH_START, (payload) => {
      this.handleGraphStart(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeGraphStart)
    
    // 监听Graph进度事件
    const unsubscribeGraphProgress = eventBus.on(eventTypes.GRAPH_PROGRESS, (payload) => {
      this.handleGraphProgress(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeGraphProgress)
    
    // 监听Graph完成事件
    const unsubscribeGraphFinish = eventBus.on(eventTypes.GRAPH_FINISH, (payload) => {
      this.handleGraphFinish(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeGraphFinish)
    
    // 监听节点执行开始事件
    const unsubscribeNodeExecutionStart = eventBus.on(eventTypes.NODE_EXECUTION_START, (payload) => {
      this.handleNodeExecutionStart(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeNodeExecutionStart)
    
    // 监听节点执行完成事件
    const unsubscribeNodeExecutionComplete = eventBus.on(eventTypes.NODE_EXECUTION_COMPLETE, (payload) => {
      this.handleNodeExecutionComplete(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeNodeExecutionComplete)
    
    // 监听节点执行错误事件
    const unsubscribeNodeExecutionError = eventBus.on(eventTypes.NODE_EXECUTION_ERROR, (payload) => {
      this.handleNodeExecutionError(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeNodeExecutionError)
    
    console.log('GraphListener: Registered 6 graph-related event listeners')
  }

  /**
   * 处理Graph开始事件
   * @param {Object} payload - Graph开始数据
   */
  async handleGraphStart(payload) {
    console.log('GraphListener: Graph execution started')
    
    // 记录执行历史
    this.recordExecutionEvent('graph_start', payload)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.GRAPH_START, payload)
    } catch (error) {
      console.error('GraphListener: Error handling graph start:', error)
    }
    
    // 发送系统事件（用于UI显示）
    eventBus.emit(eventTypes.SYSTEM_INIT, {
      type: 'graph_start',
      message: 'Graph执行开始',
      timestamp: Date.now()
    })
  }

  /**
   * 处理Graph进度事件
   * @param {Object} payload - Graph进度数据
   */
  async handleGraphProgress(payload) {
    const progress = payload.progress || 0
    console.log(`GraphListener: Graph progress - ${progress}%`)
    
    // 记录执行历史
    this.recordExecutionEvent('graph_progress', payload)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.GRAPH_PROGRESS, payload)
    } catch (error) {
      console.error('GraphListener: Error handling graph progress:', error)
    }
    
    // 发送进度更新事件（用于UI显示）
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      type: 'graph_progress',
      data: {
        progress,
        message: payload.message || `执行进度: ${progress}%`,
        currentStep: payload.currentStep,
        totalSteps: payload.totalSteps
      },
      timestamp: Date.now()
    })
  }

  /**
   * 处理Graph完成事件
   * @param {Object} payload - Graph完成数据
   */
  async handleGraphFinish(payload) {
    console.log('GraphListener: Graph execution finished')
    
    // 记录执行历史
    this.recordExecutionEvent('graph_finish', payload)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.GRAPH_FINISH, payload)
    } catch (error) {
      console.error('GraphListener: Error handling graph finish:', error)
    }
    
    // 发送Graph完成事件到Result Bridge
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      type: 'graph_complete',
      data: payload,
      timestamp: Date.now()
    })
    
    // 发送系统事件（用于UI显示）
    eventBus.emit(eventTypes.SYSTEM_INIT, {
      type: 'graph_finish',
      message: 'Graph执行完成',
      timestamp: Date.now(),
      summary: payload.summary || {}
    })
  }

  /**
   * 处理节点执行开始事件
   * @param {Object} payload - 节点执行开始数据
   */
  async handleNodeExecutionStart(payload) {
    const { nodeId } = payload
    console.log(`GraphListener: Node ${nodeId} execution started`)
    
    // 记录执行历史
    this.recordExecutionEvent('node_start', payload)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.NODE_EXECUTION_START, payload)
    } catch (error) {
      console.error(`GraphListener: Error handling node ${nodeId} execution start:`, error)
    }
    
    // 发送节点状态更新事件
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
      nodeId,
      status: 'running',
      timestamp: Date.now()
    })
  }

  /**
   * 处理节点执行完成事件
   * @param {Object} payload - 节点执行完成数据
   */
  async handleNodeExecutionComplete(payload) {
    const { nodeId, result, executionTime } = payload
    console.log(`GraphListener: Node ${nodeId} execution completed in ${executionTime || 'unknown'}ms`)
    
    // 记录执行历史
    this.recordExecutionEvent('node_complete', payload)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.NODE_EXECUTION_COMPLETE, payload)
    } catch (error) {
      console.error(`GraphListener: Error handling node ${nodeId} execution complete:`, error)
    }
    
    // 发送节点状态更新事件
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
      nodeId,
      status: 'done',
      executionTime,
      timestamp: Date.now()
    })
    
    // 发送节点结果就绪事件
    eventBus.emit(eventTypes.NODE_RESULT_READY, {
      nodeId,
      result,
      timestamp: Date.now()
    })
    
    // 发送Graph进度事件（节点完成）
    this.updateGraphProgress(nodeId)
  }

  /**
   * 处理节点执行错误事件
   * @param {Object} payload - 节点执行错误数据
   */
  async handleNodeExecutionError(payload) {
    const { nodeId, error } = payload
    console.error(`GraphListener: Node ${nodeId} execution error: ${error}`)
    
    // 记录执行历史
    this.recordExecutionEvent('node_error', payload)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.NODE_EXECUTION_ERROR, payload)
    } catch (error) {
      console.error(`GraphListener: Error handling node ${nodeId} execution error:`, error)
    }
    
    // 发送节点状态更新事件
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
      nodeId,
      status: 'error',
      error,
      timestamp: Date.now()
    })
    
    // 发送系统错误事件
    eventBus.emit(eventTypes.SYSTEM_ERROR, {
      type: 'node_execution_error',
      nodeId,
      error,
      timestamp: Date.now()
    })
  }

  /**
   * 更新Graph进度（基于节点完成）
   * @param {string} nodeId - 完成的节点ID
   */
  updateGraphProgress(nodeId) {
    // 这里可以实现基于节点完成的进度计算逻辑
    // 例如：统计已完成节点数 / 总节点数
    
    // 发送进度更新事件
    eventBus.emit(eventTypes.GRAPH_PROGRESS, {
      progress: 50, // 示例进度，实际应根据具体逻辑计算
      message: `节点 ${nodeId} 执行完成`,
      currentStep: 'node_execution',
      timestamp: Date.now()
    })
  }

  /**
   * 记录执行事件到历史
   * @param {string} eventType - 事件类型
   * @param {Object} data - 事件数据
   */
  recordExecutionEvent(eventType, data) {
    const event = {
      type: eventType,
      data,
      timestamp: Date.now()
    }
    
    this.executionHistory.push(event)
    
    // 限制历史记录大小
    if (this.executionHistory.length > this.maxHistorySize) {
      this.executionHistory = this.executionHistory.slice(-this.maxHistorySize)
    }
  }

  /**
   * 获取执行历史
   * @param {number} limit - 限制返回的记录数（可选）
   * @returns {Array} 执行历史记录
   */
  getExecutionHistory(limit = null) {
    if (limit && limit > 0) {
      return this.executionHistory.slice(-limit)
    }
    return [...this.executionHistory]
  }

  /**
   * 清除执行历史
   */
  clearExecutionHistory() {
    this.executionHistory = []
    console.log('GraphListener: Execution history cleared')
  }

  /**
   * 获取Graph执行统计
   * @returns {Object} 执行统计信息
   */
  getExecutionStats() {
    const history = this.executionHistory
    const stats = {
      totalEvents: history.length,
      graphStarts: history.filter(e => e.type === 'graph_start').length,
      graphFinishes: history.filter(e => e.type === 'graph_finish').length,
      nodeStarts: history.filter(e => e.type === 'node_start').length,
      nodeCompletes: history.filter(e => e.type === 'node_complete').length,
      nodeErrors: history.filter(e => e.type === 'node_error').length,
      lastEvent: history.length > 0 ? history[history.length - 1] : null,
      firstEvent: history.length > 0 ? history[0] : null
    }
    
    return stats
  }

  /**
   * 手动触发Graph开始（用于测试或直接调用）
   * @param {Object} graphData - Graph数据
   */
  async triggerGraphStart(graphData = {}) {
    const payload = {
      ...graphData,
      timestamp: Date.now(),
      source: 'manual-trigger'
    }
    
    eventBus.emit(eventTypes.GRAPH_START, payload)
  }

  /**
   * 手动触发Graph进度更新（用于测试或直接调用）
   * @param {number} progress - 进度百分比
   * @param {string} message - 进度消息
   */
  async triggerGraphProgress(progress, message = '') {
    const payload = {
      progress,
      message,
      timestamp: Date.now(),
      source: 'manual-trigger'
    }
    
    eventBus.emit(eventTypes.GRAPH_PROGRESS, payload)
  }

  /**
   * 手动触发Graph完成（用于测试或直接调用）
   * @param {Object} resultData - 结果数据
   */
  async triggerGraphFinish(resultData = {}) {
    const payload = {
      ...resultData,
      timestamp: Date.now(),
      source: 'manual-trigger'
    }
    
    eventBus.emit(eventTypes.GRAPH_FINISH, payload)
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
    this.executionHistory = []
    
    console.log('GraphListener destroyed')
  }

  /**
   * 获取Graph Listener状态
   */
  getStatus() {
    return {
      isInitialized: this.isInitialized,
      listenerType: 'graph',
      activeListeners: this.unsubscribeFunctions.length,
      historySize: this.executionHistory.length,
      maxHistorySize: this.maxHistorySize
    }
  }
}

// 创建单例实例
let instance = null

/**
 * 获取GraphListener单例实例
 * @returns {GraphListener} GraphListener实例
 */
export function getGraphListener() {
  if (!instance) {
    instance = new GraphListener()
  }
  return instance
}

/**
 * 初始化Graph Listener
 */
export function initializeGraphListener() {
  const listener = getGraphListener()
  listener.initialize()
  return listener
}

/**
 * 销毁Graph Listener
 */
export function destroyGraphListener() {
  if (instance) {
    instance.destroy()
    instance = null
  }
}

/**
 * 重置GraphListener（主要用于测试）
 */
export function resetGraphListener() {
  destroyGraphListener()
}

// 导出默认实例
export default getGraphListener()