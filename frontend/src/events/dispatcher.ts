import eventBus from './eventBus'
import * as eventTypes from './eventTypes'

type BridgeType = Record<string, unknown> & {
  handleClickNode?: (data: unknown) => Promise<void>
  handleTaskSubmit?: (data: unknown) => Promise<void>
  handlePanelAction?: (data: unknown) => Promise<void>
  handleNodeSelect?: (payload: unknown) => Promise<void>
  handleNodeUpdate?: (payload: unknown) => Promise<void>
  handleNodeRun?: (payload: unknown) => Promise<void>
  handleGraphStart?: (payload: unknown) => Promise<void>
  handleGraphProgress?: (payload: unknown) => Promise<void>
  handleGraphFinish?: (payload: unknown) => Promise<void>
  handleResultUpdate?: (payload: unknown) => Promise<void>
  handleResultRender?: (payload: unknown) => Promise<void>
  handleNodeStatusChange?: (payload: unknown) => Promise<void>
  handleNodeResultReady?: (payload: unknown) => Promise<void>
  handleNodeExecutionStart?: (payload: unknown) => Promise<void>
  handleNodeExecutionComplete?: (payload: unknown) => Promise<void>
  handleNodeExecutionError?: (payload: unknown) => Promise<void>
}

let uiBridge: BridgeType | null = null
let graphBridge: BridgeType | null = null
let resultBridge: BridgeType | null = null

async function loadBridges(): Promise<void> {
  if (!uiBridge) {
    uiBridge = (await import('./bridge/uiBridge')).default as unknown as BridgeType
  }
  if (!graphBridge) {
    graphBridge = (await import('./bridge/graphBridge')).default as unknown as BridgeType
  }
  if (!resultBridge) {
    resultBridge = (await import('./bridge/resultBridge')).default as unknown as BridgeType
  }
}

type EventHandler = (payload: unknown) => Promise<void>

class EventDispatcher {
  isInitialized: boolean = false
  eventHandlers: Map<string, EventHandler> = new Map()

  constructor() {
    this.initializeEventHandlers()
  }

  private initializeEventHandlers(): void {
    this.eventHandlers.set(eventTypes.UI_ACTION, this.handleUIAction.bind(this))
    this.eventHandlers.set(eventTypes.NODE_SELECT, this.handleNodeSelect.bind(this))
    this.eventHandlers.set(eventTypes.NODE_UPDATE, this.handleNodeUpdate.bind(this))
    this.eventHandlers.set(eventTypes.NODE_RUN, this.handleNodeRun.bind(this))
    this.eventHandlers.set(eventTypes.GRAPH_START, this.handleGraphStart.bind(this))
    this.eventHandlers.set(eventTypes.GRAPH_PROGRESS, this.handleGraphProgress.bind(this))
    this.eventHandlers.set(eventTypes.GRAPH_FINISH, this.handleGraphFinish.bind(this))
    this.eventHandlers.set(eventTypes.RESULT_UPDATE, this.handleResultUpdate.bind(this))
    this.eventHandlers.set(eventTypes.RESULT_RENDER, this.handleResultRender.bind(this))
    this.eventHandlers.set(eventTypes.NODE_STATUS_CHANGE, this.handleNodeStatusChange.bind(this))
    this.eventHandlers.set(eventTypes.NODE_RESULT_READY, this.handleNodeResultReady.bind(this))
    this.eventHandlers.set(eventTypes.NODE_EXECUTION_START, this.handleNodeExecutionStart.bind(this))
    this.eventHandlers.set(eventTypes.NODE_EXECUTION_COMPLETE, this.handleNodeExecutionComplete.bind(this))
    this.eventHandlers.set(eventTypes.NODE_EXECUTION_ERROR, this.handleNodeExecutionError.bind(this))
  }

  async initialize(): Promise<void> {
    if (this.isInitialized) return
    await loadBridges()
    this.registerEventListeners()
    this.isInitialized = true
    console.log('EventDispatcher initialized')
  }

  private registerEventListeners(): void {
    for (const eventType of this.eventHandlers.keys()) {
      eventBus.on(eventType, (payload: unknown): void => {
        this.handle(eventType, payload)
      })
    }
  }

