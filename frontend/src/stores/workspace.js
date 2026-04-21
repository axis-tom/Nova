import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { 
  initializeGraph, 
  runNode, 
  runFromNode, 
  executeAll, 
  markDirtyChain,
  graphRetryNode as retryNode,  // 使用别名
  getStatus as getNodeStatus,
  getNodeResult,
  getGraphState,
  resetGraph,
  NODE_STATE
} from '@/core/graph'

export const useWorkspaceStore = defineStore('workspace', () => {
  // 任务相关状态
  const activeTask = ref(null)
  const tasks = ref([
    { id: 'listing', name: 'Listing生成', description: '生成电商Listing文案' },
    { id: 'customer-service', name: '客服对话', description: 'AI客服对话处理' },
    { id: 'product-selection', name: '选品分析', description: '市场选品分析' }
  ])

  // 策略相关状态
  const strategy = ref({
    tone: 'professional', // 语气: professional, friendly, persuasive
    market: 'global', // 市场: global, us, eu, asia
    seoStrength: 'medium', // SEO强度: low, medium, high
    creativity: 'balanced' // 创意度: conservative, balanced, creative
  })

  // Graph节点状态
  const nodes = ref([])
  const edges = ref([])
  const activeNode = ref(null)

  // 执行结果状态
  const results = ref({}) // nodeId -> result data

  // 节点状态管理
  const nodeStatus = ref({}) // nodeId -> status (idle, running, done, dirty)

  // Graph引擎状态
  const graphEngineInitialized = ref(false)
  const isGraphRunning = ref(false)

  // 任务操作
  const setActiveTask = (task) => {
    activeTask.value = task
    // 初始化Graph数据并初始化Graph引擎
    initializeGraphForTask(task)
  }

  // Graph初始化
  const initializeGraphForTask = (task) => {
    // 根据任务类型初始化节点
    if (task.id === 'listing') {
      nodes.value = [
        { id: 'market-research', type: 'research', label: '市场调研', data: {} },
        { id: 'keyword-analysis', type: 'analysis', label: '关键词分析', data: {} },
        { id: 'content-generation', type: 'generation', label: '内容生成', data: {} },
        { id: 'seo-optimization', type: 'optimization', label: 'SEO优化', data: {} }
      ]
      edges.value = [
        { id: 'e1', source: 'market-research', target: 'keyword-analysis' },
        { id: 'e2', source: 'keyword-analysis', target: 'content-generation' },
        { id: 'e3', source: 'content-generation', target: 'seo-optimization' }
      ]
    } else if (task.id === 'customer-service') {
      nodes.value = [
        { id: 'intent-analysis', type: 'analysis', label: '意图分析', data: {} },
        { id: 'response-generation', type: 'generation', label: '回复生成', data: {} },
        { id: 'sentiment-check', type: 'check', label: '情感检查', data: {} }
      ]
      edges.value = [
        { id: 'e1', source: 'intent-analysis', target: 'response-generation' },
        { id: 'e2', source: 'response-generation', target: 'sentiment-check' }
      ]
    } else if (task.id === 'product-selection') {
      nodes.value = [
        { id: 'market-trends', type: 'research', label: '市场趋势', data: {} },
        { id: 'competitor-analysis', type: 'analysis', label: '竞品分析', data: {} },
        { id: 'profitability', type: 'analysis', label: '盈利分析', data: {} },
        { id: 'risk-assessment', type: 'assessment', label: '风险评估', data: {} }
      ]
      edges.value = [
        { id: 'e1', source: 'market-trends', target: 'competitor-analysis' },
        { id: 'e2', source: 'competitor-analysis', target: 'profitability' },
        { id: 'e3', source: 'profitability', target: 'risk-assessment' }
      ]
    }

    // 初始化节点状态
    nodes.value.forEach(node => {
      nodeStatus.value[node.id] = 'idle'
    })

    // 初始化Graph引擎
    initializeGraphEngine()
  }

  // 初始化Graph引擎
  const initializeGraphEngine = () => {
    try {
      initializeGraph(nodes.value, edges.value)
      graphEngineInitialized.value = true
      console.log('Graph引擎初始化成功')
      
      // 设置状态同步监听
      setupStatusSync()
    } catch (error) {
      console.error('Graph引擎初始化失败:', error)
      graphEngineInitialized.value = false
    }
  }

  // 设置状态同步
  const setupStatusSync = () => {
    // 定期同步Graph引擎状态到store
    // 实际项目中可以使用事件监听
    setInterval(() => {
      if (graphEngineInitialized.value) {
        syncGraphState()
      }
    }, 1000)
  }

  // 同步Graph状态
  const syncGraphState = () => {
    try {
      const graphState = getGraphState()
      
      // 同步节点状态
      graphState.nodes.forEach(graphNode => {
        const currentStatus = nodeStatus.value[graphNode.id]
        if (currentStatus !== graphNode.status) {
          nodeStatus.value[graphNode.id] = graphNode.status
        }
      })
      
      // 同步结果
      Object.keys(graphState.results).forEach(nodeId => {
        if (!results.value[nodeId] || JSON.stringify(results.value[nodeId]) !== JSON.stringify(graphState.results[nodeId])) {
          results.value[nodeId] = graphState.results[nodeId]
        }
      })
      
      // 同步运行状态
      isGraphRunning.value = graphState.isRunning
    } catch (error) {
      console.error('同步Graph状态失败:', error)
    }
  }

  // 策略操作
  const updateStrategy = (newStrategy) => {
    strategy.value = { ...strategy.value, ...newStrategy }
    // 标记所有节点为dirty
    Object.keys(nodeStatus.value).forEach(nodeId => {
      if (nodeStatus.value[nodeId] === 'done') {
        nodeStatus.value[nodeId] = 'dirty'
      }
    })
  }

  // 节点操作
  const setActiveNode = (nodeId) => {
    activeNode.value = nodes.value.find(n => n.id === nodeId) || null
  }

  const markNodeDirty = (nodeId) => {
    if (nodeStatus.value[nodeId]) {
      nodeStatus.value[nodeId] = 'dirty'
    }
  }

  const updateNodeStatus = (nodeId, status) => {
    if (nodeStatus.value[nodeId]) {
      nodeStatus.value[nodeId] = status
    }
  }

  // 结果操作
  const updateResult = (nodeId, resultData) => {
    results.value[nodeId] = resultData
    // 标记节点为dirty（因为结果被编辑）
    markNodeDirty(nodeId)
  }

  // Graph执行操作
  const executeNode = async (nodeId) => {
    if (!graphEngineInitialized.value) {
      console.error('Graph引擎未初始化')
      throw new Error('Graph引擎未初始化')
    }

    try {
      isGraphRunning.value = true
      const result = await runNode(nodeId)
      syncGraphState() // 立即同步状态
      return result
    } catch (error) {
      console.error(`执行节点 ${nodeId} 失败:`, error)
      syncGraphState() // 同步错误状态
      throw error
    } finally {
      isGraphRunning.value = false
    }
  }

  const executeFromNode = async (nodeId) => {
    if (!graphEngineInitialized.value) {
      console.error('Graph引擎未初始化')
      throw new Error('Graph引擎未初始化')
    }

    try {
      isGraphRunning.value = true
      const results = await runFromNode(nodeId)
      syncGraphState() // 立即同步状态
      return results
    } catch (error) {
      console.error(`从节点 ${nodeId} 开始执行失败:`, error)
      syncGraphState() // 同步错误状态
      throw error
    } finally {
      isGraphRunning.value = false
    }
  }

  const executeAllNodes = async () => {
    console.log('workspace.executeAllNodes 开始执行');
    
    if (!graphEngineInitialized.value) {
      console.error('Graph引擎未初始化');
      throw new Error('Graph引擎未初始化');
    }

    try {
      // ✅ 在执行前重置所有节点状态，确保全新执行
      resetGraphState();
      
      isGraphRunning.value = true;
      console.log('准备调用 graphEngine.executeAll');
      const results = await executeAll();
      console.log('graphEngine.executeAll 返回结果:', results);
      syncGraphState();
      return results;
    } catch (error) {
      console.error('执行所有节点失败:', error);
      syncGraphState();
      throw error;
    } finally {
      isGraphRunning.value = false;
      console.log('workspace.executeAllNodes 执行结束');
    }
  };

  const markNodeChainDirty = (nodeId) => {
    if (!graphEngineInitialized.value) {
      console.error('Graph引擎未初始化')
      return
    }

    try {
      markDirtyChain(nodeId)
      syncGraphState() // 立即同步状态
    } catch (error) {
      console.error(`标记节点 ${nodeId} 脏链失败:`, error)
    }
  }

  const retryFailedNode = async (nodeId) => {
    if (!graphEngineInitialized.value) {
      console.error('Graph引擎未初始化')
      throw new Error('Graph引擎未初始化')
    }

    try {
      isGraphRunning.value = true
      const result = await retryNode(nodeId)
      syncGraphState() // 立即同步状态
      return result
    } catch (error) {
      console.error(`重试节点 ${nodeId} 失败:`, error)
      syncGraphState() // 同步错误状态
      throw error
    } finally {
      isGraphRunning.value = false
    }
  }

  const resetGraphState = () => {
    if (!graphEngineInitialized.value) {
      console.error('Graph引擎未初始化')
      return
    }

    try {
      resetGraph()
      // 重置本地状态
      Object.keys(nodeStatus.value).forEach(nodeId => {
        nodeStatus.value[nodeId] = 'idle'
      })
      results.value = {}
      isGraphRunning.value = false
      console.log('Graph状态已重置')
    } catch (error) {
      console.error('重置Graph状态失败:', error)
    }
  }

  // 获取节点状态（从Graph引擎）
  const getNodeStatusFromEngine = (nodeId) => {
    if (!graphEngineInitialized.value) {
      return nodeStatus.value[nodeId] || 'idle'
    }

    try {
      return getNodeStatus(nodeId)
    } catch (error) {
      console.error(`获取节点 ${nodeId} 状态失败:`, error)
      return nodeStatus.value[nodeId] || 'idle'
    }
  }

  // 获取节点结果（从Graph引擎）
  const getNodeResultFromEngine = (nodeId) => {
    if (!graphEngineInitialized.value) {
      return results.value[nodeId] || null
    }

    try {
      return getNodeResult(nodeId)
    } catch (error) {
      console.error(`获取节点 ${nodeId} 结果失败:`, error)
      return results.value[nodeId] || null
    }
  }

  // 计算属性
  const activeNodeResult = computed(() => {
    if (!activeNode.value) return null
    return results.value[activeNode.value.id]
  })

  const activeNodeStatus = computed(() => {
    if (!activeNode.value) return null
    return nodeStatus.value[activeNode.value.id]
  })

  // 更多计算属性
  const graphEngineReady = computed(() => graphEngineInitialized.value)
  const canExecuteNode = computed(() => (nodeId) => {
    const status = nodeStatus.value[nodeId]
    return status === 'idle' || status === 'dirty'
  })
  
  const executionProgress = computed(() => {
    const total = nodes.value.length
    if (total === 0) return 0
    
    const completed = Object.values(nodeStatus.value).filter(status => status === 'done').length
    return Math.round((completed / total) * 100)
  })

  return {
    // 状态
    activeTask,
    tasks,
    strategy,
    nodes,
    edges,
    activeNode,
    results,
    nodeStatus,
    graphEngineInitialized,
    isGraphRunning,
    
    // 计算属性
    activeNodeResult,
    activeNodeStatus,
    graphEngineReady,
    canExecuteNode,
    executionProgress,
    
    // 操作
    setActiveTask,
    updateStrategy,
    setActiveNode,
    markNodeDirty,
    updateNodeStatus,
    updateResult,
    
    // Graph执行操作
    executeNode,
    executeFromNode,
    executeAllNodes,
    markNodeChainDirty,
    retryFailedNode,
    resetGraphState,
    getNodeStatusFromEngine,
    getNodeResultFromEngine,
    
    // 常量
    NODE_STATE
  }
})