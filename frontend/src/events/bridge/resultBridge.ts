import eventBus from '../eventBus'
import * as eventTypes from '../eventTypes'

interface NodeResultInput {
  nodeId: string
  type?: string
  output?: unknown
  metadata?: Record<string, unknown>
}

interface GraphResultInput {
  nodes?: Array<{
    id: string
    label?: string
    type?: string
    status?: string
    executionTime?: number
  }>
  edges?: Array<{
    id: string
    source: string
    target: string
  }>
  executionSummary?: Record<string, unknown>
  graphId?: string
}

interface FormattedResult {
  type: string
  payload: Record<string, unknown>
  meta: Record<string, unknown>
}

class ResultBridge {
  isInitialized: boolean = false
  resultCache: Map<string, FormattedResult> = new Map()

  initialize(): void {
    if (this.isInitialized) return
    this.isInitialized = true
    console.log('ResultBridge initialized')
  }

  formatNodeOutput(nodeData: NodeResultInput): FormattedResult {
    if (!nodeData?.nodeId) {
      console.warn('Invalid node data for formatNodeOutput')
      return this.createErrorResult('Invalid node data')
    }
    const { nodeId, output, type, metadata = {} } = nodeData
    let resultType = 'markdown'
    let formattedPayload: Record<string, unknown>
    switch (type) {
      case 'research':
      case 'analysis':
        resultType = 'markdown'
        formattedPayload = this.formatMarkdownOutput(output, metadata)
        break
      case 'generation':
        resultType = 'markdown'
        formattedPayload = this.formatGenerationOutput(output, metadata)
        break
      case 'optimization':
        resultType = 'table'
        formattedPayload = this.formatTableOutput(output, metadata)
        break
      case 'check':
      case 'assessment':
        resultType = 'markdown'
        formattedPayload = this.formatAssessmentOutput(output, metadata)
        break
      default:
        resultType = 'markdown'
        formattedPayload = this.formatDefaultOutput(output, metadata)
    }
    const result: FormattedResult = {
      type: resultType,
      payload: formattedPayload,
      meta: { nodeId, nodeType: type, timestamp: Date.now(), ...metadata },
    }
    this.resultCache.set(nodeId, result)
    console.log(`Result Bridge: Formatted output for node ${nodeId} as ${resultType}`)
    return result
  }

  formatGraphResult(graphData: GraphResultInput): FormattedResult {
    if (!graphData) {
      console.warn('Invalid graph data for formatGraphResult')
      return this.createErrorResult('Invalid graph data')
    }
    const { nodes = [], edges = [], executionSummary = {} } = graphData
    const nodeResults: Array<Record<string, unknown>> = []
    let hasErrors = false
    let totalExecutionTime = 0
    nodes.forEach((node) => {
      const cachedResult = this.resultCache.get(node.id)
      if (cachedResult) {
        nodeResults.push({
          nodeId: node.id,
          nodeLabel: node.label,
          nodeType: node.type,
          resultType: cachedResult.type,
          status: node.status || 'unknown',
          executionTime: node.executionTime || 0,
        })
        if (node.status === 'error') hasErrors = true
        if (node.executionTime) totalExecutionTime += node.executionTime
      }
    })
    return {
      type: 'composite',
      payload: {
        summary: {
          totalNodes: nodes.length,
          executedNodes: nodeResults.length,
          successfulNodes: nodeResults.filter((r) => r.status === 'done').length,
          failedNodes: nodeResults.filter((r) => r.status === 'error').length,
          totalExecutionTime,
          hasErrors,
          ...executionSummary,
        },
        nodeResults,
        edges: edges.map((edge) => ({ source: edge.source, target: edge.target, id: edge.id })),
      },
      meta: { type: 'graph_result', timestamp: Date.now(), graphId: graphData.graphId || 'unknown' },
    }
  }

  async handleResultUpdate(payload: Record<string, unknown>): Promise<void> {
    if (!payload) {
      console.warn('Invalid payload for handleResultUpdate')
      return
    }
    const { type, data, nodeId } = payload
    let formattedResult: FormattedResult | null = null
    switch (type) {
      case 'node_result':
        formattedResult = this.formatNodeOutput({ nodeId: nodeId as string, ...(data as object) })
        break
      case 'graph_complete':
        formattedResult = this.formatGraphResult(data as GraphResultInput)
        break
      default:
        console.warn(`Unknown result type: ${type}`)
        formattedResult = this.createErrorResult(`Unknown result type: ${type}`)
    }
    if (formattedResult) {
      eventBus.emit(eventTypes.RESULT_RENDER, {
        result: formattedResult,
        source: 'result-bridge',
        timestamp: Date.now(),
      })
      console.log(`Result Bridge: Result updated and rendered (type: ${type})`)
    }
  }

