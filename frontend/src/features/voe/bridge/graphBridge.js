/**
 * Graph Bridge - 事件到Graph指令的转换器
 * 
 * 负责把事件转换为graph可执行指令，输出nodeRunner command format
 * 
 * 规则：
 * - 只做数据转换，不包含业务逻辑
 * - 不直接调用core graph执行
 * - 输出标准化的graph指令格式
 */

import eventBus from '../eventBus.js'
import * as eventTypes from '../eventTypes.js'

// Graph引擎引用（动态导入以避免循环依赖）
let graphEngine = null

/**
 * 加载Graph引擎模块
 */
async function loadGraphEngine() {
  if (!graphEngine) {
    graphEngine = await import('@/core/graph')
  }
}

/**
 * Graph Bridge类
 */
class GraphBridge {
  constructor() {
    this.isInitialized = false
    this.graphManager = null
  }

  /**
   * 初始化Graph Bridge
   */
  async initialize() {
    if (this.isInitialized) {
      return
    }
    
    // 加载Graph引擎
    await loadGraphEngine()
    
    // 创建Graph管理器
    this.graphManager = graphEngine.getDefaultGraphManager()
    
    this.isInitialized = true
    console.log('GraphBridge initialized')
  }

  /**
   * 触发节点运行
   * @param {Object} payload - 节点运行数据
   */
  async triggerNodeRun(payload) {
    if (!payload || !payload.nodeId) {
      console.warn('Invalid payload for triggerNodeRun')
      return
    }
    
    // 发送节点执行开始事件
    eventBus.emit(eventTypes.NODE_EXECUTION_START, {
      nodeId: payload.nodeId,
      timestamp: Date.now()
    })
    
    try {
      // 调用Graph引擎执行节点
      if (!this.graphManager) {
        await this.initialize()
      }
      
      console.log(`Graph Bridge: Running node ${payload.nodeId}`)
      
      // 这里应该调用Graph引擎的runNode方法
      // 由于Graph引擎的具体实现未知，我们发送一个事件让外部处理
      eventBus.emit(eventTypes.NODE_RUN, {
        nodeId: payload.nodeId,
        parameters: payload.parameters || {},
        timestamp: Date.now(),
        source: 'graph-bridge'
      })
      
    } catch (error) {
      console.error(`Graph Bridge: Error running node ${payload.nodeId}:`, error)
      
      // 发送节点执行错误事件
      eventBus.emit(eventTypes.NODE_EXECUTION_ERROR, {
        nodeId: payload.nodeId,
        error: error.message,
        timestamp: Date.now()
      })
    }
  }

  /**
   * 触发Graph开始执行
   * @param {Object} payload - Graph开始数据
   */
  async triggerGraphStart(payload) {
    // 发送Graph开始事件
    eventBus.emit(eventTypes.GRAPH_START, {
      timestamp: Date.now(),
      ...payload
    })
    
    try {
      if (!this.graphManager) {
        await this.initialize()
      }
      
      console.log('Graph Bridge: Starting graph execution')
      
      // 这里应该调用Graph引擎的executeAll方法
      // 发送事件让外部处理
      eventBus.emit(eventTypes.GRAPH_START, {
        action: 'executeAll',
        timestamp: Date.now(),
        source: 'graph-bridge'
      })
      
    } catch (error) {
      console.error('Graph Bridge: Error starting graph:', error)
    }
  }

