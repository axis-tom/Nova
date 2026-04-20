<template>
  <div class="console-container">
    <!-- 引入Console主题 -->
    <link rel="stylesheet" href="@/assets/css/console-theme.css">
    
    <!-- Console布局骨架 -->
    <div class="console-layout">
      <!-- 左侧导航栏 -->
      <div class="console-left-bar">
        <div class="console-logo">
          <span class="logo-text">Nova Console</span>
        </div>
        <div class="console-nav">
          <div class="nav-item" :class="{ active: activeTab === 'graph' }" @click="activeTab = 'graph'">
            <i class="el-icon-monitor"></i>
            <span>Graph执行</span>
          </div>
          <div class="nav-item" :class="{ active: activeTab === 'run' }" @click="activeTab = 'run'">
            <i class="el-icon-video-play"></i>
            <span>Run控制台</span>
          </div>
          <div class="nav-item" :class="{ active: activeTab === 'trace' }" @click="activeTab = 'trace'">
            <i class="el-icon-data-analysis"></i>
            <span>Trace观察</span>
          </div>
          <div class="nav-item" :class="{ active: activeTab === 'traceGraph' }" @click="activeTab = 'traceGraph'">
            <i class="el-icon-connection"></i>
            <span>Trace+Graph整合</span>
          </div>
          <div class="nav-item" :class="{ active: activeTab === 'debug' }" @click="activeTab = 'debug'">
            <i class="el-icon-bug"></i>
            <span>系统调试</span>
          </div>
          <div class="nav-item" :class="{ active: activeTab === 'settings' }" @click="activeTab = 'settings'">
            <i class="el-icon-setting"></i>
            <span>配置</span>
          </div>
        </div>
        <div class="console-status">
          <div class="status-item">
            <span class="status-label">系统状态</span>
            <span class="status-indicator active"></span>
          </div>
          <div class="status-item">
            <span class="status-label">Graph引擎</span>
            <span class="status-indicator active"></span>
          </div>
          <div class="status-item">
            <span class="status-label">API状态</span>
            <span class="status-indicator active"></span>
          </div>
        </div>
      </div>

      <!-- 主内容区域 -->
      <div class="console-main">
        <!-- Graph Canvas视图 -->
        <div v-if="activeTab === 'graph'" class="graph-view">
          <div class="view-header">
            <h3>Graph Canvas - 系统核心</h3>
            <p class="view-subtitle">可视化展示AI工作流，让用户"看到AI在干嘛"</p>
          </div>
          <GraphCanvas class="graph-canvas-component" />
        </div>

        <!-- Run控制台视图 -->
        <div v-else-if="activeTab === 'run'" class="run-view">
          <div class="view-header">
            <h3>Run控制台 - 统一AI执行入口</h3>
            <p class="view-subtitle">所有AI行为必须通过此入口执行</p>
          </div>
          <RunConsole class="run-console-component" />
        </div>

        <!-- Trace观察视图 -->
        <div v-else-if="activeTab === 'trace'" class="trace-view">
          <div class="view-header">
            <h3>Trace观察</h3>
            <p class="view-subtitle">查看Graph执行的历史记录和Trace详情</p>
          </div>
          <TraceList class="trace-list-component" />
        </div>

        <!-- Trace+Graph整合视图 -->
        <div v-else-if="activeTab === 'traceGraph'" class="trace-graph-view">
          <div class="view-header">
            <h3>Trace+Graph整合视图</h3>
            <p class="view-subtitle">左Trace详情，右Graph可视化，双向同步</p>
          </div>
          <TraceGraphIntegration 
            class="trace-graph-integration-component"
            :trace-id="selectedTraceId"
          />
        </div>

        <!-- 调试工具视图 -->
        <div v-else-if="activeTab === 'debug'" class="debug-view">
          <div class="view-header">
            <h3>系统调试工具</h3>
            <p class="view-subtitle">系统诊断和性能监控工具</p>
          </div>
          <DebugTools class="debug-tools-component" />
        </div>

        <!-- 配置视图 -->
        <div v-else-if="activeTab === 'settings'" class="settings-view">
          <div class="view-header">
            <h3>系统配置</h3>
            <p class="view-subtitle">系统参数和功能配置</p>
          </div>
          <div class="settings-content">
            <el-alert
              title="配置功能开发中"
              type="info"
              description="系统配置功能正在开发中，敬请期待"
              show-icon
              :closable="false"
            />
          </div>
        </div>

        <!-- 默认视图 -->
        <div v-else class="default-view">
          <div class="view-header">
            <h3>Nova Console</h3>
            <p class="view-subtitle">AI工作流管理和执行控制台</p>
          </div>
          <div class="welcome-content">
            <div class="welcome-card">
              <i class="el-icon-monitor welcome-icon"></i>
              <h4>Graph Canvas</h4>
              <p>可视化展示AI工作流，实时查看节点状态</p>
              <el-button type="primary" @click="activeTab = 'graph'">进入Graph Canvas</el-button>
            </div>
            <div class="welcome-card">
              <i class="el-icon-video-play welcome-icon"></i>
              <h4>Run控制台</h4>
              <p>统一AI执行入口，管理所有AI行为</p>
              <el-button type="success" @click="activeTab = 'run'">进入Run控制台</el-button>
            </div>
            <div class="welcome-card">
              <i class="el-icon-data-analysis welcome-icon"></i>
              <h4>Trace观察</h4>
              <p>查看执行历史，分析AI行为轨迹</p>
              <el-button type="info" @click="activeTab = 'trace'">进入Trace观察</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧状态面板 -->
      <div class="console-right-panel">
        <div class="panel-tabs">
          <div class="panel-tab" :class="{ active: rightPanelTab === 'status' }" @click="rightPanelTab = 'status'">系统状态</div>
          <div class="panel-tab" :class="{ active: rightPanelTab === 'quickActions' }" @click="rightPanelTab = 'quickActions'">快捷操作</div>
          <div class="panel-tab" :class="{ active: rightPanelTab === 'notifications' }" @click="rightPanelTab = 'notifications'">通知</div>
        </div>
        <div class="panel-content">
          <!-- 系统状态面板 -->
          <div v-if="rightPanelTab === 'status'" class="status-panel">
            <div class="status-section">
              <h5>Graph引擎状态</h5>
              <div class="status-item">
                <span class="status-label">运行状态</span>
                <span class="status-value success">正常</span>
              </div>
              <div class="status-item">
                <span class="status-label">场景数量</span>
                <span class="status-value">{{ scenarioCount }}</span>
              </div>
              <div class="status-item">
                <span class="status-label">节点总数</span>
                <span class="status-value">{{ totalNodes }}</span>
              </div>
            </div>
            <div class="status-section">
              <h5>执行统计</h5>
              <div class="status-item">
                <span class="status-label">今日执行</span>
                <span class="status-value">{{ todayExecutions }}</span>
              </div>
              <div class="status-item">
                <span class="status-label">成功率</span>
                <span class="status-value success">98.5%</span>
              </div>
              <div class="status-item">
                <span class="status-label">平均耗时</span>
                <span class="status-value">2.3s</span>
              </div>
            </div>
          </div>

          <!-- 快捷操作面板 -->
          <div v-else-if="rightPanelTab === 'quickActions'" class="quick-actions-panel">
            <el-button type="primary" size="small" icon="el-icon-video-play" @click="quickRunGraph">快速执行</el-button>
            <el-button size="small" icon="el-icon-refresh" @click="refreshAll">刷新所有</el-button>
            <el-button size="small" icon="el-icon-download" @click="exportData">导出数据</el-button>
            <el-button size="small" icon="el-icon-upload" @click="importData">导入配置</el-button>
            <el-button size="small" icon="el-icon-setting" @click="activeTab = 'settings'">系统设置</el-button>
            <el-button size="small" icon="el-icon-help" @click="showHelp">帮助文档</el-button>
          </div>

          <!-- 通知面板 -->
          <div v-else-if="rightPanelTab === 'notifications'" class="notifications-panel">
            <div class="notification-item" v-for="notification in notifications" :key="notification.id">
              <div class="notification-header">
                <span class="notification-title">{{ notification.title }}</span>
                <span class="notification-time">{{ notification.time }}</span>
              </div>
              <div class="notification-content">
                {{ notification.content }}
              </div>
            </div>
            <div v-if="notifications.length === 0" class="no-notifications">
              <i class="el-icon-bell"></i>
              <p>暂无通知</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Trace Viewer抽屉 -->
  <el-drawer
    v-model="traceViewerVisible"
    title="Trace详情"
    direction="rtl"
    size="50%"
    :before-close="handleTraceViewerClose"
  >
    <TraceViewer
      v-if="traceViewerVisible"
      :trace-id="selectedTraceId"
      :visible="traceViewerVisible"
      @close="traceViewerVisible = false"
      @update:traceId="selectedTraceId = $event"
    />
  </el-drawer>

  <!-- Debug Panel抽屉 -->
  <el-drawer
    v-model="debugPanelVisible"
    title="调试面板"
    direction="rtl"
    size="40%"
    :before-close="handleDebugPanelClose"
  >
    <DebugPanel
      v-if="debugPanelVisible"
      :trace-id="selectedTraceId"
      @close="debugPanelVisible = false"
      @nodeFocus="handleNodeFocus"
    />
  </el-drawer>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import GraphCanvas from '@/components/console/GraphCanvas.vue'
