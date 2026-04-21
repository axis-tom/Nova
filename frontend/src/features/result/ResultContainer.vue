<template>
  <div class="result-container">
    <!-- 结果容器头部 -->
    <div class="result-header">
      <div class="header-left">
        <span class="header-icon">📊</span>
        <div class="header-info">
          <div class="header-title">结果展示</div>
          <div class="header-subtitle" v-if="currentResult">
            {{ getResultTitle() }}
          </div>
          <div class="header-subtitle" v-else>
            等待结果...
          </div>
        </div>
      </div>
      <div class="header-right">
        <div class="header-status" v-if="currentResult">
          <span class="status-indicator" :class="getStatusClass()"></span>
          <span class="result-type">{{ getResultTypeLabel() }}</span>
        </div>
        <div class="header-actions" v-if="currentResult">
          <button class="action-btn small" @click="handleRefresh" title="刷新">
            <span class="action-icon">🔄</span>
          </button>
          <button class="action-btn small" @click="handleCopy" title="复制" v-if="currentResult.editable">
            <span class="action-icon">📋</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 结果内容区域 -->
    <div class="result-content">
      <!-- 无结果提示 -->
      <div v-if="!currentResult" class="no-result">
        <div class="no-result-icon">📝</div>
        <div class="no-result-title">暂无结果</div>
        <div class="no-result-description">
          执行Graph节点以查看结果
        </div>
      </div>

      <!-- 错误结果 -->
      <div v-else-if="currentResult.meta.error" class="error-result">
        <div class="error-icon">⚠️</div>
        <div class="error-title">结果处理错误</div>
        <div class="error-message">{{ currentResult.content.text }}</div>
        <div class="error-actions">
          <button class="action-btn" @click="handleRetry">
            <span class="action-icon">🔄</span>
            <span>重试</span>
          </button>
        </div>
      </div>

      <!-- 正常结果渲染 -->
      <div v-else class="result-renderer-wrapper">
        <ResultRenderer 
          :result="currentResult"
          @edit="handleEdit"
          @save="handleSave"
          @cancel="handleCancel"
        />
      </div>
    </div>

    <!-- 结果操作栏 -->
    <div class="result-actions" v-if="currentResult && !currentResult.meta.error">
      <div class="actions-left">
        <div class="result-meta">
          <span class="meta-item">
            <span class="meta-icon">🕒</span>
            <span class="meta-text">更新时间: {{ formatTimestamp(currentResult.meta.timestamp) }}</span>
          </span>
          <span class="meta-item">
            <span class="meta-icon">📌</span>
            <span class="meta-text">来源: {{ currentResult.meta.sourceNode || '未知' }}</span>
          </span>
          <span class="meta-item" v-if="currentResult.editable">
            <span class="meta-icon">✏️</span>
            <span class="meta-text">可编辑</span>
          </span>
        </div>
      </div>
      <div class="actions-right">
        <button class="action-btn secondary" @click="handleClear">
          <span class="action-icon">🗑️</span>
          <span>清除</span>
        </button>
        <button class="action-btn primary" @click="handleSaveAll" v-if="hasUnsavedChanges">
          <span class="action-icon">💾</span>
          <span>保存所有更改</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import eventBus from '../voe/eventBus.js'
import * as eventTypes from '../voe/eventTypes.js'
import { parseGraphOutput, validateResultSchema } from './parser/resultParser.js'
import ResultRenderer from './ResultRenderer.vue'

// 响应式数据
const currentResult = ref(null)
const resultHistory = ref([])
const hasUnsavedChanges = ref(false)
const editState = ref({
  isEditing: false,
  editData: null
})

// 计算属性
const getResultTitle = () => {
  if (!currentResult.value) return ''
  return currentResult.value.content.title || currentResult.value.meta.sourceNode || '结果'
}

const getResultTypeLabel = () => {
  if (!currentResult.value) return ''
  const typeLabels = {
    text: '文本',
    markdown: 'Markdown',
    table: '表格',
    chart: '图表',
    image: '图片',
    composite: '复合结果',
    json: 'JSON数据'
  }
  return typeLabels[currentResult.value.type] || currentResult.value.type
}

const getStatusClass = () => {
  if (!currentResult.value) return 'idle'
  if (currentResult.value.meta.error) return 'error'
  if (hasUnsavedChanges.value) return 'dirty'
  return 'done'
}

// 生命周期
onMounted(() => {
  // 监听RESULT_UPDATE事件
  eventBus.on(eventTypes.RESULT_UPDATE, handleResultUpdate)
  console.log('ResultContainer: 监听RESULT_UPDATE事件')
})

onUnmounted(() => {
  // 清理事件监听
  eventBus.off(eventTypes.RESULT_UPDATE, handleResultUpdate)
  console.log('ResultContainer: 清理事件监听')
})

