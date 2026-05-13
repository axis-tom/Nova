/**
 * 节点状态机
 * 
 * 职责：管理节点状态流转
 * 
 * 状态流转规则：
 * idle → running → done
 * idle → running → error
 * error → retry → running
 * done → dirty → running
 */

import type { NodeStateInfo } from '@/types'

// 节点状态映射
const NODE_STATUS = {
  IDLE: 'idle',
  RUNNING: 'running',
  DONE: 'done',
  ERROR: 'error',
  DIRTY: 'dirty'
} as const

type NodeStatus = typeof NODE_STATUS[keyof typeof NODE_STATUS]

// 状态流转规则
const STATE_TRANSITIONS: Record<string, string[]> = {
  [NODE_STATUS.IDLE]: [NODE_STATUS.RUNNING],
  [NODE_STATUS.RUNNING]: [NODE_STATUS.DONE, NODE_STATUS.ERROR],
  [NODE_STATUS.DONE]: [NODE_STATUS.DIRTY],
  [NODE_STATUS.ERROR]: [NODE_STATUS.RUNNING], // 通过retry
  [NODE_STATUS.DIRTY]: [NODE_STATUS.RUNNING]
}

// 节点状态存储
const nodeStates: Map<string, NodeStateInfo> = new Map()

/**
 * 检查状态流转是否有效
 */
function isValidTransition(fromStatus: string, toStatus: string): boolean {
  const allowedTransitions = STATE_TRANSITIONS[fromStatus]
  return allowedTransitions && allowedTransitions.includes(toStatus)
}

/**
 * 设置节点状态
 */
export function setStatus(nodeId: string, status: string): void {
  const currentStatus = getStatus(nodeId)
  
  if (!isValidTransition(currentStatus, status)) {
    throw new Error(`无效的状态流转: ${currentStatus} → ${status}`)
  }
  
  nodeStates.set(nodeId, {
    status,
    lastUpdated: new Date().toISOString(),
    previousStatus: currentStatus
  })
  
  console.log(`节点 ${nodeId} 状态更新: ${currentStatus} → ${status}`)
  
  // 触发状态变更事件
  triggerStatusChange(nodeId, currentStatus, status)
}

/**
 * 获取节点状态
 */
export function getStatus(nodeId: string): string {
  const state = nodeStates.get(nodeId)
  return state ? state.status : NODE_STATUS.IDLE
}

/**
 * 重置节点状态
 */
export function resetNode(nodeId: string): void {
  nodeStates.set(nodeId, {
    status: NODE_STATUS.IDLE,
    lastUpdated: new Date().toISOString(),
    previousStatus: getStatus(nodeId)
  })
  
  console.log(`节点 ${nodeId} 状态已重置为 idle`)
}

/**
 * 标记节点为dirty
 */
export function markDirty(nodeId: string): void {
  const currentStatus = getStatus(nodeId)
  
  if (currentStatus === NODE_STATUS.DONE) {
    setStatus(nodeId, NODE_STATUS.DIRTY)
  } else {
    console.log(`节点 ${nodeId} 当前状态为 ${currentStatus}，无法标记为 dirty`)
  }
}

/**
 * 重试节点（从error状态恢复）
 */
export function retryNode(nodeId: string): void {
  const currentStatus = getStatus(nodeId)
  
  if (currentStatus === NODE_STATUS.ERROR) {
    setStatus(nodeId, NODE_STATUS.RUNNING)
  } else {
    throw new Error(`节点 ${nodeId} 当前状态为 ${currentStatus}，无法重试`)
  }
}

/**
 * 获取节点状态历史
 */
export function getStatusHistory(nodeId: string): Array<{ status: string; timestamp: string; type: string }> {
  const state = nodeStates.get(nodeId)
  if (!state) {
    return []
  }
  
  const history: Array<{ status: string; timestamp: string; type: string }> = []
  
  // 添加当前状态
  history.push({
    status: state.status,
    timestamp: state.lastUpdated,
    type: 'current'
  })
  
  // 添加上一个状态（如果有）
  if (state.previousStatus) {
    history.push({
      status: state.previousStatus,
      timestamp: state.lastUpdated,
      type: 'previous'
    })
  }
  
  return history
}

