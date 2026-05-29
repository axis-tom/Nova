<template>
  <div class="echart-renderer" ref="chartRef" :style="{ width: '100%', height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { ChartConfig } from '@/api/agentChat'

const props = defineProps<{
  chartConfig?: ChartConfig | null
  chartType?: string
  height?: string
}>()

const chartRef = ref<HTMLElement | null>(null)
let instance: echarts.ECharts | null = null

function buildOption(): Record<string, any> {
  const cfg = props.chartConfig
  if (!cfg) return {}

  const type = props.chartType || 'bar'

  if (type === 'bar') {
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 36, right: 12, top: 24, bottom: 28 },
      xAxis: {
        type: 'category',
        data: cfg.xAxis?.data || [],
        axisLabel: { fontSize: 10, interval: 0, rotate: (cfg.xAxis?.data?.length ?? 0) > 6 ? 45 : 0 },
      },
      yAxis: { type: 'value', name: cfg.yAxis?.name || '', nameTextStyle: { fontSize: 10 } },
      series: (cfg.series || []).map((s: any) => ({
        type: 'bar',
        name: s.name || '',
        data: s.data || [],
        itemStyle: {
          color: '#3b82f6',
          borderRadius: [3, 3, 0, 0],
          ...(s.itemStyle || {}),
        },
        barMaxWidth: 24,
      })),
    }
  }

  if (type === 'pie') {
    return {
      tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
      series: [{
        type: 'pie',
        radius: ['30%', '60%'],
        center: ['50%', '55%'],
        data: cfg.data || cfg.series?.[0]?.data?.map((v: number, i: number) => ({
          name: cfg.xAxis?.data?.[i] || `项${i + 1}`,
          value: v,
        })) || [],
        label: { fontSize: 10 },
        emphasis: {
          label: { show: true, fontSize: 12, fontWeight: 'bold' },
        },
      }],
    }
  }

  if (type === 'line') {
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 36, right: 12, top: 24, bottom: 28 },
      xAxis: {
        type: 'category',
        data: cfg.xAxis?.data || [],
        axisLabel: { fontSize: 10 },
      },
      yAxis: { type: 'value', name: cfg.yAxis?.name || '', nameTextStyle: { fontSize: 10 } },
      series: (cfg.series || []).map((s: any) => ({
        type: 'line',
        name: s.name || '',
        data: s.data || [],
        smooth: true,
        itemStyle: { color: '#3b82f6' },
        lineStyle: { width: 2 },
        symbol: 'circle',
        symbolSize: 6,
      })),
    }
  }

  if (type === 'scatter') {
    return {
      tooltip: { trigger: 'item' },
      grid: { left: 36, right: 12, top: 24, bottom: 28 },
      xAxis: { type: 'category', data: cfg.xAxis?.data || [], axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value', name: cfg.yAxis?.name || '', nameTextStyle: { fontSize: 10 } },
      series: (cfg.series || []).map((s: any) => ({
        type: 'scatter',
        name: s.name || '',
        data: s.data?.map((v: number, i: number) => [i, v]) || [],
        symbolSize: 8,
        itemStyle: { color: '#3b82f6' },
      })),
    }
  }

  // fallback: 柱状图
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 36, right: 12, top: 24, bottom: 28 },
    xAxis: { type: 'category', data: cfg.xAxis?.data || [] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: cfg.series?.[0]?.data || [] }],
  }
}

function render() {
  if (!chartRef.value) return
  if (!instance) {
    instance = echarts.init(chartRef.value)
  }
  const option = buildOption()
  instance.setOption(option, true)
}

function handleResize() {
  instance?.resize()
}

watch(
  () => [props.chartConfig, props.chartType],
  () => nextTick(render),
  { deep: true },
)

onMounted(() => {
  nextTick(render)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  instance?.dispose()
  instance = null
})
</script>

<style scoped>
.echart-renderer {
  min-height: 160px;
}
</style>