<template>
  <div class="category" :class="{ collapsed: !isOpen }">
    <!-- Header -->
    <div class="category-header" @click="isOpen = !isOpen">
      <span class="category-toggle" :class="{ open: isOpen }">▶</span>
      <span class="category-name">{{ category.category_label || category.agent_name }}</span>
      <span class="dim-count">{{ category.dimensions.length }} 维度</span>
      <button
        class="priority-btn"
        :class="{ active: category.priority }"
        @click.stop="$emit('setPriority', category.agent_name)"
      >
        {{ category.priority ? '★ 优先' : '☆ 优先' }}
      </button>
    </div>

    <!-- Dimensions -->
    <div v-if="isOpen" class="category-dims">
      <DimensionCard
        v-for="dim in category.dimensions"
        :key="dim.dimension_id"
        :dimension="dim"
        @toggle="$emit('toggleDimension', category.agent_name, $event)"
        @follow-up="$emit('followUp', category.agent_name, $event)"
        @supplement="$emit('supplement', category.agent_name, $event)"
      />
      <div v-if="category.dimensions.length === 0" class="no-dims">
        暂无分析维度
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { CockpitCategory } from '@/api/agentChat'
import DimensionCard from './DimensionCard.vue'

defineProps<{
  category: CockpitCategory
}>()

defineEmits<{
  setPriority: [agentName: string]
  toggleDimension: [agentName: string, dimId: string]
  followUp: [agentName: string, dimId: string]
  supplement: [agentName: string, dimId: string]
}>()

const isOpen = ref(true)
</script>

<style scoped>
.category {
  background: #fff;
  border: 1px solid #e8ecf1;
  border-radius: 10px;
  overflow: hidden;
}

.category-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  cursor: pointer;
  background: #f8fafc;
  border-bottom: 1px solid #e8ecf1;
  user-select: none;
}
.category-header:hover {
  background: #f1f5f9;
}

.category-toggle {
  font-size: 10px;
  color: #94a3b8;
  transition: transform 0.2s;
}
.category-toggle.open {
  transform: rotate(90deg);
}

.category-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  flex: 1;
}

.dim-count {
  font-size: 11px;
  color: #94a3b8;
  background: #e8ecf1;
  padding: 1px 8px;
  border-radius: 8px;
}

.priority-btn {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #d0d5dd;
  background: #fff;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s;
}
.priority-btn:hover {
  border-color: #f59e0b;
  color: #b45309;
  background: #fffbeb;
}
.priority-btn.active {
  background: #f59e0b;
  color: #fff;
  border-color: #f59e0b;
}

.category-dims {
  display: flex;
  flex-direction: column;
}

.no-dims {
  padding: 20px;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
}
</style>