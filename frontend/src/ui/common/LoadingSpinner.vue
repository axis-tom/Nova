<template>
  <div v-if="overlay" class="spinner-overlay" :class="{ inline }">
    <el-icon class="is-loading" :size="iconSize" :color="color">
      <Loading />
    </el-icon>
    <p v-if="text" class="spinner-text">{{ text }}</p>
  </div>
  <div v-else class="spinner-container" :class="[size, { inline }]">
    <el-icon class="is-loading" :size="iconSize" :color="color">
      <Loading />
    </el-icon>
    <p v-if="text" class="spinner-text">{{ text }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { Loading } from '@element-plus/icons-vue';

const props = defineProps({
  size: {
    type: String,
    default: 'medium', // small, medium, large
    validator: (val) => ['small', 'medium', 'large'].includes(val)
  },
  color: {
    type: String,
    default: '#3b82f6'
  },
  text: {
    type: String,
    default: ''
  },
  overlay: {
    type: Boolean,
    default: false
  },
  inline: {
    type: Boolean,
    default: false
  }
});

const sizeMap = {
  small: '24px',
  medium: '40px',
  large: '56px'
};

const iconSize = computed(() => sizeMap[props.size]);
</script>

<style scoped>
.spinner-container,
.spinner-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.spinner-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.8);
  z-index: 9999;
}

.spinner-container.inline,
.spinner-overlay.inline {
  position: relative;
  width: auto;
  height: auto;
  background: none;
}

.spinner-text {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

/* 使用 Element Plus 自带的 is-loading 类（旋转动画） */
.is-loading {
  animation: rotating 1.2s linear infinite;
}

@keyframes rotating {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>