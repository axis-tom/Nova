<template>
  <div class="graph-canvas-container">
    <!-- 画布控制栏 -->
    <div class="canvas-controls">
      <div class="controls-left">
        <div class="canvas-title">
          <h3 v-if="traceData">执行流程图</h3>
          <h3 v-else>Graph画布</h3>
        </div>
        <div class="canvas-info" v-if="traceData">
          <span class="info-item">
            <i class="el-icon-data-line"></i>
            {{ traceData.session.graph_name || traceData.session.graph_id }}
          </span>
          <span class="info-item">
            <i class="el-icon-time"></i>
            {{ formatDuration(traceData.session.duration) }}
          </span>
          <span class="info-item">
            <i class="el-icon-s-check"></i>
            {{ traceData.nodes.filter(n => n.status === 'completed').length }}/{{ traceData.nodes.length }}
          </span>
        </div>
      </div>
      <div class="controls-right">
        <el-button-group size="small">
          <el-button icon="el-icon-zoom-in" @click="zoomIn"></el-button>
          <el-button icon="el-icon-zoom-out" @click="zoomOut"></el-button>
          <el-button icon="el-icon-full-screen" @click="fitToView"></el-button>
          <el-button icon="el-icon-refresh-left" @click="resetView"></el-button>
        </el-button-group>
      </div>
    </div>

    <!-- Graph画布 -->
    <div class="graph-canvas" ref="canvasRef">
      <svg
        :width="svgWidth"
        :height="svgHeight"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
        @wheel="onWheel"
      >
        <!-- 网格背景 -->
        <defs>
          <pattern
            id="grid"
            width="50"
            height="50"
            patternUnits="userSpaceOnUse"
          >
            <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#334155" stroke-width="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />

        <!-- 边（连接线） -->
        <g v-for="edge in graphEdges" :key="edge.id">
          <path
            :d="calculateEdgePath(edge)"
            fill="none"
            :stroke="getEdgeColor(edge)"
            stroke-width="2"
            marker-end="url(#arrowhead)"
          />
        </g>

        <!-- 节点 -->
        <g v-for="node in graphNodes" :key="node.id">
          <rect
            :x="node.x"
            :y="node.y"
            :width="nodeWidth"
            :height="nodeHeight"
            rx="8"
            ry="8"
            :fill="getNodeColor(node)"
            :stroke="getNodeBorderColor(node)"
            stroke-width="2"
            @mousedown="onNodeMouseDown(node, $event)"
            @mouseenter="hoveredNode = node"
            @mouseleave="hoveredNode = null"
          />
          <foreignObject
            :x="node.x"
            :y="node.y"
            :width="nodeWidth"
            :height="nodeHeight"
          >
            <div class="node-content">
              <div class="node-header">
                <div class="node-type-icon">
                  <i :class="getNodeIcon(node.type)"></i>
                </div>
                <div class="node-name">{{ node.name }}</div>
              </div>
              <div class="node-status">
                <span class="status-indicator" :class="node.status"></span>
                <span class="status-text">{{ node.status }}</span>
              </div>
              <div class="node-type">
                {{ getNodeTypeLabel(node.type) }}
              </div>
            </div>
          </foreignObject>
        </g>

        <!-- 箭头标记定义 -->
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#3b82f6" />
          </marker>
        </defs>
      </svg>
    </div>

    <!-- 节点详情面板 -->
    <div v-if="selectedNode" class="node-details-panel">
      <div class="panel-header">
        <h4>节点详情: {{ selectedNode.name }}</h4>
        <el-button
          type="text"
          icon="el-icon-close"
          @click="selectedNode = null"
        ></el-button>
      </div>
      <div class="panel-content">
        <!-- 基本信息 -->
        <div class="detail-section" v-if="selectedNode.originalNode">
          <h5>基本信息</h5>
          <div class="detail-grid">
            <div class="detail-item">
              <label>节点ID:</label>
              <span>{{ selectedNode.originalNode.node_id }}</span>
            </div>
            <div class="detail-item">
              <label>执行顺序:</label>
              <span>{{ selectedNode.originalNode.execution_order }}</span>
            </div>
            <div class="detail-item">
              <label>智能体:</label>
              <span>{{ selectedNode.originalNode.agent_name }} ({{ selectedNode.originalNode.agent_type || '未知类型' }})</span>
            </div>
            <div class="detail-item">
              <label>状态:</label>
              <span class="status-badge" :class="selectedNode.originalNode.status">
                {{ getNodeStatusText(selectedNode.originalNode.status) }}
              </span>
            </div>
            <div class="detail-item">
              <label>开始时间:</label>
              <span>{{ formatTime(selectedNode.originalNode.start_time) }}</span>
            </div>
            <div class="detail-item">
              <label>结束时间:</label>
              <span>{{ formatTime(selectedNode.originalNode.end_time) }}</span>
            </div>
            <div class="detail-item">
              <label>持续时间:</label>
              <span>{{ formatDuration(selectedNode.originalNode.duration) }}</span>
            </div>
          </div>
        </div>

        <!-- 输入数据 -->
        <div class="detail-section" v-if="selectedNode.originalNode?.input_data">
          <h5>输入数据</h5>
          <div class="data-viewer">
            <pre>{{ formatJson(selectedNode.originalNode.input_data) }}</pre>
          </div>
        </div>

        <!-- 输出数据 -->
        <div class="detail-section" v-if="selectedNode.originalNode?.output_data">
          <h5>输出数据</h5>
          <div class="data-viewer">
            <pre>{{ formatJson(selectedNode.originalNode.output_data) }}</pre>
          </div>
        </div>

        <!-- 错误信息 -->
        <div class="detail-section" v-if="selectedNode.originalNode?.error_message">
          <h5>错误信息</h5>
          <div class="error-viewer">
            <div class="error-message">{{ selectedNode.originalNode.error_message }}</div>
            <div v-if="selectedNode.originalNode.error_details" class="error-details">
              <pre>{{ formatJson(selectedNode.originalNode.error_details) }}</pre>
            </div>
          </div>
        </div>

        <!-- 如果没有原始节点数据，显示基本节点信息 -->
        <div class="detail-section" v-else>
          <div class="detail-item">
            <label>节点ID:</label>
            <span>{{ selectedNode.id }}</span>
          </div>
          <div class="detail-item">
            <label>节点类型:</label>
            <span>{{ getNodeTypeLabel(selectedNode.type) }}</span>
          </div>
          <div class="detail-item">
            <label>状态:</label>
            <span class="status-badge" :class="selectedNode.status">
              {{ selectedNode.status }}
            </span>
          </div>
          <div class="detail-item" v-if="selectedNode.config">
            <label>配置:</label>
            <pre class="config-json">{{ JSON.stringify(selectedNode.config, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-overlay">
      <el-icon class="loading-icon"><el-icon-loading /></el-icon>
      <p>加载Graph Schema...</p>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && graphNodes.length === 0" class="empty-state">
      <i class="el-icon-data-line"></i>
      <p>暂无Graph数据</p>
      <p class="empty-hint">请选择场景或点击刷新按钮加载Graph</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getGraphSchema, listScenarios } from '@/api/graph.js'
import { ElMessage } from 'element-plus'

// Props
const props = defineProps({
  traceData: {
    type: Object,
    default: null
  },
  traceId: {
    type: String,
    default: null
  },
  selectedNodeId: {
    type: String,
    default: null
  }
})

// Emits
const emit = defineEmits(['node-selected'])

// 响应式数据
const canvasRef = ref(null)
const selectedScenario = ref('')
const scenarios = ref([])
const graphSchema = ref(null)
const loading = ref(false)
const hoveredNode = ref(null)
const selectedNode = ref(null)

// 视图状态
const svgWidth = ref(800)
const svgHeight = ref(600)
const zoomLevel = ref(1)
const panOffset = ref({ x: 0, y: 0 })
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0 })

