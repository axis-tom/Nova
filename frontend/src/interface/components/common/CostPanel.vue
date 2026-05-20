<template>
  <el-card>
    <template #header>
      <div class="cost-header">
        <span>AI 模型调用成本</span>
        <el-button size="small" type="warning" plain @click="handleReset">重置计数</el-button>
      </div>
    </template>

    <div v-if="loading" v-loading="true" style="height: 100px"></div>

    <div v-else-if="agents.length === 0" class="empty">
      暂无调用记录
    </div>

    <el-table v-else :data="agents" stripe size="small">
      <el-table-column prop="name" label="Agent" width="160" />
      <el-table-column prop="model" label="模型" width="160" />
      <el-table-column prop="calls" label="调用次数" width="90" align="center" />
      <el-table-column prop="input_tokens" label="输入 Tokens" width="110" align="right" />
      <el-table-column prop="output_tokens" label="输出 Tokens" width="110" align="right" />
      <el-table-column prop="cost" label="估算费用" width="100" align="right">
        <template #default="{ row }">
          ${{ row.cost }}
        </template>
      </el-table-column>
    </el-table>

    <div v-if="totalCost > 0" class="total-row">
      合计估算费用：<strong>${{ totalCost }}</strong>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'

interface AgentCost {
  name: string
  model: string
  calls: number
  input_tokens: number
  output_tokens: number
  cost: string
}

const loading = ref(true)
const agents = ref<AgentCost[]>([])
const totalCost = ref(0)

async function loadCostReport() {
  loading.value = true
  try {
    const res = await client.get('/agent/cost-report') as any
    const report = res.cost_report || {}
    const total = report._total_estimated_cost_usd || 0
    totalCost.value = total

    agents.value = Object.entries(report)
      .filter(([k]) => !k.startsWith('_'))
      .map(([name, data]: [string, any]) => ({
        name,
        model: data.model || '-',
        calls: data.calls || 0,
        input_tokens: data.input_tokens || 0,
        output_tokens: data.output_tokens || 0,
        cost: (data.estimated_cost_usd || 0).toFixed(4),
      }))
  } catch (e) {
    console.error('Failed to load cost report', e)
  } finally {
    loading.value = false
  }
}

async function handleReset() {
  try {
    await ElMessageBox.confirm('确定重置所有调用计数？', '重置', { type: 'warning' })
    await client.post('/agent/cost-report/reset')
    ElMessage.success('已重置')
    await loadCostReport()
  } catch {}
}

onMounted(loadCostReport)
</script>

<style scoped>
.cost-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 24px;
}

.total-row {
  margin-top: 12px;
  text-align: right;
  font-size: 14px;
  color: #334155;
}
</style>
