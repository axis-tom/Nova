<template>
  <div class="chart-renderer">
    <div class="chart-header">
      <div class="header-left">
        <span class="header-icon">📈</span>
        <span class="header-title">{{ result.content.title || '图表' }}</span>
        <span class="chart-type" v-if="chartType">
          {{ getChartTypeLabel() }}
        </span>
      </div>
      <div class="header-right">
        <div class="header-actions">
          <button class="action-btn small" @click="handleExportImage" title="导出图片">
            <span class="action-icon">🖼️</span>
          </button>
          <button class="action-btn small" @click="toggleChartType" title="切换图表类型">
            <span class="action-icon">🔄</span>
          </button>
        </div>
      </div>
    </div>
    
    <div class="chart-container">
      <div class="chart-placeholder">
        <div class="placeholder-icon">📊</div>
        <div class="placeholder-title">图表渲染器</div>
        <div class="placeholder-description">
          这是一个图表渲染器占位符。实际实现需要集成图表库（如Chart.js、ECharts等）。
        </div>
        <div class="chart-info">
          <div class="info-item">
            <span class="info-label">图表类型:</span>
            <span class="info-value">{{ chartType || '未指定' }}</span>
          </div>
          <div class="info-item" v-if="result.content.data">
            <span class="info-label">数据点:</span>
            <span class="info-value">{{ getDataPointCount() }}</span>
          </div>
          <div class="info-item" v-if="result.meta.sourceNode">
            <span class="info-label">来源:</span>
            <span class="info-value">{{ result.meta.sourceNode }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <div class="chart-footer">
      <div class="footer-left">
        <div class="chart-meta">
          <span class="meta-item">
            <span class="meta-icon">📊</span>
            <span class="meta-text">数据可视化</span>
          </span>
          <span class="meta-item">
            <span class="meta-icon">🔄</span>
            <span class="meta-text">实时更新</span>
          </span>
        </div>
      </div>
      <div class="footer-right">
        <button class="action-btn secondary" @click="handleRefresh">
          <span class="action-icon">🔄</span>
          <span>刷新</span>
        </button>
        <button class="action-btn primary" @click="handleViewData">
          <span class="action-icon">👁️</span>
          <span>查看数据</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

// 定义props
interface Props {
  result: Record<string, unknown>
  editable?: boolean
}


const props = defineProps<Props>()

// 定义事件
interface Emits {
  (e: 'edit', ...args: unknown[]): void
  (e: 'save', ...args: unknown[]): void
  (e: 'cancel', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

// 响应式数据
const chartType = ref(props.result.content.type || 'bar')

// 计算属性
const chartData = computed(() => {
  if (!props.result || !props.result.content) return {}
  return props.result.content.data || {}
})

const chartOptions = computed(() => {
  if (!props.result || !props.result.content) return {}
  return props.result.content.options || {}
})

// 方法
const getChartTypeLabel = () => {
  const typeLabels = {
    bar: '柱状图',
    line: '折线图',
    pie: '饼图',
    scatter: '散点图',
    area: '面积图',
    radar: '雷达图'
  }
  return typeLabels[chartType.value] || chartType.value
}

const getDataPointCount = () => {
  if (!chartData.value || !chartData.value.datasets) return 0
  
  let count = 0
  if (chartData.value.datasets && Array.isArray(chartData.value.datasets)) {
    chartData.value.datasets.forEach(dataset => {
      if (dataset.data && Array.isArray(dataset.data)) {
        count += dataset.data.length
      }
    })
  }
  return count
}

const toggleChartType = () => {
  const types = ['bar', 'line', 'pie', 'scatter', 'area', 'radar']
  const currentIndex = types.indexOf(chartType.value)
  const nextIndex = (currentIndex + 1) % types.length
  chartType.value = types[nextIndex]
}

const handleExportImage = () => {
  console.log('ChartRenderer: 导出图表图片')
  // 实际实现中，这里会使用图表库的导出功能
  alert('图表导出功能需要集成图表库实现')
}

const handleRefresh = () => {
  console.log('ChartRenderer: 刷新图表')
  emit('edit', {
    type: 'chart_refresh',
    chartType: chartType.value,
    chartData: chartData.value
  })
}

const handleViewData = () => {
  console.log('ChartRenderer: 查看数据', chartData.value)
  
  // 在新窗口或弹窗中显示数据
  const dataStr = JSON.stringify(chartData.value, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `chart-${props.result.id}-data.json`
  a.click()
  URL.revokeObjectURL(url)
}

// 暴露方法
defineExpose({
  getChartType: () => chartType.value,
  getDataInfo: () => ({
    type: chartType.value,
    dataPoints: getDataPointCount(),
    hasData: !!chartData.value && Object.keys(chartData.value).length > 0
  })
})
</script>

<style scoped>
.chart-renderer {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #1e293b;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.chart-header {
  padding: 12px 16px;
  background-color: #0f172a;
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
  font-size: 16px;
}

.header-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.chart-type {
  font-size: 12px;
  color: #94a3b8;
  background-color: rgba(148, 163, 184, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.header-right {
  display: flex;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 4px;
}

.chart-container {
  flex-grow: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.chart-placeholder {
  text-align: center;
  color: #94a3b8;
  max-width: 400px;
}

.placeholder-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.placeholder-title {
  font-size: 18px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.placeholder-description {
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 24px;
}

.chart-info {
  background-color: rgba(148, 163, 184, 0.1);
  border-radius: 6px;
  padding: 16px;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.info-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-label {
  font-size: 13px;
  color: #cbd5e1;
}

.info-value {
  font-size: 13px;
  color: #94a3b8;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.chart-footer {
  padding: 12px 16px;
  background-color: #0f172a;
  border-top: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-left {
  flex-grow: 1;
}

.chart-meta {
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

.footer-right {
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
</style>