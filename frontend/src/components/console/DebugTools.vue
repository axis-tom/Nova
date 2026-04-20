<template>
  <div class="debug-tools">
    <div class="debug-tools-header">
      <h3 class="debug-tools-title">系统调试工具</h3>
      <div class="debug-tools-actions">
        <el-button
          size="small"
          type="text"
          icon="el-icon-refresh"
          :loading="refreshing"
          @click="$emit('refresh')"
        >刷新</el-button>
      </div>
    </div>
    
    <div class="debug-tools-content">
      <!-- 系统状态监控 -->
      <div class="debug-section">
        <h4 class="section-title">系统状态</h4>
        <div class="system-status-grid">
          <div class="status-card" :class="systemStatus.overall">
            <div class="status-card-header">
              <span class="status-card-title">整体状态</span>
              <span class="status-indicator" :class="systemStatus.overall"></span>
            </div>
            <div class="status-card-content">
              <div class="status-metric">
                <span class="metric-label">运行时间</span>
                <span class="metric-value">{{ systemStatus.uptime }}</span>
              </div>
              <div class="status-metric">
                <span class="metric-label">版本</span>
                <span class="metric-value">{{ systemStatus.version }}</span>
              </div>
            </div>
          </div>
          
          <div class="status-card" :class="systemStatus.graphEngine">
            <div class="status-card-header">
              <span class="status-card-title">Graph引擎</span>
              <span class="status-indicator" :class="systemStatus.graphEngine"></span>
            </div>
            <div class="status-card-content">
              <div class="status-metric">
                <span class="metric-label">活跃Graph</span>
                <span class="metric-value">{{ systemStatus.activeGraphs }}</span>
              </div>
              <div class="status-metric">
                <span class="metric-label">队列长度</span>
                <span class="metric-value">{{ systemStatus.queueLength }}</span>
              </div>
            </div>
          </div>
          
          <div class="status-card" :class="systemStatus.database">
            <div class="status-card-header">
              <span class="status-card-title">数据库</span>
              <span class="status-indicator" :class="systemStatus.database"></span>
            </div>
            <div class="status-card-content">
              <div class="status-metric">
                <span class="metric-label">连接数</span>
                <span class="metric-value">{{ systemStatus.dbConnections }}</span>
              </div>
              <div class="status-metric">
                <span class="metric-label">响应时间</span>
                <span class="metric-value">{{ systemStatus.dbResponseTime }}</span>
              </div>
            </div>
          </div>
          
          <div class="status-card" :class="systemStatus.api">
            <div class="status-card-header">
              <span class="status-card-title">API服务</span>
              <span class="status-indicator" :class="systemStatus.api"></span>
            </div>
            <div class="status-card-content">
              <div class="status-metric">
                <span class="metric-label">请求/分钟</span>
                <span class="metric-value">{{ systemStatus.apiRequestsPerMin }}</span>
              </div>
              <div class="status-metric">
                <span class="metric-label">错误率</span>
                <span class="metric-value">{{ systemStatus.apiErrorRate }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 性能监控 -->
      <div class="debug-section">
        <h4 class="section-title">性能监控</h4>
        <div class="performance-metrics">
          <div class="performance-chart">
            <div class="chart-header">
              <span class="chart-title">CPU使用率</span>
              <span class="chart-value">{{ performance.cpuUsage }}%</span>
            </div>
            <el-progress
              :percentage="performance.cpuUsage"
              :stroke-width="8"
              :color="getProgressColor(performance.cpuUsage)"
              :show-text="false"
            />
          </div>
          
          <div class="performance-chart">
            <div class="chart-header">
              <span class="chart-title">内存使用</span>
              <span class="chart-value">{{ performance.memoryUsage }}%</span>
            </div>
            <el-progress
              :percentage="performance.memoryUsage"
              :stroke-width="8"
              :color="getProgressColor(performance.memoryUsage)"
              :show-text="false"
            />
          </div>
          
          <div class="performance-chart">
            <div class="chart-header">
              <span class="chart-title">磁盘使用</span>
              <span class="chart-value">{{ performance.diskUsage }}%</span>
            </div>
            <el-progress
              :percentage="performance.diskUsage"
              :stroke-width="8"
              :color="getProgressColor(performance.diskUsage)"
              :show-text="false"
            />
          </div>
        </div>
      </div>
      
      <!-- 调试工具 -->
      <div class="debug-section">
        <h4 class="section-title">调试工具</h4>
        <div class="tool-buttons">
          <el-button
            size="small"
            type="primary"
            icon="el-icon-cpu"
            @click="$emit('performance-analysis')"
          >性能分析</el-button>
          
          <el-button
            size="small"
            type="warning"
            icon="el-icon-memory"
            @click="$emit('memory-monitor')"
          >内存监控</el-button>
          
          <el-button
            size="small"
            type="info"
            icon="el-icon-connection"
            @click="$emit('connection-test')"
          >连接测试</el-button>
          
          <el-button
            size="small"
            type="success"
            icon="el-icon-document-checked"
            @click="$emit('health-check')"
          >健康检查</el-button>
          
          <el-button
            size="small"
            type="danger"
            icon="el-icon-switch-button"
            @click="$emit('restart-service')"
          >重启服务</el-button>
        </div>
        
        <div class="quick-actions">
          <el-button
            size="small"
            type="text"
            icon="el-icon-view"
            @click="$emit('view-logs')"
          >查看日志</el-button>
          
          <el-button
            size="small"
            type="text"
            icon="el-icon-download"
            @click="$emit('export-metrics')"
          >导出指标</el-button>
          
          <el-button
            size="small"
            type="text"
            icon="el-icon-setting"
            @click="$emit('open-settings')"
          >调试设置</el-button>
        </div>
      </div>
      
      <!-- 实时日志 -->
      <div class="debug-section">
        <h4 class="section-title">
          实时日志
          <el-button
            size="mini"
            type="text"
            :icon="showLogs ? 'el-icon-arrow-up' : 'el-icon-arrow-down'"
            @click="showLogs = !showLogs"
          />
        </h4>
        
        <div v-if="showLogs" class="realtime-logs">
          <div class="log-controls">
            <el-select
              v-model="logLevel"
              placeholder="日志级别"
              size="small"
              style="width: 100px;"
            >
              <el-option label="全部" value="all" />
              <el-option label="调试" value="debug" />
              <el-option label="信息" value="info" />
              <el-option label="警告" value="warn" />
              <el-option label="错误" value="error" />
            </el-select>
            
            <el-button
              size="small"
              type="text"
              icon="el-icon-video-play"
              :disabled="logStreaming"
              @click="$emit('start-log-stream')"
            >开始</el-button>
            
            <el-button
              size="small"
              type="text"
              icon="el-icon-switch-button"
              :disabled="!logStreaming"
              @click="$emit('stop-log-stream')"
            >停止</el-button>
            
            <el-button
              size="small"
              type="text"
              icon="el-icon-delete"
              @click="$emit('clear-logs')"
            >清空</el-button>
          </div>
          
          <div class="log-content">
            <div v-if="logs.length === 0" class="log-empty">
              暂无日志数据
            </div>
            <div v-else class="log-entries">
              <div
                v-for="(log, index) in filteredLogs"
                :key="index"
                class="log-entry"
                :class="log.level"
              >
                <span class="log-time">{{ log.time }}</span>
                <span class="log-level" :class="log.level">{{ log.level.toUpperCase() }}</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  systemStatus: {
    type: Object,
    default: () => ({
      overall: 'healthy',
      graphEngine: 'healthy',
      database: 'healthy',
      api: 'healthy',
      uptime: '2天3小时',
      version: 'v1.0.0',
      activeGraphs: 5,
      queueLength: 3,
      dbConnections: 12,
      dbResponseTime: '45ms',
      apiRequestsPerMin: 120,
      apiErrorRate: '0.5%'
    })
  },
  performance: {
    type: Object,
    default: () => ({
      cpuUsage: 45,
      memoryUsage: 68,
      diskUsage: 32
    })
  },
  logs: {
    type: Array,
    default: () => []
  },
  logStreaming: {
    type: Boolean,
    default: false
  },
  refreshing: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'refresh',
  'performance-analysis',
  'memory-monitor',
  'connection-test',
  'health-check',
  'restart-service',
  'view-logs',
  'export-metrics',
  'open-settings',
  'start-log-stream',
  'stop-log-stream',
  'clear-logs'
])

