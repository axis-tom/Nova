/**
 * UI Bridge - UI操作到事件的转换器
 * 
 * 负责将UI操作标准化为事件，输出统一格式的UI_ACTION事件
 * 
 * 规则：
 * - 只做数据转换，不包含业务逻辑
 * - 不直接操作DOM
 * - 输出标准化的事件格式
 */

import eventBus from '../eventBus.js'
import * as eventTypes from '../eventTypes.js'

/**
 * UI Bridge类
 */
class UIBridge {
  constructor() {
    this.isInitialized = false
  }

  /**
   * 初始化UI Bridge
   */
  initialize() {
    if (this.isInitialized) {
      return
    }
    
    this.isInitialized = true
    console.log('UIBridge initialized')
  }

  /**
   * 处理节点点击事件
   * @param {Object} node - 节点数据
   */
  async handleClickNode(node) {
    if (!node || !node.id) {
      console.warn('Invalid node data for handleClickNode')
      return
    }
    
    // 标准化节点点击事件
    const payload = {
      nodeId: node.id,
      nodeType: node.type,
      nodeLabel: node.label,
      timestamp: Date.now(),
      source: 'ui-click'
    }
    
    // 发送节点选择事件
    eventBus.emit(eventTypes.NODE_SELECT, payload)
    
    // 同时发送UI_ACTION事件（兼容旧系统）
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'clickNode',
      data: payload,
      timestamp: Date.now()
    })
    
    console.log(`UI Bridge: Node ${node.id} clicked`)
  }

  /**
   * 处理节点选择事件（从dispatcher调用）
   * @param {Object} payload - 节点选择数据
   */
  async handleNodeSelect(payload) {
    // 这里可以添加额外的UI相关处理逻辑
    // 例如：记录用户交互、更新UI状态等
    
    console.log(`UI Bridge: Node ${payload.nodeId} selected`)
    
    // 转发到Graph Bridge进行进一步处理
    eventBus.emit(eventTypes.NODE_SELECT, payload)
  }

  /**
   * 处理任务提交事件
   * @param {Object} taskData - 任务数据
   */
  async handleTaskSubmit(taskData) {
    if (!taskData || !taskData.taskId) {
      console.warn('Invalid task data for handleTaskSubmit')
      return
    }
    
    // 标准化任务提交事件
    const payload = {
      taskId: taskData.taskId,
      taskType: taskData.type || 'default',
      parameters: taskData.parameters || {},
      timestamp: Date.now(),
      source: 'task-submit'
    }
    
    // 发送UI_ACTION事件
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'taskSubmit',
      data: payload,
      timestamp: Date.now()
    })
    
    // 发送任务开始事件
    eventBus.emit(eventTypes.TASK_START, payload)
    
    console.log(`UI Bridge: Task ${taskData.taskId} submitted`)
  }

  /**
   * 处理面板操作事件
   * @param {Object} actionData - 操作数据
   */
  async handlePanelAction(actionData) {
    if (!actionData || !actionData.action) {
      console.warn('Invalid action data for handlePanelAction')
      return
    }
    
    // 标准化面板操作事件
    const payload = {
      action: actionData.action,
      panelId: actionData.panelId || 'unknown',
      data: actionData.data || {},
      timestamp: Date.now(),
      source: 'panel-action'
    }
    
    // 发送UI_ACTION事件
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'panelAction',
      data: payload,
      timestamp: Date.now()
    })
    
    console.log(`UI Bridge: Panel action ${actionData.action} triggered`)
  }

  /**
   * 处理节点运行请求（从UI触发）
   * @param {Object} nodeData - 节点数据
   */
  async triggerNodeRun(nodeData) {
    if (!nodeData || !nodeData.nodeId) {
      console.warn('Invalid node data for triggerNodeRun')
      return
    }
    
    // 标准化节点运行事件
    const payload = {
      nodeId: nodeData.nodeId,
      nodeType: nodeData.type,
      parameters: nodeData.parameters || {},
      timestamp: Date.now(),
      source: 'ui-trigger'
    }
    
    // 发送节点运行事件
    eventBus.emit(eventTypes.NODE_RUN, payload)
    
    console.log(`UI Bridge: Node ${nodeData.nodeId} run triggered`)
  }

  /**
   * 处理Graph开始请求（从UI触发）
   */
  async triggerGraphStart() {
    // 标准化Graph开始事件
    const payload = {
      timestamp: Date.now(),
      source: 'ui-trigger'
    }
    
    // 发送Graph开始事件
    eventBus.emit(eventTypes.GRAPH_START, payload)
    
    console.log('UI Bridge: Graph start triggered')
  }

  /**
   * 处理结果编辑事件（从Result UI触发）
   * @param {Object} resultData - 结果数据
   */
  async handleResultEdit(resultData) {
    if (!resultData || !resultData.resultId) {
      console.warn('Invalid result data for handleResultEdit')
      return
    }
    
    // 标准化结果编辑事件
    const payload = {
      resultId: resultData.resultId,
      nodeId: resultData.nodeId,
      changes: resultData.changes || {},
      timestamp: Date.now(),
      source: 'result-edit'
    }
    
    // 发送UI_ACTION事件
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'resultEdit',
      data: payload,
      timestamp: Date.now()
    })
    
    // 发送节点更新事件（触发重新执行）
    eventBus.emit(eventTypes.NODE_UPDATE, {
      nodeId: resultData.nodeId,
      changes: resultData.changes,
      timestamp: Date.now()
    })
    
    console.log(`UI Bridge: Result ${resultData.resultId} edited, triggering node update`)
  }

  /**
   * 处理策略更新事件
   * @param {Object} strategyData - 策略数据
   */
  async handleStrategyUpdate(strategyData) {
    if (!strategyData) {
      console.warn('Invalid strategy data for handleStrategyUpdate')
      return
    }
    
    // 标准化策略更新事件
    const payload = {
      strategy: strategyData,
      timestamp: Date.now(),
      source: 'strategy-update'
    }
    
    // 发送UI_ACTION事件
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'strategyUpdate',
      data: payload,
      timestamp: Date.now()
    })
    
    // 发送数据更新事件
    eventBus.emit(eventTypes.DATA_UPDATE, {
      type: 'strategy',
      data: strategyData,
      timestamp: Date.now()
    })
    
    console.log('UI Bridge: Strategy updated')
  }

  /**
   * 获取UI Bridge状态
   */
  getStatus() {
    return {
      isInitialized: this.isInitialized,
      bridgeType: 'ui'
    }
  }
}

// 创建单例实例
let instance = null

/**
 * 获取UIBridge单例实例
 * @returns {UIBridge} UIBridge实例
 */
export function getUIBridge() {
  if (!instance) {
    instance = new UIBridge()
  }
  return instance
}

/**
 * 初始化UI Bridge
 */
export function initializeUIBridge() {
  const bridge = getUIBridge()
  bridge.initialize()
  return bridge
}

/**
 * 重置UIBridge（主要用于测试）
 */
export function resetUIBridge() {
  instance = null
}

// 导出默认实例
export default getUIBridge()