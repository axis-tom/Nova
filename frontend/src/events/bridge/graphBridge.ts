import eventBus from '../eventBus'
import * as eventTypes from '../eventTypes'

let graphEngine: unknown = null

async function loadGraphEngine(): Promise<void> {
  if (!graphEngine) {
    graphEngine = await import('@/core/graph')
  }
}

class GraphBridge {
  isInitialized: boolean = false
  graphManager: unknown = null

  async initialize(): Promise<void> {
    if (this.isInitialized) return
    await loadGraphEngine()
    this.graphManager = (graphEngine as { getDefaultGraphManager?: () => unknown })?.getDefaultGraphManager?.() ?? null
    this.isInitialized = true
    console.log('GraphBridge initialized')
  }

  async triggerNodeRun(payload: { nodeId: string; parameters?: Record<string, unknown> }): Promise<void> {
    if (!payload?.nodeId) {
      console.warn('Invalid payload for triggerNodeRun')
      return
    }
    eventBus.emit(eventTypes.NODE_EXECUTION_START, {
      nodeId: payload.nodeId,
      timestamp: Date.now(),
    })
    try {
      if (!this.graphManager) await this.initialize()
      console.log(`Graph Bridge: Running node ${payload.nodeId}`)
      eventBus.emit(eventTypes.NODE_RUN, {
        nodeId: payload.nodeId,
        parameters: payload.parameters || {},
        timestamp: Date.now(),
        source: 'graph-bridge',
      })
    } catch (error) {
      console.error(`Graph Bridge: Error running node ${payload.nodeId}:`, error)
      eventBus.emit(eventTypes.NODE_EXECUTION_ERROR, {
        nodeId: payload.nodeId,
        error: (error as Error).message,
        timestamp: Date.now(),
      })
    }
  }

  async triggerGraphStart(payload?: Record<string, unknown>): Promise<void> {
    eventBus.emit(eventTypes.GRAPH_START, { timestamp: Date.now(), ...payload })
    try {
      if (!this.graphManager) await this.initialize()
      console.log('Graph Bridge: Starting graph execution')
      eventBus.emit(eventTypes.GRAPH_START, {
        action: 'executeAll',
        timestamp: Date.now(),
        source: 'graph-bridge',
      })
    } catch (error) {
      console.error('Graph Bridge: Error starting graph:', error)
    }
  }

  async triggerNodeUpdate(payload: { nodeId: string; changes?: Record<string, unknown> }): Promise<void> {
    if (!payload?.nodeId) {
      console.warn('Invalid payload for triggerNodeUpdate')
      return
    }
    console.log(`Graph Bridge: Updating node ${payload.nodeId}`)
    eventBus.emit(eventTypes.NODE_UPDATE, {
      nodeId: payload.nodeId,
      changes: payload.changes || {},
      timestamp: Date.now(),
      source: 'graph-bridge',
    })
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
      nodeId: payload.nodeId,
      status: 'dirty',
      reason: 'node_updated',
      timestamp: Date.now(),
    })
  }

  async handleNodeRun(payload: Record<string, unknown>): Promise<void> {
    await this.triggerNodeRun(payload as { nodeId: string; parameters?: Record<string, unknown> })
  }

  async handleNodeUpdate(payload: Record<string, unknown>): Promise<void> {
    await this.triggerNodeUpdate(payload as { nodeId: string; changes?: Record<string, unknown> })
  }

  async handleGraphStart(payload: Record<string, unknown>): Promise<void> {
    await this.triggerGraphStart(payload)
  }

  async handleGraphProgress(payload: Record<string, unknown>): Promise<void> {
    eventBus.emit(eventTypes.GRAPH_PROGRESS, payload)
    console.log(`Graph Bridge: Graph progress - ${payload.progress || 'unknown'}`)
  }

  async handleGraphFinish(payload: Record<string, unknown>): Promise<void> {
    eventBus.emit(eventTypes.GRAPH_FINISH, payload)
    console.log('Graph Bridge: Graph execution finished')
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      type: 'graph_complete',
      data: payload,
      timestamp: Date.now(),
    })
  }

  async handleNodeStatusChange(payload: { nodeId: string; status: string }): Promise<void> {
    if (!payload?.nodeId || !payload?.status) {
      console.warn('Invalid payload for handleNodeStatusChange')
      return
    }
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, payload)
    console.log(`Graph Bridge: Node ${payload.nodeId} status changed to ${payload.status}`)
    if (payload.status === 'done' || payload.status === 'completed') {
      eventBus.emit(eventTypes.NODE_RESULT_READY, {
        nodeId: payload.nodeId,
        timestamp: Date.now(),
      })
    }
  }

  async handleNodeResultReady(payload: { nodeId: string }): Promise<void> {
    if (!payload?.nodeId) {
      console.warn('Invalid payload for handleNodeResultReady')
      return
    }
    console.log(`Graph Bridge: Node ${payload.nodeId} result ready`)
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      nodeId: payload.nodeId,
      type: 'node_result',
      timestamp: Date.now(),
    })
  }

  async handleNodeExecutionStart(payload: Record<string, unknown>): Promise<void> {
    eventBus.emit(eventTypes.NODE_EXECUTION_START, payload)
    console.log(`Graph Bridge: Node ${payload.nodeId} execution started`)
  }

  async handleNodeExecutionComplete(payload: Record<string, unknown>): Promise<void> {
    eventBus.emit(eventTypes.NODE_EXECUTION_COMPLETE, payload)
    console.log(`Graph Bridge: Node ${payload.nodeId} execution completed`)
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
      nodeId: payload.nodeId,
      status: 'done',
      timestamp: Date.now(),
    })
  }

  async handleNodeExecutionError(payload: { nodeId: string; error: string }): Promise<void> {
    eventBus.emit(eventTypes.NODE_EXECUTION_ERROR, payload)
    console.error(`Graph Bridge: Node ${payload.nodeId} execution error: ${payload.error}`)
    eventBus.emit(eventTypes.NODE_STATUS_CHANGE, {
      nodeId: payload.nodeId,
      status: 'error',
      error: payload.error,
      timestamp: Date.now(),
    })
  }

  async rerunNodeChain(nodeId: string): Promise<void> {
    if (!nodeId) {
      console.warn('Invalid nodeId for rerunNodeChain')
      return
    }
    console.log(`Graph Bridge: Rerunning chain from node ${nodeId}`)
    try {
      if (!this.graphManager) await this.initialize()
      eventBus.emit(eventTypes.GRAPH_START, {
        action: 'rerunChain',
        nodeId,
        timestamp: Date.now(),
      })
      eventBus.emit(eventTypes.NODE_RUN, {
        nodeId,
        action: 'rerunChain',
        timestamp: Date.now(),
        source: 'graph-bridge',
      })
    } catch (error) {
      console.error(`Graph Bridge: Error rerunning chain from node ${nodeId}:`, error)
    }
  }

  getStatus(): Record<string, unknown> {
    return {
      isInitialized: this.isInitialized,
      bridgeType: 'graph',
      graphManager: !!this.graphManager,
    }
  }
}

let instance: GraphBridge | null = null

export function getGraphBridge(): GraphBridge {
  if (!instance) instance = new GraphBridge()
  return instance
}

export async function initializeGraphBridge(): Promise<GraphBridge> {
  const bridge = getGraphBridge()
  await bridge.initialize()
  return bridge
}

export function resetGraphBridge(): void {
  instance = null
}

export default getGraphBridge()