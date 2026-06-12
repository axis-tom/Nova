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
    <div v-if="availableCharts.length > 1 && !isDecisionCard" class="chart-switcher">
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

    <!-- Decision Card (不是图表，是决策卡片) -->
    <div v-if="isDecisionCard" class="decision-area">
      <div class="decision-score" :class="decisionScoreClass">
        <span class="score-number">{{ decisionMeta.score }}</span>
        <span class="score-label">{{ decisionMeta.label }}</span>
      </div>
      <p class="decision-summary">{{ decisionMeta.summary }}</p>

      <div v-if="decisionMeta.positives && decisionMeta.positives.length" class="decision-factors">
        <div class="factor-group-title">✅ 有利因素</div>
        <div v-for="p in decisionMeta.positives" :key="p" class="factor-item positive">{{ p }}</div>
      </div>
      <div v-if="decisionMeta.negatives && decisionMeta.negatives.length" class="decision-factors">
        <div class="factor-group-title">⚠️ 风险因素</div>
        <div v-for="n in decisionMeta.negatives" :key="n" class="factor-item negative">{{ n }}</div>
      </div>

      <div v-if="decisionMeta.entry_routes && decisionMeta.entry_routes.length" class="entry-routes">
        <div class="factor-group-title">🎯 推荐切入路径</div>
        <div v-for="(r, i) in decisionMeta.entry_routes" :key="i" class="route-item">
          <strong>{{ r.route }}</strong>
          <span class="route-meta">{{ r.type }} · 难度 {{ r.effort }} · 潜力 {{ r.potential }}</span>
          <p class="route-reason">{{ r.rationale }}</p>
        </div>
      </div>
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

// ── 决策卡支持（业务规则引擎输出） ──
const isDecisionCard = computed(() => {
  return currentChart.value === 'decision' && !!(props.dimension.charts as any)?.decision
})

const decisionMeta = computed(() => {
  return ((props.dimension.charts as any)?.decision || {}) as {
    score: number
    label: string
    recommendation: string
    summary: string
    positives: string[]
    negatives: string[]
    entry_routes: { route: string; type: string; effort: string; potential: string; rationale: string }[]
  }
})

const decisionScoreClass = computed(() => {
  const rec = decisionMeta.value.recommendation
  if (rec === 'strong_buy' || rec === 'buy') return 'score-positive'
  if (rec === 'hold') return 'score-neutral'
  return 'score-negative'
})

const chartLabels: Record<string, string> = {
  bar: '柱状',
  pie: '饼图',
  line: '折线',
  scatter: '散点',
  hist: '直方',
  decision: '决策卡',
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

/* ── 决策卡样式（业务规则引擎输出） ── */
.decision-area {
  padding: 8px 0;
}
.decision-score {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 12px;
}
.decision-score.score-positive {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}
.decision-score.score-neutral {
  background: #fffbeb;
  border: 1px solid #fde68a;
}
.decision-score.score-negative {
  background: #fef2f2;
  border: 1px solid #fecaca;
}
.score-number {
  font-size: 32px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1;
}
.score-label {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
}
.decision-summary {
  font-size: 13px;
  color: #475569;
  margin-bottom: 12px;
  line-height: 1.5;
}
.decision-factors {
  margin-bottom: 10px;
}
.factor-group-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 4px;
}
.factor-item {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 2px;
  line-height: 1.4;
}
.factor-item.positive {
  color: #065f46;
  background: #ecfdf5;
}
.factor-item.negative {
  color: #991b1b;
  background: #fef2f2;
}
.entry-routes {
  margin-top: 8px;
}
.route-item {
  padding: 8px 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  margin-bottom: 6px;
}
.route-item strong {
  font-size: 13px;
  color: #1e293b;
  display: block;
  margin-bottom: 2px;
}
.route-meta {
  font-size: 11px;
  color: #64748b;
}
.route-reason {
  font-size: 12px;
  color: #475569;
  margin-top: 4px;
  line-height: 1.4;
}
/* ── 结束决策卡样式 ── */

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