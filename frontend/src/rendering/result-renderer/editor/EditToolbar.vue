<template>
  <div class="edit-toolbar" :class="{ 'visible': isVisible, 'floating': floating }">
    <div class="toolbar-content">
      <!-- 左侧工具 -->
      <div class="toolbar-left">
        <div class="tool-group">
          <button class="tool-btn" @click="handleUndo" :disabled="!canUndo" title="撤销">
            <span class="tool-icon">↶</span>
            <span class="tool-text" v-if="showLabels">撤销</span>
          </button>
          <button class="tool-btn" @click="handleRedo" :disabled="!canRedo" title="重做">
            <span class="tool-icon">↷</span>
            <span class="tool-text" v-if="showLabels">重做</span>
          </button>
        </div>
        
        <div class="tool-divider"></div>
        
        <div class="tool-group">
          <button class="tool-btn" @click="handleCopy" title="复制">
            <span class="tool-icon">📋</span>
            <span class="tool-text" v-if="showLabels">复制</span>
          </button>
          <button class="tool-btn" @click="handlePaste" title="粘贴">
            <span class="tool-icon">📄</span>
            <span class="tool-text" v-if="showLabels">粘贴</span>
          </button>
          <button class="tool-btn" @click="handleCut" title="剪切">
            <span class="tool-icon">✂️</span>
            <span class="tool-text" v-if="showLabels">剪切</span>
          </button>
        </div>
        
        <div class="tool-divider"></div>
        
        <div class="tool-group" v-if="editType === 'text' || editType === 'markdown'">
          <button class="tool-btn" @click="handleFormat('bold')" title="粗体">
            <span class="tool-icon">B</span>
            <span class="tool-text" v-if="showLabels">粗体</span>
          </button>
          <button class="tool-btn" @click="handleFormat('italic')" title="斜体">
            <span class="tool-icon">I</span>
            <span class="tool-text" v-if="showLabels">斜体</span>
          </button>
          <button class="tool-btn" @click="handleFormat('code')" title="代码">
            <span class="tool-icon">`</span>
            <span class="tool-text" v-if="showLabels">代码</span>
          </button>
        </div>
      </div>
      
      <!-- 右侧工具 -->
      <div class="toolbar-right">
        <div class="tool-group">
          <button class="tool-btn" @click="handleSave" title="保存">
            <span class="tool-icon">💾</span>
            <span class="tool-text" v-if="showLabels">保存</span>
          </button>
          <button class="tool-btn danger" @click="handleCancel" title="取消">
            <span class="tool-icon">❌</span>
            <span class="tool-text" v-if="showLabels">取消</span>
          </button>
        </div>
        
        <div class="tool-divider"></div>
        
        <div class="tool-group">
          <button class="tool-btn" @click="toggleLabels" title="切换标签显示">
            <span class="tool-icon">{{ showLabels ? '🔤' : '🔡' }}</span>
          </button>
          <button class="tool-btn" @click="toggleFloating" title="切换浮动模式">
            <span class="tool-icon">{{ floating ? '📌' : '🔄' }}</span>
          </button>
        </div>
      </div>
    </div>
    
    <!-- 状态指示器 -->
    <div class="toolbar-status" v-if="statusMessage">
      <span class="status-icon">ℹ️</span>
      <span class="status-text">{{ statusMessage }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

// 定义props
interface Props {
  editType?: string
  canUndo?: boolean
  canRedo?: boolean
  isVisible?: boolean
  floating?: boolean
}

const props = defineProps<Props>()

// 定义事件
interface Emits {
  (e: 'undo', ...args: unknown[]): void
  (e: 'redo', ...args: unknown[]): void
  (e: 'copy', ...args: unknown[]): void
  (e: 'paste', ...args: unknown[]): void
  (e: 'cut', ...args: unknown[]): void
  (e: 'format', ...args: unknown[]): void
  (e: 'save', ...args: unknown[]): void
  (e: 'cancel', ...args: unknown[]): void
  (e: 'toggle-labels', ...args: unknown[]): void
  (e: 'toggle-floating', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

// 响应式数据
const showLabels = ref<boolean>(true)
const statusMessage = ref<string>('')
const statusTimeout = ref<unknown | null>(null)

// 计算属性
const toolbarClass = computed(() => {
  const classes = []
  if (props.isVisible) classes.push('visible')
  if (props.floating) classes.push('floating')
  return classes.join(' ')
})

// 方法
const handleUndo = () => {
  if (!props.canUndo) return
  emit('undo')
  showStatus('已撤销')
}

const handleRedo = () => {
  if (!props.canRedo) return
  emit('redo')
  showStatus('已重做')
}

const handleCopy = () => {
  emit('copy')
  showStatus('已复制到剪贴板')
}

const handlePaste = () => {
  emit('paste')
  showStatus('已粘贴')
}

const handleCut = () => {
  emit('cut')
  showStatus('已剪切')
}

const handleFormat = (formatType) => {
  emit('format', formatType)
  
  const formatLabels = {
    bold: '粗体',
    italic: '斜体',
    code: '代码',
    link: '链接',
    heading: '标题',
    list: '列表'
  }
  
  showStatus(`已应用${formatLabels[formatType] || formatType}格式`)
}

const handleSave = () => {
  emit('save')
  showStatus('已保存')
}

const handleCancel = () => {
  emit('cancel')
  showStatus('已取消编辑')
}

const toggleLabels = () => {
  showLabels.value = !showLabels.value
  emit('toggle-labels', showLabels.value)
  showStatus(showLabels.value ? '显示标签' : '隐藏标签')
}

const toggleFloating = () => {
  const newFloating = !props.floating
  emit('toggle-floating', newFloating)
  showStatus(newFloating ? '浮动模式' : '固定模式')
}

const showStatus = (message) => {
  statusMessage.value = message
  
  // 清除之前的定时器
  if (statusTimeout.value) {
    clearTimeout(statusTimeout.value)
  }
  
  // 设置新的定时器
  statusTimeout.value = setTimeout(() => {
    statusMessage.value = ''
    statusTimeout.value = null
  }, 2000)
}

// 清理定时器
const cleanup = () => {
  if (statusTimeout.value) {
    clearTimeout(statusTimeout.value)
    statusTimeout.value = null
  }
}

// 暴露方法
defineExpose({
  showStatus,
  toggleLabels: () => {
    toggleLabels()
    return showLabels.value
  },
  toggleFloating: () => {
    toggleFloating()
    return !props.floating
  }
})
</script>

<style scoped>
.edit-toolbar {
  width: 100%;
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.3s ease;
  opacity: 0;
  transform: translateY(-10px);
  pointer-events: none;
}

.edit-toolbar.visible {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.edit-toolbar.floating {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%) translateY(-10px);
  width: auto;
  min-width: 400px;
  max-width: 80%;
  z-index: 1000;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.edit-toolbar.floating.visible {
  transform: translateX(-50%) translateY(0);
}

.toolbar-content {
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-group {
  display: flex;
  gap: 4px;
}

.tool-divider {
  width: 1px;
  height: 24px;
  background-color: #334155;
}

.tool-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background-color: #334155;
  border: 1px solid #475569;
  border-radius: 4px;
  color: #cbd5e1;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.tool-btn:hover {
  background-color: #475569;
  border-color: #64748b;
}

.tool-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tool-btn:disabled:hover {
  background-color: #334155;
  border-color: #475569;
}

.tool-btn.danger {
  background-color: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.tool-btn.danger:hover {
  background-color: rgba(239, 68, 68, 0.3);
  border-color: rgba(239, 68, 68, 0.4);
}

.tool-icon {
  font-size: 14px;
  font-weight: 500;
}

.tool-text {
  font-size: 12px;
}

.toolbar-status {
  padding: 6px 12px;
  background-color: rgba(59, 130, 246, 0.1);
  border-top: 1px solid rgba(59, 130, 246, 0.3);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.status-icon {
  font-size: 12px;
}

.status-text {
  flex-grow: 1;
}
</style>