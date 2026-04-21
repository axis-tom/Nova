<template>
  <div class="debug-panel">
    <!-- 调试面板头部 -->
    <div class="debug-header">
      <h3 class="debug-title">调试面板</h3>
      <div class="debug-actions">
        <el-button
          size="small"
          type="text"
          icon="el-icon-close"
          @click="$emit('close')"
        ></el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="debug-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载调试信息中...</span>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="debug-error">
      <el-alert
        :title="error"
        type="error"
        :closable="false"
        show-icon
      />
      <el-button
        size="small"
        type="primary"
        @click="loadDebugInfo"
      >重试</el-button>
    </div>

    <!-- 调试信息内容 -->
    <div v-else-if="debugInfo" class="debug-content">
      <!-- 错误摘要 -->
      <div class="debug-section error-summary">
        <div class="section-header">
          <h4>错误摘要</h4>
          <el-tag
            :type="getErrorSeverity(debugInfo.error_summary)"
            size="small"
          >
            {{ getErrorSummaryText(debugInfo.error_summary) }}
          </el-tag>
        </div>
        
        <div class="summary-stats">
          <div class="stat-item">
            <div class="stat-value">{{ debugInfo.error_summary.total_nodes }}</div>
            <div class="stat-label">总节点数</div>
          </div>
          <div class="stat-item">
            <div class="stat-value" :class="debugInfo.error_summary.failed_nodes > 0 ? 'error' : 'success'">
              {{ debugInfo.error_summary.failed_nodes }}
            </div>
            <div class="stat-label">失败节点</div>
          </div>
          <div class="stat-item">
            <div class="stat-value" :class="debugInfo.error_summary.success_rate < 0.8 ? 'warning' : 'success'">
              {{ (debugInfo.error_summary.success_rate * 100).toFixed(1) }}%
            </div>
            <div class="stat-label">成功率</div>
          </div>
        </div>

        <!-- 错误类别分布 -->
        <div v-if="Object.keys(debugInfo.error_summary.error_categories).length > 0" class="error-categories">
          <h5>错误类别分布</h5>
          <div class="categories-list">
            <div
              v-for="(count, category) in debugInfo.error_summary.error_categories"
              :key="category"
              class="category-item"
            >
              <span class="category-name">{{ category }}</span>
              <span class="category-count">{{ count }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 失败节点列表 -->
      <div v-if="debugInfo.failed_nodes.length > 0" class="debug-section failed-nodes">
        <div class="section-header">
          <h4>失败节点 ({{ debugInfo.failed_nodes.length }})</h4>
          <el-button
            size="small"
            type="danger"
            icon="el-icon-warning"
            @click="highlightFailedNodes"
          >高亮显示</el-button>
        </div>
        
        <div class="failed-nodes-list">
          <div
            v-for="node in debugInfo.failed_nodes"
            :key="node.node_id"
            class="failed-node-item"
            @click="focusOnNode(node.node_id)"
          >
            <div class="node-header">
              <div class="node-info">
                <span class="node-order">{{ node.execution_order }}</span>
                <span class="node-name">{{ node.node_name || node.node_id }}</span>
              </div>
              <el-tag size="small" type="danger">失败</el-tag>
            </div>
            
            <div class="node-error">
              <el-icon><Warning /></el-icon>
              <span class="error-message">{{ node.error_message || '未知错误' }}</span>
            </div>
            
            <div class="node-meta">
              <span class="meta-item">
                <el-icon><Timer /></el-icon>
                {{ formatDuration(node.duration) }}
              </span>
              <span class="meta-item" v-if="node.start_time">
                <el-icon><Clock /></el-icon>
                {{ formatTime(node.start_time) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 执行时间线 -->
      <div class="debug-section execution-timeline">
        <div class="section-header">
          <h4>执行时间线</h4>
          <el-button
            size="small"
            type="info"
            icon="el-icon-timer"
            @click="showTimelineChart = !showTimelineChart"
          >
            {{ showTimelineChart ? '隐藏图表' : '显示图表' }}
          </el-button>
        </div>
        
        <!-- 时间线图表 -->
        <div v-if="showTimelineChart" class="timeline-chart">
          <div class="chart-container">
            <div
              v-for="node in debugInfo.execution_timeline"
              :key="node.node_id"
              class="timeline-bar"
              :class="node.status"
              :style="{
                width: `${Math.min(node.duration * 10, 100)}%`,
                marginLeft: `${(node.execution_order - 1) * 5}px`
              }"
              :title="`${node.node_name}: ${formatDuration(node.duration)}`"
            >
              <span class="bar-label">{{ node.execution_order }}</span>
            </div>
          </div>
          <div class="chart-legend">
            <div class="legend-item">
              <span class="legend-color completed"></span>
              <span class="legend-text">成功</span>
            </div>
            <div class="legend-item">
              <span class="legend-color failed"></span>
              <span class="legend-text">失败</span>
            </div>
            <div class="legend-item">
              <span class="legend-color running"></span>
              <span class="legend-text">运行中</span>
            </div>
            <div class="legend-item">
              <span class="legend-color pending"></span>
              <span class="legend-text">等待中</span>
            </div>
          </div>
        </div>
        
        <!-- 时间线列表 -->
        <div class="timeline-list">
          <div
            v-for="node in debugInfo.execution_timeline"
            :key="node.node_id"
            class="timeline-item"
            :class="node.status"
          >
            <div class="timeline-order">{{ node.execution_order }}</div>
            <div class="timeline-content">
              <div class="timeline-info">
                <span class="timeline-name">{{ node.node_name || node.node_id }}</span>
                <span class="timeline-agent">{{ node.agent_name }}</span>
              </div>
              <div class="timeline-meta">
                <span class="meta-item">
                  <el-icon><Timer /></el-icon>
                  {{ formatDuration(node.duration) }}
                </span>
                <span class="meta-item" v-if="node.start_time">
                  <el-icon><Clock /></el-icon>
                  {{ formatTime(node.start_time) }}
                </span>
              </div>
            </div>
            <div class="timeline-status" :class="node.status">
              {{ getNodeStatusText(node.status) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 调试建议 -->
      <div v-if="debugInfo.suggestions.length > 0" class="debug-section suggestions">
        <div class="section-header">
          <h4>调试建议</h4>
          <el-button
            size="small"
            type="primary"
            icon="el-icon-lightbulb"
            @click="copySuggestions"
          >复制建议</el-button>
        </div>
        
        <div class="suggestions-list">
          <div
            v-for="(suggestion, index) in debugInfo.suggestions"
            :key="index"
            class="suggestion-item"
          >
            <el-icon class="suggestion-icon"><Lightbulb /></el-icon>
            <span class="suggestion-text">{{ suggestion }}</span>
          </div>
        </div>
      </div>

      <!-- 调试操作 -->
      <div class="debug-section debug-actions-section">
        <div class="section-header">
          <h4>调试操作</h4>
        </div>
        
        <div class="actions-grid">
          <el-button
            type="primary"
            icon="el-icon-video-play"
            @click="handleReplay"
            :loading="replaying"
          >
            逐步回放
          </el-button>
          <el-button
            type="warning"
            icon="el-icon-refresh"
            @click="handleRetry"
            :loading="retrying"
          >
            重试执行
          </el-button>
          <el-button
            type="info"
            icon="el-icon-download"
            @click="exportDebugInfo"
          >
            导出报告
          </el-button>
          <el-button
            type="success"
            icon="el-icon-check"
            @click="markAsResolved"
          >
            标记为已解决
          </el-button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="debug-empty">
      <el-icon><Bug /></el-icon>
      <p>暂无调试信息</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Loading,
  Bug,
  Timer,
  Clock,
  Warning,
  Lightbulb
} from '@element-plus/icons-vue'
import { getTraceDebugInfo, replayTrace, retryTrace } from '@/api/graph.js'

const props = defineProps({
  traceId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['close', 'nodeFocus'])

// 数据状态
const debugInfo = ref(null)
const loading = ref(false)
const error = ref(null)
const showTimelineChart = ref(true)
const replaying = ref(false)
const retrying = ref(false)

// 方法
const loadDebugInfo = async () => {
  try {
    loading.value = true
    error.value = null
    
    const response = await getTraceDebugInfo(props.traceId)
    debugInfo.value = response.data
    
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || '加载调试信息失败'
    console.error('加载调试信息失败:', err)
  } finally {
    loading.value = false
  }
}

const getErrorSeverity = (errorSummary) => {
  if (errorSummary.failed_nodes === 0) return 'success'
  if (errorSummary.success_rate < 0.5) return 'danger'
  if (errorSummary.success_rate < 0.8) return 'warning'
  return 'info'
}

const getErrorSummaryText = (errorSummary) => {
  if (errorSummary.failed_nodes === 0) return '无错误'
  if (errorSummary.success_rate < 0.5) return '严重错误'
  if (errorSummary.success_rate < 0.8) return '一般错误'
  return '轻微错误'
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

const highlightFailedNodes = () => {
  if (!debugInfo.value) return
  
  const failedNodeIds = debugInfo.value.failed_nodes.map(node => node.node_id)
  emit('nodeFocus', failedNodeIds)
  
  ElMessage.success(`已高亮显示 ${failedNodeIds.length} 个失败节点`)
}

const focusOnNode = (nodeId) => {
  emit('nodeFocus', [nodeId])
}

const copySuggestions = async () => {
  if (!debugInfo.value?.suggestions.length) return
  
  const text = debugInfo.value.suggestions.join('\n')
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('调试建议已复制到剪贴板')
  } catch (err) {
    console.error('复制失败:', err)
    ElMessage.error('复制失败，请手动复制')
  }
}

const handleReplay = async () => {
  if (!debugInfo.value) return
  
  try {
    replaying.value = true
    
    await ElMessageBox.confirm(
      '确定要逐步回放此Trace的执行过程吗？',
      '回放确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const response = await replayTrace(props.traceId, {
      replay_type: 'step_by_step'
    })
    
    ElMessage.success('逐步回放请求已发送')
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
  if (!debugInfo.value) return
  
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
    
    const response = await retryTrace(props.traceId)
    
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

const exportDebugInfo = () => {
  if (!debugInfo.value) return
  
  const data = {
    trace_id: props.traceId,
    debug_info: debugInfo.value,
    export_time: new Date().toISOString()
  }
  
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `debug-report-${props.traceId}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  
  ElMessage.success('调试报告已导出')
}

const markAsResolved = () => {
  ElMessageBox.confirm(
    '确定要将此Trace标记为已解决吗？',
    '标记确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    }
  )
    .then(() => {
      ElMessage.success('Trace已标记为已解决')
      // 这里可以调用API更新Trace状态
    })
    .catch(() => {})
}

// 监听Trace ID变化
watch(() => props.traceId, (newTraceId) => {
  if (newTraceId) {
    loadDebugInfo()
  } else {
    debugInfo.value = null
  }
}, { immediate: true })
</script>

<style scoped>
.debug-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--console-bg-surface);
}

.debug-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--console-spacing-md) var(--console-spacing-lg);
  border-bottom: 1px solid var(--console-border-base);
  background-color: var(--console-bg-elevated);
}

.debug-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--console-text-primary);
  margin: 0;
}

.debug-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--console-spacing-xl);
  color: var(--console-text-tertiary);
}

.debug-loading .el-icon {
  font-size: 24px;
  margin-bottom: var(--console-spacing-sm);
  animation: rotate 2s linear infinite;
}

.debug-error {
  padding: var(--console-spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-md);
  align-items: center;
}

.debug-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--console-spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-lg);
}

.debug-section {
  background-color: var(--console-bg-elevated);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-md);
  padding: var(--console-spacing-md);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--console-spacing-md);
  padding-bottom: var(--console-spacing-sm);
  border-bottom: 1px solid var(--console-border-base);
}

.section-header h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--console-text-primary);
  margin: 0;
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--console-spacing-md);
  margin-bottom: var(--console-spacing-md);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--console-spacing-md);
  background-color: var(--console-bg-surface);
  border-radius: var(--console-radius-sm);
  border: 1px solid var(--console-border-base);
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: var(--console-spacing-xs);
}

.stat-value.success {
  color: var(--console-color-success);
}

.stat-value.error {
  color: var(--console-color-error);
}

.stat-value.warning {
  color: var(--console-color-warning);
}

.stat-label {
  font-size: 12px;
  color: var(--console-text-tertiary);
}

.error-categories {
  margin-top: var(--console-spacing-md);
}

.error-categories h5 {
  font-size: 13px;
  font-weight: 600;
  color: var(--console-text-secondary);
  margin: 0 0 var(--console-spacing-sm) 0;
}

.categories-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--console-spacing-sm);
}

.category-item {
  display: flex;
  align-items: center;
  gap: var(--console-spacing-sm);
  padding: var(--console-spacing-xs) var(--console-spacing-sm);
  background-color: var(--console-bg-surface);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-sm);
  font-size: 12px;
}

.category-name {
  color: var(--console-text-secondary);
}

.category-count {
  color: var(--console-color-error);
  font-weight: 600;
}

.failed-nodes-list {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-sm);
}

.failed-node-item {
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--console-color-error);
  border-radius: var(--console-radius-sm);
  padding: var(--console-spacing-md);
  cursor: pointer;
  transition: all var(--console-transition-fast);
}

.failed-node-item:hover {
  background-color: rgba(239, 68, 68, 0.2);
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--console-spacing-sm);
}

.node-info {
  display: flex;
  align-items: center;
  gap: var(--console-spacing-md);
}

.node-order {
  font-size: 12px;
  font-weight: 600;
  color: var(--console-text-muted);
  background-color: var(--console-bg-elevated);
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

.node-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--console-text-primary);
}

.node-error {
  display: flex;
  align-items: flex-start;
  gap: var(--console-spacing-sm);
  margin-bottom: var(--console-spacing-sm);
}

.node-error .el-icon {
  font-size: 14px;
  color: var(--console-color-error);
  margin-top: 1px;
}

.error-message {
  font-size: 12px;
  color: var(--console-color-error);
  line-height: 1.4;
}

.node-meta {
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

.timeline-chart {
  margin-bottom: var(--console-spacing-md);
  padding: var(--console-spacing-md);
  background-color: var(--console-bg-surface);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-sm);
}

.chart-container {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: var(--console-spacing-md);
  min-height: 60px;
}

.timeline-bar {
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--console-transition-fast);
  position: relative;
}

.timeline-bar:hover {
  transform: scale(1.02);
  z-index: 1;
}

.timeline-bar.completed {
  background-color: rgba(16, 185, 129, 0.3);
}

.timeline-bar.failed {
  background-color: rgba(239, 68, 68, 0.3);
}

.timeline-bar.running {
  background-color: rgba(59, 130, 246, 0.3);
}

.timeline-bar.pending {
  background-color: rgba(245, 158, 11, 0.3);
}

.bar-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--console-text-primary);
}

.chart-legend {
  display: flex;
  justify-content: center;
  gap: var(--console-spacing-md);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.legend-color.completed {
  background-color: var(--console-color-success);
}

.legend-color.failed {
  background-color: var(--console-color-error);
}

.legend-color.running {
  background-color: var(--console-color-info);
}

.legend-color.pending {
  background-color: var(--console-color-warning);
}

.legend-text {
  font-size: 11px;
  color: var(--console-text-tertiary);
}

.timeline-list {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-sm);
}

.timeline-item {
  display: flex;
  align-items: center;
  gap: var(--console-spacing-md);
  padding: var(--console-spacing-sm);
  background-color: var(--console-bg-surface);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-sm);
  transition: all var(--console-transition-fast);
}

.timeline-item:hover {
  background-color: var(--console-bg-hover);
}

.timeline-item.completed {
  border-left: 3px solid var(--console-color-success);
}

.timeline-item.failed {
  border-left: 3px solid var(--console-color-error);
}

.timeline-item.running {
  border-left: 3px solid var(--console-color-info);
}

.timeline-item.pending {
  border-left: 3px solid var(--console-color-warning);
}

.timeline-order {
  font-size: 12px;
  font-weight: 600;
  color: var(--console-text-muted);
  background-color: var(--console-bg-elevated);
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

.timeline-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-xs);
}

.timeline-info {
  display: flex;
  align-items: center;
  gap: var(--console-spacing-md);
}

.timeline-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--console-text-primary);
}

.timeline-agent {
  font-size: 11px;
  color: var(--console-text-tertiary);
  background-color: var(--console-bg-elevated);
  padding: 2px 6px;
  border-radius: 4px;
}

.timeline-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 500;
  min-width: 60px;
  text-align: center;
}

.timeline-status.completed {
  background-color: rgba(16, 185, 129, 0.2);
  color: var(--console-color-success);
}

.timeline-status.failed {
  background-color: rgba(239, 68, 68, 0.2);
  color: var(--console-color-error);
}

.timeline-status.running {
  background-color: rgba(59, 130, 246, 0.2);
  color: var(--console-color-info);
}

.timeline-status.pending {
  background-color: rgba(245, 158, 11, 0.2);
  color: var(--console-color-warning);
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-sm);
}

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: var(--console-spacing-sm);
  padding: var(--console-spacing-sm);
  background-color: rgba(59, 130, 246, 0.1);
  border: 1px solid var(--console-color-info);
  border-radius: var(--console-radius-sm);
}

.suggestion-icon {
  font-size: 14px;
  color: var(--console-color-info);
  margin-top: 2px;
}

.suggestion-text {
  font-size: 13px;
  color: var(--console-text-secondary);
  line-height: 1.4;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--console-spacing-md);
}

.debug-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--console-spacing-xl);
  color: var(--console-text-tertiary);
  text-align: center;
  flex: 1;
}

.debug-empty .el-icon {
  font-size: 48px;
  margin-bottom: var(--console-spacing-md);
  opacity: 0.5;
}

.debug-empty p {
  margin: 0;
  font-size: 14px;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
