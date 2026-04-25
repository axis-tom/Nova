/**
 * VOE事件类型常量中心
 * 
 * 定义所有系统事件常量，确保事件名称一致性
 */

// UI操作事件
export const UI_ACTION = 'UI_ACTION'
export const NODE_SELECT = 'NODE_SELECT'
export const NODE_UPDATE = 'NODE_UPDATE'
export const NODE_RUN = 'NODE_RUN'

// Graph执行事件
export const GRAPH_START = 'GRAPH_START'
export const GRAPH_PROGRESS = 'GRAPH_PROGRESS'
export const GRAPH_FINISH = 'GRAPH_FINISH'

// 结果事件
export const RESULT_UPDATE = 'RESULT_UPDATE'
export const RESULT_RENDER = 'RESULT_RENDER'

// 系统事件
export const SYSTEM_INIT = 'SYSTEM_INIT'
export const SYSTEM_ERROR = 'SYSTEM_ERROR'
export const SYSTEM_WARNING = 'SYSTEM_WARNING'

// 任务事件
export const TASK_START = 'TASK_START'
export const TASK_COMPLETE = 'TASK_COMPLETE'
export const TASK_CANCEL = 'TASK_CANCEL'

// 数据事件
export const DATA_LOAD = 'DATA_LOAD'
export const DATA_UPDATE = 'DATA_UPDATE'
export const DATA_DELETE = 'DATA_DELETE'

// 节点状态事件
export const NODE_STATUS_CHANGE = 'NODE_STATUS_CHANGE'
export const NODE_RESULT_READY = 'NODE_RESULT_READY'
export const NODE_EXECUTION_START = 'NODE_EXECUTION_START'
export const NODE_EXECUTION_COMPLETE = 'NODE_EXECUTION_COMPLETE'
export const NODE_EXECUTION_ERROR = 'NODE_EXECUTION_ERROR'

// 事件分组
export const UI_EVENTS = {
  UI_ACTION,
  NODE_SELECT,
  NODE_UPDATE,
  NODE_RUN
}

export const GRAPH_EVENTS = {
  GRAPH_START,
  GRAPH_PROGRESS,
  GRAPH_FINISH
}

export const RESULT_EVENTS = {
  RESULT_UPDATE,
  RESULT_RENDER
}

export const NODE_EVENTS = {
  NODE_SELECT,
  NODE_UPDATE,
  NODE_RUN,
  NODE_STATUS_CHANGE,
  NODE_RESULT_READY,
  NODE_EXECUTION_START,
  NODE_EXECUTION_COMPLETE,
  NODE_EXECUTION_ERROR
}

export const SYSTEM_EVENTS = {
  SYSTEM_INIT,
  SYSTEM_ERROR,
  SYSTEM_WARNING
}

// 事件类型映射（用于dispatcher路由）
export const EVENT_TYPE_MAPPING = {
  // UI事件 → UI Bridge
  [UI_ACTION]: 'ui',
  [NODE_SELECT]: 'ui',
  [NODE_UPDATE]: 'ui',
  [NODE_RUN]: 'ui',
  
  // Graph事件 → Graph Bridge
  [GRAPH_START]: 'graph',
  [GRAPH_PROGRESS]: 'graph',
  [GRAPH_FINISH]: 'graph',
  
  // 结果事件 → Result Bridge
  [RESULT_UPDATE]: 'result',
  [RESULT_RENDER]: 'result',
  
  // 节点事件 → Graph Bridge
  [NODE_STATUS_CHANGE]: 'graph',
  [NODE_RESULT_READY]: 'graph',
  [NODE_EXECUTION_START]: 'graph',
  [NODE_EXECUTION_COMPLETE]: 'graph',
  [NODE_EXECUTION_ERROR]: 'graph',
  
  // 系统事件 → System Bridge（未来扩展）
  [SYSTEM_INIT]: 'system',
  [SYSTEM_ERROR]: 'system',
  [SYSTEM_WARNING]: 'system'
}

/**
 * 获取事件类型对应的桥接器
 * @param {string} eventType - 事件类型
 * @returns {string} 桥接器类型
 */
export function getBridgeForEvent(eventType) {
  return EVENT_TYPE_MAPPING[eventType] || 'default'
}

/**
 * 验证事件类型是否有效
 * @param {string} eventType - 事件类型
 * @returns {boolean} 是否有效
 */
export function isValidEventType(eventType) {
  return Object.values(EVENT_TYPE_MAPPING).some(type => type === getBridgeForEvent(eventType))
}

/**
 * 获取所有事件类型
 * @returns {string[]} 所有事件类型数组
 */
export function getAllEventTypes() {
  return Object.keys(EVENT_TYPE_MAPPING)
}

export default {
  // UI操作事件
  UI_ACTION,
  NODE_SELECT,
  NODE_UPDATE,
  NODE_RUN,
  
  // Graph执行事件
  GRAPH_START,
  GRAPH_PROGRESS,
  GRAPH_FINISH,
  
  // 结果事件
  RESULT_UPDATE,
  RESULT_RENDER,
  
  // 系统事件
  SYSTEM_INIT,
  SYSTEM_ERROR,
  SYSTEM_WARNING,
  
  // 任务事件
  TASK_START,
  TASK_COMPLETE,
  TASK_CANCEL,
  
  // 数据事件
  DATA_LOAD,
  DATA_UPDATE,
  DATA_DELETE,
  
  // 节点状态事件
  NODE_STATUS_CHANGE,
  NODE_RESULT_READY,
  NODE_EXECUTION_START,
  NODE_EXECUTION_COMPLETE,
  NODE_EXECUTION_ERROR,
  
  // 分组
  UI_EVENTS,
  GRAPH_EVENTS,
  RESULT_EVENTS,
  NODE_EVENTS,
  SYSTEM_EVENTS,
  
  // 工具函数
  getBridgeForEvent,
  isValidEventType,
  getAllEventTypes
}