const showLogs = ref(false)
const logLevel = ref('all')

const filteredLogs = computed(() => {
  if (logLevel.value === 'all') {
    return props.logs
  }
  return props.logs.filter(log => log.level === logLevel.value)
})

const getProgressColor = (percentage) => {
  if (percentage < 50) return '#10b981'
  if (percentage < 80) return '#f59e0b'
  return '#ef4444'
}
</script>

<style scoped>
.debug-tools {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.debug-tools-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: var(--console-spacing-md);
  border-bottom: 1px solid var(--console-border-base);
  margin-bottom: var(--console-spacing-md);
}

.debug-tools-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--console-text-primary);
  margin: 0;
}

.debug-tools-content {
  flex: 1;
  overflow-y: auto;
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

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--console-text-primary);
  margin: 0 0 var(--console-spacing-md) 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.system-status-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--console-spacing-md);
}

.status-card {
  background-color: var(--console-bg-surface);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-sm);
  padding: var(--console-spacing-md);
  transition: all var(--console-transition-fast);
}

.status-card.healthy {
  border-left: 3px solid var(--console-color-success);
}

.status-card.warning {
  border-left: 3px solid var(--console-color-warning);
}

.status-card.error {
  border-left: 3px solid var(--console-color-error);
}

.status-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--console-spacing-sm);
}

