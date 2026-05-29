<template>
  <span class="sufficiency-badge" :class="status">
    {{ label }}
    <template v-if="percent !== undefined"> {{ percent }}%</template>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: 'sufficient' | 'moderate' | 'insufficient'
  percent?: number
  message?: string
}>()

const label = computed(() => {
  const map: Record<string, string> = {
    sufficient: '充足',
    moderate: '一般',
    insufficient: '不足',
  }
  return map[props.status] || props.status
})
</script>

<style scoped>
.sufficiency-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
  white-space: nowrap;
  display: inline-block;
}
.sufficiency-badge.sufficient {
  background: #dcfce7;
  color: #166534;
}
.sufficiency-badge.moderate {
  background: #fef9c3;
  color: #854d0e;
}
.sufficiency-badge.insufficient {
  background: #fee2e2;
  color: #991b1b;
}
</style>