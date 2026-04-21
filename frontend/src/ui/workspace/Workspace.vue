<template>
  <div class="workspace">
    <!-- HeaderBar 可选工具栏 -->
    <div class="workspace-header">
      <div class="header-content">
        <div class="header-left">
          <span class="logo">Nova</span>
          <span class="workspace-title">AI 工作台</span>
        </div>
        <div class="header-right">
          <div class="header-actions">
            <span class="action-item">设置</span>
            <span class="action-item">用户</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 三栏布局主体 -->
    <div class="workspace-body">
      <!-- 左侧：情报与策略面板 -->
      <LeftPanel class="workspace-left" />

      <!-- 中间：执行画布 -->
      <ExecutionCanvas class="workspace-center" />

      <!-- 右侧：结果层 -->
      <ResultLayer class="workspace-right" />
    </div>
  </div>
</template>

<script setup>
import LeftPanel from '@/ui/workspace/LeftPanel.vue'
import ExecutionCanvas from '@/ui/workspace/ExecutionCanvas.vue'
import ResultLayer from '@/ui/workspace/ResultLayer.vue'
</script>

<style scoped>
.workspace {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background-color: #0f172a;
  color: #e2e8f0;
}

.workspace-header {
  height: 48px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  padding: 0 16px;
  flex-shrink: 0;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  font-size: 18px;
  font-weight: bold;
  color: #60a5fa;
}

.workspace-title {
  font-size: 14px;
  color: #94a3b8;
}

.header-right {
  display: flex;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 16px;
}

.action-item {
  font-size: 14px;
  color: #cbd5e1;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.action-item:hover {
  background-color: #334155;
}

.workspace-body {
  display: grid;
  grid-template-columns: 20% 55% 25%;
  height: calc(100vh - 48px);
  overflow: hidden;
  flex-grow: 1;
}

.workspace-left,
.workspace-center,
.workspace-right {
  overflow: auto;
  border-right: 1px solid #334155;
}

.workspace-right {
  border-right: none;
}
</style>