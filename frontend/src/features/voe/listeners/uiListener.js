/**
 * UI Listener - UI操作事件监听器
 * 
 * 监听UI操作事件：
 * - UI_ACTION
 * 
 * 行为：UI_ACTION → dispatcher → graphBridge / resultBridge
 */

import eventBus from '../eventBus.js'
import * as eventTypes from '../eventTypes.js'
import dispatcher from '../dispatcher.js'

/**
 * UI Listener类
 */
class UIListener {
  constructor() {
    this.isInitialized = false
    this.unsubscribeFunctions = []
  }

  /**
   * 初始化UI Listener
   */
  initialize() {
    if (this.isInitialized) {
      return
    }
    
    // 注册事件监听
    this.registerListeners()
    
    this.isInitialized = true
    console.log('UIListener initialized')
  }

  /**
   * 注册事件监听器
   */
  registerListeners() {
    // 监听UI操作事件
    const unsubscribeUIAction = eventBus.on(eventTypes.UI_ACTION, (payload) => {
      this.handleUIAction(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeUIAction)
    
    // 监听任务开始事件
    const unsubscribeTaskStart = eventBus.on(eventTypes.TASK_START, (payload) => {
      this.handleTaskStart(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeTaskStart)
    
    // 监听任务完成事件
    const unsubscribeTaskComplete = eventBus.on(eventTypes.TASK_COMPLETE, (payload) => {
      this.handleTaskComplete(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeTaskComplete)
    
    // 监听数据加载事件
    const unsubscribeDataLoad = eventBus.on(eventTypes.DATA_LOAD, (payload) => {
      this.handleDataLoad(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeDataLoad)
    
    // 监听数据更新事件
    const unsubscribeDataUpdate = eventBus.on(eventTypes.DATA_UPDATE, (payload) => {
      this.handleDataUpdate(payload)
    })
    this.unsubscribeFunctions.push(unsubscribeDataUpdate)
    
    console.log('UIListener: Registered 5 UI-related event listeners')
  }

  /**
   * 处理UI操作事件
   * @param {Object} payload - UI操作数据
   */
  async handleUIAction(payload) {
    console.log(`UIListener: UI action received - ${payload.action || 'unknown'}`)
    
    // 转发到dispatcher处理
    try {
      await dispatcher.handle(eventTypes.UI_ACTION, payload)
    } catch (error) {
      console.error('UIListener: Error handling UI action:', error)
    }
    
    // 根据action类型进行额外处理
    this.processUIAction(payload)
  }

  /**
   * 处理任务开始事件
   * @param {Object} payload - 任务开始数据
   */
  async handleTaskStart(payload) {
    console.log(`UIListener: Task ${payload.taskId} started`)
    
    // 发送Graph开始事件
    eventBus.emit(eventTypes.GRAPH_START, {
      taskId: payload.taskId,
      taskType: payload.taskType,
      timestamp: Date.now()
    })
  }

  /**
   * 处理任务完成事件
   * @param {Object} payload - 任务完成数据
   */
  async handleTaskComplete(payload) {
    console.log(`UIListener: Task ${payload.taskId} completed`)
    
    // 发送结果更新事件
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      type: 'task_complete',
      data: payload,
      timestamp: Date.now()
    })
  }

  /**
   * 处理数据加载事件
   * @param {Object} payload - 数据加载数据
   */
  async handleDataLoad(payload) {
    console.log(`UIListener: Data loaded - ${payload.type || 'unknown'}`)
    
    // 这里可以添加数据加载后的处理逻辑
    // 例如：更新UI状态、缓存数据等
  }

  /**
   * 处理数据更新事件
   * @param {Object} payload - 数据更新数据
   */
  async handleDataUpdate(payload) {
    console.log(`UIListener: Data updated - ${payload.type || 'unknown'}`)
    
    // 这里可以添加数据更新后的处理逻辑
    // 例如：刷新UI、通知相关组件等
    
    // 如果是策略更新，可能需要重新执行相关节点
    if (payload.type === 'strategy') {
      this.handleStrategyUpdate(payload.data)
    }
  }

  /**
   * 处理UI操作的具体逻辑
   * @param {Object} payload - UI操作数据
   */
  processUIAction(payload) {
    const { action, data } = payload
    
    switch (action) {
      case 'clickNode':
        // 节点点击的额外处理
        this.processNodeClick(data)
        break
        
      case 'taskSubmit':
        // 任务提交的额外处理
        this.processTaskSubmit(data)
        break
        
      case 'panelAction':
        // 面板操作的额外处理
        this.processPanelAction(data)
        break
        
      case 'resultEdit':
        // 结果编辑的额外处理
        this.processResultEdit(data)
        break
        
      case 'strategyUpdate':
        // 策略更新的额外处理
        this.processStrategyUpdate(data)
        break
        
      default:
        console.log(`UIListener: Unknown UI action: ${action}`)
    }
  }

  /**
   * 处理节点点击
   * @param {Object} data - 节点数据
   */
  processNodeClick(data) {
    // 这里可以添加节点点击的额外UI逻辑
    // 例如：高亮显示节点、显示节点详情等
    
    console.log(`UIListener: Node ${data.nodeId} clicked, additional UI processing`)
  }

  /**
   * 处理任务提交
   * @param {Object} data - 任务数据
   */
  processTaskSubmit(data) {
    // 这里可以添加任务提交的额外UI逻辑
    // 例如：显示加载状态、禁用提交按钮等
    
    console.log(`UIListener: Task ${data.taskId} submitted, additional UI processing`)
  }

  /**
   * 处理面板操作
   * @param {Object} data - 面板操作数据
   */
  processPanelAction(data) {
    // 这里可以添加面板操作的额外UI逻辑
    // 例如：切换面板状态、更新面板内容等
    
    console.log(`UIListener: Panel action ${data.action} processed, additional UI processing`)
  }

  /**
   * 处理结果编辑
   * @param {Object} data - 结果编辑数据
   */
  processResultEdit(data) {
    // 这里可以添加结果编辑的额外UI逻辑
    // 例如：显示编辑状态、保存编辑历史等
    
    console.log(`UIListener: Result ${data.resultId} edited, additional UI processing`)
    
    // 标记相关节点为脏状态
    if (data.nodeId) {
      eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
        nodeId: data.nodeId,
        status: 'dirty',
        reason: 'result_edited',
        timestamp: Date.now()
      })
    }
  }

  /**
   * 处理策略更新
   * @param {Object} data - 策略数据
   */
  processStrategyUpdate(data) {
    // 这里可以添加策略更新的额外UI逻辑
    // 例如：更新策略显示、保存策略配置等
    
    console.log('UIListener: Strategy updated, additional UI processing')
  }

  /**
   * 处理策略更新（从数据更新事件）
   * @param {Object} strategyData - 策略数据
   */
  handleStrategyUpdate(strategyData) {
    // 策略更新可能需要重新执行相关节点
    // 这里可以添加逻辑来确定哪些节点受策略影响
    
    console.log('UIListener: Strategy updated, checking affected nodes')
    
    // 发送策略更新事件，让Graph Bridge处理
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'strategyUpdate',
      data: {
        strategy: strategyData,
        timestamp: Date.now()
      }
    })
  }

  /**
   * 手动触发UI操作（用于测试或直接调用）
   * @param {string} action - 操作类型
   * @param {Object} data - 操作数据
   */
  async triggerUIAction(action, data = {}) {
    const payload = {
      action,
      data,
      timestamp: Date.now(),
      source: 'manual-trigger'
    }
    
    eventBus.emit(eventTypes.UI_ACTION, payload)
  }

  /**
   * 手动触发任务开始（用于测试或直接调用）
   * @param {string} taskId - 任务ID
   * @param {Object} taskData - 任务数据
   */
  async triggerTaskStart(taskId, taskData = {}) {
    const payload = {
      taskId,
      ...taskData,
      timestamp: Date.now(),
      source: 'manual-trigger'
    }
    
    eventBus.emit(eventTypes.TASK_START, payload)
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
    
    console.log('UIListener destroyed')
  }

  /**
   * 获取UI Listener状态
   */
  getStatus() {
    return {
      isInitialized: this.isInitialized,
      listenerType: 'ui',
      activeListeners: this.unsubscribeFunctions.length
    }
  }
}

// 创建单例实例
let instance = null

/**
 * 获取UIListener单例实例
 * @returns {UIListener} UIListener实例
 */
export function getUIListener() {
  if (!instance) {
    instance = new UIListener()
  }
  return instance
}

/**
 * 初始化UI Listener
 */
export function initializeUIListener() {
  const listener = getUIListener()
  listener.initialize()
  return listener
}

/**
 * 销毁UI Listener
 */
export function destroyUIListener() {
  if (instance) {
    instance.destroy()
    instance = null
  }
}

/**
 * 重置UIListener（主要用于测试）
 */
export function resetUIListener() {
  destroyUIListener()
}

// 导出默认实例
export default getUIListener()