  async handle(eventType: string, payload: unknown): Promise<void> {
    if (!this.isInitialized) await this.initialize()
    const handler = this.eventHandlers.get(eventType)
    if (!handler) {
      console.warn(`No handler found for event type: ${eventType}`)
      return
    }
    try {
      await handler(payload)
    } catch (error) {
      console.error(`Error handling event ${eventType}:`, error)
      eventBus.emit(eventTypes.SYSTEM_ERROR, {
        eventType,
        error: (error as Error).message,
        timestamp: Date.now(),
      })
    }
  }

  async handleUIAction(payload: unknown): Promise<void> {
    if (!uiBridge) await loadBridges()
    const { action, data } = payload as { action: string; data: unknown }
    switch (action) {
      case 'clickNode': await uiBridge?.handleClickNode?.(data); break
      case 'taskSubmit': await uiBridge?.handleTaskSubmit?.(data); break
      case 'panelAction': await uiBridge?.handlePanelAction?.(data); break
      default: console.warn(`Unknown UI action: ${action}`)
    }
  }

  async handleNodeSelect(payload: unknown): Promise<void> {
    if (!uiBridge) await loadBridges()
    await uiBridge?.handleNodeSelect?.(payload)
  }

  async handleNodeUpdate(payload: unknown): Promise<void> {
    if (!graphBridge) await loadBridges()
    await graphBridge?.handleNodeUpdate?.(payload)
  }

  async handleNodeRun(payload: unknown): Promise<void> {
    if (!graphBridge) await loadBridges()
    await graphBridge?.handleNodeRun?.(payload)
  }

  async handleGraphStart(payload: unknown): Promise<void> {
    if (!graphBridge) await loadBridges()
    await graphBridge?.handleGraphStart?.(payload)
  }

  async handleGraphProgress(payload: unknown): Promise<void> {
    if (!graphBridge) await loadBridges()
    await graphBridge?.handleGraphProgress?.(payload)
  }

  async handleGraphFinish(payload: unknown): Promise<void> {
    if (!graphBridge) await loadBridges()
    await graphBridge?.handleGraphFinish?.(payload)
  }

  async handleResultUpdate(payload: unknown): Promise<void> {
    if (!resultBridge) await loadBridges()
    await resultBridge?.handleResultUpdate?.(payload)
  }

  async handleResultRender(payload: unknown): Promise<void> {
    if (!resultBridge) await loadBridges()
    await resultBridge?.handleResultRender?.(payload)
  }

  async handleNodeStatusChange(payload: unknown): Promise<void> {
    if (!graphBridge) await loadBridges()
    await graphBridge?.handleNodeStatusChange?.(payload)
  }

  async handleNodeResultReady(payload: unknown): Promise<void> {
    if (!graphBridge) await loadBridges()
    await graphBridge?.handleNodeResultReady?.(payload)
  }

  async handleNodeExecutionStart(payload: unknown): Promise<void> {
    if (!graphBridge) await loadBridges()
    await graphBridge?.handleNodeExecutionStart?.(payload)
  }

  async handleNodeExecutionComplete(payload: unknown): Promise<void> {
    if (!graphBridge) await loadBridges()
    await graphBridge?.handleNodeExecutionComplete?.(payload)
  }

  async handleNodeExecutionError(payload: unknown): Promise<void> {
    if (!graphBridge) await loadBridges()
    await graphBridge?.handleNodeExecutionError?.(payload)
  }

  async trigger(eventType: string, payload: unknown): Promise<void> {
    await this.handle(eventType, payload)
  }

  getStatus(): Record<string, unknown> {
    return {
      isInitialized: this.isInitialized,
      eventHandlerCount: this.eventHandlers.size,
      bridgesLoaded: { ui: !!uiBridge, graph: !!graphBridge, result: !!resultBridge },
    }
  }
}

let instance: EventDispatcher | null = null

export function getEventDispatcher(): EventDispatcher {
  if (!instance) instance = new EventDispatcher()
  return instance
}

export async function initializeEventDispatcher(): Promise<EventDispatcher> {
  const dispatcher = getEventDispatcher()
  await dispatcher.initialize()
  return dispatcher
}

export function resetEventDispatcher(): void {
  instance = null
}

export default getEventDispatcher()