// 节点布局参数
const nodeWidth = 180
const nodeHeight = 80
const nodeSpacing = 100

// 计算属性：根据traceData生成节点
const graphNodes = computed(() => {
  // 如果提供了traceData，根据execution_path生成节点
  if (props.traceData && props.traceData.nodes && props.traceData.nodes.length > 0) {
    const nodes = props.traceData.nodes
    
    // 按执行顺序排序
    const sortedNodes = [...nodes].sort((a, b) => a.execution_order - b.execution_order)
    
    // 生成布局位置
    return sortedNodes.map((node, index) => {
      const x = 100 + index * (nodeWidth + nodeSpacing) + panOffset.value.x
      const y = 100 + panOffset.value.y
      
      return {
        id: node.node_id,
        name: node.node_name || node.node_id,
        type: 'agent_node', // 默认为agent节点
        status: node.status || 'idle',
        x,
        y,
        // 原始节点数据
        originalNode: node
      }
    })
  }
  
  // 如果没有traceData，使用原有的graphSchema逻辑
  if (!graphSchema.value || !graphSchema.value.nodes) return []
  
  // 简单布局：水平排列节点
  return graphSchema.value.nodes.map((node, index) => {
    const x = 100 + index * (nodeWidth + nodeSpacing) + panOffset.value.x
    const y = 100 + panOffset.value.y
    
    return {
      ...node,
      x,
      y,
      // 添加执行状态（模拟）
      status: node.status || 'idle'
    }
  })
})

