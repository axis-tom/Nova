<template>
  <div class="left-panel">
    <div class="panel-header">
      <h3 class="panel-title">情报与策略</h3>
      <div class="panel-subtitle">任务选择与AI策略控制</div>
    </div>

    <div class="panel-content">
      <!-- TaskLauncher 组件 -->
      <div class="section">
        <div class="section-header">
          <span class="section-icon">🚀</span>
          <span class="section-title">任务启动器</span>
        </div>
        <div class="section-content">
          <TaskLauncher @taskSelected="handleTaskSelected" />
        </div>
      </div>

      <!-- StrategyPanel 组件 -->
      <div class="section">
        <div class="section-header">
          <span class="section-icon">🧠</span>
          <span class="section-title">AI策略面板</span>
        </div>
        <div class="section-content">
          <StrategyPanel @updateStrategy="handleStrategyUpdate" />
        </div>
      </div>

      <!-- 系统状态 -->
      <div class="section">
        <div class="section-header">
          <span class="section-icon">📊</span>
          <span class="section-title">系统状态</span>
        </div>
        <div class="section-content">
          <div class="status-info">
            <div class="status-item">
              <span class="status-label">活动任务:</span>
              <span class="status-value">{{ activeTask || '无' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">节点状态:</span>
              <span class="status-value">{{ nodeStatusSummary }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">执行进度:</span>
              <span class="status-value">{{ executionProgress }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useWorkspaceStore } from '@/stores/workspace'
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import TaskLauncher from './components/TaskLauncher.vue'
import StrategyPanel from './components/StrategyPanel.vue'

const workspaceStore = useWorkspaceStore()
const { activeTask, nodes, nodeStatus } = storeToRefs(workspaceStore)

// 计算属性
const nodeStatusSummary = computed(() => {
  const statusCount = {
    idle: 0,
    running: 0,
    done: 0,
    dirty: 0
  }
  
  Object.values(nodeStatus.value).forEach(status => {
    statusCount[status] = (statusCount[status] || 0) + 1
  })
  
  const parts = []
  if (statusCount.done > 0) parts.push(`${statusCount.done}完成`)
  if (statusCount.running > 0) parts.push(`${statusCount.running}执行中`)
  if (statusCount.dirty > 0) parts.push(`${statusCount.dirty}需更新`)
  if (statusCount.idle > 0) parts.push(`${statusCount.idle}待执行`)
  
  return parts.length > 0 ? parts.join(', ') : '无节点'
})

const executionProgress = computed(() => {
  const total = Object.keys(nodeStatus.value).length
  const done = Object.values(nodeStatus.value).filter(s => s === 'done').length
  
  if (total === 0) return '0%'
  return `${Math.round((done / total) * 100)}%`
})

// 方法
const handleTaskSelected = (task) => {
  console.log('任务选择:', task)
  // 通过store处理任务选择
  workspaceStore.setActiveTask(task)
}

const handleStrategyUpdate = (strategy) => {
  console.log('策略更新:', strategy)
  // 通过store更新策略
  workspaceStore.updateStrategy(strategy)
}
</script>

<style scoped>
.left-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #1e293b;
  padding: 16px;
}

.panel-header {
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid #334155;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #f1f5f9;
  margin: 0 0 4px 0;
}

.panel-subtitle {
  font-size: 12px;
  color: #94a3b8;
}

.panel-content {
  flex-grow: 1;
  overflow-y: auto;
}

.section {
  margin-bottom: 20px;
  background-color: #0f172a;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
}

.section-icon {
  font-size: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.section-content {
  padding: 16px;
}

.placeholder {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.placeholder-item {
  padding: 10px 12px;
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
  cursor: default;
  transition: all 0.2s;
}

.placeholder-item:hover {
  background-color: #334155;
  color: #cbd5e1;
}
</style>