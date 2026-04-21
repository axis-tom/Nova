/**
 * Result Parser - Graph输出到UI结构的转换器
 * 
 * 将graph raw output转换为标准result schema：
 * {
 *   id: "node_x",
 *   type: "text | markdown | table | chart | image",
 *   content: {},
 *   editable: true,
 *   meta: {
 *     sourceNode: "",
 *     timestamp: ""
 *   }
 * }
 * 
 * 规则：
 * 1. 只做数据转换，不包含业务逻辑
 * 2. 输出标准化的结果格式
 * 3. 支持所有result类型
 */

import { getResultBridge } from '../../voe/bridge/resultBridge.js'

/**
 * 解析Graph输出为UI结构
 * @param {Object} graphOutput - Graph原始输出
 * @returns {Object} 标准result schema
 */
export function parseGraphOutput(graphOutput) {
  if (!graphOutput) {
    return createErrorResult('Invalid graph output')
  }

  const { type, data, nodeId, metadata = {} } = graphOutput
  
  // 使用Result Bridge进行格式化
  const resultBridge = getResultBridge()
  
  let formattedResult = null
  
  switch (type) {
    case 'node_result':
      formattedResult = resultBridge.formatNodeOutput({
        nodeId,
        output: data,
        type: metadata.nodeType || 'unknown',
        metadata
      })
      break
      
    case 'graph_complete':
      formattedResult = resultBridge.formatGraphResult(data)
      break
      
    default:
      console.warn(`Unknown graph output type: ${type}`)
      return createErrorResult(`Unknown output type: ${type}`)
  }
  
  // 转换为标准result schema
  return convertToResultSchema(formattedResult, graphOutput)
}

/**
 * 将Result Bridge格式转换为标准result schema
 * @param {Object} bridgeResult - Result Bridge格式的结果
 * @param {Object} originalOutput - 原始Graph输出
 * @returns {Object} 标准result schema
 */
function convertToResultSchema(bridgeResult, originalOutput) {
  if (!bridgeResult || !bridgeResult.type) {
    return createErrorResult('Invalid bridge result')
  }
  
  const { type, payload, meta = {} } = bridgeResult
  
  // 确定result类型
  let resultType = 'text'
  let content = {}
  let editable = true
  
  switch (type) {
    case 'markdown':
      resultType = 'markdown'
      content = {
        text: payload.content || '',
        title: payload.title || 'Markdown内容',
        format: payload.format || 'markdown'
      }
      editable = true
      break
      
    case 'table':
      resultType = 'table'
      content = {
        data: payload.data || [],
        columns: payload.columns || [],
        title: payload.title || '表格数据',
        summary: payload.summary || {}
      }
      editable = true
      break
      
    case 'chart':
      resultType = 'chart'
      content = {
        data: payload.data || {},
        type: payload.chartType || 'bar',
        title: payload.title || '图表',
        options: payload.options || {}
      }
      editable = false // 图表通常不可直接编辑
      break
      
    case 'image':
      resultType = 'image'
      content = {
        images: payload.images || [],
        title: payload.title || '图片对比',
        comparison: payload.comparison || false
      }
      editable = false // 图片不可直接编辑
      break
      
    case 'composite':
      resultType = 'composite'
      content = {
        summary: payload.summary || {},
        nodeResults: payload.nodeResults || [],
        edges: payload.edges || []
      }
      editable = false // 复合结果不可直接编辑
      break
      
    case 'error':
      resultType = 'text'
      content = {
        text: payload.content || '未知错误',
        title: payload.title || '错误',
        format: 'text'
      }
      editable = false
      break
      
    default:
      resultType = 'text'
      content = {
        text: typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2),
        title: '结果',
        format: 'text'
      }
      editable = true
  }
  
  // 构建标准result schema
  return {
    id: meta.nodeId || originalOutput.nodeId || `result_${Date.now()}`,
    type: resultType,
    content,
    editable,
    meta: {
      sourceNode: meta.nodeId || originalOutput.nodeId || '',
      sourceType: meta.nodeType || originalOutput.metadata?.nodeType || 'unknown',
      timestamp: meta.timestamp || Date.now(),
      bridgeType: type,
      originalMeta: meta
    }
  }
}

