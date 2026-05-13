<template>
  <div 
    class="business-node"
    :class="[statusClass, { active: isActive }]"
    @click="handleClick"
  >
    <!-- 节点头部 -->
    <div class="node-header">
      <div class="node-icon">
        <span v-if="node.type === 'research'">🔍</span>
        <span v-else-if="node.type === 'collection'">📡</span>
        <span v-else-if="node.type === 'analysis'">📊</span>
        <span v-else-if="node.type === 'generation'">✨</span>
        <span v-else-if="node.type === 'optimization'">⚡</span>
        <span v-else-if="node.type === 'check'">✅</span>
        <span v-else-if="node.type === 'assessment'">⚠️</span>
        <span v-else>📋</span>
      </div>
      <div class="node-info">
        <div class="node-label">{{ node.label }}</div>
        <div class="node-type">{{ getNodeTypeLabel() }}</div>
      </div>
      <div class="node-status">
        <span class="status-indicator" :class="statusClass"></span>
        <span class="status-text">{{ getStatusText() }}</span>
      </div>
    </div>

    <!-- 节点内容 -->
    <div class="node-content">
      <div class="node-description">
        {{ getNodeDescription() }}
      </div>
      
      <!-- 运行状态指示器 -->
      <div v-if="status === 'running'" class="running-indicator">
        <div class="running-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="running-text">执行中...</div>
      </div>

      <!-- 结果预览 -->
      <div v-if="hasResult && status === 'done'" class="result-preview">
        <div class="preview-header">
          <span class="preview-icon">📄</span>
          <span class="preview-title">结果预览</span>
        </div>
        <div class="preview-content">
          {{ getResultPreview() }}
        </div>
      </div>

      <!-- 脏状态提示 -->
      <div v-if="status === 'dirty'" class="dirty-indicator">
        <span class="dirty-icon">🔄</span>
        <span class="dirty-text">需要重新执行</span>
      </div>
    </div>

    <!-- 节点操作 -->
    <div class="node-actions">
      <button 
        v-if="status === 'done' || status === 'dirty'"
        class="action-btn rerun-btn"
        @click.stop="handleRerun"
        :disabled="status === 'running'"
      >
        <span class="action-icon">🔄</span>
        <span class="action-text">重新执行</span>
      </button>
      
      <button 
        v-if="hasResult"
        class="action-btn view-btn"
        @click.stop="handleViewResult"
      >
        <span class="action-icon">👁️</span>
        <span class="action-text">查看结果</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '@/state/workspace'
import { computed } from 'vue'

interface Props {
  node?: Record<string, unknown>
}

const props = defineProps<Props>()

