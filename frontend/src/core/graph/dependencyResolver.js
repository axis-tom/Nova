/**
 * 依赖解析器
 * 
 * 职责：判断节点是否可执行，解析依赖关系
 * 
 * 规则：
 * - upstream全部done → 可执行
 * - 否则return false
 */

import * as nodeStateMachine from './nodeStateMachine.js'

/**
 * 检查节点是否可执行
 * @param {string} nodeId - 节点ID
 * @param {Array} allNodes - 所有节点数组
 * @returns {boolean} 是否可执行
 */
export function canExecute(nodeId, allNodes) {
  const node = findNode(nodeId, allNodes)
  if (!node) {
    console.warn(`节点 ${nodeId} 不存在`)
    return false
  }

  // 如果没有上游依赖，可以直接执行
  if (!node.upstream || node.upstream.length === 0) {
    return true
  }

  // 检查所有上游节点是否都已完成
  const allUpstreamDone = node.upstream.every(upstreamId => {
    const upstreamNode = findNode(upstreamId, allNodes)
    if (!upstreamNode) {
      console.warn(`上游节点 ${upstreamId} 不存在`)
      return false
    }
    
    return nodeStateMachine.isDone(upstreamId)
  })

  return allUpstreamDone
}

/**
 * 获取节点的执行顺序
 * @param {Array} nodes - 节点数组
 * @returns {Array} 执行顺序（节点ID数组）
 */
export function getExecutionOrder(nodes) {
  if (!nodes || nodes.length === 0) {
    return []
  }

  // 构建图数据结构
  const graph = buildDependencyGraph(nodes)
  
  // 拓扑排序
  const executionOrder = topologicalSort(graph)
  
  return executionOrder
}

/**
 * 获取节点的下游链
 * @param {string} nodeId - 节点ID
 * @param {Array} allNodes - 所有节点数组
 * @returns {Array} 下游节点ID数组
 */
export function getDownstreamChain(nodeId, allNodes) {
  const visited = new Set()
  const downstreamChain = []
  
  function traverse(currentNodeId) {
    if (visited.has(currentNodeId)) {
      return
    }
    
    visited.add(currentNodeId)
    
    const node = findNode(currentNodeId, allNodes)
    if (!node) {
      return
    }
    
    // 添加当前节点到下游链（除了起始节点）
    if (currentNodeId !== nodeId) {
      downstreamChain.push(currentNodeId)
    }
    
    // 递归遍历下游节点
    if (node.downstream && node.downstream.length > 0) {
      node.downstream.forEach(downstreamId => {
        traverse(downstreamId)
      })
    }
  }
  
  // 从起始节点的下游开始遍历
  const startNode = findNode(nodeId, allNodes)
  if (startNode && startNode.downstream) {
    startNode.downstream.forEach(downstreamId => {
      traverse(downstreamId)
    })
  }
  
  return downstreamChain
}

/**
 * 获取节点的上游链
 * @param {string} nodeId - 节点ID
 * @param {Array} allNodes - 所有节点数组
 * @returns {Array} 上游节点ID数组
 */
export function getUpstreamChain(nodeId, allNodes) {
  const visited = new Set()
  const upstreamChain = []
  
  function traverse(currentNodeId) {
    if (visited.has(currentNodeId)) {
      return
    }
    
    visited.add(currentNodeId)
    
    const node = findNode(currentNodeId, allNodes)
    if (!node) {
      return
    }
    
    // 添加当前节点到上游链（除了目标节点）
    if (currentNodeId !== nodeId) {
      upstreamChain.push(currentNodeId)
    }
    
    // 递归遍历上游节点
    if (node.upstream && node.upstream.length > 0) {
      node.upstream.forEach(upstreamId => {
        traverse(upstreamId)
      })
    }
  }
  
  // 从目标节点的上游开始遍历
  const targetNode = findNode(nodeId, allNodes)
  if (targetNode && targetNode.upstream) {
    targetNode.upstream.forEach(upstreamId => {
      traverse(upstreamId)
    })
  }
  
  return upstreamChain
}

