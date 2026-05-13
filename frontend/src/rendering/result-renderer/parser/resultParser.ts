/**
 * Result Parser - Graph输出到UI结构的转换器
 * 将graph raw output转换为标准result schema
 */

// 修正导入路径 —— 旧路径是 '../../voe/bridge/resultBridge.js'
// 现在我们直接从 events/ 导入
import { getResultBridge } from '@/events/bridge/resultBridge'

interface GraphOutput {
  type?: string
  data?: unknown
  nodeId?: string | number
  metadata?: Record<string, unknown>
}

interface ResultSchema {
  id: string
  type: string
  content: Record<string, unknown>
  editable: boolean
  meta: Record<string, unknown>
}

interface FormattedResult {
  type: string
  payload: Record<string, unknown>
  meta: Record<string, unknown>
}

interface BridgeResultNode {
  nodeId: string | number
  output?: unknown
  type?: string
  metadata?: Record<string, unknown>
}

interface BridgeGraphResultData {
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

interface ResultBridge {
  formatNodeOutput: (data: BridgeResultNode) => FormattedResult
  formatGraphResult: (data: unknown) => FormattedResult
}

export function parseGraphOutput(graphOutput: GraphOutput): ResultSchema {
  if (!graphOutput) {
    return createErrorResult('Invalid graph output')
  }

  const { type, data, nodeId, metadata = {} } = graphOutput
  const resultBridge = getResultBridge() as unknown as ResultBridge

  let formattedResult: FormattedResult | null = null

  switch (type) {
    case 'node_result':
      formattedResult = resultBridge.formatNodeOutput({
        nodeId: nodeId ?? 'unknown',
        output: data,
        type: (metadata.nodeType as string) || 'unknown',
        metadata,
      })
      break
    case 'graph_complete':
      formattedResult = resultBridge.formatGraphResult(data)
      break
    default:
      console.warn(`Unknown graph output type: ${type}`)
      return createErrorResult(`Unknown output type: ${type}`)
  }

  return convertToResultSchema(formattedResult, graphOutput)
}

function convertToResultSchema(
  bridgeResult: FormattedResult | null,
  originalOutput: GraphOutput
): ResultSchema {
  if (!bridgeResult || !bridgeResult.type) {
    return createErrorResult('Invalid bridge result')
  }

  const { type, payload = {}, meta = {} } = bridgeResult

  let resultType = 'text'
  let content: Record<string, unknown> = {}
  let editable = true

  switch (type) {
    case 'markdown':
      resultType = 'markdown'
      content = {
        text: payload.content || '',
        title: payload.title || 'Markdown内容',
        format: payload.format || 'markdown',
      }
      editable = true
      break
    case 'table':
      resultType = 'table'
      content = {
        data: payload.data || [],
        columns: payload.columns || [],
        title: payload.title || '表格数据',
        summary: payload.summary || {},
      }
      editable = true
      break
    case 'chart':
      resultType = 'chart'
      content = {
        data: payload.data || {},
        type: payload.chartType || 'bar',
        title: payload.title || '图表',
        options: payload.options || {},
      }
      editable = false
      break
    case 'image':
      resultType = 'image'
      content = {
        images: payload.images || [],
        title: payload.title || '图片对比',
        comparison: payload.comparison || false,
      }
      editable = false
      break
    case 'composite':
      resultType = 'composite'
      content = {
        summary: payload.summary || {},
        nodeResults: payload.nodeResults || [],
        edges: payload.edges || [],
      }
      editable = false
      break
    case 'error':
      resultType = 'text'
      content = {
        text: payload.content || '未知错误',
        title: payload.title || '错误',
        format: 'text',
      }
      editable = false
      break
    default:
      resultType = 'text'
      content = {
        text: typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2),
        title: '结果',
        format: 'text',
      }
      editable = true
  }

