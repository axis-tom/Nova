/**
 * Result Bridge - Graph输出到UI结果的转换器
 * 
 * 负责把graph输出转换为Result UI可识别结构
 * 输出结构：
 * {
 *   type: "markdown | table | chart | image",
 *   payload: {},
 *   meta: {}
 * }
 * 
 * 规则：
 * - 只做数据转换，不包含业务逻辑
 * - 不直接操作DOM
 * - 输出标准化的结果格式
 */

import eventBus from '../eventBus.js'
import * as eventTypes from '../eventTypes.js'

/**
 * Result Bridge类
 */
class ResultBridge {
  constructor() {
    this.isInitialized = false
    this.resultCache = new Map() // nodeId -> result data
  }

  /**
   * 初始化Result Bridge
   */
  initialize() {
    if (this.isInitialized) {
      return
    }
    
    this.isInitialized = true
    console.log('ResultBridge initialized')
  }

  /**
   * 格式化节点输出
   * @param {Object} nodeData - 节点数据
   * @returns {Object} 格式化后的结果
   */
  formatNodeOutput(nodeData) {
    if (!nodeData || !nodeData.nodeId) {
      console.warn('Invalid node data for formatNodeOutput')
      return this.createErrorResult('Invalid node data')
    }
    
    const { nodeId, output, type, metadata = {} } = nodeData
    
    // 根据节点类型确定结果类型
    let resultType = 'markdown'
    let formattedPayload = {}
    
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
    
    // 创建标准化结果
    const result = {
      type: resultType,
      payload: formattedPayload,
      meta: {
        nodeId,
        nodeType: type,
        timestamp: Date.now(),
        ...metadata
      }
    }
    
    // 缓存结果
    this.resultCache.set(nodeId, result)
    
    console.log(`Result Bridge: Formatted output for node ${nodeId} as ${resultType}`)
    return result
  }

  /**
   * 格式化Graph结果
   * @param {Object} graphData - Graph数据
   * @returns {Object} 格式化后的结果
   */
  formatGraphResult(graphData) {
    if (!graphData) {
      console.warn('Invalid graph data for formatGraphResult')
      return this.createErrorResult('Invalid graph data')
    }
    
    const { nodes = [], edges = [], executionSummary = {} } = graphData
    
    // 收集所有节点结果
    const nodeResults = []
    let hasErrors = false
    let totalExecutionTime = 0
    
    nodes.forEach(node => {
      const cachedResult = this.resultCache.get(node.id)
      if (cachedResult) {
        nodeResults.push({
          nodeId: node.id,
          nodeLabel: node.label,
          nodeType: node.type,
          resultType: cachedResult.type,
          status: node.status || 'unknown',
          executionTime: node.executionTime || 0
        })
        
        if (node.status === 'error') {
          hasErrors = true
        }
        
        if (node.executionTime) {
          totalExecutionTime += node.executionTime
        }
      }
    })
    
    // 创建Graph级结果
    const result = {
      type: 'composite',
      payload: {
        summary: {
          totalNodes: nodes.length,
          executedNodes: nodeResults.length,
          successfulNodes: nodeResults.filter(r => r.status === 'done').length,
          failedNodes: nodeResults.filter(r => r.status === 'error').length,
          totalExecutionTime,
          hasErrors,
          ...executionSummary
        },
        nodeResults,
        edges: edges.map(edge => ({
          source: edge.source,
          target: edge.target,
          id: edge.id
        }))
      },
      meta: {
        type: 'graph_result',
        timestamp: Date.now(),
        graphId: graphData.graphId || 'unknown'
      }
    }
    
    console.log(`Result Bridge: Formatted graph result with ${nodeResults.length} node results`)
    return result
  }

  /**
   * 处理结果更新事件（从dispatcher调用）
   * @param {Object} payload - 结果更新数据
   */
  async handleResultUpdate(payload) {
    if (!payload) {
      console.warn('Invalid payload for handleResultUpdate')
      return
    }
    
    const { type, data, nodeId } = payload
    
    let formattedResult = null
    
    switch (type) {
      case 'node_result':
        // 格式化节点结果
        formattedResult = this.formatNodeOutput({
          nodeId,
          ...data
        })
        break
        
      case 'graph_complete':
        // 格式化Graph结果
        formattedResult = this.formatGraphResult(data)
        break
        
      default:
        console.warn(`Unknown result type: ${type}`)
        formattedResult = this.createErrorResult(`Unknown result type: ${type}`)
    }
    
    if (formattedResult) {
      // 发送结果渲染事件
      eventBus.emit(eventTypes.RESULT_RENDER, {
        result: formattedResult,
        source: 'result-bridge',
        timestamp: Date.now()
      })
      
      console.log(`Result Bridge: Result updated and rendered (type: ${type})`)
    }
  }

