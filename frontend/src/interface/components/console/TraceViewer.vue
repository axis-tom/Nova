<style scoped>
.trace-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--console-bg-surface);
}

.trace-viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--console-spacing-md) var(--console-spacing-lg);
  border-bottom: 1px solid var(--console-border-base);
  background-color: var(--console-bg-elevated);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-xs);
}

.viewer-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--console-text-primary);
  margin: 0;
}

.trace-id {
  font-size: 12px;
  color: var(--console-text-tertiary);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.trace-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--console-spacing-xl);
  color: var(--console-text-tertiary);
}

.trace-loading .el-icon {
  font-size: 24px;
  margin-bottom: var(--console-spacing-sm);
  animation: rotate 2s linear infinite;
}

.trace-error {
  padding: var(--console-spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-md);
  align-items: center;
}

.trace-viewer-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--console-spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-lg);
}

.trace-summary {
  background-color: var(--console-bg-elevated);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-md);
  padding: var(--console-spacing-md);
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--console-spacing-md);
}

.summary-header h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--console-text-primary);
  margin: 0;
}

.summary-actions {
  display: flex;
  gap: var(--console-spacing-sm);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--console-spacing-md);
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-xs);
}

.summary-label {
  font-size: 12px;
  color: var(--console-text-tertiary);
}

.summary-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--console-text-secondary);
}

.summary-value.success {
  color: var(--console-color-success);
}

.summary-value.running {
  color: var(--console-color-info);
}

.summary-value.failed {
  color: var(--console-color-error);
}

.summary-value.pending {
  color: var(--console-color-warning);
}

.execution-steps {
  background-color: var(--console-bg-elevated);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-md);
  padding: var(--console-spacing-md);
  flex: 1;
  display: flex;
  flex-direction: column;
}

.steps-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--console-spacing-md);
}

.steps-header h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--console-text-primary);
  margin: 0;
}

.steps-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-sm);
}

.step-item {
  background-color: var(--console-bg-surface);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-sm);
  padding: var(--console-spacing-md);
  cursor: pointer;
  transition: all var(--console-transition-fast);
}

.step-item:hover {
  background-color: var(--console-bg-hover);
  border-color: var(--console-border-light);
}

.step-item.selected {
  border-color: var(--console-color-primary);
  background-color: rgba(59, 130, 246, 0.1);
}

.step-item.completed {
  border-left: 3px solid var(--console-color-success);
}

.step-item.running {
  border-left: 3px solid var(--console-color-info);
}

.step-item.failed {
  border-left: 3px solid var(--console-color-error);
}

.step-item.pending {
  border-left: 3px solid var(--console-color-warning);
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--console-spacing-sm);
}

.step-info {
  display: flex;
  align-items: center;
  gap: var(--console-spacing-md);
}

.step-order {
  font-size: 12px;
  font-weight: 600;
  color: var(--console-text-muted);
  background-color: var(--console-bg-elevated);
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

.step-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--console-text-primary);
}

.step-agent {
  font-size: 11px;
  color: var(--console-text-tertiary);
  background-color: var(--console-bg-elevated);
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
  color: var(--console-color-success);
}

.step-status.running {
  background-color: rgba(59, 130, 246, 0.2);
  color: var(--console-color-info);
}

.step-status.failed {
  background-color: rgba(239, 68, 68, 0.2);
  color: var(--console-color-error);
}

.step-status.pending {
  background-color: rgba(245, 158, 11, 0.2);
  color: var(--console-color-warning);
}

.step-details {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-sm);
}

.step-meta {
  display: flex;
  gap: var(--console-spacing-md);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--console-text-muted);
}

.meta-item .el-icon {
  font-size: 12px;
}

.step-error {
  display: flex;
  align-items: flex-start;
  gap: var(--console-spacing-sm);
  padding: var(--console-spacing-sm);
  background-color: rgba(239, 68, 68, 0.1);
  border-radius: var(--console-radius-sm);
  border-left: 3px solid var(--console-color-error);
}

.step-error .el-icon {
  font-size: 14px;
  color: var(--console-color-error);
  margin-top: 1px;
}

.error-message {
  font-size: 12px;
  color: var(--console-color-error);
  line-height: 1.4;
}