// 事件处理
const handleResultUpdate = (payload) => {
  console.log('ResultContainer: 收到RESULT_UPDATE事件', payload)
  
  if (!payload || !payload.result) {
    console.warn('ResultContainer: 无效的RESULT_UPDATE数据')
    return
  }
  
  // 解析结果
  const parsedResult = parseGraphOutput(payload.result)
  
  // 验证结果schema
  if (!validateResultSchema(parsedResult)) {
    console.error('ResultContainer: 结果schema验证失败', parsedResult)
    return
  }
  
  // 添加到历史记录
  resultHistory.value.push({
    ...parsedResult,
    receivedAt: Date.now(),
    sourceEvent: payload
  })
  
  // 更新当前结果
  currentResult.value = parsedResult
  hasUnsavedChanges.value = false
  
  console.log(`ResultContainer: 更新结果 (类型: ${parsedResult.type}, ID: ${parsedResult.id})`)
}

const handleEdit = (editData) => {
  console.log('ResultContainer: 开始编辑', editData)
  editState.value = {
    isEditing: true,
    editData
  }
  hasUnsavedChanges.value = true
}

const handleSave = (savedData) => {
  console.log('ResultContainer: 保存编辑', savedData)
  
  if (!currentResult.value) return
  
  // 更新结果内容
  currentResult.value = {
    ...currentResult.value,
    content: {
      ...currentResult.value.content,
      ...savedData
    },
    meta: {
      ...currentResult.value.meta,
      lastEdited: Date.now(),
      editedBy: 'user'
    }
  }
  
  editState.value = {
    isEditing: false,
    editData: null
  }
  hasUnsavedChanges.value = false
  
  // 发送结果更新事件（触发Graph重算）
  eventBus.emit(eventTypes.RESULT_UPDATE, {
    action: 'user_edit',
    result: currentResult.value,
    originalResult: resultHistory.value[resultHistory.value.length - 1],
    timestamp: Date.now()
  })
  
  console.log('ResultContainer: 结果已保存并发送更新事件')
}

const handleCancel = () => {
  console.log('ResultContainer: 取消编辑')
  editState.value = {
    isEditing: false,
    editData: null
  }
  hasUnsavedChanges.value = false
}

const handleRefresh = () => {
  console.log('ResultContainer: 刷新结果')
  // 这里可以重新请求数据或触发重新解析
  if (currentResult.value) {
    // 发送刷新请求
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      action: 'refresh',
      resultId: currentResult.value.id,
      timestamp: Date.now()
    })
  }
}

const handleCopy = () => {
  if (!currentResult.value) return
  
  try {
    const textToCopy = currentResult.value.content.text || 
                      JSON.stringify(currentResult.value.content, null, 2)
    
    navigator.clipboard.writeText(textToCopy)
    console.log('ResultContainer: 结果已复制到剪贴板')
    
    // 可以添加复制成功的提示
  } catch (error) {
    console.error('ResultContainer: 复制失败', error)
  }
}

const handleRetry = () => {
  console.log('ResultContainer: 重试结果处理')
  // 重新处理最后一个结果
  if (resultHistory.value.length > 0) {
    const lastResult = resultHistory.value[resultHistory.value.length - 1]
    currentResult.value = parseGraphOutput(lastResult.sourceEvent.result)
  }
}

const handleClear = () => {
  console.log('ResultContainer: 清除结果')
  currentResult.value = null
  resultHistory.value = []
  hasUnsavedChanges.value = false
  editState.value = {
    isEditing: false,
    editData: null
  }
}

const handleSaveAll = () => {
  console.log('ResultContainer: 保存所有更改')
  // 如果有编辑状态，先保存
  if (editState.value.isEditing && editState.value.editData) {
    handleSave(editState.value.editData)
  }
  hasUnsavedChanges.value = false
}

// 工具函数
const formatTimestamp = (timestamp) => {
  if (!timestamp) return '未知'
  
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  
  // 如果小于1分钟，显示"刚刚"
  if (diffMs < 60000) {
    return '刚刚'
  }
  
  // 如果小于1小时，显示分钟
  if (diffMs < 3600000) {
    const minutes = Math.floor(diffMs / 60000)
    return `${minutes}分钟前`
  }
  
  // 如果小于1天，显示小时
  if (diffMs < 86400000) {
    const hours = Math.floor(diffMs / 3600000)
    return `${hours}小时前`
  }
  
  // 显示日期
  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 暴露方法供外部调用
defineExpose({
  getCurrentResult: () => currentResult.value,
  getResultHistory: () => [...resultHistory.value],
  clearResults: handleClear,
  refreshResult: handleRefresh
})
</script>

<style scoped>
.result-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #0f172a;
  border-radius: 8px;
  overflow: hidden;
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
  gap: 12px;
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

.status-indicator.error {
  background-color: #ef4444;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.result-type {
  font-size: 12px;
  color: #cbd5e1;
}

.header-actions {
  display: flex;
  gap: 4px;
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

.action-btn.small {
  padding: 6px 10px;
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

.result-content {
  flex-grow: 1;
  overflow-y: auto;
  padding: 20px;
}

.no-result, .error-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #94a3b8;
}

.no-result-icon, .error-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.no-result-title, .error-title {
  font-size: 18px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.no-result-description, .error-message {
  font-size: 14px;
  max-width: 300px;
  line-height: 1.5;
  margin-bottom: 20px;
}

.error-message {
  color: #f87171;
  background-color: rgba(239, 68, 68, 0.1);
  padding: 12px;
  border-radius: 6px;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.error-actions {
  margin-top: 16px;
}

.result-renderer-wrapper {
  height: 100%;
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
</style>