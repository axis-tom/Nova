import eventBus from '../eventBus'
import * as eventTypes from '../eventTypes'
import dispatcher from '../dispatcher'

class UIListener {
  isInitialized: boolean = false
  private unsubscribeFunctions: Array<() => void> = []

  initialize(): void {
    if (this.isInitialized) return
    this.registerListeners()
    this.isInitialized = true
    console.log('UIListener initialized')
  }

  private registerListeners(): void {
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.UI_ACTION, (payload: unknown): void => {
        this.handleUIAction(payload)
      })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.TASK_START, (payload: unknown): void => {
        this.handleTaskStart(payload)
      })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.TASK_COMPLETE, (payload: unknown): void => {
        this.handleTaskComplete(payload)
      })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.DATA_LOAD, (payload: unknown): void => {
        this.handleDataLoad(payload)
      })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.DATA_UPDATE, (payload: unknown): void => {
        this.handleDataUpdate(payload)
      })
    )
    console.log('UIListener: Registered 5 UI-related event listeners')
  }

  async handleUIAction(payload: unknown): Promise<void> {
    const p = payload as { action?: string }
    console.log(`UIListener: UI action received - ${p.action || 'unknown'}`)
    try {
      await dispatcher.handle(eventTypes.UI_ACTION, payload)
    } catch (error) {
      console.error('UIListener: Error handling UI action:', error)
    }
    this.processUIAction(payload as { action: string; data: unknown })
  }

  async handleTaskStart(payload: unknown): Promise<void> {
    const p = payload as { taskId: string; taskType?: string }
    console.log(`UIListener: Task ${p.taskId} started`)
    eventBus.emit(eventTypes.GRAPH_START, {
      taskId: p.taskId,
      taskType: p.taskType,
      timestamp: Date.now(),
    })
  }

  async handleTaskComplete(payload: unknown): Promise<void> {
    const p = payload as { taskId: string }
    console.log(`UIListener: Task ${p.taskId} completed`)
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      type: 'task_complete',
      data: payload,
      timestamp: Date.now(),
    })
  }

  async handleDataLoad(payload: unknown): Promise<void> {
    const p = payload as { type?: string }
    console.log(`UIListener: Data loaded - ${p.type || 'unknown'}`)
  }

  async handleDataUpdate(payload: unknown): Promise<void> {
    const p = payload as { type?: string; data?: unknown }
    console.log(`UIListener: Data updated - ${p.type || 'unknown'}`)
    if (p.type === 'strategy') {
      this.handleStrategyUpdate(p.data)
    }
  }

  private processUIAction(payload: { action: string; data: unknown }): void {
    const { action } = payload
    switch (action) {
      case 'clickNode': this.processNodeClick(payload.data); break
      case 'taskSubmit': this.processTaskSubmit(payload.data); break
      case 'panelAction': this.processPanelAction(payload.data); break
      case 'resultEdit': this.processResultEdit(payload.data); break
      case 'strategyUpdate': this.processStrategyUpdate(payload.data); break
      default: console.log(`UIListener: Unknown UI action: ${action}`)
    }
  }

  private processNodeClick(data: unknown): void {
    const d = data as { nodeId?: string }
    console.log(`UIListener: Node ${d.nodeId} clicked, additional UI processing`)
  }

  private processTaskSubmit(data: unknown): void {
    const d = data as { taskId?: string }
    console.log(`UIListener: Task ${d.taskId} submitted, additional UI processing`)
  }

  private processPanelAction(data: unknown): void {
    const d = data as { action?: string }
    console.log(`UIListener: Panel action ${d.action} processed, additional UI processing`)
  }

  private processResultEdit(data: unknown): void {
    const d = data as { resultId?: string; nodeId?: string }
    console.log(`UIListener: Result ${d.resultId} edited, additional UI processing`)
    if (d.nodeId) {
      eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
        nodeId: d.nodeId,
        status: 'dirty',
        reason: 'result_edited',
        timestamp: Date.now(),
      })
    }
  }

  private processStrategyUpdate(data: unknown): void {
    console.log('UIListener: Strategy updated, additional UI processing')
  }

  private handleStrategyUpdate(strategyData: unknown): void {
    console.log('UIListener: Strategy updated, checking affected nodes')
    eventBus.emit(eventTypes.UI_ACTION, {
      action: 'strategyUpdate',
      data: { strategy: strategyData, timestamp: Date.now() },
    })
  }

  async triggerUIAction(action: string, data: unknown = {}): Promise<void> {
    eventBus.emit(eventTypes.UI_ACTION, {
      action,
      data,
      timestamp: Date.now(),
      source: 'manual-trigger',
    })
  }

  async triggerTaskStart(taskId: string, taskData: unknown = {}): Promise<void> {
    eventBus.emit(eventTypes.TASK_START, {
      taskId,
      ...(taskData as Record<string, unknown>),
      timestamp: Date.now(),
      source: 'manual-trigger',
    })
  }

  destroy(): void {
    this.unsubscribeFunctions.forEach((fn) => fn())
    this.unsubscribeFunctions = []
    this.isInitialized = false
    console.log('UIListener destroyed')
  }

  getStatus(): Record<string, unknown> {
    return {
      isInitialized: this.isInitialized,
      listenerType: 'ui',
      activeListeners: this.unsubscribeFunctions.length,
    }
  }
}

let instance: UIListener | null = null

export function getUIListener(): UIListener {
  if (!instance) instance = new UIListener()
  return instance
}

export function initializeUIListener(): UIListener {
  const listener = getUIListener()
  listener.initialize()
  return listener
}

export function destroyUIListener(): void {
  instance?.destroy()
  instance = null
}

export function resetUIListener(): void {
  destroyUIListener()
}

export default getUIListener()