/**
 * 检查节点是否有循环依赖
 * @param {Array} nodes - 节点数组
 * @returns {boolean} 是否有循环依赖
 */
export function hasCyclicDependency(nodes) {
  const graph = buildDependencyGraph(nodes)
  return hasCycle(graph)
}

/**
 * 获取节点的直接依赖
 * @param {string} nodeId - 节点ID
 * @param {Array} allNodes - 所有节点数组
 * @returns {Object} 直接依赖信息
 */
export function getDirectDependencies(nodeId, allNodes) {
  const node = findNode(nodeId, allNodes)
  if (!node) {
    return { upstream: [], downstream: [] }
  }
  
  return {
    upstream: node.upstream || [],
    downstream: node.downstream || []
  }
}

/**
 * 获取节点的所有依赖（包括间接依赖）
 * @param {string} nodeId - 节点ID
 * @param {Array} allNodes - 所有节点数组
 * @returns {Object} 所有依赖信息
 */
export function getAllDependencies(nodeId, allNodes) {
  return {
    upstream: getUpstreamChain(nodeId, allNodes),
    downstream: getDownstreamChain(nodeId, allNodes)
  }
}

/**
 * 检查节点是否被阻塞
 * @param {string} nodeId - 节点ID
 * @param {Array} allNodes - 所有节点数组
 * @returns {Object} 阻塞状态和信息
 */
export function getBlockingStatus(nodeId, allNodes) {
  const node = findNode(nodeId, allNodes)
  if (!node) {
    return {
      isBlocked: true,
      reason: '节点不存在',
      blockingNodes: []
    }
  }
  
  // 如果没有上游依赖，不会被阻塞
  if (!node.upstream || node.upstream.length === 0) {
    return {
      isBlocked: false,
      reason: null,
      blockingNodes: []
    }
  }
  
  // 找出未完成的上游节点
  const blockingNodes = node.upstream.filter(upstreamId => {
    return !nodeStateMachine.isDone(upstreamId)
  })
  
  return {
    isBlocked: blockingNodes.length > 0,
    reason: blockingNodes.length > 0 ? '上游节点未完成' : null,
    blockingNodes
  }
}

/**
 * 获取可立即执行的节点
 * @param {Array} nodes - 节点数组
 * @returns {Array} 可执行节点ID数组
 */
export function getExecutableNodes(nodes) {
  if (!nodes || nodes.length === 0) {
    return []
  }
  
  return nodes
    .filter(node => canExecute(node.id, nodes))
    .map(node => node.id)
}

/**
 * 获取执行进度
 * @param {Array} nodes - 节点数组
 * @returns {Object} 执行进度信息
 */
export function getExecutionProgress(nodes) {
  if (!nodes || nodes.length === 0) {
    return {
      total: 0,
      completed: 0,
      pending: 0,
      blocked: 0,
      progress: 0
    }
  }
  
  let completed = 0
  let pending = 0
  let blocked = 0
  
  nodes.forEach(node => {
    const status = nodeStateMachine.getStatus(node.id)
    
    if (status === 'done') {
      completed++
    } else if (canExecute(node.id, nodes)) {
      pending++
    } else {
      blocked++
    }
  })
  
  const total = nodes.length
  const progress = total > 0 ? (completed / total) * 100 : 0
  
  return {
    total,
    completed,
    pending,
    blocked,
    progress: Math.round(progress)
  }
}

/**
 * 构建依赖图
 * @param {Array} nodes - 节点数组
 * @returns {Object} 图数据结构
 */
function buildDependencyGraph(nodes) {
  const graph = {
    nodes: new Map(),
    edges: []
  }
  
  // 添加节点
  nodes.forEach(node => {
    graph.nodes.set(node.id, {
      id: node.id,
      upstream: node.upstream || [],
      downstream: node.downstream || []
    })
  })
  
  // 添加边
  nodes.forEach(node => {
    if (node.downstream && node.downstream.length > 0) {
      node.downstream.forEach(downstreamId => {
        graph.edges.push({
          from: node.id,
          to: downstreamId
        })
      })
    }
  })
  
  return graph
}

