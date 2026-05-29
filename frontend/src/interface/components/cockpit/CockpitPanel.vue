<template>
  <div class="cockpit-panel">
    <div class="cockpit-header">
      <h3>📊 多维驾驶舱</h3>
      <span class="cockpit-badge">{{ totalDimensions }} 维度</span>
    </div>

    <div class="cockpit-body">
      <!-- Empty state -->
      <div v-if="categories.length === 0" class="cockpit-empty">
        <div class="empty-icon">📊</div>
        <p>发送分析需求后，<br/>每个 Agent 的分析结果将实时展现在这里</p>
      </div>

      <!-- Categories -->
      <CategoryGroup
        v-for="cat in categories"
        :key="cat.agent_name"
        :category="cat"
        @set-priority="handleSetPriority"
        @toggle-dimension="handleToggleDimension"
        @follow-up="handleFollowUp"
        @supplement="handleSupplement"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CockpitCategory, CockpitUpdateData } from '@/api/agentChat'
import CategoryGroup from './CategoryGroup.vue'

const props = defineProps<{
  categories: CockpitCategory[]
}>()

const emit = defineEmits<{
  update: [data: CockpitUpdateData]
  setPriority: [agentName: string]
  toggleDimension: [agentName: string, dimId: string]
  followUp: [agentName: string, dimId: string]
  supplement: [agentName: string, dimId: string]
}>()

const totalDimensions = computed(() => {
  return props.categories.reduce((sum, cat) => sum + cat.dimensions.length, 0)
})

function handleSetPriority(agentName: string) {
  emit('setPriority', agentName)
}

function handleToggleDimension(agentName: string, dimId: string) {
  emit('toggleDimension', agentName, dimId)
}

function handleFollowUp(agentName: string, dimId: string) {
  emit('followUp', agentName, dimId)
}

function handleSupplement(agentName: string, dimId: string) {
  emit('supplement', agentName, dimId)
}
</script>

<style scoped>
.cockpit-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fafbfc;
}

.cockpit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e8ecf1;
  flex-shrink: 0;
}

.cockpit-header h3 {
  margin: 0;
  font-size: 15px;
  color: #1e293b;
}

.cockpit-badge {
  font-size: 12px;
  color: #64748b;
  background: #e8ecf1;
  padding: 2px 10px;
  border-radius: 10px;
}

.cockpit-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cockpit-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #94a3b8;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.4;
}

.cockpit-empty p {
  font-size: 13px;
  line-height: 1.6;
}
</style>