  /**
   * 处理结果渲染事件（从dispatcher调用）
   * @param {Object} payload - 结果渲染数据
   */
  async handleResultRender(payload) {
    if (!payload || !payload.result) {
      console.warn('Invalid payload for handleResultRender')
      return
    }
    
    const { result, source } = payload
    
    // 这里可以添加额外的结果渲染逻辑
    // 例如：验证结果格式、记录渲染历史等
    
    console.log(`Result Bridge: Result rendered from ${source}, type: ${result.type}`)
    
    // 发送结果就绪事件（通知UI更新）
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      action: 'render',
      result,
      timestamp: Date.now()
    })
  }

  /**
   * 获取节点结果
   * @param {string} nodeId - 节点ID
   * @returns {Object|null} 节点结果
   */
  getNodeResult(nodeId) {
    return this.resultCache.get(nodeId) || null
  }

  /**
   * 获取所有缓存结果
   * @returns {Object} 所有缓存结果
   */
  getAllResults() {
    const results = {}
    this.resultCache.forEach((result, nodeId) => {
      results[nodeId] = result
    })
    return results
  }

  /**
   * 清除结果缓存
   * @param {string} nodeId - 节点ID（可选，不传则清除所有）
   */
  clearCache(nodeId = null) {
    if (nodeId) {
      this.resultCache.delete(nodeId)
      console.log(`Result Bridge: Cleared cache for node ${nodeId}`)
    } else {
      this.resultCache.clear()
      console.log('Result Bridge: Cleared all cache')
    }
  }

  /**
   * 格式化Markdown输出
   */
  formatMarkdownOutput(output, metadata) {
    if (typeof output === 'string') {
      return {
        content: output,
        title: metadata.title || '分析结果',
        format: 'markdown'
      }
    } else if (output && output.content) {
      return {
        content: output.content,
        title: output.title || metadata.title || '分析结果',
        format: output.format || 'markdown',
        ...output
      }
    } else {
      return {
        content: JSON.stringify(output, null, 2),
        title: metadata.title || '数据结果',
        format: 'json'
      }
    }
  }

  /**
   * 格式化生成输出
   */
  formatGenerationOutput(output, metadata) {
    if (typeof output === 'string') {
      return {
        content: output,
        title: metadata.title || '生成内容',
        format: 'markdown',
        generatedAt: Date.now()
      }
    } else {
      return {
        content: output.text || JSON.stringify(output, null, 2),
        title: metadata.title || '生成结果',
        format: output.format || 'markdown',
        ...output
      }
    }
  }

  /**
   * 格式化表格输出
   */
  formatTableOutput(output, metadata) {
    let tableData = []
    let columns = []
    
    if (Array.isArray(output)) {
      tableData = output
      if (output.length > 0) {
        columns = Object.keys(output[0]).map(key => ({
          key,
          title: this.formatColumnTitle(key)
        }))
      }
    } else if (output && output.data && Array.isArray(output.data)) {
      tableData = output.data
      columns = output.columns || []
    } else if (output && typeof output === 'object') {
      tableData = [output]
      columns = Object.keys(output).map(key => ({
        key,
        title: this.formatColumnTitle(key)
      }))
    }
    
    return {
      data: tableData,
      columns,
      title: metadata.title || '优化结果',
      summary: metadata.summary || {}
    }
  }

  /**
   * 格式化评估输出
   */
  formatAssessmentOutput(output, metadata) {
    const isPass = output?.passed || output?.success || false
    const score = output?.score || output?.rating || 0
    
    return {
      content: output?.details || output?.message || JSON.stringify(output, null, 2),
      title: metadata.title || '评估结果',
      format: 'markdown',
      assessment: {
        passed: isPass,
        score,
        criteria: output?.criteria || [],
        recommendations: output?.recommendations || []
      }
    }
  }

  /**
   * 格式化默认输出
   */
  formatDefaultOutput(output, metadata) {
    if (typeof output === 'string') {
      return {
        content: output,
        title: metadata.title || '结果',
        format: 'text'
      }
    } else {
      return {
        content: JSON.stringify(output, null, 2),
        title: metadata.title || '数据结果',
        format: 'json'
      }
    }
  }

  /**
   * 创建错误结果
   */
  createErrorResult(message) {
    return {
      type: 'error',
      payload: {
        content: `错误: ${message}`,
        title: '处理错误',
        format: 'text'
      },
      meta: {
        error: true,
        message,
        timestamp: Date.now()
      }
    }
  }

  /**
   * 格式化列标题
   */
  formatColumnTitle(key) {
    return key
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, str => str.toUpperCase())
      .trim()
  }

  /**
   * 获取Result Bridge状态
   */
  getStatus() {
    return {
      isInitialized: this.isInitialized,
      bridgeType: 'result',
      cacheSize: this.resultCache.size,
      cachedNodes: Array.from(this.resultCache.keys())
    }
  }
}

// 创建单例实例
let instance = null

/**
 * 获取ResultBridge单例实例
 * @returns {ResultBridge} ResultBridge实例
 */
export function getResultBridge() {
  if (!instance) {
    instance = new ResultBridge()
  }
  return instance
}

/**
 * 初始化Result Bridge
 */
export function initializeResultBridge() {
  const bridge = getResultBridge()
  bridge.initialize()
  return bridge
}

/**
 * 重置ResultBridge（主要用于测试）
 */
export function resetResultBridge() {
  instance = null
}

// 导出默认实例
export default getResultBridge()