interface Emits {
  (e: 'click', ...args: unknown[]): void
  (e: 'rerun', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

const workspaceStore = useWorkspaceStore()

// 计算属性
const status = computed(() => {
  return workspaceStore.nodeStatus[props.node.id] || 'idle'
})

const isActive = computed(() => {
  return workspaceStore.activeNode?.id === props.node.id
})

const statusClass = computed(() => {
  return `status-${status.value}`
})

const hasResult = computed(() => {
  return !!workspaceStore.results[props.node.id]
})

// 方法
const handleClick = () => {
  // 通过store设置活动节点
  workspaceStore.setActiveNode(props.node.id)
  // 发射事件通知父组件
  emit('click', props.node.id)
}

const handleRerun = () => {
  // 发射重新执行事件
  emit('rerun', props.node.id)
  // 注意：组件不直接执行Graph，只发射事件
}

const handleViewResult = () => {
  // 设置活动节点以查看结果
  workspaceStore.setActiveNode(props.node.id)
}

const getNodeTypeLabel = () => {
  const typeLabels = {
    research: '调研',
    analysis: '分析',
    generation: '生成',
    optimization: '优化',
    check: '检查',
    assessment: '评估'
  }
  return typeLabels[props.node.type] || props.node.type
}

const getNodeDescription = () => {
  const descriptions = {
    research: '收集和分析市场数据',
    analysis: '深度数据处理和洞察',
    generation: 'AI内容生成',
    optimization: '性能优化和调整',
    check: '质量验证和检查',
    assessment: '风险评估和预测'
  }
  return descriptions[props.node.type] || '执行特定业务任务'
}

const getStatusText = () => {
  const statusTexts = {
    idle: '待执行',
    running: '执行中',
    done: '已完成',
    dirty: '需更新'
  }
  return statusTexts[status.value] || status.value
}

const getResultPreview = () => {
  const result = workspaceStore.results[props.node.id]
  if (!result) return '无结果'
  
  if (typeof result === 'string') {
    return result.length > 60 ? result.substring(0, 60) + '...' : result
  }
  
  if (typeof result === 'object') {
    const text = JSON.stringify(result)
    return text.length > 60 ? text.substring(0, 60) + '...' : text
  }
  
  return '结果已生成'
}
</script>

<style scoped>
.business-node {
  background-color: #1e293b;
  border: 2px solid #334155;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
}

.business-node:hover {
  border-color: #475569;
  background-color: #2d3748;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.business-node.active {
  border-color: #3b82f6;
  background-color: rgba(59, 130, 246, 0.1);
}

/* 状态样式 */
.status-idle {
  border-left-color: #94a3b8;
}

.status-running {
  border-left-color: #3b82f6;
  animation: pulse-border 2s infinite;
}

.status-done {
  border-left-color: #10b981;
}

.status-dirty {
  border-left-color: #f59e0b;
}

@keyframes pulse-border {
  0%, 100% {
    border-left-color: #3b82f6;
  }
  50% {
    border-left-color: #60a5fa;
  }
}

/* 节点头部 */
.node-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.node-icon {
  font-size: 24px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #0f172a;
  border-radius: 8px;
  flex-shrink: 0;
}

.node-info {
  flex-grow: 1;
}

.node-label {
  font-size: 16px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 2px;
}

.node-type {
  font-size: 12px;
  color: #94a3b8;
  background-color: #334155;
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-block;
}

.node-status {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-indicator.status-idle {
  background-color: #94a3b8;
}

.status-indicator.status-running {
  background-color: #3b82f6;
  animation: pulse 1.5s infinite;
}

.status-indicator.status-done {
  background-color: #10b981;
}

.status-indicator.status-dirty {
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
  color: #94a3b8;
}

/* 节点内容 */
.node-content {
  margin-bottom: 16px;
}

.node-description {
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.5;
  margin-bottom: 12px;
}

.running-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background-color: rgba(59, 130, 246, 0.1);
  border-radius: 6px;
  margin-top: 8px;
}

.running-dots {
  display: flex;
  gap: 4px;
}

.running-dots span {
  width: 6px;
  height: 6px;
  background-color: #3b82f6;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.running-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.running-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.running-text {
  font-size: 12px;
  color: #60a5fa;
}

.result-preview {
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 10px;
  margin-top: 8px;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.preview-icon {
  font-size: 12px;
}

.preview-title {
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
}

.preview-content {
  font-size: 12px;
  color: #cbd5e1;
  line-height: 1.4;
  max-height: 40px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.dirty-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  background-color: rgba(245, 158, 11, 0.1);
  border-radius: 6px;
  margin-top: 8px;
}

.dirty-icon {
  font-size: 14px;
}

.dirty-text {
  font-size: 12px;
  color: #f59e0b;
}

/* 节点操作 */
.node-actions {
  display: flex;
  gap: 8px;
  border-top: 1px solid #334155;
  padding-top: 12px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background-color: #334155;
  border: 1px solid #475569;
  border-radius: 6px;
  color: #cbd5e1;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  flex: 1;
  justify-content: center;
}

.action-btn:hover:not(:disabled) {
  background-color: #475569;
  border-color: #64748b;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.rerun-btn:hover:not(:disabled) {
  background-color: rgba(245, 158, 11, 0.2);
  border-color: #f59e0b;
  color: #f59e0b;
}

.view-btn:hover:not(:disabled) {
  background-color: rgba(59, 130, 246, 0.2);
  border-color: #3b82f6;
  color: #60a5fa;
}

.action-icon {
  font-size: 12px;
}

.action-text {
  font-weight: 500;
}
</style>