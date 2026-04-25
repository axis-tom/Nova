<template>
  <div class="strategy-panel">
    <div class="section-header">
      <span class="section-icon">🧠</span>
      <span class="section-title">AI策略面板</span>
    </div>

    <div class="strategy-controls">
      <!-- 语气控制 -->
      <div class="control-group">
        <label class="control-label">语气风格</label>
        <div class="control-options">
          <button 
            v-for="option in toneOptions" 
            :key="option.value"
            class="option-btn"
            :class="{ active: strategy.tone === option.value }"
            @click="updateStrategyField('tone', option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <!-- 市场选择 -->
      <div class="control-group">
        <label class="control-label">目标市场</label>
        <div class="control-options">
          <button 
            v-for="option in marketOptions" 
            :key="option.value"
            class="option-btn"
            :class="{ active: strategy.market === option.value }"
            @click="updateStrategyField('market', option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <!-- SEO强度 -->
      <div class="control-group">
        <label class="control-label">SEO强度</label>
        <div class="control-slider">
          <div class="slider-labels">
            <span>低</span>
            <span>中</span>
            <span>高</span>
          </div>
          <div class="slider-track">
            <div 
              class="slider-fill"
              :style="{ width: getSeoStrengthWidth() }"
            ></div>
            <button 
              v-for="level in seoLevels"
              :key="level.value"
              class="slider-dot"
              :class="{ active: strategy.seoStrength === level.value }"
              :style="{ left: level.position }"
              @click="updateStrategyField('seoStrength', level.value)"
            ></button>
          </div>
        </div>
      </div>

      <!-- 创意度 -->
      <div class="control-group">
        <label class="control-label">创意度</label>
        <div class="control-options">
          <button 
            v-for="option in creativityOptions" 
            :key="option.value"
            class="option-btn"
            :class="{ active: strategy.creativity === option.value }"
            @click="updateStrategyField('creativity', option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <!-- 策略状态 -->
      <div class="strategy-status">
        <div class="status-item">
          <span class="status-label">节点状态:</span>
          <span class="status-value" :class="getDirtyStatusClass()">
            {{ getDirtyStatusText() }}
          </span>
        </div>
        <div class="status-item">
          <span class="status-label">策略影响:</span>
          <span class="status-value">全局生效</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '@/state/workspace'
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

interface Emits {
  (e: 'updateStrategy', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

const workspaceStore = useWorkspaceStore()
const { strategy, nodeStatus } = storeToRefs(workspaceStore)

// 选项配置
const toneOptions = [
  { value: 'professional', label: '专业' },
  { value: 'friendly', label: '友好' },
  { value: 'persuasive', label: '说服性' }
]

const marketOptions = [
  { value: 'global', label: '全球' },
  { value: 'us', label: '美国' },
  { value: 'eu', label: '欧洲' },
  { value: 'asia', label: '亚洲' }
]

const creativityOptions = [
  { value: 'conservative', label: '保守' },
  { value: 'balanced', label: '平衡' },
  { value: 'creative', label: '创意' }
]

const seoLevels = [
  { value: 'low', position: '0%' },
  { value: 'medium', position: '50%' },
  { value: 'high', position: '100%' }
]

// 计算属性
const dirtyNodesCount = computed(() => {
  return Object.values(nodeStatus.value).filter(status => status === 'dirty').length
})

const totalNodesCount = computed(() => {
  return Object.keys(nodeStatus.value).length
})

// 方法
const updateStrategyField = (field, value) => {
  const newStrategy = { [field]: value }
  // 通过store更新策略
  workspaceStore.updateStrategy(newStrategy)
  // 发射事件通知父组件
  emit('updateStrategy', newStrategy)
}

const getSeoStrengthWidth = () => {
  const widths = {
    low: '33%',
    medium: '66%',
    high: '100%'
  }
  return widths[strategy.value.seoStrength] || '66%'
}

const getDirtyStatusText = () => {
  if (dirtyNodesCount.value === 0) return '全部就绪'
  return `${dirtyNodesCount.value}/${totalNodesCount.value} 节点待更新`
}

const getDirtyStatusClass = () => {
  if (dirtyNodesCount.value === 0) return 'status-ready'
  return 'status-dirty'
}
</script>

<style scoped>
.strategy-panel {
  background-color: #0f172a;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
}

.section-icon {
  font-size: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.strategy-controls {
  padding: 16px;
}

.control-group {
  margin-bottom: 20px;
}

.control-group:last-child {
  margin-bottom: 0;
}

.control-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.control-options {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.option-btn {
  padding: 8px 12px;
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  flex: 1;
  min-width: 60px;
}

.option-btn:hover {
  background-color: #2d3748;
  border-color: #475569;
}

.option-btn.active {
  background-color: #1e3a8a;
  border-color: #3b82f6;
  color: #e2e8f0;
}

.control-slider {
  margin-top: 8px;
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.slider-labels span {
  font-size: 11px;
  color: #94a3b8;
}

.slider-track {
  position: relative;
  height: 4px;
  background-color: #334155;
  border-radius: 2px;
  margin: 12px 0;
}

.slider-fill {
  position: absolute;
  height: 100%;
  background-color: #3b82f6;
  border-radius: 2px;
  transition: width 0.2s;
}

.slider-dot {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 16px;
  height: 16px;
  background-color: #475569;
  border: 2px solid #334155;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.2s;
}

.slider-dot:hover {
  background-color: #64748b;
  border-color: #475569;
}

.slider-dot.active {
  background-color: #3b82f6;
  border-color: #60a5fa;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
}

.strategy-status {
  margin-top: 20px;
  padding: 12px;
  background-color: #1e293b;
  border-radius: 6px;
  border: 1px solid #334155;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.status-item:last-child {
  margin-bottom: 0;
}

.status-label {
  font-size: 12px;
  color: #94a3b8;
}

.status-value {
  font-size: 12px;
  font-weight: 500;
}

.status-ready {
  color: #10b981;
}

.status-dirty {
  color: #f59e0b;
}
</style>