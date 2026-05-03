import eventBus from '../eventBus'
import * as eventTypes from '../eventTypes'

interface NodeClickData {
  id: string
  type?: string
  label?: string
}

interface TaskData {
  taskId: string
  type?: string
  parameters?: Record<string, unknown>
}

interface ActionData {
  action: string
  panelId?: string
  data?: Record<string, unknown>
}

interface ResultEditData {
  resultId: string
  nodeId?: string
  changes?: Record<string, unknown>
}

class UIBridge {
  isInitialized: boolean = false

  initialize(): void {
    if (this.isInitialized) return
    this.isInitialized = true
    console.log('UIBridge initialized')
  }

  async handleClickNode(node: NodeClickData): Promise<void> {
    if (!node || !node.id) {
      console.warn('Invalid node data for handleClickNode')
      return
    }
    const payload = {
      nodeId: node.id,
      nodeType: node.type,
      nodeLabel: node.label,
      timestamp: Date.now(),
      source: 'ui-click',
    }
    eventBus.emit(eventTypes.NODE_SELECT, payload)
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'clickNode',
      data: payload,
      timestamp: Date.now(),
    })
    console.log(`UI Bridge: Node ${node.id} clicked`)
  }

  async handleNodeSelect(payload: Record<string, unknown>): Promise<void> {
    console.log(`UI Bridge: Node ${payload.nodeId as string} selected`)
    eventBus.emit(eventTypes.NODE_SELECT, payload)
  }

  async handleTaskSubmit(taskData: TaskData): Promise<void> {
    if (!taskData || !taskData.taskId) {
      console.warn('Invalid task data for handleTaskSubmit')
      return
    }
    const payload = {
      taskId: taskData.taskId,
      taskType: taskData.type || 'default',
      parameters: taskData.parameters || {},
      timestamp: Date.now(),
      source: 'task-submit',
    }
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'taskSubmit',
      data: payload,
      timestamp: Date.now(),
    })
    eventBus.emit(eventTypes.TASK_START, payload)
    console.log(`UI Bridge: Task ${taskData.taskId} submitted`)
  }

  async handlePanelAction(actionData: ActionData): Promise<void> {
    if (!actionData || !actionData.action) {
      console.warn('Invalid action data for handlePanelAction')
      return
    }
    const payload = {
      action: actionData.action,
      panelId: actionData.panelId || 'unknown',
      data: actionData.data || {},
      timestamp: Date.now(),
      source: 'panel-action',
    }
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'panelAction',
      data: payload,
      timestamp: Date.now(),
    })
    console.log(`UI Bridge: Panel action ${actionData.action} triggered`)
  }

  async triggerNodeRun(nodeData: { nodeId: string; type?: string; parameters?: Record<string, unknown> }): Promise<void> {
    if (!nodeData || !nodeData.nodeId) {
      console.warn('Invalid node data for triggerNodeRun')
      return
    }
    const payload = {
      nodeId: nodeData.nodeId,
      nodeType: nodeData.type,
      parameters: nodeData.parameters || {},
      timestamp: Date.now(),
      source: 'ui-trigger',
    }
    eventBus.emit(eventTypes.NODE_RUN, payload)
    console.log(`UI Bridge: Node ${nodeData.nodeId} run triggered`)
  }

  async triggerGraphStart(): Promise<void> {
    eventBus.emit(eventTypes.GRAPH_START, {
      timestamp: Date.now(),
      source: 'ui-trigger',
    })
    console.log('UI Bridge: Graph start triggered')
  }

  async handleResultEdit(resultData: ResultEditData): Promise<void> {
    if (!resultData || !resultData.resultId) {
      console.warn('Invalid result data for handleResultEdit')
      return
    }
    const payload = {
      resultId: resultData.resultId,
      nodeId: resultData.nodeId,
      changes: resultData.changes || {},
      timestamp: Date.now(),
      source: 'result-edit',
    }
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'resultEdit',
      data: payload,
      timestamp: Date.now(),
    })
    eventBus.emit(eventTypes.NODE_UPDATE, {
      nodeId: resultData.nodeId,
      changes: resultData.changes,
      timestamp: Date.now(),
    })
    console.log(`UI Bridge: Result ${resultData.resultId} edited, triggering node update`)
  }

  async handleStrategyUpdate(strategyData: Record<string, unknown>): Promise<void> {
    if (!strategyData) {
      console.warn('Invalid strategy data for handleStrategyUpdate')
      return
    }
    const payload = {
      strategy: strategyData,
      timestamp: Date.now(),
      source: 'strategy-update',
    }
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'strategyUpdate',
      data: payload,
      timestamp: Date.now(),
    })
    eventBus.emit(eventTypes.DATA_UPDATE, {
      type: 'strategy',
      data: strategyData,
      timestamp: Date.now(),
    })
    console.log('UI Bridge: Strategy updated')
  }

  getStatus(): Record<string, unknown> {
    return {
      isInitialized: this.isInitialized,
      bridgeType: 'ui',
    }
  }
}

let instance: UIBridge | null = null

export function getUIBridge(): UIBridge {
  if (!instance) instance = new UIBridge()
  return instance
}

export function initializeUIBridge(): UIBridge {
  const bridge = getUIBridge()
  bridge.initialize()
  return bridge
}

export function resetUIBridge(): void {
  instance = null
}

export default getUIBridge()