/**
 * 检查节点是否可执行
 */
export function canExecute(nodeId: string): boolean {
  const status = getStatus(nodeId)
  return status === NODE_STATUS.IDLE || status === NODE_STATUS.DIRTY
}

/**
 * 检查节点是否已完成
 */
export function isDone(nodeId: string): boolean {
  return getStatus(nodeId) === NODE_STATUS.DONE
}

/**
 * 检查节点是否正在运行
 */
export function isRunning(nodeId: string): boolean {
  return getStatus(nodeId) === NODE_STATUS.RUNNING
}

/**
 * 检查节点是否为错误状态
 */
export function isError(nodeId: string): boolean {
  return getStatus(nodeId) === NODE_STATUS.ERROR
}

/**
 * 检查节点是否为脏状态
 */
export function isDirty(nodeId: string): boolean {
  return getStatus(nodeId) === NODE_STATUS.DIRTY
}

/**
 * 批量设置节点状态
 */
export function batchSetStatus(nodeIds: string[], status: string): void {
  nodeIds.forEach(nodeId => {
    try {
      setStatus(nodeId, status)
    } catch (error) {
      console.error(`批量设置节点 ${nodeId} 状态失败:`, error)
    }
  })
}

/**
 * 批量重置节点状态
 */
export function batchResetNodes(nodeIds: string[]): void {
  nodeIds.forEach(nodeId => {
    resetNode(nodeId)
  })
}

/**
 * 获取所有节点状态
 */
export function getAllNodeStatuses(): Record<string, NodeStateInfo> {
  const statuses: Record<string, NodeStateInfo> = {}
  
  nodeStates.forEach((state, nodeId) => {
    statuses[nodeId] = {
      status: state.status,
      lastUpdated: state.lastUpdated,
      previousStatus: state.previousStatus
    }
  })
  
  return statuses
}

/**
 * 清除所有节点状态
 */
export function clearAllStatuses(): void {
  nodeStates.clear()
  console.log('所有节点状态已清除')
}

/**
 * 状态变更事件监听器
 */
const statusChangeListeners: Set<(nodeId: string, oldStatus: string, newStatus: string) => void> = new Set()

/**
 * 注册状态变更监听器
 */
export function onStatusChange(listener: (nodeId: string, oldStatus: string, newStatus: string) => void): void {
  statusChangeListeners.add(listener)
}

/**
 * 移除状态变更监听器
 */
export function offStatusChange(listener: (nodeId: string, oldStatus: string, newStatus: string) => void): void {
  statusChangeListeners.delete(listener)
}

/**
 * 触发状态变更事件
 */
function triggerStatusChange(nodeId: string, oldStatus: string, newStatus: string): void {
  statusChangeListeners.forEach(listener => {
    try {
      listener(nodeId, oldStatus, newStatus)
    } catch (error) {
      console.error('状态变更监听器执行失败:', error)
    }
  })
}

/**
 * 获取状态流转图
 */
export function getStateTransitionGraph(): { states: string[]; transitions: Record<string, string[]>; description: string } {
  return {
    states: Object.values(NODE_STATUS),
    transitions: STATE_TRANSITIONS,
    description: '节点状态流转规则'
  }
}

/**
 * 验证状态流转路径
 */
export function validateTransitionPath(path: string[]): boolean {
  if (path.length < 2) {
    return false
  }
  
  for (let i = 0; i < path.length - 1; i++) {
    if (!isValidTransition(path[i], path[i + 1])) {
      return false
    }
  }
  
  return true
}

/**
 * 节点状态机常量
 */
export const NODE_STATE = NODE_STATUS
