import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  initializeGraph,
  runNode,
  runFromNode,
  executeAll,
  markDirtyChain,
  graphRetryNode as retryNode,
  getStatus as getNodeStatus,
  getNodeResult,
  getGraphState,
  resetGraph,
  NODE_STATE,
} from '@/core/graph'

interface Task {
  id: string
  name: string
  description: string
}

interface Strategy {
  tone: string
  market: string
  seoStrength: string
  creativity: string
}

interface Node {
  id: string
  type: string
  label: string
  data: Record<string, unknown>
}

interface Edge {
  id: string
  source: string
  target: string
}

type NodeStatusMap = Record<string, string>
type ResultsMap = Record<string, unknown>

export const useWorkspaceStore = defineStore('workspace', () => {
  const activeTask = ref<Task | null>(null)
  const tasks = ref<Task[]>([
    { id: 'listing', name: 'Listing生成', description: '生成电商Listing文案' },
    { id: 'customer-service', name: '客服对话', description: 'AI客服对话处理' },
    { id: 'product-selection', name: '选品分析', description: '市场选品分析' },
  ])
  const strategy = ref<Strategy>({
    tone: 'professional',
    market: 'global',
    seoStrength: 'medium',
    creativity: 'balanced',
  })

  const nodes = ref<Node[]>([])
  const edges = ref<Edge[]>([])
  const activeNode = ref<Node | null>(null)
  const results = ref<ResultsMap>({})
  const nodeStatus = ref<NodeStatusMap>({})
  const graphEngineInitialized = ref<boolean>(false)
  const isGraphRunning = ref<boolean>(false)

  const initializeGraphForTask = (task: Task) => {
    if (task.id === 'listing') {
      nodes.value = [
        { id: 'market-research', type: 'research', label: '市场调研', data: {} },
        { id: 'keyword-analysis', type: 'analysis', label: '关键词分析', data: {} },
        { id: 'content-generation', type: 'generation', label: '内容生成', data: {} },
        { id: 'seo-optimization', type: 'optimization', label: 'SEO优化', data: {} },
      ]
      edges.value = [
        { id: 'e1', source: 'market-research', target: 'keyword-analysis' },
        { id: 'e2', source: 'keyword-analysis', target: 'content-generation' },
        { id: 'e3', source: 'content-generation', target: 'seo-optimization' },
      ]
    } else if (task.id === 'customer-service') {
      nodes.value = [
        { id: 'intent-analysis', type: 'analysis', label: '意图分析', data: {} },
        { id: 'response-generation', type: 'generation', label: '回复生成', data: {} },
        { id: 'sentiment-check', type: 'check', label: '情感检查', data: {} },
      ]
      edges.value = [
        { id: 'e1', source: 'intent-analysis', target: 'response-generation' },
        { id: 'e2', source: 'response-generation', target: 'sentiment-check' },
      ]
    } else if (task.id === 'product-selection') {
      nodes.value = [
        { id: 'market-trends', type: 'research', label: '市场趋势', data: {} },
        { id: 'competitor-analysis', type: 'analysis', label: '竞品分析', data: {} },
        { id: 'profitability', type: 'analysis', label: '盈利分析', data: {} },
        { id: 'risk-assessment', type: 'assessment', label: '风险评估', data: {} },
      ]
      edges.value = [
        { id: 'e1', source: 'market-trends', target: 'competitor-analysis' },
        { id: 'e2', source: 'competitor-analysis', target: 'profitability' },
        { id: 'e3', source: 'profitability', target: 'risk-assessment' },
      ]
    }
    nodes.value.forEach((node) => {
      nodeStatus.value[node.id] = 'idle'
    })
    initializeGraphEngine()
  }

  const initializeGraphEngine = () => {
    try {
      initializeGraph(nodes.value as any, edges.value as any) // 暂时的兼容
      graphEngineInitialized.value = true
      setupStatusSync()
    } catch (error) {
      console.error('Graph引擎初始化失败:', error)
      graphEngineInitialized.value = false
    }
  }

  let syncTimer: ReturnType<typeof setInterval> | null = null
  const setupStatusSync = () => {
    if (syncTimer) clearInterval(syncTimer)
    syncTimer = setInterval(() => {
      if (graphEngineInitialized.value) syncGraphState()
    }, 1000)
  }

  const syncGraphState = () => {
    try {
      const graphState = getGraphState() as {
        nodes: { id: string; status: string }[]
        results: ResultsMap
        isRunning: boolean
      }
      graphState.nodes.forEach((gNode) => {
        nodeStatus.value[gNode.id] = gNode.status
      })
      Object.keys(graphState.results).forEach((nodeId) => {
        results.value[nodeId] = graphState.results[nodeId]
      })
      isGraphRunning.value = graphState.isRunning
    } catch (error) {
      console.error('同步Graph状态失败:', error)
    }
  }

  const setActiveTask = (task: Task) => {
    activeTask.value = task
    initializeGraphForTask(task)
  }

  const updateStrategy = (newStrategy: Partial<Strategy>) => {
    strategy.value = { ...strategy.value, ...newStrategy }
    Object.keys(nodeStatus.value).forEach((nodeId) => {
      if (nodeStatus.value[nodeId] === 'done') {
        nodeStatus.value[nodeId] = 'dirty'
      }
    })
  }

  const setActiveNode = (nodeId: string) => {
    activeNode.value = nodes.value.find((n) => n.id === nodeId) || null
  }

  const markNodeDirty = (nodeId: string) => {
    if (nodeStatus.value[nodeId]) nodeStatus.value[nodeId] = 'dirty'
  }

  const updateNodeStatus = (nodeId: string, status: string) => {
    if (nodeStatus.value[nodeId]) nodeStatus.value[nodeId] = status
  }

  const updateResult = (nodeId: string, resultData: unknown) => {
    results.value[nodeId] = resultData
    markNodeDirty(nodeId)
  }

  const executeNode = async (nodeId: string) => {
    if (!graphEngineInitialized.value) throw new Error('Graph引擎未初始化')
    isGraphRunning.value = true
    try {
      const result = await runNode(nodeId)
      syncGraphState()
      return result
    } finally {
      isGraphRunning.value = false
    }
  }

  const executeFromNode = async (nodeId: string) => {
    if (!graphEngineInitialized.value) throw new Error('Graph引擎未初始化')
    isGraphRunning.value = true
    try {
      const results = await runFromNode(nodeId)
      syncGraphState()
      return results
    } finally {
      isGraphRunning.value = false
    }
  }

  const executeAllNodes = async () => {
    if (!graphEngineInitialized.value) throw new Error('Graph引擎未初始化')
    resetGraphState()
    isGraphRunning.value = true
    try {
      const results = await executeAll()
      syncGraphState()
      return results
    } finally {
      isGraphRunning.value = false
    }
  }

  const markNodeChainDirty = (nodeId: string) => {
    if (!graphEngineInitialized.value) return
    markDirtyChain(nodeId)
    syncGraphState()
  }

  const retryFailedNode = async (nodeId: string) => {
    if (!graphEngineInitialized.value) throw new Error('Graph引擎未初始化')
    isGraphRunning.value = true
    try {
      const result = await retryNode(nodeId)
      syncGraphState()
      return result
    } finally {
      isGraphRunning.value = false
    }
  }

  const resetGraphState = () => {
    if (!graphEngineInitialized.value) return
    resetGraph()
    Object.keys(nodeStatus.value).forEach((nodeId) => {
      nodeStatus.value[nodeId] = 'idle'
    })
    results.value = {}
    isGraphRunning.value = false
  }

  const getNodeStatusFromEngine = (nodeId: string) => {
    if (!graphEngineInitialized.value) return nodeStatus.value[nodeId] || 'idle'
    return getNodeStatus(nodeId) as any
  }

  const getNodeResultFromEngine = (nodeId: string) => {
    if (!graphEngineInitialized.value) return results.value[nodeId] || null
    return getNodeResult(nodeId) as any
  }

  const activeNodeResult = computed(() =>
    activeNode.value ? results.value[activeNode.value.id] : null
  )
  const activeNodeStatus = computed(() =>
    activeNode.value ? nodeStatus.value[activeNode.value.id] : null
  )
  const graphEngineReady = computed(() => graphEngineInitialized.value)
  const canExecuteNode = computed(() => (nodeId: string) => {
    const status = nodeStatus.value[nodeId]
    return status === 'idle' || status === 'dirty'
  })
  const executionProgress = computed(() => {
    const total = nodes.value.length
    if (total === 0) return 0
    const completed = Object.values(nodeStatus.value).filter(
      (status) => status === 'done'
    ).length
    return Math.round((completed / total) * 100)
  })

  return {
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
    activeNodeResult,
    activeNodeStatus,
    graphEngineReady,
    canExecuteNode,
    executionProgress,
    setActiveTask,
    updateStrategy,
    setActiveNode,
    markNodeDirty,
    updateNodeStatus,
    updateResult,
    executeNode,
    executeFromNode,
    executeAllNodes,
    markNodeChainDirty,
    retryFailedNode,
    resetGraphState,
    getNodeStatusFromEngine,
    getNodeResultFromEngine,
    NODE_STATE,
  }
})