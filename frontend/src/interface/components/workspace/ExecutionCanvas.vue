<template>
  <div class="execution-canvas">
    <div class="canvas-header">
      <div class="header-left">
        <span class="header-icon">📈</span>
        <div class="header-info">
          <div class="header-title">执行画布</div>
          <div class="header-subtitle">AI工作流可视化执行</div>
        </div>
      </div>
      <div class="header-right">
        <div class="canvas-controls">
          <button class="control-btn" @click="toggleViewMode">
            <span class="btn-icon">{{ viewMode === 'graph' ? '📋' : '📊' }}</span>
            <span class="btn-text">{{ viewMode === 'graph' ? '列表视图' : '图形视图' }}</span>
          </button>
          <button class="control-btn" @click="handleAutoLayout">
            <span class="btn-icon">🔧</span>
            <span class="btn-text">自动布局</span>
          </button>
        </div>
      </div>
    </div>

    <div class="canvas-container">
      <!-- 图形视图 -->
      <div class="graph-view" v-if="viewMode === 'graph'">
        <div class="graph-placeholder" v-if="!hasNodes">
          <div class="placeholder-icon">📊</div>
          <div class="placeholder-title">工作流画布</div>
          <div class="placeholder-description">
            在此处可视化AI工作流的执行流程
          </div>
          <div class="placeholder-hint">
            选择任务后，将在此处显示工作流节点
          </div>
        </div>

        <div class="graph-content" v-else>
          <!-- 模拟图形布局 -->
          <div class="mock-graph">
            <!-- 节点容器 -->
            <div class="nodes-container">
              <BusinessNode 
                v-for="node in displayedNodes" 
                :key="node.id"
                :node="node"
                @click="handleNodeClick"
                @rerun="handleNodeRerun"
              />
            </div>

            <!-- 连接线 -->
            <div class="connections-container">
              <svg class="connections-svg">
                <line 
                  v-for="(edge, index) in edges" 
                  :key="index"
                  :x1="getNodeX(edge.source)" 
                  :y1="getNodeY(edge.source)"
                  :x2="getNodeX(edge.target)" 
                  :y2="getNodeY(edge.target)"
                  stroke="#3b82f6" 
                  stroke-width="2"
                  stroke-dasharray="5,5"
                />
              </svg>
            </div>
          </div>
        </div>
      </div>

      <!-- 列表视图 -->
      <div class="list-view" v-else>
        <div class="list-header">
          <div class="list-column">节点</div>
          <div class="list-column">类型</div>
          <div class="list-column">状态</div>
          <div class="list-column">操作</div>
        </div>
        <div class="list-content">
          <div 
            v-for="node in displayedNodes" 
            :key="node.id"
            class="list-item"
            :class="{ active: activeNodeId === node.id }"
            @click="handleNodeClick(node.id)"
          >
            <div class="item-cell">
              <span class="node-icon">
                <span v-if="node.type === 'research'">🔍</span>
                <span v-else-if="node.type === 'analysis'">📊</span>
                <span v-else-if="node.type === 'generation'">✨</span>
                <span v-else-if="node.type === 'optimization'">⚡</span>
                <span v-else>📋</span>
              </span>
              <span class="node-label">{{ node.label }}</span>
            </div>
            <div class="item-cell">
              <span class="node-type">{{ getNodeTypeLabel(node.type) }}</span>
            </div>
            <div class="item-cell">
              <span class="node-status" :class="getNodeStatusClass(node.id)">
                {{ getNodeStatusText(node.id) }}
              </span>
            </div>
            <div class="item-cell">
              <button class="action-btn" @click.stop="handleNodeRerun(node.id)">
                <span class="btn-icon">🔄</span>
                <span class="btn-text">重新执行</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 画布控制栏 -->
    <div class="canvas-footer">
      <div class="footer-left">
        <div class="canvas-stats">
          <span class="stat-item">
            <span class="stat-icon">📊</span>
            <span class="stat-text">{{ nodeCount }} 个节点</span>
          </span>
          <span class="stat-item">
            <span class="stat-icon">🔗</span>
            <span class="stat-text">{{ edgeCount }} 条连接</span>
          </span>
          <span class="stat-item">
            <span class="stat-icon">⚡</span>
            <span class="stat-text">{{ runningCount }} 个执行中</span>
          </span>
        </div>
      </div>
      <div class="footer-right">
        <button class="action-btn secondary" @click="handleClearSelection">
          <span class="btn-icon">🗑️</span>
          <span class="btn-text">清除选择</span>
        </button>
        <button class="action-btn primary" @click="handleExecuteAll">
          <span class="btn-icon">🚀</span>
          <span class="btn-text">执行全部</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '@/state/workspace'
import { storeToRefs } from 'pinia'
import { computed, ref } from 'vue'
import BusinessNode from './components/BusinessNode.vue';

