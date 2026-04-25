<template>
  <div class="result-container">
    <!-- 结果容器头部 -->
    <div class="result-header">
      <div class="header-left">
        <span class="header-icon">📊</span>
        <div class="header-info">
          <div class="header-title">结果展示</div>
          <div class="header-subtitle" v-if="activeNode">
            {{ activeNode.label }} - {{ getNodeTypeLabel() }}
          </div>
          <div class="header-subtitle" v-else>
            选择节点查看结果
          </div>
        </div>
      </div>
      <div class="header-right">
        <div class="header-status" v-if="activeNodeStatus">
          <span class="status-indicator" :class="activeNodeStatus"></span>
          <span class="status-text">{{ getStatusText() }}</span>
        </div>
      </div>
    </div>

    <!-- 结果内容区域 -->
    <div class="result-content">
      <!-- 无活动节点提示 -->
      <div v-if="!activeNode" class="no-result">
        <div class="no-result-icon">👈</div>
        <div class="no-result-title">请选择节点</div>
        <div class="no-result-description">
          在左侧画布中选择一个节点以查看其执行结果
        </div>
      </div>

      <!-- 有活动节点但无结果 -->
      <div v-else-if="!activeNodeResult" class="no-result">
        <div class="no-result-icon">📝</div>
        <div class="no-result-title">暂无结果</div>
        <div class="no-result-description">
          该节点尚未执行或未生成结果
        </div>
        <div class="no-result-actions" v-if="activeNodeStatus === 'idle' || activeNodeStatus === 'dirty'">
          <button class="action-btn" @click="handleRequestExecution">
            <span class="action-icon">🚀</span>
            <span>请求执行</span>
          </button>
        </div>
      </div>

      <!-- 根据节点类型动态渲染结果 -->
      <div v-else class="result-renderer">
        <!-- Listing类型结果 -->
        <div v-if="activeNode.type === 'generation' || activeNode.type === 'optimization'" class="listing-result">
          <ListingEditor 
            :content="activeNodeResult"
            @update="handleUpdateResult"
          />
        </div>

        <!-- 图片类型结果 -->
        <div v-else-if="activeNode.type === 'research' && Array.isArray(activeNodeResult.images)" class="image-result">
          <ImageCompare :images="activeNodeResult.images" />
        </div>

        <!-- 图表类型结果 -->
        <div v-else-if="activeNode.type === 'analysis' && activeNodeResult.metrics" class="chart-result">
          <ChartPanel :metrics="activeNodeResult.metrics" />
        </div>

        <!-- 文本类型结果 -->
        <div v-else-if="typeof activeNodeResult === 'string'" class="text-result">
          <div class="text-result-header">
            <span class="result-icon">📄</span>
            <span class="result-title">文本结果</span>
          </div>
          <div class="text-result-content">
            <pre>{{ activeNodeResult }}</pre>
          </div>
          <div class="text-result-actions">
            <button class="action-btn" @click="handleCopyResult">
              <span class="action-icon">📋</span>
              <span>复制</span>
            </button>
            <button class="action-btn" @click="handleDownloadResult">
              <span class="action-icon">⬇️</span>
              <span>下载</span>
            </button>
          </div>
        </div>

        <!-- JSON类型结果 -->
        <div v-else class="json-result">
          <div class="json-result-header">
            <span class="result-icon">🔧</span>
            <span class="result-title">数据结果</span>
          </div>
          <div class="json-result-content">
            <pre>{{ formatJSON(activeNodeResult) }}</pre>
          </div>
          <div class="json-result-actions">
            <button class="action-btn" @click="handleCopyJSON">
              <span class="action-icon">📋</span>
              <span>复制JSON</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 结果操作栏 -->
    <div class="result-actions" v-if="activeNode && activeNodeResult">
      <div class="actions-left">
        <div class="result-meta">
          <span class="meta-item">
            <span class="meta-icon">🕒</span>
            <span class="meta-text">最近更新: {{ getUpdateTime() }}</span>
          </span>
          <span class="meta-item">
            <span class="meta-icon">📏</span>
            <span class="meta-text">数据大小: {{ getDataSize() }}</span>
          </span>
        </div>
      </div>
      <div class="actions-right">
        <button class="action-btn secondary" @click="handleRefresh">
          <span class="action-icon">🔄</span>
          <span>刷新</span>
        </button>
        <button class="action-btn primary" @click="handleUpdateResult(activeNodeResult)">
          <span class="action-icon">💾</span>
          <span>保存更改</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '@/state/workspace'
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import ListingEditor from './components/ListingEditor.vue'
import ImageCompare from './components/ImageCompare.vue'
import ChartPanel from './components/ChartPanel.vue'