import RunConsole from '@/components/console/RunConsole.vue'
import TraceList from '@/components/console/TraceList.vue'
import DebugTools from '@/components/console/DebugTools.vue'
import TraceViewer from '@/components/console/TraceViewer.vue'
import DebugPanel from '@/components/console/DebugPanel.vue'
import TraceGraphIntegration from '@/components/console/TraceGraphIntegration.vue'
import { listScenarios } from '@/api/graph.js'
import { ElMessage, ElMessageBox } from 'element-plus'

// 标签页状态
const activeTab = ref('graph')
const rightPanelTab = ref('status')

// Trace Viewer和Debug Panel状态
const traceViewerVisible = ref(false)
const debugPanelVisible = ref(false)
const selectedTraceId = ref(null)

// 系统状态数据
const scenarioCount = ref(0)
const totalNodes = ref(0)
const todayExecutions = ref(0)

// 通知数据
const notifications = ref([
  {
    id: 1,
    title: '系统启动完成',
    content: 'Nova Console已成功启动，所有服务正常运行',
    time: '10:30'
  },
  {
    id: 2,
    title: 'Graph引擎就绪',
    content: 'Graph引擎已初始化完成，可以开始执行任务',
    time: '10:31'
  },
  {
    id: 3,
    title: 'API连接正常',
    content: '后端API连接正常，所有接口可用',
    time: '10:32'
  }
])

