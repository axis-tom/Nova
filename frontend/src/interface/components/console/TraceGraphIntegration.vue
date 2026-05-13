<template>
  <div class="trace-graph-integration">
    <!-- 控制栏 -->
    <div class="integration-controls">
      <div class="controls-left">
        <div class="integration-title">
          <h3>Trace & Graph 整合视图</h3>
          <p class="subtitle">左Trace详情，右Graph可视化，双向同步</p>
        </div>
        <div class="trace-info" v-if="currentTrace">
          <span class="info-item">
            <i class="el-icon-data-line"></i>
            {{ (currentTrace as TraceData).session.graph_name || (currentTrace as TraceData).session.graph_id }}
          </span>
          <span class="info-item">
            <i class="el-icon-time"></i>
            {{ formatDuration((currentTrace as TraceData).session.duration) }}
          </span>
          <span class="info-item">
            <i class="el-icon-s-check"></i>
            {{ ((currentTrace as TraceData).nodes as TraceNode[]).filter((n: TraceNode) => n.status === 'completed').length }}/{{ ((currentTrace as TraceData).nodes as TraceNode[]).length }}
          </span>
          <span class="info-item">
            <i class="el-icon-user"></i>
            {{ (currentTrace as TraceData).session.status }}
          </span>
        </div>
      </div>
      <div class="controls-right">
        <el-button-group size="small">
          <el-button 
            icon="el-icon-refresh" 
            @click="refreshTraceData"
            :loading="loading"
          >刷新</el-button>
          <el-button 
            icon="el-icon-download" 
            @click="exportData"
          >导出</el-button>
          <el-button 
            icon="el-icon-full-screen" 
            @click="toggleFullscreen"
          >全屏</el-button>
        </el-button-group>
      </div>
    </div>

    <!-- 主内容区域：左右布局 -->
    <div class="integration-main">
      <!-- 左侧：Trace详情 -->
      <div class="trace-panel">
        <div class="panel-header">
          <h4>Trace详情</h4>
          <div class="panel-actions">
            <el-input
              v-model="nodeFilter"
              placeholder="搜索节点..."
              size="small"
              prefix-icon="el-icon-search"
              clearable
              style="width: 180px;"
            />
            <el-button
              size="small"
              type="primary"
              icon="el-icon-video-play"
              @click="handleReplay"
              :loading="replaying"
              :disabled="!currentTrace"
            >回放</el-button>
          </div>
        </div>
        
        <!-- Trace加载状态 -->
        <div v-if="loading" class="loading-state">
          <el-icon class="loading-icon"><Loading /></el-icon>
          <p>加载Trace数据中...</p>
        </div>
        
        <!-- Trace错误状态 -->
        <div v-else-if="error" class="error-state">
          <el-alert
            :title="error as string"
            type="error"
            :closable="false"
            show-icon
          />
          <el-button
            size="small"
            type="primary"
            @click="refreshTraceData"
          >重试</el-button>
        </div>
        
        <!-- Trace内容 -->
        <div v-else-if="currentTrace" class="trace-content">
          <!-- 执行摘要 -->
          <div class="trace-summary">
            <div class="summary-grid">
              <div class="summary-item">
                <span class="summary-label">Graph</span>
                <span class="summary-value">{{ (currentTrace as TraceData).session.graph_name || (currentTrace as TraceData).session.graph_id }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">状态</span>
                <span class="summary-value" :class="(currentTrace as TraceData).session.status">
                  {{ getStatusText((currentTrace as TraceData).session.status) }}
                </span>
              </div>
              <div class="summary-item">
                <span class="summary-label">开始时间</span>
                <span class="summary-value">{{ formatTime((currentTrace as TraceData).session.start_time) }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">持续时间</span>
                <span class="summary-value">{{ formatDuration((currentTrace as TraceData).session.duration) }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">节点总数</span>
                <span class="summary-value">{{ (currentTrace as TraceData).summary?.node_statistics?.total || ((currentTrace as TraceData).nodes as TraceNode[]).length }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">成功率</span>
                <span class="summary-value success">
                  {{ (((currentTrace as TraceData).summary?.node_statistics?.success_rate || 0) * 100).toFixed(1) }}%
                </span>
              </div>
            </div>
          </div>
          
          <!-- 执行步骤列表 -->
          <div class="execution-steps">
            <div class="steps-list">
              <div
                v-for="node in filteredNodes"
                :key="(node as TraceNode).id"
                class="step-item"
                :class="{
                  'selected': selectedNodeId === (node as TraceNode).id,
                  [(node as TraceNode).status]: true
                }"
                @click="selectNode(node as TraceNode)"
              >
                <div class="step-header">
                  <div class="step-info">
                    <span class="step-order">{{ (node as TraceNode).execution_order }}</span>
                    <span class="step-name">{{ (node as TraceNode).node_name || (node as TraceNode).node_id }}</span>
                    <span class="step-agent">{{ (node as TraceNode).agent_name }}</span>
                  </div>
                  <div class="step-status" :class="(node as TraceNode).status">
                    {{ getNodeStatusText((node as TraceNode).status) }}
                  </div>
                </div>
                
                <div class="step-details">
                  <div class="step-meta">
                    <span class="meta-item">
                      <el-icon><Timer /></el-icon>
                      {{ formatDuration((node as TraceNode).duration) }}
                    </span>
                    <span class="meta-item" v-if="(node as TraceNode).start_time">
                      <el-icon><Clock /></el-icon>
                      {{ formatTime((node as TraceNode).start_time) }}
                    </span>
                  </div>
                  
                  <div v-if="(node as TraceNode).error_message" class="step-error">
                    <el-icon><Warning /></el-icon>
                    <span class="error-message">{{ (node as TraceNode).error_message }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 空状态 -->
        <div v-else class="empty-state">
          <i class="el-icon-data-line"></i>
          <p>请选择一个Trace查看详情</p>
          <p class="empty-hint">可以从Trace列表中选择一个Trace</p>
        </div>
      </div>
      
      <!-- 右侧：Graph可视化 -->
      <div class="graph-panel">
        <div class="panel-header">
          <h4>Graph可视化</h4>
          <div class="panel-actions">
            <el-button-group size="small">
              <el-button icon="el-icon-zoom-in" @click="zoomIn"></el-button>
              <el-button icon="el-icon-zoom-out" @click="zoomOut"></el-button>
              <el-button icon="el-icon-full-screen" @click="fitToView"></el-button>
              <el-button icon="el-icon-refresh-left" @click="resetView"></el-button>
            </el-button-group>
          </div>
        </div>
        
        <!-- Graph Canvas -->
        <div class="graph-canvas-wrapper">
          <GraphCanvas
            ref="graphCanvasRef"
            :trace-data="currentTrace as Record<string, unknown> | undefined"
            :selected-node-id="selectedNodeId as string | undefined"
            @node-selected="handleGraphNodeSelected"
          />
        </div>
        
        <!-- 节点详情面板 -->
        <div v-if="selectedNodeDetail" class="node-detail-panel">
          <div class="panel-header">
            <h4>节点详情: {{ (selectedNodeDetail as TraceNode).node_name || (selectedNodeDetail as TraceNode).node_id }}</h4>
            <el-button
              type="text"
              icon="el-icon-close"
              @click="selectedNodeDetail = null"
            ></el-button>
          </div>
          <div class="panel-content">
            <!-- 基本信息 -->
            <div class="detail-section">
              <h5>基本信息</h5>
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="detail-label">节点ID</span>
                  <span class="detail-value">{{ (selectedNodeDetail as TraceNode).node_id }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">执行顺序</span>
                  <span class="detail-value">{{ (selectedNodeDetail as TraceNode).execution_order }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">智能体</span>
                  <span class="detail-value">{{ (selectedNodeDetail as TraceNode).agent_name }} ({{ (selectedNodeDetail as TraceNode).agent_type || '未知类型' }})</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">状态</span>
                  <span class="detail-value" :class="(selectedNodeDetail as TraceNode).status">
                    {{ getNodeStatusText((selectedNodeDetail as TraceNode).status) }}
                  </span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">开始时间</span>
                  <span class="detail-value">{{ formatTime((selectedNodeDetail as TraceNode).start_time) }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">结束时间</span>
                  <span class="detail-value">{{ formatTime((selectedNodeDetail as TraceNode).end_time) }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">持续时间</span>
                  <span class="detail-value">{{ formatDuration((selectedNodeDetail as TraceNode).duration) }}</span>
                </div>
              </div>
            </div>

            <!-- 输入数据 -->
            <div class="detail-section" v-if="(selectedNodeDetail as TraceNode).input_data">
              <h5>输入数据</h5>
              <div class="data-viewer">
                <pre>{{ formatJson((selectedNodeDetail as TraceNode).input_data) }}</pre>
              </div>
            </div>

            <!-- 输出数据 -->
            <div class="detail-section" v-if="(selectedNodeDetail as TraceNode).output_data">
              <h5>输出数据</h5>
              <div class="data-viewer">
                <pre>{{ formatJson((selectedNodeDetail as TraceNode).output_data) }}</pre>
              </div>
            </div>

            <!-- 错误信息 -->
            <div class="detail-section" v-if="(selectedNodeDetail as TraceNode).error_message">
              <h5>错误信息</h5>
              <div class="error-viewer">
                <div class="error-message">{{ (selectedNodeDetail as TraceNode).error_message }}</div>
                <div v-if="(selectedNodeDetail as TraceNode).error_details" class="error-details">
                  <pre>{{ formatJson((selectedNodeDetail as TraceNode).error_details) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Loading,
  Timer,
  Clock,
  Warning
} from '@element-plus/icons-vue'
import { getTraceDetails, replayTrace } from '@/api/graph'
import GraphCanvas from './GraphCanvas.vue'

interface TraceSession {
  trace_id: string
  graph_id: string
  graph_name?: string
  status: string
  start_time?: string
  end_time?: string
  duration?: number
}

interface TraceNode {
  id: string
  node_id: string
  node_name?: string
  agent_name: string
  agent_type?: string
  execution_order: number
  status: string
  start_time?: string
  end_time?: string
  duration?: number
  input_data?: unknown
  output_data?: unknown
  error_message?: string
  error_details?: unknown
}

interface TraceSummary {
  node_statistics?: {
    total: number
    success_rate: number
  }
}

interface TraceData {
  session: TraceSession
  nodes: TraceNode[]
  summary?: TraceSummary
}

// Props
interface Props {
  traceId?: string
}

const props = defineProps<Props>()

// 响应式数据
const currentTrace = ref<TraceData | null>(null)
const loading = ref<boolean>(false)
const error = ref<string | null>(null)
const selectedNodeId = ref<string | null>(null)
const selectedNodeDetail = ref<TraceNode | null>(null)
const nodeFilter = ref<string>('')
const replaying = ref<boolean>(false)
const graphCanvasRef = ref<InstanceType<typeof GraphCanvas> | null>(null)

// 计算属性：过滤节点
const filteredNodes = computed(() => {
  if (!currentTrace.value?.nodes) return []
  
  let nodes = currentTrace.value.nodes
  
  if (nodeFilter.value) {
    const searchText = nodeFilter.value.toLowerCase()
    nodes = nodes.filter((node: TraceNode) => 
      node.node_id.toLowerCase().includes(searchText) ||
      (node.node_name && node.node_name.toLowerCase().includes(searchText)) ||
      node.agent_name.toLowerCase().includes(searchText)
    )
  }
  
  return nodes
})

// 方法
const loadTraceData = async () => {
  if (!props.traceId) {
    currentTrace.value = null
    return
  }
  
  try {
    loading.value = true
    error.value = null
    
    const response = await getTraceDetails(props.traceId) as Record<string, unknown>
    currentTrace.value = response.data as TraceData
    
    // 重置选择
    selectedNodeId.value = null
    selectedNodeDetail.value = null
    
    // 保存到localStorage
    saveToLocalStorage()
    
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } }; message?: string }
    error.value = e.response?.data?.detail || e.message || '加载Trace详情失败'
    console.error('加载Trace详情失败:', err)
  } finally {
    loading.value = false
  }
}

const refreshTraceData = async () => {
  await loadTraceData()
}

const selectNode = (node: TraceNode) => {
  selectedNodeId.value = node.id
  selectedNodeDetail.value = node
  
  // 通知GraphCanvas高亮节点
  if (graphCanvasRef.value) {
    graphCanvasRef.value.highlightNode(node.id)
  }
}

const handleGraphNodeSelected = (node: { id: string; name: string; type: string; status: string; x: number; y: number; originalNode?: TraceNode }) => {
  if (node && node.originalNode) {
    selectedNodeId.value = node.id
    selectedNodeDetail.value = node.originalNode
  }
}

const getStatusText = (status: string): string => {
  const statusMap: Record<string, string> = {
    'running': '运行中',
    'completed': '已完成',
    'failed': '已失败',
    'cancelled': '已取消',
    'pending': '等待中'
  }
  return statusMap[status] || status
}

const getNodeStatusText = (status: string): string => {
  const statusMap: Record<string, string> = {
    'running': '运行中',
    'completed': '已完成',
    'failed': '已失败',
    'pending': '等待中'
  }
  return statusMap[status] || status
}

const formatTime = (timeString?: string): string => {
  if (!timeString) return '--'
  try {
    const date = new Date(timeString)
    return date.toLocaleString('zh-CN')
  } catch {
    return timeString
  }
}

const formatDuration = (seconds?: number): string => {
  if (!seconds) return '--'
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}m ${remainingSeconds.toFixed(0)}s`
}

const formatJson = (data: unknown): string => {
  try {
    if (typeof data === 'string') {
      return data
    }
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

const handleReplay = async () => {
  if (!currentTrace.value) return
  
  try {
    replaying.value = true
    
    await ElMessageBox.confirm(
      '确定要回放此Trace的执行过程吗？',
      '回放确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const response = await replayTrace(currentTrace.value.session.trace_id, {
      replay_type: 'step_by_step'
    }) as Record<string, unknown>
    
    ElMessage.success('回放请求已发送')
    console.log('回放结果:', response.data)
    
  } catch (err: unknown) {
    if (err !== 'cancel') {
      const e = err as { response?: { data?: { detail?: string } }; message?: string }
      ElMessage.error(e.response?.data?.detail || '回放失败')
    }
  } finally {
    replaying.value = false
  }
}

const exportData = () => {
  if (!currentTrace.value) {
    ElMessage.warning('请先加载Trace数据')
    return
  }
  
  try {
    const dataStr = JSON.stringify(currentTrace.value, null, 2)
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr)
    
    const exportFileDefaultName = `trace_${currentTrace.value.session.trace_id}_${new Date().toISOString().slice(0,10)}.json`
    
    const linkElement = document.createElement('a')
    linkElement.setAttribute('href', dataUri)
    linkElement.setAttribute('download', exportFileDefaultName)
    linkElement.click()
    
    ElMessage.success('数据导出成功')
  } catch (err: unknown) {
    const e = err as { message?: string }
    ElMessage.error('导出失败: ' + e.message)
  }
}

const toggleFullscreen = () => {
  const element = document.querySelector('.trace-graph-integration')
  if (!document.fullscreenElement) {
    (element as HTMLElement).requestFullscreen().catch((err: unknown) => {
      console.error('全屏失败:', err)
    })
  } else {
    document.exitFullscreen()
  }
}

// Graph Canvas控制方法
const zoomIn = () => {
  if (graphCanvasRef.value) {
    graphCanvasRef.value.zoomIn()
  }
}

const zoomOut = () => {
  if (graphCanvasRef.value) {
    graphCanvasRef.value.zoomOut()
  }
}

const fitToView = () => {
  if (graphCanvasRef.value) {
    graphCanvasRef.value.fitToView()
  }
}

const resetView = () => {
  if (graphCanvasRef.value) {
    graphCanvasRef.value.resetView()
  }
}

// 数据持久化方法
const saveToLocalStorage = () => {
  if (!currentTrace.value) return
  
  try {
    const storageKey = `trace_graph_integration_${props.traceId}`
    const data = {
      traceId: props.traceId,
      selectedNodeId: selectedNodeId.value,
      nodeFilter: nodeFilter.value,
      timestamp: new Date().toISOString()
    }
    
    localStorage.setItem(storageKey, JSON.stringify(data))
  } catch (err) {
    console.warn('保存到localStorage失败:', err)
  }
}

const loadFromLocalStorage = () => {
  if (!props.traceId) return
  
  try {
    const storageKey = `trace_graph_integration_${props.traceId}`
    const savedData = localStorage.getItem(storageKey)
    
    if (savedData) {
      const data = JSON.parse(savedData) as {
        traceId: string
        selectedNodeId: string | null
        nodeFilter: string
        timestamp: string
      }
      
      // 检查数据是否过期（超过1小时）
      const savedTime = new Date(data.timestamp)
      const currentTime = new Date()
      const hoursDiff = (currentTime.getTime() - savedTime.getTime()) / (1000 * 60 * 60)
      
      if (hoursDiff < 1) { // 1小时内有效
        nodeFilter.value = data.nodeFilter || ''
        selectedNodeId.value = data.selectedNodeId || null
        
        // 如果保存了选中的节点ID，找到对应的节点详情
        if (selectedNodeId.value && currentTrace.value) {
          const node = currentTrace.value.nodes.find((n: TraceNode) => n.id === selectedNodeId.value)
          if (node) {
            selectedNodeDetail.value = node
          }
        }
      } else {
        // 清除过期数据
        localStorage.removeItem(storageKey)
      }
    }
  } catch (err) {
    console.warn('从localStorage加载失败:', err)
  }
}

// 生命周期
onMounted(() => {
  // 加载Trace数据
  if (props.traceId) {
    loadTraceData()
  }
  
  // 监听页面刷新/关闭事件
  window.addEventListener('beforeunload', saveToLocalStorage)
})

// 清理
const cleanup = () => {
  window.removeEventListener('beforeunload', saveToLocalStorage)
}

// 监听traceId变化
watch(() => props.traceId, (newTraceId) => {
  if (newTraceId) {
    loadTraceData()
  } else {
    currentTrace.value = null
    selectedNodeId.value = null
    selectedNodeDetail.value = null
  }
})

// 监听currentTrace变化
watch(() => currentTrace.value, (newTrace) => {
  if (newTrace) {
    // 从localStorage加载保存的状态
    loadFromLocalStorage()
  }
})

// 监听selectedNodeId变化
watch(() => selectedNodeId.value, () => {
  saveToLocalStorage()
})

// 监听nodeFilter变化
watch(() => nodeFilter.value, () => {
  saveToLocalStorage()
})
</script>

<style scoped>
.trace-graph-integration {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #0f172a;
  color: #e2e8f0;
}

.integration-controls {
  padding: 16px 24px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.controls-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.integration-title h3 {
  margin: 0;
  font-size: 18px;
  color: #f8fafc;
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: #94a3b8;
}

.trace-info {
  display: flex;
  gap: 16px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #cbd5e1;
}

.info-item i {
  font-size: 14px;
}

.integration-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.trace-panel {
  width: 40%;
  min-width: 400px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #334155;
  background-color: #0f172a;
}

.graph-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #0f172a;
}

.panel-header {
  padding: 16px 20px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #f8fafc;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.trace-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.trace-summary {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-label {
  font-size: 11px;
  color: #94a3b8;
}

.summary-value {
  font-size: 13px;
  font-weight: 500;
  color: #f1f5f9;
}

.summary-value.success {
  color: #10b981;
}

.summary-value.running {
  color: #3b82f6;
}

.summary-value.failed {
  color: #ef4444;
}

.summary-value.pending {
  color: #f59e0b;
}

.execution-steps {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.steps-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-item {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.step-item:hover {
  background-color: #334155;
  border-color: #475569;
}

.step-item.selected {
  border-color: #3b82f6;
  background-color: rgba(59, 130, 246, 0.1);
}

.step-item.completed {
  border-left: 3px solid #10b981;
}

.step-item.running {
  border-left: 3px solid #3b82f6;
}

.step-item.failed {
  border-left: 3px solid #ef4444;
}

.step-item.pending {
  border-left: 3px solid #f59e0b;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-order {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  background-color: #0f172a;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

.step-name {
  font-size: 13px;
  font-weight: 500;
  color: #f8fafc;
}

.step-agent {
  font-size: 11px;
  color: #94a3b8;
  background-color: #0f172a;
  padding: 2px 6px;
  border-radius: 4px;
}

.step-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 500;
}

.step-status.completed {
  background-color: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.step-status.running {
  background-color: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
}

.step-status.failed {
  background-color: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.step-status.pending {
  background-color: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.step-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-meta {
  display: flex;
  gap: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #94a3b8;
}

.meta-item .el-icon {
  font-size: 12px;
}

.step-error {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  background-color: rgba(239, 68, 68, 0.1);
  border-radius: 4px;
  border-left: 3px solid #ef4444;
}

.step-error .el-icon {
  font-size: 14px;
  color: #ef4444;
  margin-top: 1px;
}

.error-message {
  font-size: 12px;
  color: #ef4444;
  line-height: 1.4;
}

.graph-canvas-wrapper {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.node-detail-panel {
  position: absolute;
  bottom: 20px;
  right: 20px;
  width: 350px;
  max-height: 500px;
  background-color: rgba(30, 41, 59, 0.95);
  border: 1px solid #334155;
  border-radius: 8px;
  z-index: 20;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section h5 {
  font-size: 13px;
  font-weight: 600;
  color: #cbd5e1;
  margin: 0 0 12px 0;
  padding-bottom: 4px;
  border-bottom: 1px solid #334155;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 11px;
  color: #94a3b8;
}

.detail-value {
  font-size: 13px;
  color: #f1f5f9;
}

.detail-value.running {
  color: #3b82f6;
}

.detail-value.completed {
  color: #10b981;
}

.detail-value.failed {
  color: #ef4444;
}

.detail-value.pending {
  color: #f59e0b;
}

.data-viewer, .error-viewer {
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 12px;
  max-height: 200px;
  overflow-y: auto;
}

.data-viewer pre, .error-viewer pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 11px;
  line-height: 1.4;
  color: #cbd5e1;
  white-space: pre-wrap;
  word-break: break-all;
}

.error-viewer .error-message {
  font-size: 12px;
  color: #ef4444;
  margin-bottom: 8px;
  font-weight: 500;
}

.error-details {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #334155;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #94a3b8;
}

.loading-state .el-icon {
  font-size: 24px;
  margin-bottom: 12px;
}

.error-state {
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #94a3b8;
}

.empty-state i {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
}

.empty-hint {
  font-size: 12px !important;
  color: #64748b;
  margin-top: 4px !important;
}
</style>