  /**
   * 触发节点更新
   * @param {Object} payload - 节点更新数据
   */
  async triggerNodeUpdate(payload) {
    if (!payload || !payload.nodeId) {
      console.warn('Invalid payload for triggerNodeUpdate')
      return
    }
    
    console.log(`Graph Bridge: Updating node ${payload.nodeId}`)
    
    // 发送节点更新事件
    eventBus.emit(eventTypes.NODE_UPDATE, {
      nodeId: payload.nodeId,
      changes: payload.changes || {},
      timestamp: Date.now(),
      source: 'graph-bridge'
    })
    
    // 标记节点为脏状态，需要重新执行
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
      nodeId: payload.nodeId,
      status: 'dirty',
      reason: 'node_updated',
      timestamp: Date.now()
    })
  }

  /**
   * 处理节点运行事件（从dispatcher调用）
   * @param {Object} payload - 节点运行数据
   */
  async handleNodeRun(payload) {
    await this.triggerNodeRun(payload)
  }

  /**
   * 处理节点更新事件（从dispatcher调用）
   * @param {Object} payload - 节点更新数据
   */
  async handleNodeUpdate(payload) {
    await this.triggerNodeUpdate(payload)
  }

  /**
   * 处理Graph开始事件（从dispatcher调用）
   * @param {Object} payload - Graph开始数据
   */
  async handleGraphStart(payload) {
    await this.triggerGraphStart(payload)
  }

  /**
   * 处理Graph进度事件（从dispatcher调用）
   * @param {Object} payload - Graph进度数据
   */
  async handleGraphProgress(payload) {
    // 转发Graph进度事件
    eventBus.emit(eventTypes.GRAPH_PROGRESS, payload)
    
    console.log(`Graph Bridge: Graph progress - ${payload.progress || 'unknown'}`)
  }

  /**
   * 处理Graph完成事件（从dispatcher调用）
   * @param {Object} payload - Graph完成数据
   */
  async handleGraphFinish(payload) {
    // 转发Graph完成事件
    eventBus.emit(eventTypes.GRAPH_FINISH, payload)
    
    console.log('Graph Bridge: Graph execution finished')
    
    // 发送结果就绪事件
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      type: 'graph_complete',
      data: payload,
      timestamp: Date.now()
    })
  }

  /**
   * 处理节点状态变化事件（从dispatcher调用）
   * @param {Object} payload - 节点状态数据
   */
  async handleNodeStatusChange(payload) {
    if (!payload || !payload.nodeId || !payload.status) {
      console.warn('Invalid payload for handleNodeStatusChange')
      return
    }
    
    // 转发节点状态变化事件
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, payload)
    
    console.log(`Graph Bridge: Node ${payload.nodeId} status changed to ${payload.status}`)
    
    // 如果节点执行完成，发送结果就绪事件
    if (payload.status === 'done' || payload.status === 'completed') {
      eventBus.emit(eventTypes.NODE_RESULT_READY, {
        nodeId: payload.nodeId,
        timestamp: Date.now()
      })
    }
  }

  /**
   * 处理节点结果就绪事件（从dispatcher调用）
   * @param {Object} payload - 节点结果数据
   */
  async handleNodeResultReady(payload) {
    if (!payload || !payload.nodeId) {
      console.warn('Invalid payload for handleNodeResultReady')
      return
    }
    
    console.log(`Graph Bridge: Node ${payload.nodeId} result ready`)
    
    // 发送结果更新事件
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      nodeId: payload.nodeId,
      type: 'node_result',
      timestamp: Date.now()
    })
  }

  /**
   * 处理节点执行开始事件（从dispatcher调用）
   * @param {Object} payload - 节点执行开始数据
   */
  async handleNodeExecutionStart(payload) {
    // 转发节点执行开始事件
    eventBus.emit(eventTypes.NODE_EXECUTION_START, payload)
    
    console.log(`Graph Bridge: Node ${payload.nodeId} execution started`)
  }

  /**
   * 处理节点执行完成事件（从dispatcher调用）
   * @param {Object} payload - 节点执行完成数据
   */
  async handleNodeExecutionComplete(payload) {
    // 转发节点执行完成事件
    eventBus.emit(eventTypes.NODE_EXECUTION_COMPLETE, payload)
    
    console.log(`Graph Bridge: Node ${payload.nodeId} execution completed`)
    
    // 发送节点状态变化事件
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
      nodeId: payload.nodeId,
      status: 'done',
      timestamp: Date.now()
    })
  }

  /**
   * 处理节点执行错误事件（从dispatcher调用）
   * @param {Object} payload - 节点执行错误数据
   */
  async handleNodeExecutionError(payload) {
    // 转发节点执行错误事件
    eventBus.emit(eventTypes.NODE_EXECUTION_ERROR, payload)
    
    console.error(`Graph Bridge: Node ${payload.nodeId} execution error: ${payload.error}`)
    
    // 发送节点状态变化事件
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
      nodeId: payload.nodeId,
      status: 'error',
      error: payload.error,
      timestamp: Date.now()
    })
  }

  /**
   * 重新运行节点链（从脏节点开始）
   * @param {string} nodeId - 节点ID
   */
  async rerunNodeChain(nodeId) {
    if (!nodeId) {
      console.warn('Invalid nodeId for rerunNodeChain')
      return
    }
    
    console.log(`Graph Bridge: Rerunning chain from node ${nodeId}`)
    
    try {
      if (!this.graphManager) {
        await this.initialize()
      }
      
      // 发送Graph开始事件
      eventBus.emit(eventTypes.GRAPH_START, {
        action: 'rerunChain',
        nodeId,
        timestamp: Date.now()
      })
      
      // 这里应该调用Graph引擎的runFromNode或markDirtyChain方法
      // 发送事件让外部处理
      eventBus.emit(eventTypes.NODE_RUN, {
        nodeId,
        action: 'rerunChain',
        timestamp: Date.now(),
        source: 'graph-bridge'
      })
      
    } catch (error) {
      console.error(`Graph Bridge: Error rerunning chain from node ${nodeId}:`, error)
    }
  }

  /**
   * 获取Graph Bridge状态
   */
  getStatus() {
    return {
      isInitialized: this.isInitialized,
      bridgeType: 'graph',
      graphManager: !!this.graphManager
    }
  }
}

// 创建单例实例
let instance = null

/**
 * 获取GraphBridge单例实例
 * @returns {GraphBridge} GraphBridge实例
 */
export function getGraphBridge() {
  if (!instance) {
    instance = new GraphBridge()
  }
  return instance
}

/**
 * 初始化Graph Bridge
 */
export async function initializeGraphBridge() {
  const bridge = getGraphBridge()
  await bridge.initialize()
  return bridge
}

/**
 * 重置GraphBridge（主要用于测试）
 */
export function resetGraphBridge() {
  instance = null
}

// 导出默认实例
export default getGraphBridge()