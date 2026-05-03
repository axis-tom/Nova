/**
 * VOE事件类型常量中心
 * 定义所有系统事件常量，确保事件名称一致性
 */

// UI 操作事件
export const UI_ACTION = 'UI_ACTION' as const
export const NODE_SELECT = 'NODE_SELECT' as const
export const NODE_UPDATE = 'NODE_UPDATE' as const
export const NODE_RUN = 'NODE_RUN' as const

// Graph 执行事件
export const GRAPH_START = 'GRAPH_START' as const
export const GRAPH_PROGRESS = 'GRAPH_PROGRESS' as const
export const GRAPH_FINISH = 'GRAPH_FINISH' as const

// 结果事件
export const RESULT_UPDATE = 'RESULT_UPDATE' as const
export const RESULT_RENDER = 'RESULT_RENDER' as const

// 系统事件
export const SYSTEM_INIT = 'SYSTEM_INIT' as const
export const SYSTEM_ERROR = 'SYSTEM_ERROR' as const
export const SYSTEM_WARNING = 'SYSTEM_WARNING' as const

// 任务事件
export const TASK_START = 'TASK_START' as const
export const TASK_COMPLETE = 'TASK_COMPLETE' as const
export const TASK_CANCEL = 'TASK_CANCEL' as const

// 数据事件
export const DATA_LOAD = 'DATA_LOAD' as const
export const DATA_UPDATE = 'DATA_UPDATE' as const
export const DATA_DELETE = 'DATA_DELETE' as const

// 节点状态事件
export const NODE_STATUS_CHANGE = 'NODE_STATUS_CHANGE' as const
export const NODE_RESULT_READY = 'NODE_RESULT_READY' as const
export const NODE_EXECUTION_START = 'NODE_EXECUTION_START' as const
export const NODE_EXECUTION_COMPLETE = 'NODE_EXECUTION_COMPLETE' as const
export const NODE_EXECUTION_ERROR = 'NODE_EXECUTION_ERROR' as const

// 事件分组
export const UI_EVENTS = {
  UI_ACTION,
  NODE_SELECT,
  NODE_UPDATE,
  NODE_RUN,
} as const

export const GRAPH_EVENTS = {
  GRAPH_START,
  GRAPH_PROGRESS,
  GRAPH_FINISH,
} as const

export const RESULT_EVENTS = {
  RESULT_UPDATE,
  RESULT_RENDER,
} as const

export const NODE_EVENTS = {
  NODE_SELECT,
  NODE_UPDATE,
  NODE_RUN,
  NODE_STATUS_CHANGE,
  NODE_RESULT_READY,
  NODE_EXECUTION_START,
  NODE_EXECUTION_COMPLETE,
  NODE_EXECUTION_ERROR,
} as const

export const SYSTEM_EVENTS = {
  SYSTEM_INIT,
  SYSTEM_ERROR,
  SYSTEM_WARNING,
} as const

// 事件类型 → 桥接器映射
export const EVENT_TYPE_MAPPING: Record<string, string> = {
  [UI_ACTION]: 'ui',
  [NODE_SELECT]: 'ui',
  [NODE_UPDATE]: 'ui',
  [NODE_RUN]: 'ui',
  [GRAPH_START]: 'graph',
  [GRAPH_PROGRESS]: 'graph',
  [GRAPH_FINISH]: 'graph',
  [RESULT_UPDATE]: 'result',
  [RESULT_RENDER]: 'result',
  [NODE_STATUS_CHANGE]: 'graph',
  [NODE_RESULT_READY]: 'graph',
  [NODE_EXECUTION_START]: 'graph',
  [NODE_EXECUTION_COMPLETE]: 'graph',
  [NODE_EXECUTION_ERROR]: 'graph',
  [SYSTEM_INIT]: 'system',
  [SYSTEM_ERROR]: 'system',
  [SYSTEM_WARNING]: 'system',
}

export function getBridgeForEvent(eventType: string): string {
  return EVENT_TYPE_MAPPING[eventType] || 'default'
}

export function isValidEventType(eventType: string): boolean {
  return eventType in EVENT_TYPE_MAPPING
}

export function getAllEventTypes(): string[] {
  return Object.keys(EVENT_TYPE_MAPPING)
}

export default {
  UI_ACTION,
  NODE_SELECT,
  NODE_UPDATE,
  NODE_RUN,
  GRAPH_START,
  GRAPH_PROGRESS,
  GRAPH_FINISH,
  RESULT_UPDATE,
  RESULT_RENDER,
  SYSTEM_INIT,
  SYSTEM_ERROR,
  SYSTEM_WARNING,
  TASK_START,
  TASK_COMPLETE,
  TASK_CANCEL,
  DATA_LOAD,
  DATA_UPDATE,
  DATA_DELETE,
  NODE_STATUS_CHANGE,
  NODE_RESULT_READY,
  NODE_EXECUTION_START,
  NODE_EXECUTION_COMPLETE,
  NODE_EXECUTION_ERROR,
  UI_EVENTS,
  GRAPH_EVENTS,
  RESULT_EVENTS,
  NODE_EVENTS,
  SYSTEM_EVENTS,
  getBridgeForEvent,
  isValidEventType,
  getAllEventTypes,
}