.node-detail-panel {
  background-color: var(--console-bg-elevated);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-md);
  padding: var(--console-spacing-md);
  margin-top: var(--console-spacing-md);
}

.node-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--console-spacing-md);
  padding-bottom: var(--console-spacing-md);
  border-bottom: 1px solid var(--console-border-base);
}

.node-detail-header h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--console-text-primary);
  margin: 0;
}

.node-detail-content {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-lg);
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-md);
}

.detail-section h5 {
  font-size: 13px;
  font-weight: 600;
  color: var(--console-text-secondary);
  margin: 0;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--console-spacing-md);
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-xs);
}

.detail-label {
  font-size: 12px;
  color: var(--console-text-tertiary);
}

.detail-value {
  font-size: 13px;
  color: var(--console-text-secondary);
  font-weight: 500;
  word-break: break-all;
}

.detail-value.completed {
  color: var(--console-color-success);
}

.detail-value.running {
  color: var(--console-color-info);
}

.detail-value.failed {
  color: var(--console-color-error);
}

.detail-value.pending {
  color: var(--console-color-warning);
}

.data-viewer, .error-viewer {
  background-color: var(--console-bg-surface);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-sm);
  padding: var(--console-spacing-md);
  max-height: 300px;
  overflow-y: auto;
}

.data-viewer pre, .error-viewer pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  line-height: 1.4;
  color: var(--console-text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
}

.error-viewer .error-message {
  font-size: 13px;
  color: var(--console-color-error);
  margin-bottom: var(--console-spacing-md);
  font-weight: 500;
}

.trace-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--console-spacing-xl);
  color: var(--console-text-tertiary);
  text-align: center;
  flex: 1;
}

.trace-empty .el-icon {
  font-size: 48px;
  margin-bottom: var(--console-spacing-md);
  opacity: 0.5;
}

