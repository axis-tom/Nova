<template>
  <div class="text-renderer" :class="{ 'editing': isEditing }">
    <!-- 编辑模式 -->
    <div v-if="isEditing" class="edit-mode">
      <div class="edit-header">
        <span class="edit-icon">✏️</span>
        <span class="edit-title">编辑文本</span>
      </div>
      <textarea
        ref="textAreaRef"
        v-model="editText"
        class="text-edit-area"
        :placeholder="placeholder"
        @keydown.ctrl.enter="handleSave"
        @keydown.esc="handleCancel"
      />
      <div class="edit-actions">
        <button class="action-btn secondary" @click="handleCancel">
          <span class="action-icon">❌</span>
          <span>取消</span>
        </button>
        <button class="action-btn primary" @click="handleSave">
          <span class="action-icon">💾</span>
          <span>保存</span>
        </button>
      </div>
    </div>
    
    <!-- 查看模式 -->
    <div v-else class="view-mode">
      <div class="text-header">
        <span class="text-icon">📄</span>
        <span class="text-title">{{ result.content.title || '文本内容' }}</span>
        <div class="text-actions" v-if="editable">
          <button class="action-btn small" @click="handleStartEdit" title="编辑">
            <span class="action-icon">✏️</span>
          </button>
          <button class="action-btn small" @click="handleCopy" title="复制">
            <span class="action-icon">📋</span>
          </button>
        </div>
      </div>
      <div class="text-content">
        <pre>{{ displayText }}</pre>
      </div>
      <div class="text-footer" v-if="result.meta">
        <span class="text-meta">
          <span class="meta-icon">📏</span>
          <span class="meta-text">{{ textLength }} 字符</span>
        </span>
        <span class="text-meta" v-if="result.meta.sourceNode">
          <span class="meta-icon">📌</span>
          <span class="meta-text">来源: {{ result.meta.sourceNode }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'

// 定义props
const props = defineProps({
  result: {
    type: Object,
    required: true
  },
  editable: {
    type: Boolean,
    default: true
  }
})

// 定义事件
const emit = defineEmits(['edit', 'save', 'cancel'])

// 响应式数据
const isEditing = ref(false)
const editText = ref('')
const textAreaRef = ref(null)

// 计算属性
const displayText = computed(() => {
  if (!props.result || !props.result.content) return ''
  return props.result.content.text || ''
})

const textLength = computed(() => {
  return displayText.value.length
})

const placeholder = computed(() => {
  return `输入文本内容...`
})

// 监听结果变化
watch(() => props.result, (newResult) => {
  if (newResult && newResult.content) {
    editText.value = newResult.content.text || ''
  }
}, { immediate: true })

// 方法
const handleStartEdit = () => {
  if (!props.editable) return
  
  editText.value = displayText.value
  isEditing.value = true
  
  // 聚焦到文本区域
  nextTick(() => {
    if (textAreaRef.value) {
      textAreaRef.value.focus()
      textAreaRef.value.select()
    }
  })
  
  // 发射编辑事件
  emit('edit', {
    type: 'text',
    originalText: displayText.value,
    editText: editText.value
  })
}

const handleSave = () => {
  if (!editText.value.trim()) {
    alert('文本内容不能为空')
    return
  }
  
  const savedData = {
    text: editText.value,
    title: props.result.content.title || '文本内容'
  }
  
  isEditing.value = false
  
  // 发射保存事件
  emit('save', savedData)
}

const handleCancel = () => {
  isEditing.value = false
  editText.value = displayText.value
  
  // 发射取消事件
  emit('cancel')
}

const handleCopy = () => {
  if (!displayText.value) return
  
  try {
    navigator.clipboard.writeText(displayText.value)
    console.log('TextRenderer: 文本已复制到剪贴板')
    
    // 可以添加复制成功的提示
    // alert('文本已复制到剪贴板')
  } catch (error) {
    console.error('TextRenderer: 复制失败', error)
  }
}

// 格式化文本（如果需要）
const formatText = (text) => {
  if (!text) return ''
  
  // 这里可以添加文本格式化逻辑
  // 例如：自动换行、缩进等
  
  return text
}

// 暴露方法
defineExpose({
  startEdit: handleStartEdit,
  copyText: handleCopy,
  getTextLength: () => textLength.value
})
</script>

<style scoped>
.text-renderer {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #1e293b;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.text-renderer.editing {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.5);
}

.edit-mode {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.edit-header {
  padding: 12px 16px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  gap: 8px;
}

.edit-icon {
  font-size: 16px;
}

.edit-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.text-edit-area {
  flex-grow: 1;
  padding: 16px;
  background-color: transparent;
  border: none;
  color: #cbd5e1;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  outline: none;
}

.text-edit-area:focus {
  outline: none;
}

.text-edit-area::placeholder {
  color: #64748b;
}

.edit-actions {
  padding: 12px 16px;
  background-color: #0f172a;
  border-top: 1px solid #334155;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.view-mode {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.text-header {
  padding: 12px 16px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.text-icon {
  font-size: 16px;
}

.text-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
  flex-grow: 1;
  margin-left: 8px;
}

.text-actions {
  display: flex;
  gap: 4px;
}

.text-content {
  flex-grow: 1;
  padding: 16px;
  overflow-y: auto;
}

.text-content pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  line-height: 1.5;
  color: #cbd5e1;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.text-footer {
  padding: 8px 16px;
  background-color: #0f172a;
  border-top: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.text-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}

.meta-icon {
  font-size: 12px;
  opacity: 0.7;
}

.meta-text {
  font-size: 12px;
  color: #94a3b8;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background-color: #334155;
  border: 1px solid #475569;
  border-radius: 6px;
  color: #cbd5e1;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background-color: #475569;
  border-color: #64748b;
}

.action-btn.small {
  padding: 6px 10px;
}

.action-btn.primary {
  background-color: #3b82f6;
  border-color: #3b82f6;
  color: white;
}

.action-btn.primary:hover {
  background-color: #2563eb;
  border-color: #2563eb;
}

.action-btn.secondary {
  background-color: #475569;
  border-color: #64748b;
}

.action-btn.secondary:hover {
  background-color: #64748b;
  border-color: #94a3b8;
}

.action-icon {
  font-size: 14px;
}
</style>