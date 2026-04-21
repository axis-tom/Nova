/**
 * Graph执行引擎 - Nova的"执行大脑"
 * 
 * 职责：让Graph能够运行、传播、回溯、重试
 * 
 * 核心原则：
 * 1. UI不能直接执行任务
 * 2. UI不能修改node.status
 * 3. UI不能绕过graphEngine
 * 4. UI只能在组件中dispatch action
 */

import * as dependencyResolver from './dependencyResolver.js';
import * as executionQueue from './executionQueue.js';
import * as nodeStateMachine from './nodeStateMachine.js';
import * as nodeRunner from './nodeRunner.js';

/**
 * Graph引擎配置
 */
const config = {
  maxRetries: 3,
  retryDelay: 1000,
  executionTimeout: 30000,
  enableParallelExecution: false
}

/**
 * Graph引擎状态
 */
let graphState = {
  nodes: [],
  edges: [],
  results: {},
  executionHistory: [],
  isRunning: false
}

/**
 * 初始化Graph引擎
 * @param {Array} nodes - 节点数组
 * @param {Array} edges - 边数组
 */
export function initializeGraph(nodes, edges) {
  graphState = {
    nodes: nodes.map(node => ({
      ...node,
      status: 'idle',
      input: null,
      output: null,
      config: {},
      upstream: [],
      downstream: [],
      retryCount: 0
    })),
    edges: edges || [],
    results: {},
    executionHistory: [],
    isRunning: false
  }

  // 构建上下游关系
  buildDependencyGraph()
  
  console.log('Graph引擎初始化完成', {
    nodes: graphState.nodes.length,
    edges: graphState.edges.length
  })
}

/**
 * 构建依赖关系图
 */
function buildDependencyGraph() {
  const nodeMap = new Map()
  
  // 创建节点映射
  graphState.nodes.forEach(node => {
    nodeMap.set(node.id, node)
    node.upstream = []
    node.downstream = []
  })

  // 构建上下游关系
  graphState.edges.forEach(edge => {
    const sourceNode = nodeMap.get(edge.source)
    const targetNode = nodeMap.get(edge.target)
    
    if (sourceNode && targetNode) {
      sourceNode.downstream.push(targetNode.id)
      targetNode.upstream.push(sourceNode.id)
    }
  })
}

/**
 * 获取节点
 * @param {string} nodeId - 节点ID
 * @returns {Object} 节点对象
 */
function getNode(nodeId) {
  return graphState.nodes.find(node => node.id === nodeId)
}

/**
 * 获取节点状态
 * @param {string} nodeId - 节点ID
 * @returns {string} 节点状态
 */
export function getNodeStatus(nodeId) {
  const node = getNode(nodeId)
  return node ? node.status : 'idle'
}

/**
 * 获取节点结果
 * @param {string} nodeId - 节点ID
 * @returns {any} 节点结果
 */
export function getNodeResult(nodeId) {
  return graphState.results[nodeId]
}

/**
 * 1️⃣ runNode - 单节点执行
 * @param {string} nodeId - 节点ID
 * @returns {Promise} 执行结果
 */
export async function runNode(nodeId) {
  console.log(`执行单节点: ${nodeId}`)
  
  const node = getNode(nodeId)
  if (!node) {
    throw new Error(`节点不存在: ${nodeId}`)
  }

  // 检查依赖是否满足
  const canExecute = dependencyResolver.canExecute(nodeId, graphState.nodes)
  if (!canExecute) {
    console.log(`节点 ${nodeId} 依赖未满足，等待上游完成`)
    return Promise.reject(new Error('依赖未满足'))
  }

  // 添加到执行队列
  return executionQueue.enqueue(async () => {
    try {
      // 更新状态为running
      nodeStateMachine.setStatus(nodeId, 'running')
      
      // 收集上游结果作为输入
      const input = collectUpstreamResults(nodeId)
      
      // 执行节点
      const output = await nodeRunner.execute(node, input)
      
      // 更新状态为done
      nodeStateMachine.setStatus(nodeId, 'done')
      
      // 保存结果
      graphState.results[nodeId] = output
      
      // 记录执行历史
      graphState.executionHistory.push({
        nodeId,
        timestamp: new Date().toISOString(),
        status: 'success',
        input,
        output
      })
      
      console.log(`节点 ${nodeId} 执行成功`)
      return output
      
    } catch (error) {
      // 更新状态为error
      nodeStateMachine.setStatus(nodeId, 'error')
      
      // 记录错误历史
      graphState.executionHistory.push({
        nodeId,
        timestamp: new Date().toISOString(),
        status: 'error',
        error: error.message
      })
      
      console.error(`节点 ${nodeId} 执行失败:`, error)
      throw error
    }
  })
}

/**
 * 2️⃣ runFromNode - 链式执行
 * @param {string} nodeId - 起始节点ID
 * @returns {Promise} 执行结果
 */