// 方法
const quickRunGraph = () => {
  ElMessage.info('快速执行功能开发中')
  // 这里可以跳转到Run控制台并自动填充一些参数
  activeTab.value = 'run'
}

const refreshAll = async () => {
  try {
    // 刷新场景数据
    const response = await listScenarios()
    scenarioCount.value = Object.keys(response.details || {}).length
    
    // 计算总节点数
    let total = 0
    Object.values(response.details || {}).forEach(scenario => {
      total += scenario.nodes?.length || 0
    })
    totalNodes.value = total
    
    ElMessage.success('系统状态已刷新')
  } catch (error) {
    ElMessage.error('刷新失败: ' + error.message)
  }
}

const exportData = () => {
  ElMessage.info('导出功能开发中')
}

const importData = () => {
  ElMessage.info('导入功能开发中')
}

const showHelp = () => {
  ElMessage.info('帮助文档功能开发中')
}

// Trace Viewer和Debug Panel相关方法
const handleTraceViewerClose = (done) => {
  ElMessageBox.confirm('确定要关闭Trace详情吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
    .then(() => {
      traceViewerVisible.value = false
      selectedTraceId.value = null
      done()
    })
    .catch(() => {})
}

const handleDebugPanelClose = (done) => {
  ElMessageBox.confirm('确定要关闭调试面板吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
    .then(() => {
      debugPanelVisible.value = false
      done()
    })
    .catch(() => {})
}

const handleNodeFocus = (nodeIds) => {
  // 这里可以处理节点聚焦逻辑，例如在Graph Canvas中高亮显示特定节点
  ElMessage.info(`已聚焦节点: ${nodeIds.join(', ')}`)
}

// 打开Trace Viewer
const openTraceViewer = (traceId) => {
  selectedTraceId.value = traceId
  traceViewerVisible.value = true
}

// 打开Debug Panel
const openDebugPanel = (traceId) => {
  selectedTraceId.value = traceId
  debugPanelVisible.value = true
}

// 生命周期
onMounted(() => {
  // 初始化时刷新系统状态
  refreshAll()
  
  // 模拟今日执行次数
  todayExecutions.value = Math.floor(Math.random() * 50) + 10
  
  // 暴露方法给子组件
  window.openTraceViewer = openTraceViewer
  window.openDebugPanel = openDebugPanel
})
</script>

<style scoped>
.console-container {
  height: 100vh;
  background-color: #0f172a;
  color: #e2e8f0;
}

.console-layout {
  display: flex;
  height: 100%;
}

/* 左侧导航栏 */
.console-left-bar {
  width: 240px;
  background-color: #1e293b;
  border-right: 1px solid #334155;
  display: flex;
  flex-direction: column;
}

.console-logo {
  padding: 20px;
  border-bottom: 1px solid #334155;
}

.logo-text {
  font-size: 18px;
  font-weight: bold;
  color: #60a5fa;
}

.console-nav {
  flex: 1;
  padding: 20px 0;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.nav-item:hover {
  background-color: #334155;
}

.nav-item.active {
  background-color: #3b82f6;
  color: white;
}

.nav-item i {
  margin-right: 10px;
  font-size: 16px;
}

.console-status {
  padding: 20px;
  border-top: 1px solid #334155;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #10b981;
}

.status-indicator.active {
  background-color: #10b981;
}

/* 主内容区域 */
.console-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 视图公共样式 */
.view-header {
  padding: 20px 24px;
  border-bottom: 1px solid #334155;
}

.view-header h3 {
  margin: 0;
  color: #f8fafc;
  font-size: 20px;
}

.view-subtitle {
  margin: 8px 0 0;
  color: #94a3b8;
  font-size: 14px;
}

/* Graph Canvas视图 */
.graph-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.graph-canvas-component {
  flex: 1;
  padding: 20px;
}

/* Run控制台视图 */
.run-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.run-console-component {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

/* Trace观察视图 */
.trace-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.trace-list-component {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

/* Trace+Graph整合视图 */
.trace-graph-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.trace-graph-integration-component {
  flex: 1;
  padding: 20px;
  overflow: hidden;
}

/* 调试工具视图 */
.debug-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.debug-tools-component {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

/* 配置视图 */
.settings-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.settings-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

/* 默认欢迎视图 */
.default-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.welcome-content {
  flex: 1;
  padding: 40px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 30px;
}

.welcome-card {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 30px;
  width: 280px;
  text-align: center;
  transition: transform 0.2s, box-shadow 0.2s;
}

.welcome-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

.welcome-icon {
  font-size: 48px;
  color: #3b82f6;
  margin-bottom: 20px;
}

.welcome-card h4 {
  margin: 0 0 12px;
  color: #f8fafc;
  font-size: 18px;
}

.welcome-card p {
  margin: 0 0 20px;
  color: #94a3b8;
  font-size: 14px;
  line-height: 1.5;
}

/* 右侧面板 */
.console-right-panel {
  width: 320px;
  background-color: #1e293b;
  border-left: 1px solid #334155;
  display: flex;
  flex-direction: column;
}

.panel-tabs {
  display: flex;
  border-bottom: 1px solid #334155;
}

.panel-tab {
  flex: 1;
  padding: 12px;
  text-align: center;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s;
}

.panel-tab:hover {
  color: #60a5fa;
}

.panel-tab.active {
  border-bottom-color: #3b82f6;
  color: #3b82f6;
}

.panel-content {
  flex: 1;
  padding: 20px;
  overflow: auto;
}

/* 系统状态面板 */
.status-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.status-section {
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 16px;
}

.status-section h5 {
  margin: 0 0 12px;
  color: #f8fafc;
  font-size: 14px;
  font-weight: 600;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.status-item:last-child {
  margin-bottom: 0;
}

.status-label {
  font-size: 13px;
  color: #94a3b8;
}

.status-value {
  font-size: 13px;
  color: #f1f5f9;
  font-weight: 500;
}

.status-value.success {
  color: #10b981;
}

/* 快捷操作面板 */
.quick-actions-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.quick-actions-panel .el-button {
  justify-content: flex-start;
}

/* 通知面板 */
.notifications-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.notification-item {
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 12px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.notification-item:hover {
  background-color: #1e293b;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.notification-title {
  font-size: 13px;
  color: #f1f5f9;
  font-weight: 500;
}

.notification-time {
  font-size: 11px;
  color: #64748b;
}

.notification-content {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
}

.no-notifications {
  text-align: center;
  padding: 40px 20px;
  color: #64748b;
}

.no-notifications i {
  font-size: 32px;
  margin-bottom: 12px;
  display: block;
}

.no-notifications p {
  margin: 0;
  font-size: 14px;
}

/* 动画 */
@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
  100% {
    opacity: 1;
  }
}
</style>