.status-card-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--console-text-secondary);
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-indicator.healthy {
  background-color: var(--console-color-success);
}

.status-indicator.warning {
  background-color: var(--console-color-warning);
}

.status-indicator.error {
  background-color: var(--console-color-error);
}

.status-card-content {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-xs);
}

.status-metric {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-label {
  font-size: 11px;
  color: var(--console-text-tertiary);
}

.metric-value {
  font-size: 11px;
  font-weight: 500;
  color: var(--console-text-secondary);
}

.performance-metrics {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-md);
}

.performance-chart {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-xs);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-title {
  font-size: 12px;
  color: var(--console-text-secondary);
}

.chart-value {
  font-size: 12px;
  font-weight: 500;
  color: var(--console-text-primary);
}

.tool-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--console-spacing-sm);
  margin-bottom: var(--console-spacing-md);
}

.quick-actions {
  display: flex;
  gap: var(--console-spacing-md);
  padding-top: var(--console-spacing-md);
  border-top: 1px solid var(--console-border-base);
}

.realtime-logs {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-md);
}

.log-controls {
  display: flex;
  align-items: center;
  gap: var(--console-spacing-sm);
}

.log-content {
  background-color: var(--console-bg-surface);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-sm);
  max-height: 200px;
  overflow-y: auto;
}

.log-empty {
  padding: var(--console-spacing-md);
  text-align: center;
  color: var(--console-text-tertiary);
  font-size: 12px;
}

.log-entries {
  display: flex;
  flex-direction: column;
}

.log-entry {
  padding: var(--console-spacing-sm) var(--console-spacing-md);
  border-bottom: 1px solid var(--console-border-base);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: var(--console-spacing-md);
}

.log-entry:last-child {
  border-bottom: none;
}

.log-entry.debug {
  color: var(--console-text-tertiary);
}

.log-entry.info {
  color: var(--console-text-secondary);
}

.log-entry.warn {
  color: var(--console-color-warning);
}

.log-entry.error {
  color: var(--console-color-error);
  background-color: rgba(239, 68, 68, 0.1);
}

.log-time {
  min-width: 60px;
  color: var(--console-text-muted);
}

.log-level {
  min-width: 40px;
  font-weight: 500;
  text-align: center;
}

.log-level.debug {
  color: var(--console-text-tertiary);
}

.log-level.info {
  color: var(--console-color-info);
}

.log-level.warn {
  color: var(--console-color-warning);
}

.log-level.error {
  color: var(--console-color-error);
}

.log-message {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>