export async function runFromNode(nodeId) {
  console.log(`从节点 ${nodeId} 开始链式执行`)
  
  const results = {}
  const visited = new Set()
  
  async function executeChain(currentNodeId) {
    if (visited.has(currentNodeId)) {
      return
    }
    
    visited.add(currentNodeId)
    
    try {
      // 执行当前节点
      const result = await runNode(currentNodeId)
      results[currentNodeId] = result
      
      // 获取下游节点
      const node = getNode(currentNodeId)
      if (node && node.downstream.length > 0) {
        // 递归执行下游节点
        for (const downstreamId of node.downstream) {
          await executeChain(downstreamId)
        }
      }
      
    } catch (error) {
      console.error(`节点 ${currentNodeId} 执行失败，停止链式执行:`, error)
      throw error
    }
  }
  
  try {
    await executeChain(nodeId)
    console.log(`链式执行完成，共执行 ${visited.size} 个节点`)
    return results
  } catch (error) {
    console.error('链式执行失败:', error)
    throw error
  }
}

/**
 * 3️⃣ markDirtyChain - 脏链标记
 * @param {string} nodeId - 起始节点ID
 */
export function markDirtyChain(nodeId) {
  console.log(`标记脏链: ${nodeId}`)
  
  const visited = new Set()
  
  function markChain(currentNodeId) {
    if (visited.has(currentNodeId)) {
      return
    }
    
    visited.add(currentNodeId)
    
    // 标记当前节点为dirty
    const node = getNode(currentNodeId)
    if (node && node.status === 'done') {
      nodeStateMachine.setStatus(currentNodeId, 'dirty')
    }
    
    // 递归标记下游节点
    if (node && node.downstream.length > 0) {
      node.downstream.forEach(downstreamId => {
        markChain(downstreamId)
      })
    }
  }
  
  markChain(nodeId)
  console.log(`脏链标记完成，共标记 ${visited.size} 个节点`)
}

/**
 * 4️⃣ retryNode - 重试节点
 * @param {string} nodeId - 节点ID
 * @returns {Promise} 重试结果
 */
export async function retryNode(nodeId) {
  console.log(`重试节点: ${nodeId}`)
  
  const node = getNode(nodeId)
  if (!node) {
    throw new Error(`节点不存在: ${nodeId}`)
  }
  
  // 重置节点状态
  nodeStateMachine.resetNode(nodeId)
  
  // 执行节点
  return runNode(nodeId)
}

/**
 * 5️⃣ executeAll - 执行所有节点
 * @returns {Promise} 所有节点结果
 */
export async function executeAll() {
  console.log('执行所有节点')
  
  const results = {}
  const executionOrder = dependencyResolver.getExecutionOrder(graphState.nodes)
  
  for (const nodeId of executionOrder) {
    try {
      const result = await runNode(nodeId)
      results[nodeId] = result
    } catch (error) {
      console.error(`节点 ${nodeId} 执行失败，停止执行全部:`, error)
      throw error
    }
  }
  
  console.log(`全部节点执行完成，共执行 ${executionOrder.length} 个节点`)
  return results
}

/**
 * 收集上游结果作为输入
 * @param {string} nodeId - 节点ID
 * @returns {Object} 输入数据
 */
function collectUpstreamResults(nodeId) {
  const node = getNode(nodeId)
  if (!node || node.upstream.length === 0) {
    return null
  }
  
  const input = {}
  node.upstream.forEach(upstreamId => {
    const upstreamResult = graphState.results[upstreamId]
    if (upstreamResult !== undefined) {
      input[upstreamId] = upstreamResult
    }
  })
  
  return input
}

/**
 * 获取Graph状态
 * @returns {Object} Graph状态
 */
export function getGraphState() {
  return {
    nodes: graphState.nodes.map(node => ({
      id: node.id,
      type: node.type,
      label: node.label,
      status: node.status,
      upstream: node.upstream,
      downstream: node.downstream,
      retryCount: node.retryCount
    })),
    edges: graphState.edges,
    results: graphState.results,
    executionHistory: graphState.executionHistory,
    isRunning: graphState.isRunning
  }
}

/**
 * 重置Graph状态
 */
export function resetGraph() {
  graphState.nodes.forEach(node => {
    nodeStateMachine.resetNode(node.id)
  })
  
  graphState.results = {}
  graphState.executionHistory = []
  graphState.isRunning = false
  
  console.log('Graph状态已重置')
}

/**
 * 获取执行历史
 * @returns {Array} 执行历史记录
 */
export function getExecutionHistory() {
  return [...graphState.executionHistory]
}

/**
 * 检查Graph是否正在运行
 * @returns {boolean} 是否正在运行
 */
export function isGraphRunning() {
  return graphState.isRunning
}

/**
 * 设置Graph运行状态
 * @param {boolean} running - 运行状态
 */
export function setGraphRunning(running) {
  graphState.isRunning = running
}