  async handleResultRender(payload: { result: FormattedResult; source?: string }): Promise<void> {
    if (!payload?.result) {
      console.warn('Invalid payload for handleResultRender')
      return
    }
    console.log(`Result Bridge: Result rendered from ${payload.source}, type: ${payload.result.type}`)
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      action: 'render',
      result: payload.result,
      timestamp: Date.now(),
    })
  }

  getNodeResult(nodeId: string): FormattedResult | null {
    return this.resultCache.get(nodeId) || null
  }

  getAllResults(): Record<string, FormattedResult> {
    const results: Record<string, FormattedResult> = {}
    this.resultCache.forEach((result, nodeId) => {
      results[nodeId] = result
    })
    return results
  }

  clearCache(nodeId: string | null = null): void {
    if (nodeId) {
      this.resultCache.delete(nodeId)
      console.log(`Result Bridge: Cleared cache for node ${nodeId}`)
    } else {
      this.resultCache.clear()
      console.log('Result Bridge: Cleared all cache')
    }
  }

  private formatMarkdownOutput(output: unknown, metadata: Record<string, unknown>): Record<string, unknown> {
    if (typeof output === 'string') {
      return { content: output, title: metadata.title || '分析结果', format: 'markdown' }
    } else if (output && typeof output === 'object' && 'content' in (output as Record<string, unknown>)) {
      return { ...(output as Record<string, unknown>), title: (output as Record<string, unknown>).title || metadata.title || '分析结果' }
    }
    return { content: JSON.stringify(output, null, 2), title: metadata.title || '数据结果', format: 'json' }
  }

  private formatGenerationOutput(output: unknown, metadata: Record<string, unknown>): Record<string, unknown> {
    if (typeof output === 'string') {
      return { content: output, title: metadata.title || '生成内容', format: 'markdown', generatedAt: Date.now() }
    }
    return {
      content: (output as Record<string, unknown>).text || JSON.stringify(output, null, 2),
      title: metadata.title || '生成结果',
      format: (output as Record<string, unknown>).format || 'markdown',
      ...(output as Record<string, unknown>),
    }
  }

  private formatTableOutput(output: unknown, metadata: Record<string, unknown>): Record<string, unknown> {
    let tableData: Array<Record<string, unknown>> = []
    let columns: Array<Record<string, unknown>> = []
    if (Array.isArray(output)) {
      tableData = output as Array<Record<string, unknown>>
      if (output.length > 0) {
        columns = Object.keys(output[0]).map((key) => ({ key, title: this.formatColumnTitle(key) }))
      }
    } else if (output && typeof output === 'object') {
      const obj = output as Record<string, unknown>
      if (obj.data && Array.isArray(obj.data)) {
        tableData = obj.data as Array<Record<string, unknown>>
        columns = (obj.columns as Array<Record<string, unknown>>) || []
      } else {
        tableData = [obj]
        columns = Object.keys(obj).map((key) => ({ key, title: this.formatColumnTitle(key) }))
      }
    }
    return { data: tableData, columns, title: metadata.title || '优化结果', summary: metadata.summary || {} }
  }

  private formatAssessmentOutput(output: unknown, metadata: Record<string, unknown>): Record<string, unknown> {
    const obj = output as Record<string, unknown> | undefined
    const isPass = obj?.passed || obj?.success || false
    const score = obj?.score || obj?.rating || 0
    return {
      content: obj?.details || obj?.message || JSON.stringify(output, null, 2),
      title: metadata.title || '评估结果',
      format: 'markdown',
      assessment: {
        passed: isPass,
        score,
        criteria: obj?.criteria || [],
        recommendations: obj?.recommendations || [],
      },
    }
  }

  private formatDefaultOutput(output: unknown, metadata: Record<string, unknown>): Record<string, unknown> {
    if (typeof output === 'string') {
      return { content: output, title: metadata.title || '结果', format: 'text' }
    }
    return { content: JSON.stringify(output, null, 2), title: metadata.title || '数据结果', format: 'json' }
  }

  private createErrorResult(message: string): FormattedResult {
    return {
      type: 'error',
      payload: { content: `错误: ${message}`, title: '处理错误', format: 'text' },
      meta: { error: true, message, timestamp: Date.now() },
    }
  }

  private formatColumnTitle(key: string): string {
    return key
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, (str) => str.toUpperCase())
      .trim()
  }

  getStatus(): Record<string, unknown> {
    return {
      isInitialized: this.isInitialized,
      bridgeType: 'result',
      cacheSize: this.resultCache.size,
      cachedNodes: Array.from(this.resultCache.keys()),
    }
  }
}

let instance: ResultBridge | null = null

export function getResultBridge(): ResultBridge {
  if (!instance) instance = new ResultBridge()
  return instance
}

export function initializeResultBridge(): ResultBridge {
  const bridge = getResultBridge()
  bridge.initialize()
  return bridge
}

export function resetResultBridge(): void {
  instance = null
}

export default getResultBridge()