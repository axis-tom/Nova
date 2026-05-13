import eventBus from '../eventBus'
import * as eventTypes from '../eventTypes'
import dispatcher from '../dispatcher'

class NodeListener {
  isInitialized: boolean = false
  private unsubscribeFunctions: Array<() => void> = []

  initialize(): void {
    if (this.isInitialized) return
    this.registerListeners()
    this.isInitialized = true
    console.log('NodeListener initialized')
  }

  private registerListeners(): void {
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.NODE_SELECT, (payload: unknown): void => { this.handleNodeSelect(payload) })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.NODE_UPDATE, (payload: unknown): void => { this.handleNodeUpdate(payload) })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.NODE_RUN, (payload: unknown): void => { this.handleNodeRun(payload) })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.NODE_STATUS_CHANGE, (payload: unknown): void => { this.handleNodeStatusChange(payload) })
    )
    this.unsubscribeFunctions.push(
      eventBus.on(eventTypes.NODE_RESULT_READY, (payload: unknown): void => { this.handleNodeResultReady(payload) })
    )
    console.log('NodeListener: Registered 5 node-related event listeners')
  }

  async handleNodeSelect(payload: unknown): Promise<void> {
    const p = payload as { nodeId: string }
    console.log(`NodeListener: Node ${p.nodeId} selected`)
    try { await dispatcher.handle(eventTypes.NODE_SELECT, payload) } catch (error) { console.error(`NodeListener: Error handling node select for ${p.nodeId}:`, error) }
  }

  async handleNodeUpdate(payload: unknown): Promise<void> {
    const p = payload as { nodeId: string }
    console.log(`NodeListener: Node ${p.nodeId} updated`)
    try { await dispatcher.handle(eventTypes.NODE_UPDATE, payload) } catch (error) { console.error(`NodeListener: Error handling node update for ${p.nodeId}:`, error) }
  }

  async handleNodeRun(payload: unknown): Promise<void> {
    const p = payload as { nodeId: string }
    console.log(`NodeListener: Node ${p.nodeId} run requested`)
    try { await dispatcher.handle(eventTypes.NODE_RUN, payload) } catch (error) { console.error(`NodeListener: Error handling node run for ${p.nodeId}:`, error) }
  }

  async handleNodeStatusChange(payload: unknown): Promise<void> {
    const p = payload as { nodeId: string; status: string }
    console.log(`NodeListener: Node ${p.nodeId} status changed to ${p.status}`)
    try { await dispatcher.handle(eventTypes.NODE_STATUS_CHANGE, payload) } catch (error) { console.error(`NodeListener: Error handling node status change for ${p.nodeId}:`, error) }
    if (p.status === 'done' || p.status === 'completed') {
      eventBus.emit(eventTypes.NODE_RESULT_READY, { nodeId: p.nodeId, timestamp: Date.now() })
    }
  }

  async handleNodeResultReady(payload: unknown): Promise<void> {
    const p = payload as { nodeId: string }
    console.log(`NodeListener: Node ${p.nodeId} result ready`)
    try { await dispatcher.handle(eventTypes.NODE_RESULT_READY, payload) } catch (error) { console.error(`NodeListener: Error handling node result ready for ${p.nodeId}:`, error) }
    eventBus.emit(eventTypes.RESULT_UPDATE, { type: 'node_result', nodeId: p.nodeId, timestamp: Date.now() })
  }

  async triggerNodeSelect(nodeId: string, nodeData: Record<string, unknown> = {}): Promise<void> {
    eventBus.emit(eventTypes.NODE_SELECT, {
      nodeId, nodeType: nodeData.type, nodeLabel: nodeData.label, timestamp: Date.now(), source: 'manual-trigger',
    })
  }

  async triggerNodeRun(nodeId: string, parameters: Record<string, unknown> = {}): Promise<void> {
    eventBus.emit(eventTypes.NODE_RUN, { nodeId, parameters, timestamp: Date.now(), source: 'manual-trigger' })
  }

  async triggerNodeUpdate(nodeId: string, changes: Record<string, unknown> = {}): Promise<void> {
    eventBus.emit(eventTypes.NODE_UPDATE, { nodeId, changes, timestamp: Date.now(), source: 'manual-trigger' })
  }

  destroy(): void {
    this.unsubscribeFunctions.forEach((fn) => fn())
    this.unsubscribeFunctions = []
    this.isInitialized = false
    console.log('NodeListener destroyed')
  }

  getStatus(): Record<string, unknown> {
    return {
      isInitialized: this.isInitialized,
      listenerType: 'node',
      activeListeners: this.unsubscribeFunctions.length,
    }
  }
}

let instance: NodeListener | null = null

export function getNodeListener(): NodeListener {
  if (!instance) instance = new NodeListener()
  return instance
}

export function initializeNodeListener(): NodeListener {
  const listener = getNodeListener()
  listener.initialize()
  return listener
}

export function destroyNodeListener(): void {
  if (instance) {
    instance.destroy()
    instance = null
  }
}

export function resetNodeListener(): void {
  destroyNodeListener()
}

export default getNodeListener()