// 计算属性：根据execution_path生成边
const graphEdges = computed(() => {
  // 如果提供了traceData，根据节点顺序生成边
  if (props.traceData && props.traceData.nodes && props.traceData.nodes.length > 1) {
    const edges = []
    const nodes = graphNodes.value
    
    // 按顺序连接节点
    for (let i = 0; i < nodes.length - 1; i++) {
      const sourceNode = nodes[i]
      const targetNode = nodes[i + 1]
      
      edges.push({
        id: `edge_${sourceNode.id}_to_${targetNode.id}`,
        source: sourceNode.id,
        target: targetNode.id,
        sourceX: sourceNode.x + nodeWidth,
        sourceY: sourceNode.y + nodeHeight / 2,
        targetX: targetNode.x,
        targetY: targetNode.y + nodeHeight / 2
      })
    }
    
    return edges
  }
  
  // 如果没有traceData，使用原有的graphSchema逻辑
  if (!graphSchema.value || !graphSchema.value.edges) return []
  
  return graphSchema.value.edges.map(edge => {
    const sourceNode = graphNodes.value.find(n => n.id === edge.source)
    const targetNode = graphNodes.value.find(n => n.id === edge.target)
    
    if (!sourceNode || !targetNode) return null
    
    return {
      ...edge,
      sourceX: sourceNode.x + nodeWidth,
      sourceY: sourceNode.y + nodeHeight / 2,
      targetX: targetNode.x,
      targetY: targetNode.y + nodeHeight / 2
    }
  }).filter(Boolean)
})

// 方法
const loadScenarios = async () => {
  try {
    const response = await listScenarios()
    scenarios.value = response.scenarios.map(name => ({
      scenario: name,
      node_count: response.details[name]?.nodes?.length || 0
    }))
    
    if (scenarios.value.length > 0 && !selectedScenario.value) {
      selectedScenario.value = scenarios.value[0].scenario
      await loadGraphSchema()
    }
  } catch (error) {
    ElMessage.error('加载场景列表失败: ' + error.message)
  }
}

