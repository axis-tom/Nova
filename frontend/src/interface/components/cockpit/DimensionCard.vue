<template>
  <div class="dim-card" :class="{ disabled: !dimension.enabled }">
    <!-- Header: name + toggle -->
    <div class="dim-header">
      <span class="dim-name">{{ dimension.name }}</span>
      <div
        class="dim-toggle"
        :class="{ on: dimension.enabled }"
        @click="$emit('toggle', dimension.dimension_id)"
      ></div>
    </div>

    <!-- Sufficiency -->
    <div class="dim-sufficiency">
      <SufficiencyBadge
        :status="dimension.sufficiency.status"
        :percent="dimension.sufficiency.percent"
      />
      <span v-if="dimension.sufficiency.message" class="sufficiency-msg">
        {{ dimension.sufficiency.message }}
      </span>
    </div>

    <!-- Chart type switcher (only available types) -->
    <div v-if="availableCharts.length > 1" class="chart-switcher">
      <button
        v-for="ct in availableCharts"
        :key="ct"
        class="switcher-btn"
        :class="{ active: ct === currentChart }"
        @click="currentChart = ct"
      >
        {{ chartLabel(ct) }}
      </button>
    </div>

    <!-- ECharts -->
    <div v-if="currentChart && currentChartConfig" class="chart-area">
      <EChartsRenderer
        :chart-config="currentChartConfig"
        :chart-type="currentChart"
        height="180px"
      />
    </div>
    <div v-else class="chart-empty">
      <span>该图表类型暂无可渲染数据</span>
    </div>

    <!-- Actions -->
    <div class="dim-actions">
      <button class="action-btn" @click="$emit('followUp', dimension.dimension_id)">
        🔍 快速跟进
      </button>
      <button class="action-btn" @click="$emit('supplement', dimension.dimension_id)">
        📎 补充数据
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { CockpitDimension } from '@/api/agentChat'
import SufficiencyBadge from './SufficiencyBadge.vue'
import EChartsRenderer from './EChartsRenderer.vue'

const props = defineProps<{
  dimension: CockpitDimension
}>()

defineEmits<{
  toggle: [id: string]
  followUp: [id: string]
  supplement: [id: string]
}>()

const currentChart = ref(props.dimension.default_chart)

const currentChartConfig = computed(() => {
  const charts = props.dimension.charts
  switch (currentChart.value) {
    case 'bar': return charts.bar ?? null
    case 'pie': return charts.pie ?? null
    case 'line': return charts.line ?? null
    case 'scatter': return charts.scatter ?? null
    case 'hist': return charts.hist ?? null
    default: return null
  }
})

const availableCharts = computed(() => {
  const charts = props.dimension.charts
  const types: string[] = []
  if (charts.bar) types.push('bar')
  if (charts.pie) types.push('pie')
  if (charts.line) types.push('line')
  if (charts.scatter) types.push('scatter')
  if (charts.hist) types.push('hist')
  return types
})

const chartLabels: Record<string, string> = {
  bar: '柱状',
  pie: '饼图',
  line: '折线',
  scatter: '散点',
  hist: '直方',
}

function chartLabel(type: string): string {
  return chartLabels[type] || type
}
</script>

<style scoped>
.dim-card {
  padding: 12px 14px;
  border-bottom: 1px solid #f1f5f9;
  transition: opacity 0.2s;
}
.dim-card:last-child {
  border-bottom: none;
}
.dim-card.disabled {
  opacity: 0.4;
  pointer-events: none;
}

.dim-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.dim-name {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  flex: 1;
}

.dim-toggle {
  width: 28px;
  height: 16px;
  border-radius: 8px;
  background: #cbd5e1;
  cursor: pointer;
  position: relative;
  transition: background 0.2s;
  flex-shrink: 0;
}
.dim-toggle.on {
  background: #3b82f6;
}
.dim-toggle::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s;
}
.dim-toggle.on::after {
  transform: translateX(12px);
}

.dim-sufficiency {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: 6px;
}

.sufficiency-msg {
  font-size: 11px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chart-switcher {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}

.switcher-btn {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #d0d5dd;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
}
.switcher-btn:hover {
  border-color: #3b82f6;
  color: #3b82f6;
}
.switcher-btn.active {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}

.chart-area {
  width: 100%;
  border-radius: 6px;
  background: #f8fafc;
  overflow: hidden;
}

.chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60px;
  font-size: 12px;
  color: #94a3b8;
  background: #f8fafc;
  border-radius: 6px;
}

.dim-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.action-btn {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid #d0d5dd;
  background: #fff;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
}
.action-btn:hover {
  border-color: #3b82f6;
  color: #3b82f6;
}
</style>