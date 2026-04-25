<template>
  <div class="result-layer">
    <div class="result-header">
      <h3 class="result-title">结果产出</h3>
      <div class="result-subtitle">AI工作流执行结果展示</div>
    </div>

    <div class="result-content">
      <!-- ResultContainer 组件 -->
      <ResultContainer @updateResult="handleUpdateResult" />
    </div>
  </div>
</template>

<script setup lang="ts">
import ResultContainer from './ResultContainer.vue'

// 方法
const handleUpdateResult = (data) => {
  console.log('结果更新:', data)
  // 这里可以处理结果更新逻辑
}
</script>

<style scoped>
.result-layer {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #1e293b;
}

.result-header {
  padding: 16px 20px;
  border-bottom: 1px solid #334155;
  background-color: #0f172a;
}

.result-title {
  font-size: 16px;
  font-weight: 600;
  color: #f1f5f9;
  margin: 0 0 4px 0;
}

.result-subtitle {
  font-size: 12px;
  color: #94a3b8;
}

.result-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 16px;
  overflow-y: auto;
}

.result-type-selector {
  display: flex;
  gap: 8px;
  padding: 8px;
  background-color: #0f172a;
  border-radius: 8px;
  border: 1px solid #334155;
}

.type-item {
  flex: 1;
  padding: 8px 12px;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
  border-radius: 6px;
  cursor: default;
  transition: all 0.2s;
}

.type-item:hover {
  background-color: #334155;
  color: #cbd5e1;
}

.type-item.active {
  background-color: #3b82f6;
  color: white;
  font-weight: 500;
}

.result-display {
  flex-grow: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  min-height: 200px;
}

.result-placeholder {
  text-align: center;
  padding: 30px;
  max-width: 300px;
}

.placeholder-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.placeholder-title {
  font-size: 16px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 8px;
}

.placeholder-description {
  font-size: 13px;
  color: #94a3b8;
  margin-bottom: 10px;
}

.placeholder-hint {
  font-size: 11px;
  color: #64748b;
  font-style: italic;
  padding: 6px;
  background-color: #1e293b;
  border-radius: 4px;
  border: 1px solid #334155;
}

.result-toolbar {
  display: flex;
  gap: 8px;
  padding: 12px;
  background-color: #0f172a;
  border-radius: 8px;
  border: 1px solid #334155;
}

.tool-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px;
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #94a3b8;
  cursor: default;
  transition: all 0.2s;
}

.tool-item:hover {
  background-color: #334155;
  color: #cbd5e1;
}

.tool-icon {
  font-size: 16px;
}

.tool-label {
  font-size: 12px;
}

.result-details {
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
}

.details-header {
  padding: 12px 16px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
}

.details-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.details-content {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-label {
  font-size: 13px;
  color: #94a3b8;
}

.detail-value {
  font-size: 13px;
  color: #cbd5e1;
  font-weight: 500;
}
</style>