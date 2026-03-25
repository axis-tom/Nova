<template>
  <el-card class="stats-card" :body-style="{ padding: '20px' }">
    <div class="stats-header">
      <div class="stats-icon" :style="{ backgroundColor: iconBgColor }">
        <el-icon :size="24" :color="iconColor">
          <component :is="icon" />
        </el-icon>
      </div>
      <el-tag v-if="trend" :type="trendType" size="small" effect="plain">
        {{ trend }}
      </el-tag>
    </div>
    <div class="stats-content">
      <div class="stats-value">{{ formattedValue }}</div>
      <div class="stats-title">{{ title }}</div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue';
import { ElCard, ElTag, ElIcon } from 'element-plus';

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  value: {
    type: [Number, String],
    required: true
  },
  // 单位（可选，如 '次', '个'）
  unit: {
    type: String,
    default: ''
  },
  // 图标组件名（如 'DataLine'）
  icon: {
    type: [String, Object],
    default: 'DataLine'
  },
  iconBgColor: {
    type: String,
    default: '#eef2ff'
  },
  iconColor: {
    type: String,
    default: '#3b82f6'
  },
  // 趋势文本，如 '+12%'
  trend: {
    type: String,
    default: ''
  },
  trendType: {
    type: String,
    default: 'success' // success, danger, warning, info
  },
  // 数值格式化函数，默认直接显示
  formatter: {
    type: Function,
    default: (val) => val
  }
});

const formattedValue = computed(() => {
  let val = props.formatter(props.value);
  if (props.unit) {
    val = `${val} ${props.unit}`;
  }
  return val;
});
</script>

<style scoped>
.stats-card {
  border-radius: 12px;
  transition: transform 0.2s, box-shadow 0.2s;
}
.stats-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.stats-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stats-content {
  text-align: left;
}

.stats-value {
  font-size: 28px;
  font-weight: bold;
  color: #1f2937;
  line-height: 1.2;
  margin-bottom: 4px;
}

.stats-title {
  font-size: 14px;
  color: #6b7280;
}
</style>