/**
 * 解析节点输出为UI结构
 * @param {string} nodeId - 节点ID
 * @param {Object} nodeOutput - 节点输出
 * @param {Object} nodeMetadata - 节点元数据
 * @returns {Object} 标准result schema
 */
export function parseNodeOutput(nodeId, nodeOutput, nodeMetadata = {}) {
  if (!nodeId) {
    return createErrorResult('Missing node ID')
  }
  
  const resultBridge = getResultBridge()
  
  const formattedResult = resultBridge.formatNodeOutput({
    nodeId,
    output: nodeOutput,
    type: nodeMetadata.type || 'unknown',
    metadata: nodeMetadata
  })
  
  return convertToResultSchema(formattedResult, {
    nodeId,
    data: nodeOutput,
    metadata: nodeMetadata
  })
}

/**
 * 解析Graph执行结果
 * @param {Object} graphResult - Graph执行结果
 * @returns {Object} 标准result schema
 */
export function parseGraphResult(graphResult) {
  if (!graphResult) {
    return createErrorResult('Invalid graph result')
  }
  
  const resultBridge = getResultBridge()
  
  const formattedResult = resultBridge.formatGraphResult(graphResult)
  
  return convertToResultSchema(formattedResult, {
    type: 'graph_complete',
    data: graphResult
  })
}

/**
 * 检测内容类型
 * @param {*} content - 内容
 * @returns {string} 内容类型
 */
export function detectContentType(content) {
  if (!content) return 'text'
  
  if (typeof content === 'string') {
    // 检查是否为Markdown
    if (content.includes('# ') || content.includes('## ') || content.includes('*') || content.includes('`')) {
      return 'markdown'
    }
    return 'text'
  }
  
  if (Array.isArray(content)) {
    // 检查是否为表格数据
    if (content.length > 0 && typeof content[0] === 'object') {
      return 'table'
    }
    return 'text'
  }
  
  if (typeof content === 'object') {
    // 检查是否为图表数据
    if (content.data && content.labels) {
      return 'chart'
    }
    
    // 检查是否为图片数据
    if (content.images && Array.isArray(content.images)) {
      return 'image'
    }
    
    // 检查是否为复合结果
    if (content.summary && content.nodeResults) {
      return 'composite'
    }
    
    return 'json'
  }
  
  return 'text'
}

/**
 * 创建错误结果
 * @param {string} message - 错误消息
 * @returns {Object} 错误结果schema
 */
function createErrorResult(message) {
  return {
    id: `error_${Date.now()}`,
    type: 'text',
    content: {
      text: `错误: ${message}`,
      title: '处理错误',
      format: 'text'
    },
    editable: false,
    meta: {
      sourceNode: '',
      sourceType: 'error',
      timestamp: Date.now(),
      error: true,
      message
    }
  }
}

/**
 * 验证result schema
 * @param {Object} result - 结果schema
 * @returns {boolean} 是否有效
 */
export function validateResultSchema(result) {
  if (!result) return false
  
  const requiredFields = ['id', 'type', 'content', 'editable', 'meta']
  for (const field of requiredFields) {
    if (!(field in result)) {
      console.warn(`Missing required field in result schema: ${field}`)
      return false
    }
  }
  
  // 验证类型
  const validTypes = ['text', 'markdown', 'table', 'chart', 'image', 'composite', 'json']
  if (!validTypes.includes(result.type)) {
    console.warn(`Invalid result type: ${result.type}`)
    return false
  }
  
  // 验证content
  if (!result.content || typeof result.content !== 'object') {
    console.warn('Invalid content in result schema')
    return false
  }
  
  // 验证meta
  if (!result.meta || typeof result.meta !== 'object') {
    console.warn('Invalid meta in result schema')
    return false
  }
  
  return true
}

/**
 * 获取Result Parser状态
 * @returns {Object} 状态信息
 */
export function getParserStatus() {
  return {
    version: '1.0.0',
    supportedTypes: ['text', 'markdown', 'table', 'chart', 'image', 'composite', 'json'],
    bridgeAvailable: !!getResultBridge(),
    timestamp: Date.now()
  }
}

export default {
  parseGraphOutput,
  parseNodeOutput,
  parseGraphResult,
  detectContentType,
  validateResultSchema,
  getParserStatus
}