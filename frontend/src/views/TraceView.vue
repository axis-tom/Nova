<template>
  <div class="trace-view-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">Trace Viewer</h1>
        <p class="page-subtitle">查看Graph执行的历史记录和Trace详情</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" icon="el-icon-back" @click="goBack">返回</el-button>
      </div>
    </div>

    <!-- 查询区域 -->
    <div class="query-section">
      <div class="query-card">
        <h3 class="query-title">Trace查询</h3>
        <div class="query-form">
          <el-input
            v-model="traceIdInput"
            placeholder="输入Trace ID (例如: email_briefing_graph_xxx)"
            size="large"
            clearable
            @keyup.enter="loadTraceData"
          >
            <template #prepend>
              <el-icon><Search /></el-icon>
            </template>
            <template #append>
              <el-button type="primary" @click="loadTraceData" :loading="loading">
                查询
              </el-button>
            </template>
          </el-input>
          <div class="query-hint">
            <el-icon><InfoFilled /></el-icon>
            <span>输入Trace ID查看执行详情，Trace ID通常格式为：email_briefing_graph_xxx</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <p>加载Trace详情中...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-state">
      <el-alert
        :title="error"
        type="error"
        :closable="false"
        show-icon
      />
      <el-button
        type="primary"
        @click="loadTraceData"
        :loading="loading"
      >重试</el-button>
    </div>

    <!-- Trace详情内容 -->
    <div v-else-if="traceData" class="trace-content">
      <!-- Trace基本信息 -->
      <div class="trace-basic-info">
        <div class="info-header">
          <h3>Trace基本信息</h3>
          <div class="info-actions">
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
          </div>
        </div>
        
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">Trace ID</span>
            <span class="info-value trace-id">{{ traceData.session.trace_id }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Graph</span>
            <span class="info-value">{{ traceData.session.graph_name || traceData.session.graph_id }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">状态</span>
            <span class="info-value" :class="traceData.session.status">
              {{ getStatusText(traceData.session.status) }}
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">开始时间</span>
            <span class="info-value">{{ formatTime(traceData.session.start_time) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">持续时间</span>
            <span class="info-value">{{ formatDuration(traceData.session.duration) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">执行路径</span>
            <span class="info-value">
              <el-tag
                v-for="(step, index) in traceData.session.execution_path"
                :key="index"
                size="small"
                type="info"
                class="execution-step-tag"
              >
                {{ step }}
              </el-tag>
            </span>
          </div>
        </div>
      </div>

      <!-- 执行步骤列表 -->
      <div class="execution-steps-section">
        <div class="steps-header">
          <h3>执行步骤 ({{ traceData.nodes.length }})</h3>
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
      <div v-if="selectedNode" class="node-detail-section">
        <div class="node-detail-header">
          <h3>节点详情: {{ selectedNode.node_name || selectedNode.node_id }}</h3>
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
            <h4>基本信息</h4>
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
            <h4>输入数据</h4>
            <div class="data-viewer">
              <pre>{{ formatJson(selectedNode.input_data) }}</pre>
            </div>
          </div>

          <!-- 输出数据 -->
          <div class="detail-section" v-if="selectedNode.output_data">
            <h4>输出数据</h4>
            <div class="data-viewer">
              <pre>{{ formatJson(selectedNode.output_data) }}</pre>
            </div>
          </div>

          <!-- 错误信息 -->
          <div class="detail-section" v-if="selectedNode.error_message">
            <h4>错误信息</h4>
            <div class="error-viewer">
              <div class="error-message">{{ selectedNode.error_message }}</div>
              <div v-if="selectedNode.error_details" class="error-details">
                <pre>{{ formatJson(selectedNode.error_details) }}</pre>
              </div>
            </div>
          </div>

          <!-- 上下文状态 -->
          <div class="detail-section" v-if="selectedNode.context_state">
            <h4>上下文状态</h4>
            <div class="data-viewer">
              <pre>{{ formatJson(selectedNode.context_state) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <el-icon><Document /></el-icon>
      <p>请输入Trace ID查询执行详情</p>
      <p class="empty-hint">Trace ID通常可以在执行日志或控制台中找到</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search,
  InfoFilled,
  Loading,
  Document,
  Timer,
  Clock,
  Warning
} from '@element-plus/icons-vue'
import { getTraceDetails, replayTrace, retryTrace } from '@/api/graph.js'

const router = useRouter()

// 数据状态
const traceIdInput = ref('')
const traceData = ref(null)
const loading = ref(false)
const error = ref(null)
const selectedNode = ref(null)
const selectedNodeId = ref(null)
const nodeFilter = ref('')
const replaying = ref(false)
const retrying = ref(false)

// 从URL参数获取Trace ID
onMounted(() => {
  const urlParams = new URLSearchParams(window.location.search)
  const traceIdFromUrl = urlParams.get('trace_id')
  if (traceIdFromUrl) {
    traceIdInput.value = traceIdFromUrl
    loadTraceData()
  }
})

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
  if (!traceIdInput.value.trim()) {
    ElMessage.warning('请输入Trace ID')
    return
  }
  
  try {
    loading.value = true
    error.value = null
    
    const response = await getTraceDetails(traceIdInput.value.trim())
    traceData.value = response.data
    
    // 重置选择
    selectedNode.value = null
    selectedNodeId.value = null
    
    // 更新URL参数
    const url = new URL(window.location)
    url.searchParams.set('trace_id', traceIdInput.value.trim())
    window.history.pushState({}, '', url)
    
    ElMessage.success('Trace详情加载成功')
    
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

const goBack = () => {
  router.back()
}
</script>

<style scoped>
.trace-view-page {
  min-height: 100vh;
  background-color: #f5f7fa;
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.header-content {
  flex: 1;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px 0;
}

.page-subtitle {
  font-size: 14px;
  color: #909399;
  margin: 0;
}

.query-section {
  margin-bottom: 24px;
}

.query-card {
  background-color: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.query-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 16px 0;
}

.query-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.query-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #909399;
  background-color: #f0f9ff;
  padding: 8px 12px;
  border-radius: 4px;
  border-left: 4px solid #409eff;
}

.query-hint .el-icon {
  color: #409eff;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.loading-icon {
  font-size: 48px;
  color: #409eff;
  margin-bottom: 16px;
  animation: rotate 2s linear infinite;
}

.loading-state p {
  margin: 0;
  color: #606266;
  font-size: 16px;
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px 20px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.trace-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.trace-basic-info {
  background-color: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.info-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.info-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.info-actions {
  display: flex;
  gap: 8px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-label {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}

.info-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  word-break: break-all;
}

.trace-id {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  background-color: #f5f7fa;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}

.info-value.completed {
  color: #67c23a;
}

.info-value.running {
  color: #409eff;
}

.info-value.failed {
  color: #f56c6c;
}

.info-value.pending {
  color: #e6a23c;
}

.execution-step-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.execution-steps-section {
  background-color: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.steps-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.steps-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-item {
  background-color: #fafafa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.step-item:hover {
  background-color: #f0f9ff;
  border-color: #c6e2ff;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.step-item.selected {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.step-item.completed {
  border-left: 4px solid #67c23a;
}

.step-item.running {
  border-left: 4px solid #409eff;
}

.step-item.failed {
  border-left: 4px solid #f56c6c;
}

.step-item.pending {
  border-left: 4px solid #e6a23c;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-order {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  background-color: #e4e7ed;
  padding: 2px 8px;
  border-radius: 10px;
  min-width: 24px;
  text-align: center;
}

.step-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.step-agent {
  font-size: 12px;
  color: #909399;
  background-color: #e4e7ed;
  padding: 2px 8px;
  border-radius: 4px;
}

.step-status {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.step-status.completed {
  background-color: rgba(103, 194, 58, 0.2);
  color: #67c23a;
}

.step-status.running {
  background-color: rgba(64, 158, 255, 0.2);
  color: #409eff;
}

.step-status.failed {
  background-color: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
}

.step-status.pending {
  background-color: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
}

.step-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-meta {
  display: flex;
  gap: 16px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}

.meta-item .el-icon {
  font-size: 14px;
}

.step-error {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  background-color: rgba(245, 108, 108, 0.1);
  border-radius: 4px;
  border-left: 3px solid #f56c6c;
}

.step-error .el-icon {
  font-size: 14px;
  color: #f56c6c;
  margin-top: 1px;
}

.error-message {
  font-size: 12px;
  color: #f56c6c;
  line-height: 1.4;
}

.node-detail-section {
  background-color: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.node-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.node-detail-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.node-detail-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-section h4 {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 12px;
  color: #909399;
}

.detail-value {
  font-size: 13px;
  color: #303133;
  font-weight: 500;
  word-break: break-all;
}

.detail-value.completed {
  color: #67c23a;
}

.detail-value.running {
  color: #409eff;
}

.detail-value.failed {
  color: #f56c6c;
}

.detail-value.pending {
  color: #e6a23c;
}

.data-viewer, .error-viewer {
  background-color: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.data-viewer pre, .error-viewer pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  line-height: 1.4;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-all;
}

.error-viewer .error-message {
  font-size: 13px;
  color: #f56c6c;
  margin-bottom: 12px;
  font-weight: 500;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  text-align: center;
}

.empty-state .el-icon {
  font-size: 64px;
  color: #c0c4cc;
  margin-bottom: 20px;
}

.empty-state p {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #606266;
}

.empty-hint {
  font-size: 14px;
  color: #909399;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

