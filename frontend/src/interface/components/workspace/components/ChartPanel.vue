<template>
  <div class="chart-panel">
    <div class="chart-header">
      <div class="header-left">
        <span class="header-icon">📊</span>
        <div class="header-info">
          <div class="header-title">数据分析图表</div>
          <div class="header-subtitle">AI分析结果可视化</div>
        </div>
      </div>
      <div class="header-right">
        <div class="chart-controls">
          <select v-model="chartType" class="chart-select">
            <option value="bar">柱状图</option>
            <option value="line">折线图</option>
            <option value="pie">饼图</option>
            <option value="radar">雷达图</option>
          </select>
          <button class="control-btn" @click="toggleTheme">
            <span class="btn-icon">{{ isDarkTheme ? '☀️' : '🌙' }}</span>
          </button>
        </div>
      </div>
    </div>

    <div class="chart-container">
      <!-- 图表占位区域 -->
      <div class="chart-placeholder" v-if="!hasData">
        <div class="placeholder-icon">📈</div>
        <div class="placeholder-title">暂无数据</div>
        <div class="placeholder-description">
          等待AI分析结果生成图表数据
        </div>
      </div>

      <!-- 图表展示区域 -->
      <div class="chart-area" v-else>
        <!-- 这里可以集成实际的图表库，如ECharts、Chart.js等 -->
        <div class="chart-visualization">
          <!-- 模拟图表 -->
          <div class="mock-chart" :class="chartType">
            <div class="chart-title">{{ getChartTitle() }}</div>
            <div class="chart-content">
              <div class="chart-bars" v-if="chartType === 'bar'">
                <div 
                  v-for="(item, index) in chartData" 
                  :key="index"
                  class="chart-bar"
                  :style="{ height: `${item.value * 2}px`, backgroundColor: getBarColor(index) }"
                  :title="`${item.label}: ${item.value}`"
                >
                  <span class="bar-value">{{ item.value }}</span>
                </div>
              </div>
              
              <div class="chart-lines" v-else-if="chartType === 'line'">
                <svg class="line-svg" width="100%" height="200">
                  <polyline 
                    :points="getLinePoints()" 
                    fill="none" 
                    stroke="#3b82f6" 
                    stroke-width="2"
                  />
                  <circle 
                    v-for="(point, index) in getLinePointsArray()" 
                    :key="index"
                    :cx="point.x" 
                    :cy="point.y" 
                    r="4" 
                    fill="#3b82f6"
                  />
                </svg>
              </div>
              
              <div class="chart-pie" v-else-if="chartType === 'pie'">
                <div class="pie-container">
                  <div class="pie-chart">
                    <div 
                      v-for="(item, index) in chartData" 
                      :key="index"
                      class="pie-segment"
                      :style="{
                        transform: `rotate(${getPieRotation(index)}deg)`,
                        backgroundColor: getPieColor(index)
                      }"
                    ></div>
                  </div>
                </div>
              </div>
              
              <div class="chart-radar" v-else-if="chartType === 'radar'">
                <svg class="radar-svg" width="100%" height="200">
                  <polygon 
                    :points="getRadarPoints()" 
                    fill="rgba(59, 130, 246, 0.2)" 
                    stroke="#3b82f6" 
                    stroke-width="2"
                  />
                </svg>
              </div>
            </div>
            <div class="chart-labels">
              <div 
                v-for="(item, index) in chartData" 
                :key="index"
                class="chart-label"
              >
                <span class="label-color" :style="{ backgroundColor: getLabelColor(index) }"></span>
                <span class="label-text">{{ item.label }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 数据表格 -->
        <div class="data-table">
          <div class="table-header">
            <span class="table-icon">📋</span>
            <span class="table-title">数据明细</span>
          </div>
          <div class="table-content">
            <table>
              <thead>
                <tr>
                  <th>指标</th>
                  <th>数值</th>
                  <th>变化</th>
                  <th>趋势</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in chartData" :key="index">
                  <td>{{ item.label }}</td>
                  <td>{{ item.value }}</td>
                  <td :class="getChangeClass(item.change)">
                    <span class="change-icon">{{ getChangeIcon(item.change) }}</span>
                    <span class="change-value">{{ item.change }}%</span>
                  </td>
                  <td>
                    <span class="trend-indicator" :class="getTrendClass(item.trend)">
                      {{ getTrendText(item.trend) }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- 图表分析 -->
    <div class="chart-analysis" v-if="hasData">
      <div class="analysis-header">
        <span class="analysis-icon">🧠</span>
        <span class="analysis-title">AI分析洞察</span>
      </div>
      <div class="analysis-content">
        <div class="insight-item" v-for="(insight, index) in insights" :key="index">
          <span class="insight-icon">💡</span>
          <span class="insight-text">{{ insight }}</span>
        </div>
      </div>
    </div>

    <!-- 图表操作 -->
    <div class="chart-actions">
      <button class="action-btn secondary" @click="handleExport">
        <span class="btn-icon">📤</span>
        <span class="btn-text">导出数据</span>
      </button>
      <button class="action-btn primary" @click="handleRefresh">
        <span class="btn-icon">🔄</span>
        <span class="btn-text">刷新分析</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  metrics?: Record<string, unknown>
}

const props = defineProps<Props>()

interface Emits {

  (e: 'export', ...args: unknown[]): void
  (e: 'refresh', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

// 响应式数据
const chartType = ref<string>('bar')
const isDarkTheme = ref<boolean>(true)

// 计算属性
const hasData = computed(() => {
  return props.metrics && Object.keys(props.metrics).length > 0
})

const chartData = computed(() => {
  if (!hasData.value) {
    // 模拟数据
    return [
      { label: 'CTR', value: 3.2, change: 12.5, trend: 'up' },
      { label: 'CVR', value: 2.1, change: -3.2, trend: 'down' },
      { label: '排名', value: 8, change: 25.0, trend: 'up' },
      { label: '曝光', value: 12500, change: 8.7, trend: 'up' },
      { label: '点击', value: 400, change: 15.3, trend: 'up' },
      { label: '转化', value: 32, change: -5.6, trend: 'down' }
    ]
  }
  
  // 如果有实际数据，转换格式
  return Object.entries(props.metrics).map(([key, value]) => ({
    label: key,
    value: typeof value === 'number' ? value : 0,
    change: Math.random() * 30 - 15, // 模拟变化
    trend: Math.random() > 0.5 ? 'up' : 'down'
  }))
})

const insights = computed(() => {
  return [
    'CTR表现优秀，高于行业平均水平',
    'CVR有待提升，建议优化落地页',
    '排名稳步上升，SEO策略有效',
    '曝光量增长健康，流量获取稳定'
  ]
})

// 方法
const toggleTheme = () => {
  isDarkTheme.value = !isDarkTheme.value
}

const getChartTitle = () => {
  const titles = {
    bar: '柱状图 - 指标对比',
    line: '折线图 - 趋势分析',
    pie: '饼图 - 占比分布',
    radar: '雷达图 - 多维评估'
  }
  return titles[chartType.value] || '数据分析图表'
}

const getBarColor = (index) => {
  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
  return colors[index % colors.length]
}

const getLabelColor = (index) => {
  return getBarColor(index)
}

const getPieColor = (index) => {
  return getBarColor(index)
}

const getLinePoints = () => {
  const points = []
  const spacing = 80
  chartData.value.forEach((item, index) => {
    const x = 40 + index * spacing
    const y = 180 - item.value * 5
    points.push(`${x},${y}`)
  })
  return points.join(' ')
}

const getLinePointsArray = () => {
  const points = []
  const spacing = 80
  chartData.value.forEach((item, index) => {
    const x = 40 + index * spacing
    const y = 180 - item.value * 5
    points.push({ x, y })
  })
  return points
}

const getPieRotation = (index) => {
  const total = chartData.value.length
  return (360 / total) * index
}

const getRadarPoints = () => {
  const points = []
  const centerX = 150
  const centerY = 100
  const radius = 80
  const sides = chartData.value.length
  
  chartData.value.forEach((item, index) => {
    const angle = (2 * Math.PI * index) / sides - Math.PI / 2
    const value = Math.min(item.value / 10, 1) // 归一化
    const x = centerX + radius * value * Math.cos(angle)
    const y = centerY + radius * value * Math.sin(angle)
    points.push(`${x},${y}`)
  })
  
  return points.join(' ')
}

const getChangeClass = (change) => {
  return change >= 0 ? 'change-positive' : 'change-negative'
}

const getChangeIcon = (change) => {
  return change >= 0 ? '📈' : '📉'
}

const getTrendClass = (trend) => {
  return `trend-${trend}`
}

const getTrendText = (trend) => {
  return trend === 'up' ? '上升' : '下降'
}

const handleExport = () => {
  emit('export', chartData.value)
}

const handleRefresh = () => {
  emit('refresh')
}
</script>

<style scoped>
.chart-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #0f172a;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.chart-header {
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

.chart-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

.chart-select {
  padding: 6px 10px;
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #cbd5e1;
  font-size: 12px;
  cursor: pointer;
  outline: none;
}

.chart-select:focus {
  border-color: #3b82f6;
}

.control-btn {
  padding: 6px 10px;
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #cbd5e1;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.control-btn:hover {
  background-color: #2d3748;
  border-color: #475569;
}

.btn-icon {
  font-size: 12px;
}

.chart-container {
  flex-grow: 1;
  padding: 16px;
  overflow: auto;
}

.chart-placeholder {
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
}

.chart-area {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chart-visualization {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 20px;
}

.mock-chart {
  min-height: 300px;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 20px;
  text-align: center;
}

.chart-content {
  margin-bottom: 20px;
}

.chart-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 200px;
  padding: 20px 0;
}

.chart-bar {
  width: 40px;
  border-radius: 4px 4px 0 0;
  position: relative;
  transition: height 0.3s;
}

.chart-bar:hover {
  opacity: 0.8;
}

.bar-value {
  position: absolute;
  top: -25px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 12px;
  color: #cbd5e1;
  font-weight: 500;
}

.chart-lines {
  padding: 20px;
}

.line-svg {
  display: block;
}

.chart-pie {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.pie-container {
  width: 150px;
  height: 150px;
  position: relative;
}

.pie-chart {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  overflow: hidden;
  position: relative;
}

.pie-segment {
  position: absolute;
  width: 100%;
  height: 100%;
  clip-path: polygon(50% 50%, 50% 0%, 100% 0%, 100% 100%, 50% 50%);
  transform-origin: 50% 50%;
}

.chart-radar {
  padding: 20px;
}

.radar-svg {
  display: block;
}

.chart-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
}

.chart-label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.label-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.label-text {
  font-size: 12px;
  color: #cbd5e1;
}

.data-table {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
}

.table-header {
  padding: 12px 16px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-icon {
  font-size: 14px;
}

.table-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.table-content {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background-color: #0f172a;
}

th {
  padding: 10px 12px;
}
</style>