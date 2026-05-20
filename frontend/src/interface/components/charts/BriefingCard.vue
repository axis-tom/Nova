<template>
  <div class="briefing-card">
    <div class="card-header">
      <span class="card-title">选品分析可视化</span>
      <el-tag size="small" type="success">{{ sectionsCount }} 个维度</el-tag>
    </div>

    <div class="charts-grid">
      <!-- 价格分布柱状图 -->
      <div v-if="priceBandData" class="chart-item">
        <v-chart :option="priceBandOption" autoresize class="chart" />
      </div>

      <!-- 市场份额饼图 -->
      <div v-if="marketShareData" class="chart-item">
        <v-chart :option="marketShareOption" autoresize class="chart" />
      </div>

      <!-- Top 商品收入条形图 -->
      <div v-if="topPicksData" class="chart-item chart-wide">
        <v-chart :option="topPicksOption" autoresize class="chart" />
      </div>

      <!-- BSR 分布 -->
      <div v-if="bsrData" class="chart-item">
        <v-chart :option="bsrOption" autoresize class="chart" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

// ── Props ──

interface BriefingData {
  market_analysis_result?: Record<string, any>
  competitor_analysis_result?: Record<string, any>
  profitability_result?: Record<string, any>
  traffic_insights?: Record<string, any>
}

const props = defineProps<{ data: BriefingData }>()

// ── 数据提取 ──

const sectionsCount = computed(() => {
  let count = 0
  if (props.data.market_analysis_result) count++
  if (props.data.competitor_analysis_result) count++
  if (props.data.profitability_result) count++
  if (props.data.traffic_insights) count++
  return count
})

const priceBandData = computed(() => {
  const bands = props.data.market_analysis_result?.price_band_analysis
  if (!bands || Object.keys(bands).length === 0) return null
  return bands
})

const marketShareData = computed(() => {
  const share = props.data.competitor_analysis_result?.market_share_distribution
  if (!share || share.length === 0) return null
  return share.slice(0, 8)
})

const topPicksData = computed(() => {
  const picks = props.data.profitability_result?.top_picks
  if (!picks || picks.length === 0) return null
  return picks.slice(0, 5)
})

const bsrData = computed(() => {
  const bsr = props.data.market_analysis_result?.bsr_trend_distribution
  if (!bsr) return null
  return bsr
})

// ── 图表配置 ──

const priceBandOption = computed(() => {
  const bands = priceBandData.value
  if (!bands) return {}
  const labels = Object.keys(bands)
  const counts = labels.map(k => bands[k]?.count || 0)
  return {
    title: { text: '价格带分布', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, bottom: 30, top: 40 },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: '商品数' },
    series: [{ type: 'bar', data: counts, itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] } }],
  }
})

const marketShareOption = computed(() => {
  const share = marketShareData.value
  if (!share) return {}
  return {
    title: { text: '市场份额', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['50%', '55%'],
      data: share.map((b: any) => ({ name: b.brand, value: b.total_monthly_sales })),
      label: { fontSize: 11 },
    }],
  }
})

const topPicksOption = computed(() => {
  const picks = topPicksData.value
  if (!picks) return {}
  const names = picks.map((p: any) => (p.title || p.asin || '').slice(0, 20))
  const revenues = picks.map((p: any) => p.monthly_revenue || 0)
  const profits = picks.map((p: any) => p.est_monthly_profit || 0)
  return {
    title: { text: 'Top 商品月收入 vs 估利', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['月收入', '估利'], top: 4, right: 16 },
    grid: { left: 80, right: 16, bottom: 30, top: 40 },
    yAxis: { type: 'category', data: names, axisLabel: { fontSize: 11 } },
    xAxis: { type: 'value', name: '$' },
    series: [
      { name: '月收入', type: 'bar', data: revenues, itemStyle: { color: '#3b82f6' } },
      { name: '估利', type: 'bar', data: profits, itemStyle: { color: '#22c55e' } },
    ],
  }
})

const bsrOption = computed(() => {
  const bsr = bsrData.value
  if (!bsr) return {}
  const labels = ['上升', '下降', '稳定', '未知']
  const values = [bsr.improving || 0, bsr.declining || 0, bsr.stable || 0, bsr.unknown || 0]
  const colors = ['#22c55e', '#ef4444', '#f59e0b', '#94a3b8']
  return {
    title: { text: 'BSR 趋势分布', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['50%', '55%'],
      data: labels.map((name, i) => ({ name, value: values[i], itemStyle: { color: colors[i] } })),
      label: { fontSize: 11 },
    }],
  }
})
</script>

<style scoped>
.briefing-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  margin: 12px 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-item {
  background: #f8fafc;
  border-radius: 8px;
  padding: 8px;
  min-height: 240px;
}

.chart-item.chart-wide {
  grid-column: 1 / -1;
}

.chart {
  width: 100%;
  height: 220px;
}
</style>