/**
 * 拓扑排序
 * @param {Object} graph - 图数据结构
 * @returns {Array} 拓扑排序结果
 */
function topologicalSort(graph) {
  const result = []
  const visited = new Set()
  const temp = new Set()
  const nodes = Array.from(graph.nodes.values())
  
  function visit(node) {
    if (temp.has(node.id)) {
      throw new Error('图中存在循环依赖')
    }
    
    if (!visited.has(node.id)) {
      temp.add(node.id)
      
      // 先访问所有下游节点
      if (node.downstream && node.downstream.length > 0) {
        node.downstream.forEach(downstreamId => {
          const downstreamNode = graph.nodes.get(downstreamId)
          if (downstreamNode) {
            visit(downstreamNode)
          }
        })
      }
      
      temp.delete(node.id)
      visited.add(node.id)
      result.unshift(node.id) // 添加到结果开头
    }
  }
  
  // 从所有节点开始访问
  nodes.forEach(node => {
    if (!visited.has(node.id)) {
      visit(node)
    }
  })
  
  return result
}

/**
 * 检查图中是否有环
 * @param {Object} graph - 图数据结构
 * @returns {boolean} 是否有环
 */
function hasCycle(graph) {
  const visited = new Set()
  const recursionStack = new Set()
  
  function dfs(nodeId) {
    if (recursionStack.has(nodeId)) {
      return true
    }
    
    if (visited.has(nodeId)) {
      return false
    }
    
    visited.add(nodeId)
    recursionStack.add(nodeId)
    
    const node = graph.nodes.get(nodeId)
    if (node && node.downstream) {
      for (const downstreamId of node.downstream) {
        if (dfs(downstreamId)) {
          return true
        }
      }
    }
    
    recursionStack.delete(nodeId)
    return false
  }
  
  for (const nodeId of graph.nodes.keys()) {
    if (dfs(nodeId)) {
      return true
    }
  }
  
  return false
}

/**
 * 查找节点
 * @param {string} nodeId - 节点ID
 * @param {Array} nodes - 节点数组
 * @returns {Object} 节点对象
 */
function findNode(nodeId, nodes) {
  return nodes.find(node => node.id === nodeId)
}

/**
 * 验证依赖关系
 * @param {Array} nodes - 节点数组
 * @returns {Object} 验证结果
 */
export function validateDependencies(nodes) {
  const errors = []
  const warnings = []
  
  // 检查节点是否存在
  nodes.forEach(node => {
    // 检查上游节点是否存在
    if (node.upstream) {
      node.upstream.forEach(upstreamId => {
        if (!findNode(upstreamId, nodes)) {
          errors.push(`节点 ${node.id} 的上游节点 ${upstreamId} 不存在`)
        }
      })
    }
    
    // 检查下游节点是否存在
    if (node.downstream) {
      node.downstream.forEach(downstreamId => {
        if (!findNode(downstreamId, nodes)) {
          errors.push(`节点 ${node.id} 的下游节点 ${downstreamId} 不存在`)
        }
      })
    }
  })
  
  // 检查循环依赖
  if (hasCyclicDependency(nodes)) {
    errors.push('图中存在循环依赖')
  }
  
  // 检查孤立节点
  const isolatedNodes = nodes.filter(node => {
    const hasUpstream = node.upstream && node.upstream.length > 0
    const hasDownstream = node.downstream && node.downstream.length > 0
    return !hasUpstream && !hasDownstream
  })
  
  if (isolatedNodes.length > 0) {
    warnings.push(`发现 ${isolatedNodes.length} 个孤立节点`)
  }
  
  return {
    isValid: errors.length === 0,
    errors,
    warnings
  }
}