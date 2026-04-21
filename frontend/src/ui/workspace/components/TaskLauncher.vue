<template>
  <div class="task-launcher">
    <div class="section-header">
      <span class="section-icon">🚀</span>
      <span class="section-title">任务启动器</span>
    </div>
    
    <div class="task-list">
      <div 
        v-for="task in tasks" 
        :key="task.id"
        class="task-item"
        :class="{ active: activeTask?.id === task.id }"
        @click="handleTaskSelect(task)"
      >
        <div class="task-icon">
          <span v-if="task.id === 'listing'">📝</span>
          <span v-else-if="task.id === 'customer-service'">💬</span>
          <span v-else-if="task.id === 'product-selection'">📊</span>
          <span v-else>📋</span>
        </div>
        <div class="task-info">
          <div class="task-name">{{ task.name }}</div>
          <div class="task-description">{{ task.description }}</div>
        </div>
        <div class="task-status" v-if="activeTask?.id === task.id">
          <span class="status-indicator active"></span>
        </div>
      </div>
    </div>

    <div class="task-actions" v-if="activeTask">
      <div class="active-task-info">
        <div class="active-task-label">当前任务</div>
        <div class="active-task-name">{{ activeTask.name }}</div>
      </div>
      <div class="action-buttons">
        <button class="btn btn-secondary" @click="handleReset">重置</button>
        <button class="btn btn-primary" @click="handleInitialize">初始化Graph</button>
        <!-- 新增：运行全部节点按钮 -->
        <button 
          class="btn btn-success" 
          :disabled="isRunning"
          @click="handleRunAll"
        >
          {{ isRunning ? '执行中...' : '运行全部' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useWorkspaceStore } from '@/stores/workspace'
import { storeToRefs } from 'pinia'

const emit = defineEmits(['taskSelected'])

const workspaceStore = useWorkspaceStore()
const { tasks, activeTask, isGraphRunning } = storeToRefs(workspaceStore)

const handleTaskSelect = (task) => {
  workspaceStore.setActiveTask(task)
  emit('taskSelected', task)
}

const handleInitialize = () => {
  console.log('Graph初始化完成（仅数据设置）')
}

const handleReset = () => {
  workspaceStore.setActiveTask(null)
  emit('taskSelected', null)
}

// 新增：运行全部节点
const handleRunAll = async () => {
  try {
    await workspaceStore.executeAllNodes()
    console.log('所有节点执行完成')
  } catch (error) {
    console.error('执行失败:', error)
  }
}

// 新增：获取运行状态
const isRunning = isGraphRunning
</script>

<style scoped>
.task-launcher {
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

.task-list {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.task-item:hover {
  background-color: #2d3748;
  border-color: #475569;
}

.task-item.active {
  background-color: #1e3a8a;
  border-color: #3b82f6;
}

.task-icon {
  font-size: 20px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #0f172a;
  border-radius: 6px;
}

.task-info {
  flex-grow: 1;
}

.task-name {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
  margin-bottom: 2px;
}

.task-description {
  font-size: 12px;
  color: #94a3b8;
}

.task-status {
  padding-left: 8px;
}

.status-indicator {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #94a3b8;
}

.status-indicator.active {
  background-color: #10b981;
}

.task-actions {
  padding: 16px;
  border-top: 1px solid #334155;
  background-color: #1e293b;
}

.active-task-info {
  margin-bottom: 12px;
}

.active-task-label {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.active-task-name {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
  flex: 1;
}

.btn-primary {
  background-color: #3b82f6;
  color: white;
}

.btn-primary:hover {
  background-color: #2563eb;
}

.btn-secondary {
  background-color: #475569;
  color: #e2e8f0;
}

.btn-secondary:hover {
  background-color: #64748b;
}

/* 新增：成功/运行按钮样式 */
.btn-success {
  background-color: #10b981;
  color: white;
}

.btn-success:hover:not(:disabled) {
  background-color: #059669;
}

.btn-success:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>