const loadGraphSchema = async () => {
  if (!selectedScenario.value) return
  
  loading.value = true
  try {
    const response = await getGraphSchema(selectedScenario.value)
    graphSchema.value = response
    ElMessage.success('Graph Schema加载成功')
  } catch (error) {
    ElMessage.error('加载Graph Schema失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const getNodeColor = (node) => {
  const colors = {
    'data_node': '#3b82f6',
    'agent_node': '#10b981',
    'output_node': '#8b5cf6'
  }
  return colors[node.type] || '#6b7280'
}

const getNodeBorderColor = (node) => {
  // 如果节点被选中，使用高亮边框
  if (props.selectedNodeId === node.id) {
    return '#f59e0b' // 橙色高亮
  }
  
  if (node.status === 'running') return '#f59e0b'
  if (node.status === 'done') return '#10b981'
  if (node.status === 'error') return '#ef4444'
  return '#334155'
}

const getEdgeColor = (edge) => {
  return '#3b82f6'
}

const getNodeIcon = (type) => {
  const icons = {
    'data_node': 'el-icon-data-board',
    'agent_node': 'el-icon-cpu',
    'output_node': 'el-icon-document'
  }
  return icons[type] || 'el-icon-question'
}

const getNodeTypeLabel = (type) => {
  const labels = {
    'data_node': 'Data Node',
    'agent_node': 'Agent Node',
    'output_node': 'Output Node'
  }
  return labels[type] || type
}

const calculateEdgePath = (edge) => {
  const { sourceX, sourceY, targetX, targetY } = edge
  
  // 创建曲线路径
  const midX = (sourceX + targetX) / 2
  const controlPoint1 = { x: midX, y: sourceY }
  const controlPoint2 = { x: midX, y: targetY }
  
  return `M ${sourceX} ${sourceY} C ${controlPoint1.x} ${controlPoint1.y}, ${controlPoint2.x} ${controlPoint2.y}, ${targetX} ${targetY}`
}

// 视图控制方法
const zoomIn = () => {
  zoomLevel.value = Math.min(zoomLevel.value * 1.2, 3)
}

const zoomOut = () => {
  zoomLevel.value = Math.max(zoomLevel.value / 1.2, 0.5)
}

const fitToView = () => {
  if (graphNodes.value.length === 0) return
  
  // 简单实现：重置视图
  zoomLevel.value = 1
  panOffset.value = { x: 0, y: 0 }
}

const resetView = () => {
  zoomLevel.value = 1
  panOffset.value = { x: 0, y: 0 }
}

// 鼠标事件处理
const onMouseDown = (event) => {
  isPanning.value = true
  panStart.value = { x: event.clientX, y: event.clientY }
}

const onMouseMove = (event) => {
  if (!isPanning.value) return
  
  const dx = event.clientX - panStart.value.x
  const dy = event.clientY - panStart.value.y
  
  panOffset.value.x += dx
  panOffset.value.y += dy
  
  panStart.value = { x: event.clientX, y: event.clientY }
}

const onMouseUp = () => {
  isPanning.value = false
}

const onWheel = (event) => {
  event.preventDefault()
  const delta = event.deltaY > 0 ? 0.9 : 1.1
  zoomLevel.value = Math.max(0.5, Math.min(3, zoomLevel.value * delta))
}

const onNodeMouseDown = (node, event) => {
  event.stopPropagation()
  selectedNode.value = node
  
  // 触发节点选择事件
  emit('node-selected', node)
}

// 格式化持续时间
const formatDuration = (seconds) => {
  if (!seconds) return '--'
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}m ${remainingSeconds.toFixed(0)}s`
}

// 格式化时间
const formatTime = (timeString) => {
  if (!timeString) return '--'
  try {
    const date = new Date(timeString)
    return date.toLocaleString('zh-CN')
  } catch {
    return timeString
  }
}

// 格式化JSON数据
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

// 获取节点状态文本
const getNodeStatusText = (status) => {
  const statusMap = {
    'running': '运行中',
    'completed': '已完成',
    'failed': '已失败',
    'pending': '等待中',
    'idle': '空闲'
  }
  return statusMap[status] || status
}

// 暴露给父组件的方法
const highlightNode = (nodeId) => {
  // 这个方法会被父组件调用，用于高亮特定节点
  // 这里我们只需要确保selectedNodeId prop被正确传递即可
  console.log('高亮节点:', nodeId)
}

// 定义暴露给父组件的方法
defineExpose({
  zoomIn,
  zoomOut,
  fitToView,
  resetView,
  highlightNode
})

// 生命周期
onMounted(() => {
  // 如果没有提供traceData，加载场景列表
  if (!props.traceData && !props.traceId) {
    loadScenarios()
  }
  
  // 初始化画布尺寸
  if (canvasRef.value) {
    svgWidth.value = canvasRef.value.clientWidth
    svgHeight.value = canvasRef.value.clientHeight
  }
})

// 监听窗口大小变化
window.addEventListener('resize', () => {
  if (canvasRef.value) {
    svgWidth.value = canvasRef.value.clientWidth
    svgHeight.value = canvasRef.value.clientHeight
  }
})

// 监听traceId变化
watch(() => props.traceId, (newTraceId) => {
  if (newTraceId) {
    // 这里可以添加根据traceId加载traceData的逻辑
    console.log('需要加载traceId:', newTraceId)
  }
})

// 监听traceData变化
watch(() => props.traceData, (newTraceData) => {
  if (newTraceData) {
    // 重置视图以显示新的trace数据
    resetView()
  }
})
</script>

<style scoped>
.graph-canvas-container {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #0f172a;
  border-radius: 8px;
  overflow: hidden;
}

.canvas-controls {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 12px 20px;
  background-color: rgba(30, 41, 59, 0.9);
  border-bottom: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 10;
}

.controls-left,
.controls-right {
  display: flex;
  align-items: center;
}

.graph-canvas {
  width: 100%;
  height: 100%;
  overflow: hidden;
  cursor: grab;
}

.graph-canvas:active {
  cursor: grabbing;
}

.node-content {
  width: 100%;
  height: 100%;
  padding: 12px;
  color: white;
  font-size: 12px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  pointer-events: none;
}

.node-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.node-type-icon {
  margin-right: 8px;
  font-size: 16px;
}

.node-name {
  font-weight: bold;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-status {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

.status-indicator.idle {
  background-color: #6b7280;
}

.status-indicator.running {
  background-color: #f59e0b;
  animation: pulse 1.5s infinite;
}

.status-indicator.done {
  background-color: #10b981;
}

.status-indicator.error {
  background-color: #ef4444;
}

.status-text {
  font-size: 11px;
  color: #94a3b8;
}

.node-type {
  font-size: 11px;
  color: #cbd5e1;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  text-align: center;
}

.node-details-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 300px;
  background-color: rgba(30, 41, 59, 0.95);
  border: 1px solid #334155;
  border-radius: 8px;
  z-index: 20;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #334155;
}

.panel-header h4 {
  margin: 0;
  color: #f8fafc;
}

.panel-content {
  padding: 16px;
}

.detail-item {
  margin-bottom: 12px;
}

.detail-item label {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.detail-item span {
  display: block;
  font-size: 14px;
  color: #f1f5f9;
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.idle {
  background-color: #6b7280;
  color: white;
}

.status-badge.running {
  background-color: #f59e0b;
  color: white;
}

.status-badge.done {
  background-color: #10b981;
  color: white;
}

.status-badge.error {
  background-color: #ef4444;
  color: white;
}

.config-json {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 8px;
  font-size: 11px;
  color: #cbd5e1;
  max-height: 200px;
  overflow-y: auto;
  margin: 0;
}

/* 新增样式 */
.canvas-title h3 {
  margin: 0;
  font-size: 16px;
  color: #f8fafc;
}

.canvas-info {
  display: flex;
  gap: 16px;
  margin-left: 20px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.info-item i {
  font-size: 14px;
}

.detail-section {
  margin-bottom: 16px;
}

.detail-section h5 {
  font-size: 13px;
  font-weight: 600;
  color: #cbd5e1;
  margin: 0 0 8px 0;
  padding-bottom: 4px;
  border-bottom: 1px solid #334155;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.data-viewer, .error-viewer {
  background-color: #1e293b;
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

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}