  return {
    id: String(meta.nodeId ?? originalOutput.nodeId ?? `result_${Date.now()}`),
    type: resultType,
    content,
    editable,
    meta: {
      sourceNode: meta.nodeId ?? originalOutput.nodeId ?? '',
      sourceType: meta.nodeType ?? originalOutput.metadata?.nodeType ?? 'unknown',
      timestamp: meta.timestamp ?? Date.now(),
      bridgeType: type,
      originalMeta: meta,
    },
  }
}

export function parseNodeOutput(
  nodeId: string,
  nodeOutput: unknown,
  nodeMetadata: Record<string, unknown> = {}
): ResultSchema {
  if (!nodeId) {
    return createErrorResult('Missing node ID')
  }

  const resultBridge = getResultBridge() as unknown as ResultBridge
  const formattedResult = resultBridge.formatNodeOutput({
    nodeId,
    output: nodeOutput,
    type: (nodeMetadata.type as string) || 'unknown',
    metadata: nodeMetadata,
  })

  return convertToResultSchema(formattedResult, {
    nodeId,
    data: nodeOutput,
    metadata: nodeMetadata,
  })
}

export function parseGraphResult(graphResult: BridgeGraphResultData): ResultSchema {
  if (!graphResult) {
    return createErrorResult('Invalid graph result')
  }

  const resultBridge = getResultBridge() as unknown as ResultBridge
  const formattedResult = resultBridge.formatGraphResult(graphResult)

  return convertToResultSchema(formattedResult, {
    type: 'graph_complete',
    data: graphResult,
  })
}

export function detectContentType(content: unknown): string {
  if (!content) return 'text'

  if (typeof content === 'string') {
    if (content.includes('# ') || content.includes('## ') || content.includes('*') || content.includes('`')) {
      return 'markdown'
    }
    return 'text'
  }

  if (Array.isArray(content)) {
    if (content.length > 0 && typeof content[0] === 'object') {
      return 'table'
    }
    return 'text'
  }

  if (typeof content === 'object') {
    const obj = content as Record<string, unknown>
    if (obj.data && obj.labels) return 'chart'
    if (obj.images && Array.isArray(obj.images)) return 'image'
    if (obj.summary && obj.nodeResults) return 'composite'
    return 'json'
  }

  return 'text'
}

function createErrorResult(message: string): ResultSchema {
  return {
    id: `error_${Date.now()}`,
    type: 'text',
    content: {
      text: `错误: ${message}`,
      title: '处理错误',
      format: 'text',
    },
    editable: false,
    meta: {
      sourceNode: '',
      sourceType: 'error',
      timestamp: Date.now(),
      error: true,
      message,
    },
  }
}

export function validateResultSchema(result: unknown): boolean {
  if (!result || typeof result !== 'object') return false
  const r = result as Record<string, unknown>

  const requiredFields = ['id', 'type', 'content', 'editable', 'meta']
  for (const field of requiredFields) {
    if (!(field in r)) {
      console.warn(`Missing required field in result schema: ${field}`)
      return false
    }
  }

  const validTypes = ['text', 'markdown', 'table', 'chart', 'image', 'composite', 'json']
  if (!validTypes.includes(r.type as string)) {
    console.warn(`Invalid result type: ${r.type}`)
    return false
  }

  if (!r.content || typeof r.content !== 'object') {
    console.warn('Invalid content in result schema')
    return false
  }

  if (!r.meta || typeof r.meta !== 'object') {
    console.warn('Invalid meta in result schema')
    return false
  }

  return true
}

export function getParserStatus(): Record<string, unknown> {
  return {
    version: '1.0.0',
    supportedTypes: ['text', 'markdown', 'table', 'chart', 'image', 'composite', 'json'],
    bridgeAvailable: !!getResultBridge(),
    timestamp: Date.now(),
  }
}

export default {
  parseGraphOutput,
  parseNodeOutput,
  parseGraphResult,
  detectContentType,
  validateResultSchema,
  getParserStatus,
}