.trace-empty p {
  margin: 0;
  font-size: 14px;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>

<template>
  <div class="trace-viewer">
    <!-- 抽屉头部 -->
    <div class="trace-viewer-header">
      <div class="header-left">
        <h3 class="viewer-title">Trace详情</h3>
        <span class="trace-id">{{ traceData?.session?.trace_id || '未选择Trace' }}</span>
      </div>
      <div class="header-right">
        <el-button
          size="small"
          type="text"
          icon="el-icon-close"
          @click="$emit('close')"
        ></el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="trace-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载Trace详情中...</span>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="trace-error">
      <el-alert
        :title="error"
        type="error"
        :closable="false"
        show-icon
      />
      <el-button
        size="small"
        type="primary"
        @click="loadTraceData"
      >重试</el-button>
    </div>

    <!-- Trace详情内容 -->
    <div v-else-if="traceData" class="trace-viewer-content">
      <!-- 执行摘要 -->
      <div class="trace-summary">
        <div class="summary-header">
          <h4>执行摘要</h4>
          <div class="summary-actions">
            <el-button
              size="small"
              type="primary"
              icon="el-icon-video-play"
              @click="handleReplay"
              :loading="replaying"
            >回放</el-button>
            <el-button
              size="small"
              type="warning"
              icon="el-icon-refresh"
              @click="handleRetry"
              :loading="retrying"
            >重试</el-button>
            <el-button
              size="small"
              type="info"
              icon="el-icon-bug"
              @click="showDebugPanel = true"
            >调试</el-button>
          </div>
        </div>
        
        <div class="summary-grid">
          <div class="summary-item">
            <span class="summary-label">Graph</span>
            <span class="summary-value">{{ traceData.session.graph_name || traceData.session.graph_id }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">状态</span>
            <span class="summary-value" :class="traceData.session.status">
              {{ getStatusText(traceData.session.status) }}
            </span>
          </div>
          <div class="summary-item">
            <span class="summary-label">开始时间</span>
            <span class="summary-value">{{ formatTime(traceData.session.start_time) }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">持续时间</span>
            <span class="summary-value">{{ formatDuration(traceData.session.duration) }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">节点总数</span>
            <span class="summary-value">{{ traceData.summary?.node_statistics?.total || traceData.nodes.length }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">成功率</span>
            <span class="summary-value success">
              {{ ((traceData.summary?.node_statistics?.success_rate || 0) * 100).toFixed(1) }}%
            </span>
          </div>
        </div>
      </div>

      <!-- 执行步骤列表 -->
      <div class="execution-steps">
        <div class="steps-header">
          <h4>执行步骤 ({{ traceData.nodes.length }})</h4>
          <el-input
            v-model="nodeFilter"
            placeholder="搜索节点..."
            size="small"
            prefix-icon="el-icon-search"
            clearable
            style="width: 200px;"
          />
        </div>

        <div class="steps-list">
          <div
            v-for="node in filteredNodes"
            :key="node.id"
            class="step-item"
            :class="{
              'selected': selectedNodeId === node.id,
              [node.status]: true
            }"
            @click="selectNode(node)"
          >
            <div class="step-header">
              <div class="step-info">
                <span class="step-order">{{ node.execution_order }}</span>
                <span class="step-name">{{ node.node_name || node.node_id }}</span>
                <span class="step-agent">{{ node.agent_name }}</span>
              </div>
              <div class="step-status" :class="node.status">
                {{ getNodeStatusText(node.status) }}
              </div>
            </div>
            
            <div class="step-details">
              <div class="step-meta">
                <span class="meta-item">
                  <el-icon><Timer /></el-icon>
                  {{ formatDuration(node.duration) }}
                </span>
                <span class="meta-item" v-if="node.start_time">
                  <el-icon><Clock /></el-icon>
                  {{ formatTime(node.start_time) }}
                </span>
              </div>
              
              <div v-if="node.error_message" class="step-error">
                <el-icon><Warning /></el-icon>
                <span class="error-message">{{ node.error_message }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 节点详情面板 -->
      <div v-if="selectedNode" class="node-detail-panel">
        <div class="node-detail-header">
          <h4>节点详情: {{ selectedNode.node_name || selectedNode.node_id }}</h4>
          <el-button
            size="small"
            type="text"
            icon="el-icon-close"
            @click="selectedNode = null"
          ></el-button>
        </div>
        
        <div class="node-detail-content">
          <!-- 基本信息 -->
          <div class="detail-section">
            <h5>基本信息</h5>
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">节点ID</span>
                <span class="detail-value">{{ selectedNode.node_id }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">执行顺序</span>
                <span class="detail-value">{{ selectedNode.execution_order }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">智能体</span>
                <span class="detail-value">{{ selectedNode.agent_name }} ({{ selectedNode.agent_type || '未知类型' }})</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">状态</span>
                <span class="detail-value" :class="selectedNode.status">
                  {{ getNodeStatusText(selectedNode.status) }}
                </span>
              </div>
              <div class="detail-item">
                <span class="detail-label">开始时间</span>
                <span class="detail-value">{{ formatTime(selectedNode.start_time) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">结束时间</span>
                <span class="detail-value">{{ formatTime(selectedNode.end_time) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">持续时间</span>
                <span class="detail-value">{{ formatDuration(selectedNode.duration) }}</span>
              </div>
            </div>
          </div>

          <!-- 输入数据 -->
          <div class="detail-section" v-if="selectedNode.input_data">
            <h5>输入数据</h5>
            <div class="data-viewer">
              <pre>{{ formatJson(selectedNode.input_data) }}</pre>
            </div>
          </div>

          <!-- 输出数据 -->
          <div class="detail-section" v-if="selectedNode.output_data">
            <h5>输出数据</h5>
            <div class="data-viewer">
              <pre>{{ formatJson(selectedNode.output_data) }}</pre>
            </div>
          </div>

          <!-- 错误信息 -->
          <div class="detail-section" v-if="selectedNode.error_message">
            <h5>错误信息</h5>
            <div class="error-viewer">
              <div class="error-message">{{ selectedNode.error_message }}</div>
              <div v-if="selectedNode.error_details" class="error-details">
                <pre>{{ formatJson(selectedNode.error_details) }}</pre>
              </div>
            </div>
          </div>

          <!-- 上下文状态 -->
          <div class="detail-section" v-if="selectedNode.context_state">
            <h5>上下文状态</h5>
            <div class="data-viewer">
              <pre>{{ formatJson(selectedNode.context_state) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="trace-empty">
      <el-icon><Document /></el-icon>
      <p>请选择一个Trace查看详情</p>
    </div>

    <!-- 调试面板抽屉 -->
    <el-drawer
      v-model="showDebugPanel"
      title="调试面板"
      direction="rtl"
      size="40%"
      :before-close="handleDebugPanelClose"
    >
      <DebugPanel
        v-if="showDebugPanel && traceData"
        :trace-id="traceData.session.trace_id"
        @close="showDebugPanel = false"
      />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Loading,
  Document,
  Timer,
  Clock,
  Warning
} from '@element-plus/icons-vue'
import { getTraceDetails, replayTrace, retryTrace } from '@/api/graph'
import DebugPanel from './DebugPanel.vue'

interface Props {
  traceId?: string
  visible?: boolean
}

const props = defineProps<Props>()

interface Emits {
  (e: 'close', ...args: unknown[]): void
  (e: 'update:traceId', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

// 数据状态
const traceData = ref<unknown | null>(null)
const loading = ref<boolean>(false)
const error = ref<unknown | null>(null)
const selectedNode = ref<HTMLElement | null>(null)
const selectedNodeId = ref<HTMLElement | null>(null)
const nodeFilter = ref<string>('')
const showDebugPanel = ref<boolean>(false)
const replaying = ref<boolean>(false)
const retrying = ref<boolean>(false)

// 计算属性
const filteredNodes = computed(() => {
  if (!traceData.value?.nodes) return []
  
  let nodes = traceData.value.nodes
  
  if (nodeFilter.value) {
    const searchText = nodeFilter.value.toLowerCase()
    nodes = nodes.filter(node => 
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
    traceData.value = null
    return
  }
  
  try {
    loading.value = true
    error.value = null
    
    const response = await getTraceDetails(props.traceId)
    traceData.value = response.data
    
    // 重置选择
    selectedNode.value = null
    selectedNodeId.value = null
    
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || '加载Trace详情失败'
    console.error('加载Trace详情失败:', err)
  } finally {
    loading.value = false
  }
}

const selectNode = (node) => {
  selectedNode.value = node
  selectedNodeId.value = node.id
}

const getStatusText = (status) => {
  const statusMap = {
    'running': '运行中',
    'completed': '已完成',
    'failed': '已失败',
    'cancelled': '已取消',
    'pending': '等待中'
  }
  return statusMap[status] || status
}

const getNodeStatusText = (status) => {
  const statusMap = {
    'running': '运行中',
    'completed': '已完成',
    'failed': '已失败',
    'pending': '等待中'
  }
  return statusMap[status] || status
}

const formatTime = (timeString) => {
  if (!timeString) return '--'
  try {
    const date = new Date(timeString)
    return date.toLocaleString('zh-CN')
  } catch {
    return timeString
  }
}

const formatDuration = (seconds) => {
  if (!seconds) return '--'
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}m ${remainingSeconds.toFixed(0)}s`
}

const formatJson = (data) => {
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
  if (!traceData.value) return
  
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
    
    const response = await replayTrace(traceData.value.session.trace_id, {
      replay_type: 'step_by_step'
    })
    
    ElMessage.success('回放请求已发送')
    console.log('回放结果:', response.data)
    
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.response?.data?.detail || '回放失败')
    }
  } finally {
    replaying.value = false
  }
}

const handleRetry = async () => {
  if (!traceData.value) return
  
  try {
    retrying.value = true
    
    await ElMessageBox.confirm(
      '确定要重试此Trace的执行吗？',
      '重试确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const response = await retryTrace(traceData.value.session.trace_id)
    
    ElMessage.success('重试请求已发送')
    console.log('重试结果:', response.data)
    
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.response?.data?.detail || '重试失败')
    }
  } finally {
    retrying.value = false
  }
}

const handleDebugPanelClose = (done) => {
  ElMessageBox.confirm('确定要关闭调试面板吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
    .then(() => {
      showDebugPanel.value = false
      done()
    })
    .catch(() => {})
}

// 监听Trace ID变化
watch(() => props.traceId, (newTraceId) => {
  if (newTraceId) {
    loadTraceData()
  } else {
    traceData.value = null
  }
}, { immediate: true })

// 监听可见性变化
watch(() => props.visible, (newVisible) => {
  if (newVisible && props.traceId) {
    loadTraceData()
  }
})
</script>