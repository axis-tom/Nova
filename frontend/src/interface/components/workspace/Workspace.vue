<template>
  <div class="workspace">
    <!-- 顶部工具栏 -->
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

    <!-- 主体区域 -->
    <div class="workspace-main">
      <!-- 左侧悬浮触发器（优化视觉） -->
      <div
        class="drawer-trigger"
        @click="toggleDrawer"
        :class="{ active: drawerVisible }"
        :title="drawerVisible ? '收起情报与策略' : '展开情报与策略'"
      >
        <span class="trigger-icon">{{ drawerVisible ? '◀' : '▶' }}</span>
        <span class="trigger-text">情 报 与 策 略</span>
      </div>

      <!-- 工作区（画布+结果，可拖拽分割） -->
      <div class="work-area">
        <div class="canvas-area" :style="{ width: canvasWidth + '%' }">
          <ExecutionCanvas />
        </div>

        <!-- 优化的拖拽分割条 -->
        <div
          class="resize-handle"
          @mousedown="startResize"
          :class="{ resizing: isResizing }"
        >
          <div class="handle-line"></div>
        </div>

        <div class="result-area" :style="{ width: 100 - canvasWidth + '%' }">
          <ResultLayer />
        </div>
      </div>

      <!-- 全局拖拽遮罩（防止鼠标进入iframe或画布时丢失事件） -->
      <div v-if="isResizing || isDrawerResizing" class="resize-overlay"></div>

      <!-- 悬浮抽屉（Teleport 到 body 确保层级） -->
      <Teleport to="body">
        <!-- 遮罩层（带模糊效果） -->
        <transition name="fade">
          <div v-if="drawerVisible" class="drawer-overlay" @click="closeDrawer"></div>
        </transition>

        <!-- 抽屉面板（带滑动动画） -->
        <div
          class="drawer-panel"
          :class="{ visible: drawerVisible }"
          :style="drawerStyle"
        >
          <div class="drawer-header">
            <span class="drawer-title">情报与策略</span>
            <span class="drawer-close" @click="closeDrawer" title="关闭">✕</span>
          </div>
          <div class="drawer-content">
            <LeftPanel />
          </div>
          <!-- 抽屉右侧拖拽边缘（优化交互） -->
          <div
            class="drawer-resize-handle"
            @mousedown="startDrawerResize"
            :class="{ resizing: isDrawerResizing }"
          >
            <div class="drawer-handle-line"></div>
          </div>
        </div>
      </Teleport>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import LeftPanel from './LeftPanel.vue'
import ExecutionCanvas from './ExecutionCanvas.vue'
import ResultLayer from './ResultLayer.vue'

// --- 状态持久化 Key ---
const STORAGE_CANVAS_WIDTH = 'nova_workspace_canvas_width'
const STORAGE_DRAWER_WIDTH = 'nova_workspace_drawer_width'

// --- 画布/结果分割 ---
// 默认黄金比例 62% / 38%
const canvasWidth = ref<number>(62)
const isResizing = ref<boolean>(false)

// --- 悬浮抽屉 ---
const drawerVisible = ref<boolean>(false)
// 默认抽屉宽度 320px，从 localStorage 读取
const drawerWidth = ref<number>(320)
const isDrawerResizing = ref<boolean>(false)

// 加载保存的设置
onMounted(() => {
  const savedCanvas = localStorage.getItem(STORAGE_CANVAS_WIDTH)
  if (savedCanvas) {
    const val = parseFloat(savedCanvas)
    if (!isNaN(val) && val >= 20 && val <= 80) {
      canvasWidth.value = val
    }
  }
  
  const savedDrawer = localStorage.getItem(STORAGE_DRAWER_WIDTH)
  if (savedDrawer) {
    const val = parseInt(savedDrawer, 10)
    if (!isNaN(val) && val >= 200 && val <= 500) {
      drawerWidth.value = val
    }
  }
})

// 抽屉样式（带滑动过渡）
const drawerStyle = computed(() => ({
  width: drawerWidth.value + 'px',
  transform: drawerVisible.value
    ? 'translateX(0)'
    : `translateX(-${drawerWidth.value}px)`,
}))

const toggleDrawer = () => {
  drawerVisible.value = !drawerVisible.value
}

const closeDrawer = () => {
  drawerVisible.value = false
}

// --- 画布分割拖拽逻辑 ---
const startResize = (e) => {
  isResizing.value = true
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  e.preventDefault()
}

const handleResize = (e) => {
  const workArea = document.querySelector('.work-area')
  if (!workArea) return

  const rect = workArea.getBoundingClientRect()
  const offsetX = e.clientX - rect.left
  let newWidth = (offsetX / rect.width) * 100

  // 限制范围：20% ~ 80%
  newWidth = Math.min(80, Math.max(20, newWidth))
  canvasWidth.value = newWidth
}

const stopResize = () => {
  isResizing.value = false
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  // 保存比例
  localStorage.setItem(STORAGE_CANVAS_WIDTH, canvasWidth.value.toString())
}

// --- 抽屉宽度拖拽逻辑 ---
const startDrawerResize = (e) => {
  isDrawerResizing.value = true
  document.addEventListener('mousemove', handleDrawerResize)
  document.addEventListener('mouseup', stopDrawerResize)
  document.body.style.cursor = 'ew-resize'
  document.body.style.userSelect = 'none'
  e.preventDefault()
  e.stopPropagation()
}