interface Emits {
  (e: 'nodeClick', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

const workspaceStore = useWorkspaceStore()
const { nodes, edges, nodeStatus, activeNode } = storeToRefs(workspaceStore)

// 响应式数据
const viewMode = ref<string>('graph') // 'graph' 或 'list'
const activeNodeId = ref<HTMLElement | null>(null)

// 计算属性
const hasNodes = computed(() => {
  return nodes.value && nodes.value.length > 0
})

const displayedNodes = computed(() => {
  if (hasNodes.value) {
    return nodes.value
  }
  // 模拟节点数据
  return [
    { id: 'node-1', label: '市场调研', type: 'research' },
    { id: 'node-2', label: '数据分析', type: 'analysis' },
    { id: 'node-3', label: '内容生成', type: 'generation' },
    { id: 'node-4', label: 'SEO优化', type: 'optimization' },
    { id: 'node-5', label: '质量检查', type: 'check' },
    { id: 'node-6', label: '效果评估', type: 'assessment' }
  ]
})

const nodeCount = computed(() => {
  return displayedNodes.value.length
})

const edgeCount = computed(() => {
  return edges.value?.length || 5
})

const runningCount = computed(() => {
  return Object.values(nodeStatus.value).filter(status => status === 'running').length
})

// 方法
const toggleViewMode = () => {
  viewMode.value = viewMode.value === 'graph' ? 'list' : 'graph'
}

const handleAutoLayout = () => {
  console.log('自动布局')
}

const handleNodeClick = (nodeId) => {
  activeNodeId.value = nodeId
  workspaceStore.setActiveNode(nodeId)
  emit('nodeClick', nodeId)
}

const handleNodeRerun = (nodeId) => {
  console.log('重新执行节点:', nodeId)
  // 这里可以发射事件请求重新执行
}

const handleClearSelection = () => {
  activeNodeId.value = null
  workspaceStore.setActiveNode(null)
}

const handleExecuteAll = async () => {
  console.log('执行全部节点');
  try {
    await workspaceStore.executeAllNodes();
    console.log('全部节点执行完成');
  } catch (error) {
    console.error('执行失败:', error);
  }
};

const getNodeTypeLabel = (type) => {
  const typeLabels = {
    research: '调研',
    analysis: '分析',
    generation: '生成',
    optimization: '优化',
    check: '检查',
    assessment: '评估'
  }
  return typeLabels[type] || type
}

const getNodeStatusClass = (nodeId) => {
  const status = nodeStatus.value[nodeId] || 'idle'
  return `status-${status}`
}

const getNodeStatusText = (nodeId) => {
  const status = nodeStatus.value[nodeId] || 'idle'
  const statusTexts = {
    idle: '待执行',
    running: '执行中',
    done: '已完成',
    dirty: '需更新'
  }
  return statusTexts[status] || status
}

const getNodeX = (nodeId) => {
  // 简单的X坐标计算
  const index = displayedNodes.value.findIndex(node => node.id === nodeId)
  return 100 + (index % 3) * 200
}

const getNodeY = (nodeId) => {
  // 简单的Y坐标计算
  const index = displayedNodes.value.findIndex(node => node.id === nodeId)
  return 100 + Math.floor(index / 3) * 150
}
</script>

<style scoped>
.execution-canvas {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #0f172a;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.canvas-header {
  padding: 12px 16px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  font-size: 20px;
}

.header-info {
  display: flex;
  flex-direction: column;
}

.header-title {
  font-size: 14px;
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

.canvas-controls {
  display: flex;
  gap: 8px;
}

.control-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background-color: #334155;
  border: 1px solid #475569;
  border-radius: 4px;
  color: #cbd5e1;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.control-btn:hover {
  background-color: #475569;
  border-color: #64748b;
}

.btn-icon {
  font-size: 12px;
}

.btn-text {
  font-weight: 500;
}

.canvas-container {
  flex-grow: 1;
  padding: 16px;
  overflow: auto;
}

.graph-view {
  height: 100%;
}

.graph-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #94a3b8;
  text-align: center;
}

.placeholder-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.placeholder-title {
  font-size: 16px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.placeholder-description {
  font-size: 14px;
  max-width: 300px;
  line-height: 1.5;
  margin-bottom: 10px;
}

.placeholder-hint {
  font-size: 11px;
  color: #64748b;
  font-style: italic;
  padding: 6px;
  background-color: #1e293b;
  border-radius: 4px;
  border: 1px solid #334155;
}

.graph-content {
  height: 100%;
  position: relative;
}

.mock-graph {
  height: 100%;
  position: relative;
}

.nodes-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
  padding: 20px;
}

.connections-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.connections-svg {
  width: 100%;
  height: 100%;
}

.list-view {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
}

.list-header {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  padding: 12px 16px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
}

.list-column {
  font-size: 13px;
  font-weight: 500;
  color: #94a3b8;
}

.list-content {
  max-height: 400px;
  overflow-y: auto;
}

.list-item {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  padding: 12px 16px;
  border-bottom: 1px solid #334155;
  cursor: pointer;
  transition: all 0.2s;
}

.list-item:hover {
  background-color: #2d3748;
}

.list-item.active {
  background-color: rgba(59, 130, 246, 0.1);
}

.list-item:last-child {
  border-bottom: none;
}

.item-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  font-size: 16px;
}

.node-label {
  font-size: 13px;
  color: #e2e8f0;
}

.node-type {
  font-size: 12px;
  color: #94a3b8;
  background-color: #334155;
  padding: 2px 8px;
  border-radius: 4px;
}

.node-status {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.status-idle {
  background-color: #334155;
  color: #94a3b8;
}

.status-running {
  background-color: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.status-done {
  background-color: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.status-dirty {
  background-color: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background-color: #334155;
  border: 1px solid #475569;
  border-radius: 4px;
  color: #cbd5e1;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background-color: #475569;
  border-color: #64748b;
}

.canvas-footer {
  padding: 12px 16px;
  background-color: #1e293b;
  border-top: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-left {
  flex-grow: 1;
}

.canvas-stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-icon {
  font-size: 12px;
  opacity: 0.7;
}

.stat-text {
  font-size: 12px;
  color: #94a3b8;
}

.footer-right {
  display: flex;
  gap: 8px;
}

.action-btn.secondary {
  background-color: #475569;
  color: #e2e8f0;
}

.action-btn.secondary:hover {
  background-color: #64748b;
}

.action-btn.primary {
  background-color: #3b82f6;
  color: white;
}

.action-btn.primary:hover {
  background-color: #2563eb;
}
</style>