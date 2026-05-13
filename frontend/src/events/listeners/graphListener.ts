import eventBus from '../eventBus'
import * as eventTypes from '../eventTypes'
import dispatcher from '../dispatcher'

interface ExecutionEvent {
  type: string
  data: unknown
  timestamp: number
}

class GraphListener {
  isInitialized: boolean = false
  private unsubscribeFunctions: Array<() => void> = []
  private executionHistory: ExecutionEvent[] = []
  private maxHistorySize: number = 100

  initialize(): void {
    if (this.isInitialized) return
    this.registerListeners()
    this.isInitialized = true
    console.log('GraphListener initialized')
  }

  private registerListeners(): void {
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.GRAPH_START, (payload: unknown): void => { this.handleGraphStart(payload) })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.GRAPH_PROGRESS, (payload: unknown): void => { this.handleGraphProgress(payload) })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.GRAPH_FINISH, (payload: unknown): void => { this.handleGraphFinish(payload) })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.NODE_EXECUTION_START, (payload: unknown): void => { this.handleNodeExecutionStart(payload) })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.NODE_EXECUTION_COMPLETE, (payload: unknown): void => { this.handleNodeExecutionComplete(payload) })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.NODE_EXECUTION_ERROR, (payload: unknown): void => { this.handleNodeExecutionError(payload) })
    )
    console.log('GraphListener: Registered 6 graph-related event listeners')
  }

  async handleGraphStart(payload: unknown): Promise<void> {
    console.log('GraphListener: Graph execution started')
    this.recordExecutionEvent('graph_start', payload)
    try { await dispatcher.handle(eventTypes.GRAPH_START, payload) } catch (error) { console.error('GraphListener: Error handling graph start:', error) }
    eventBus.emit(eventTypes.SYSTEM_INIT, { type: 'graph_start', message: 'Graph 执行开始', timestamp: Date.now() })
  }

  async handleGraphProgress(payload: unknown): Promise<void> {
    const p = payload as { progress?: number; message?: string; currentStep?: unknown; totalSteps?: unknown }
    const progress = p.progress || 0
    console.log(`GraphListener: Graph progress - ${progress}%`)
    this.recordExecutionEvent('graph_progress', payload)
    try { await dispatcher.handle(eventTypes.GRAPH_PROGRESS, payload) } catch (error) { console.error('GraphListener: Error handling graph progress:', error) }
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      type: 'graph_progress',
      data: { progress, message: p.message || `执行进度: ${progress}%`, currentStep: p.currentStep, totalSteps: p.totalSteps },
      timestamp: Date.now(),
    })
  }

  async handleGraphFinish(payload: unknown): Promise<void> {
    console.log('GraphListener: Graph execution finished')
    this.recordExecutionEvent('graph_finish', payload)
    try { await dispatcher.handle(eventTypes.GRAPH_FINISH, payload) } catch (error) { console.error('GraphListener: Error handling graph finish:', error) }
    eventBus.emit(eventTypes.RESULT_UPDATE, { type: 'graph_complete', data: payload, timestamp: Date.now() })
    eventBus.emit(eventTypes.SYSTEM_INIT, {
      type: 'graph_finish',
      message: 'Graph 执行完成',
      timestamp: Date.now(),
      summary: (payload as { summary?: unknown }).summary || {},
    })
  }

  async handleNodeExecutionStart(payload: unknown): Promise<void> {
    const p = payload as { nodeId: string }
    console.log(`GraphListener: Node ${p.nodeId} execution started`)
    this.recordExecutionEvent('node_start', payload)
    try { await dispatcher.handle(eventTypes.NODE_EXECUTION_START, payload) } catch (error) { console.error(`GraphListener: Error handling node ${p.nodeId} execution start:`, error) }
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, { nodeId: p.nodeId, status: 'running', timestamp: Date.now() })
  }

  async handleNodeExecutionComplete(payload: unknown): Promise<void> {
    const p = payload as { nodeId: string; result?: unknown; executionTime?: number }
    console.log(`GraphListener: Node ${p.nodeId} execution completed in ${p.executionTime || 'unknown'}ms`)
    this.recordExecutionEvent('node_complete', payload)
    try { await dispatcher.handle(eventTypes.NODE_EXECUTION_COMPLETE, payload) } catch (error) { console.error(`GraphListener: Error handling node ${p.nodeId} execution complete:`, error) }
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, { nodeId: p.nodeId, status: 'done', executionTime: p.executionTime, timestamp: Date.now() })
    eventBus.emit(eventTypes.NODE_RESULT_READY, { nodeId: p.nodeId, result: p.result, timestamp: Date.now() })
    this.updateGraphProgress(p.nodeId)
  }

  async handleNodeExecutionError(payload: unknown): Promise<void> {
    const p = payload as { nodeId: string; error: string }
    console.error(`GraphListener: Node ${p.nodeId} execution error: ${p.error}`)
    this.recordExecutionEvent('node_error', payload)
    try { await dispatcher.handle(eventTypes.NODE_EXECUTION_ERROR, payload) } catch (error) { console.error(`GraphListener: Error handling node ${p.nodeId} execution error:`, error) }
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, { nodeId: p.nodeId, status: 'error', error: p.error, timestamp: Date.now() })
    eventBus.emit(eventTypes.SYSTEM_ERROR, { type: 'node_execution_error', nodeId: p.nodeId, error: p.error, timestamp: Date.now() })
  }

  private updateGraphProgress(nodeId: string): void {
    eventBus.emit(eventTypes.GRAPH_PROGRESS, {
      progress: 50,
      message: `节点 ${nodeId} 执行完成`,
      currentStep: 'node_execution',
      timestamp: Date.now(),
    })
  }

  private recordExecutionEvent(eventType: string, data: unknown): void {
    this.executionHistory.push({ type: eventType, data, timestamp: Date.now() })
    if (this.executionHistory.length > this.maxHistorySize) {
      this.executionHistory = this.executionHistory.slice(-this.maxHistorySize)
    }
  }

  getExecutionHistory(limit: number | null = null): ExecutionEvent[] {
    if (limit && limit > 0) return this.executionHistory.slice(-limit)
    return [...this.executionHistory]
  }

  clearExecutionHistory(): void {
    this.executionHistory = []
    console.log('GraphListener: Execution history cleared')
  }

  getExecutionStats(): Record<string, unknown> {
    const h = this.executionHistory
    return {
      totalEvents: h.length,
      graphStarts: h.filter((e) => e.type === 'graph_start').length,
      graphFinishes: h.filter((e) => e.type === 'graph_finish').length,
      nodeStarts: h.filter((e) => e.type === 'node_start').length,
      nodeCompletes: h.filter((e) => e.type === 'node_complete').length,
      nodeErrors: h.filter((e) => e.type === 'node_error').length,
      lastEvent: h.length > 0 ? h[h.length - 1] : null,
      firstEvent: h.length > 0 ? h[0] : null,
    }
  }

  async triggerGraphStart(graphData: unknown = {}): Promise<void> {
    eventBus.emit(eventTypes.GRAPH_START, { ...(graphData as Record<string, unknown>), timestamp: Date.now(), source: 'manual-trigger' })
  }

  async triggerGraphProgress(progress: number, message: string = ''): Promise<void> {
    eventBus.emit(eventTypes.GRAPH_PROGRESS, { progress, message, timestamp: Date.now(), source: 'manual-trigger' })
  }

  async triggerGraphFinish(resultData: unknown = {}): Promise<void> {
    eventBus.emit(eventTypes.GRAPH_FINISH, { ...(resultData as Record<string, unknown>), timestamp: Date.now(), source: 'manual-trigger' })
  }

  destroy(): void {
    this.unsubscribeFunctions.forEach((fn) => fn())
    this.unsubscribeFunctions = []
    this.isInitialized = false
    this.executionHistory = []
    console.log('GraphListener destroyed')
  }

  getStatus(): Record<string, unknown> {
    return {
      isInitialized: this.isInitialized,
      listenerType: 'graph',
      activeListeners: this.unsubscribeFunctions.length,
      historySize: this.executionHistory.length,
      maxHistorySize: this.maxHistorySize,
    }
  }
}

let instance: GraphListener | null = null

export function getGraphListener(): GraphListener {
  if (!instance) instance = new GraphListener()
  return instance
}

export function initializeGraphListener(): GraphListener {
  const listener = getGraphListener()
  listener.initialize()
  return listener
}

export function destroyGraphListener(): void {
  if (instance) {
    instance.destroy()
    instance = null
  }
}

export function resetGraphListener(): void {
  destroyGraphListener()
}

export default getGraphListener()