const handleDrawerResize = (e) => {
  // 抽屉左边缘固定在 0，宽度直接等于鼠标X坐标
  const newWidth = e.clientX
  // 限制范围：220px ~ 480px
  drawerWidth.value = Math.min(480, Math.max(220, newWidth))
}

const stopDrawerResize = () => {
  isDrawerResizing.value = false
  document.removeEventListener('mousemove', handleDrawerResize)
  document.removeEventListener('mouseup', stopDrawerResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  // 保存宽度
  localStorage.setItem(STORAGE_DRAWER_WIDTH, drawerWidth.value.toString())
}

onUnmounted(() => {
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
  document.removeEventListener('mousemove', handleDrawerResize)
  document.removeEventListener('mouseup', stopDrawerResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
})
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
  padding: 0 20px;
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
  letter-spacing: 0.5px;
}

.workspace-title {
  font-size: 14px;
  color: #94a3b8;
  font-weight: 400;
}

.header-right {
  display: flex;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 20px;
}

.action-item {
  font-size: 14px;
  color: #cbd5e1;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: all 0.2s;
}

.action-item:hover {
  background-color: #334155;
  color: #f1f5f9;
}

.workspace-main {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

/* --- 优化后的触发器 --- */
.drawer-trigger {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 36px;
  height: 120px;
  background: rgba(30, 41, 59, 0.9);
  backdrop-filter: blur(4px);
  border: 1px solid #475569;
  border-left: none;
  border-radius: 0 12px 12px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  z-index: 20;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  writing-mode: vertical-rl;
  text-orientation: upright;
  color: #cbd5e1;
  box-shadow: 2px 4px 8px rgba(0, 0, 0, 0.2);
}

.drawer-trigger:hover {
  background: #2d3748;
  border-color: #3b82f6;
  color: #f1f5f9;
  box-shadow: 4px 6px 12px rgba(0, 0, 0, 0.3);
  width: 40px;
}

.drawer-trigger.active {
  background: #2563eb;
  border-color: #3b82f6;
  color: white;
  box-shadow: 4px 6px 12px rgba(37, 99, 235, 0.3);
}

.trigger-icon {
  font-size: 18px;
  font-weight: bold;
}

.trigger-text {
  font-size: 13px;
  letter-spacing: 6px;
  font-weight: 500;
}

/* --- 工作区 --- */
.work-area {
  flex: 1;
  display: flex;
  overflow: hidden;
  width: 100%;
}

.canvas-area,
.result-area {
  height: 100%;
  overflow: auto;
}

.canvas-area {
  background-color: #0a0f1a; /* 深色画布背景，更聚焦 */
}

.result-area {
  background-color: #0f172a;
  border-left: 1px solid #334155;
}

/* --- 拖拽分割条（精致版） --- */
.resize-handle {
  width: 8px;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: transparent;
  transition: background-color 0.15s;
  position: relative;
  z-index: 5;
}

.resize-handle:hover,
.resize-handle.resizing {
  background-color: rgba(59, 130, 246, 0.2);
}

.handle-line {
  width: 2px;
  height: 60px;
  background-color: #475569;
  border-radius: 2px;
  transition: all 0.15s;
}

.resize-handle:hover .handle-line,
.resize-handle.resizing .handle-line {
  background-color: #3b82f6;
  width: 3px;
  height: 80px;
  box-shadow: 0 0 8px #3b82f6;
}

/* 拖拽时的全局遮罩，保证鼠标事件不丢失 */
.resize-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  cursor: col-resize;
  background-color: transparent;
}

/* --- 悬浮抽屉（精致版）--- */
.drawer-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(3px);
  z-index: 100;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.drawer-panel {
  position: fixed;
  top: 48px;
  left: 0;
  bottom: 0;
  background-color: #1e293b;
  border-right: 1px solid #334155;
  box-shadow: 4px 0 20px rgba(0, 0, 0, 0.4);
  z-index: 101;
  display: flex;
  flex-direction: column;
  transition: transform 0.3s cubic-bezier(0.2, 0.9, 0.4, 1);
}

.drawer-header {
  height: 52px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #334155;
  background-color: #0f172a;
}

.drawer-title {
  font-size: 16px;
  font-weight: 600;
  color: #f1f5f9;
}

.drawer-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  cursor: pointer;
  font-size: 20px;
  color: #94a3b8;
  transition: all 0.2s;
}

.drawer-close:hover {
  background-color: #334155;
  color: #f1f5f9;
}

.drawer-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

/* 抽屉拖拽边缘 */
.drawer-resize-handle {
  position: absolute;
  top: 0;
  right: -4px;
  width: 8px;
  height: 100%;
  cursor: ew-resize;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer-resize-handle:hover,
.drawer-resize-handle.resizing {
  background-color: rgba(59, 130, 246, 0.2);
}

.drawer-handle-line {
  width: 2px;
  height: 60px;
  background-color: transparent;
  border-radius: 2px;
  transition: all 0.15s;
}

.drawer-resize-handle:hover .drawer-handle-line,
.drawer-resize-handle.resizing .drawer-handle-line {
  background-color: #3b82f6;
  width: 3px;
  height: 80px;
  box-shadow: 0 0 8px #3b82f6;
}
</style>