interface Emits {
  (e: 'updateResult', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

const workspaceStore = useWorkspaceStore()
const { activeNode, activeNodeResult, activeNodeStatus } = storeToRefs(workspaceStore)

// 方法
const handleUpdateResult = (newContent) => {
  if (!activeNode.value) return
  
  // 通过store更新结果
  workspaceStore.updateResult(activeNode.value.id, newContent)
  // 发射事件通知父组件
  emit('updateResult', { nodeId: activeNode.value.id, data: newContent })
}

const handleRequestExecution = () => {
  if (!activeNode.value) return
  console.log('请求执行节点:', activeNode.value.id)
  // 这里可以发射事件请求执行，但组件不直接控制Graph
}

const handleCopyResult = () => {
  if (typeof activeNodeResult.value === 'string') {
    navigator.clipboard.writeText(activeNodeResult.value)
    alert('结果已复制到剪贴板')
  }
}

const handleDownloadResult = () => {
  if (typeof activeNodeResult.value === 'string') {
    const blob = new Blob([activeNodeResult.value], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `result-${activeNode.value?.id || 'unknown'}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }
}

const handleCopyJSON = () => {
  try {
    const jsonStr = JSON.stringify(activeNodeResult.value, null, 2)
    navigator.clipboard.writeText(jsonStr)
    alert('JSON已复制到剪贴板')
  } catch (error) {
    console.error('复制JSON失败:', error)
  }
}

const handleRefresh = () => {
  // 刷新结果（可以重新获取数据）
  console.log('刷新结果')
}

const getNodeTypeLabel = () => {
  if (!activeNode.value) return ''
  const typeLabels = {
    research: '调研',
    analysis: '分析',
    generation: '生成',
    optimization: '优化',
    check: '检查',
    assessment: '评估'
  }
  return typeLabels[activeNode.value.type] || activeNode.value.type
}

const getStatusText = () => {
  const statusTexts = {
    idle: '待执行',
    running: '执行中',
    done: '已完成',
    dirty: '需更新'
  }
  return statusTexts[activeNodeStatus.value] || activeNodeStatus.value
}

const formatJSON = (obj) => {
  try {
    return JSON.stringify(obj, null, 2)
  } catch (error) {
    return String(obj)
  }
}

const getUpdateTime = () => {
  // 这里可以添加实际的时间戳逻辑
  return '刚刚'
}

const getDataSize = () => {
  if (!activeNodeResult.value) return '0 B'
  
  let size
  if (typeof activeNodeResult.value === 'string') {
    size = new Blob([activeNodeResult.value]).size
  } else {
    size = new Blob([JSON.stringify(activeNodeResult.value)]).size
  }
  
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<style scoped>
.result-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #0f172a;
}

.result-header {
  padding: 16px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  font-size: 24px;
}

.header-info {
  display: flex;
  flex-direction: column;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 2px;
}

.header-subtitle {
  font-size: 12px;
  color: #94a3b8;
}

.header-right {
  display: flex;
  align-items: center;
}

.header-status {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background-color: #0f172a;
  border-radius: 6px;
  border: 1px solid #334155;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-indicator.idle {
  background-color: #94a3b8;
}

.status-indicator.running {
  background-color: #3b82f6;
  animation: pulse 1.5s infinite;
}

.status-indicator.done {
  background-color: #10b981;
}

.status-indicator.dirty {
  background-color: #f59e0b;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.status-text {
  font-size: 12px;
  color: #cbd5e1;
}

.result-content {
  flex-grow: 1;
  overflow-y: auto;
  padding: 20px;
}

.no-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #94a3b8;
}

.no-result-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.no-result-title {
  font-size: 18px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.no-result-description {
  font-size: 14px;
  max-width: 300px;
  line-height: 1.5;
  margin-bottom: 20px;
}

.no-result-actions {
  margin-top: 16px;
}

.text-result,
.json-result {
  background-color: #1e293b;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.text-result-header,
.json-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
}

.result-icon {
  font-size: 16px;
}

.result-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.text-result-content,
.json-result-content {
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.text-result-content pre,
.json-result-content pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #cbd5e1;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.text-result-actions,
.json-result-actions {
  padding: 12px 16px;
  border-top: 1px solid #334155;
  background-color: #0f172a;
  display: flex;
  gap: 8px;
}

.result-actions {
  padding: 12px 16px;
  background-color: #1e293b;
  border-top: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.actions-left {
  flex-grow: 1;
}

.result-meta {
  display: flex;
  gap: 16px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.meta-icon {
  font-size: 12px;
  opacity: 0.7;
}

.meta-text {
  font-size: 12px;
  color: #94a3b8;
}

.actions-right {
  display: flex;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background-color: #334155;
  border: 1px solid #475569;
  border-radius: 6px;
  color: #cbd5e1;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background-color: #475569;
  border-color: #64748b;
}

.action-btn.primary {
  background-color: #3b82f6;
  border-color: #3b82f6;
  color: white;
}

.action-btn.primary:hover {
  background-color: #2563eb;
  border-color: #2563eb;
}

.action-btn.secondary {
  background-color: #475569;
  border-color: #64748b;
}

.action-btn.secondary:hover {
  background-color: #64748b;
  border-color: #94a3b8;
}

.action-icon {
  font-size: 14px;
}
</style>