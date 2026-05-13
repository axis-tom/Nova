<template>
  <div class="inline-editor" :class="{ 'editing': isEditing }">
    <!-- 编辑模式 -->
    <div v-if="isEditing" class="editor-mode">
      <div class="editor-header">
        <span class="editor-icon">✏️</span>
        <span class="editor-title">编辑内容</span>
        <div class="editor-type">
          <span class="type-badge">{{ editType }}</span>
        </div>
      </div>
      
      <div class="editor-content">
        <!-- 文本编辑器 -->
        <textarea
          v-if="editType === 'text'"
          ref="editorRef"
          v-model="editValue"
          class="text-editor"
          :placeholder="placeholder"
          @keydown.ctrl.enter="handleSave"
          @keydown.esc="handleCancel"
        />
        
        <!-- Markdown编辑器 -->
        <div v-else-if="editType === 'markdown'" class="markdown-editor-container">
          <div class="editor-toolbar">
            <button class="tool-btn" @click="insertText('**', '**')" title="粗体">
              <span class="tool-icon">B</span>
            </button>
            <button class="tool-btn" @click="insertText('*', '*')" title="斜体">
              <span class="tool-icon">I</span>
            </button>
            <button class="tool-btn" @click="insertText('`', '`')" title="代码">
              <span class="tool-icon">`</span>
            </button>
            <button class="tool-btn" @click="insertText('# ', '')" title="标题">
              <span class="tool-icon">H</span>
            </button>
            <button class="tool-btn" @click="insertText('- ', '')" title="列表">
              <span class="tool-icon">•</span>
            </button>
            <button class="tool-btn" @click="insertText('[链接](', ')')" title="链接">
              <span class="tool-icon">🔗</span>
            </button>
          </div>
          <textarea
            ref="editorRef"
            v-model="editValue"
            class="markdown-editor"
            :placeholder="placeholder"
            @keydown.ctrl.enter="handleSave"
            @keydown.esc="handleCancel"
          />
        </div>
        
        <!-- JSON编辑器 -->
        <div v-else-if="editType === 'json'" class="json-editor-container">
          <div class="editor-toolbar">
            <button class="tool-btn" @click="formatJson" title="格式化JSON">
              <span class="tool-icon">🔄</span>
              <span class="tool-text">格式化</span>
            </button>
            <button class="tool-btn" @click="validateJson" title="验证JSON">
              <span class="tool-icon">✓</span>
              <span class="tool-text">验证</span>
            </button>
          </div>
          <textarea
            ref="editorRef"
            v-model="editValue"
            class="json-editor"
            :placeholder="placeholder"
            @keydown.ctrl.enter="handleSave"
            @keydown.esc="handleCancel"
          />
        </div>
        
        <!-- 通用编辑器 -->
        <textarea
          v-else
          ref="editorRef"
          v-model="editValue"
          class="generic-editor"
          :placeholder="placeholder"
          @keydown.ctrl.enter="handleSave"
          @keydown.esc="handleCancel"
        />
      </div>
      
      <div class="editor-footer">
        <div class="editor-stats">
          <span class="stat-item">
            <span class="stat-icon">📏</span>
            <span class="stat-text">{{ editValue.length }} 字符</span>
          </span>
          <span class="stat-item" v-if="editType === 'json'">
            <span class="stat-icon">📊</span>
            <span class="stat-text">{{ jsonLineCount }} 行</span>
          </span>
        </div>
        <div class="editor-actions">
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
    </div>
    
    <!-- 查看模式 -->
    <div v-else class="view-mode">
      <slot>
        <div class="default-view">
          <span class="view-icon">📝</span>
          <span class="view-text">点击编辑内容</span>
        </div>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'

// 定义props
interface Props {
  value?: string
  placeholder?: string
  editable?: boolean
}

const props = defineProps<Props>()

// 定义事件
interface Emits {
  (e: 'edit', ...args: unknown[]): void
  (e: 'save', ...args: unknown[]): void
  (e: 'cancel', ...args: unknown[]): void
  (e: 'update:value', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

// 响应式数据
const isEditing = ref<boolean>(false)
const editValue = ref<string>('')
const editType = ref(props.type)
const editorRef = ref<HTMLElement | null>(null)

// 计算属性
const jsonLineCount = computed(() => {
  if (editType.value !== 'json') return 0
  try {
    const json = JSON.parse(editValue.value)
    return JSON.stringify(json, null, 2).split('\n').length
  } catch {
    return editValue.value.split('\n').length
  }
})

// 监听值变化
watch(() => props.value, (newValue) => {
  if (typeof newValue === 'object') {
    editValue.value = JSON.stringify(newValue, null, 2)
  } else {
    editValue.value = String(newValue || '')
  }
}, { immediate: true })

// 方法
const startEdit = () => {
  if (!props.editable) return
  
  editType.value = props.type
  isEditing.value = true
  
  // 聚焦到编辑器
  nextTick(() => {
    if (editorRef.value) {
      editorRef.value.focus()
      editorRef.value.select()
    }
  })
  
  // 发射编辑事件
  emit('edit', {
    type: editType.value,
    value: editValue.value
  })
}

const handleSave = () => {
  if (!editValue.value.trim() && editType.value !== 'json') {
    alert('内容不能为空')
    return
  }
  
  let savedValue = editValue.value
  
  // 验证和格式化JSON
  if (editType.value === 'json') {
    try {
      const parsed = JSON.parse(editValue.value)
      savedValue = JSON.stringify(parsed, null, 2)
    } catch (error) {
      alert('JSON格式错误: ' + error.message)
      return
    }
  }
  
  isEditing.value = false
  
  // 发射保存事件
  emit('save', savedValue)
  emit('update:value', savedValue)
}

const handleCancel = () => {
  isEditing.value = false
  
  // 恢复原始值
  if (typeof props.value === 'object') {
    editValue.value = JSON.stringify(props.value, null, 2)
  } else {
    editValue.value = String(props.value || '')
  }
  
  // 发射取消事件
  emit('cancel')
}

const insertText = (prefix, suffix) => {
  if (!editorRef.value) return
  
  const textarea = editorRef.value
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const selectedText = editValue.value.substring(start, end)
  
  const newText = prefix + selectedText + suffix
  editValue.value = editValue.value.substring(0, start) + newText + editValue.value.substring(end)
  
  // 重新聚焦并设置光标位置
  nextTick(() => {
    textarea.focus()
    const newCursorPos = start + prefix.length + selectedText.length + suffix.length
    textarea.setSelectionRange(newCursorPos, newCursorPos)
  })
}

const formatJson = () => {
  try {
    const parsed = JSON.parse(editValue.value)
    editValue.value = JSON.stringify(parsed, null, 2)
  } catch (error) {
    alert('JSON格式错误: ' + error.message)
  }
}

const validateJson = () => {
  try {
    JSON.parse(editValue.value)
    alert('JSON格式正确')
  } catch (error) {
    alert('JSON格式错误: ' + error.message)
  }
}

// 暴露方法
defineExpose({
  startEdit,
  save: handleSave,
  cancel: handleCancel,
  getValue: () => editValue.value,
  getType: () => editType.value
})
</script>

<style scoped>
.inline-editor {
  width: 100%;
  height: 100%;
  border-radius: 6px;
  border: 1px solid #334155;
  background-color: #1e293b;
  transition: all 0.2s;
}

.inline-editor.editing {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.5);
}

.editor-mode {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.editor-header {
  padding: 12px 16px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  gap: 12px;
}

.editor-icon {
  font-size: 16px;
}

.editor-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
  flex-grow: 1;
}

.editor-type {
  display: flex;
  align-items: center;
}

.type-badge {
  font-size: 11px;
  color: #94a3b8;
  background-color: rgba(148, 163, 184, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}

.editor-content {
  flex-grow: 1;
  overflow: hidden;
}

.text-editor,
.markdown-editor,
.json-editor,
.generic-editor {
  width: 100%;
  height: 100%;
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

.text-editor:focus,
.markdown-editor:focus,
.json-editor:focus,
.generic-editor:focus {
  outline: none;
}

.text-editor::placeholder,
.markdown-editor::placeholder,
.json-editor::placeholder,
.generic-editor::placeholder {
  color: #64748b;
}

.markdown-editor-container,
.json-editor-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.editor-toolbar {
  padding: 8px 16px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
  display: flex;
  gap: 8px;
}

.tool-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background-color: #334155;
  border: 1px solid #475569;
  border-radius: 4px;
  color: #cbd5e1;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.tool-btn:hover {
  background-color: #475569;
  border-color: #64748b;
}

.tool-icon {
  font-size: 12px;
  font-weight: 600;
}

.tool-text {
  font-size: 11px;
}

.markdown-editor,
.json-editor {
  flex-grow: 1;
}

.editor-footer {
  padding: 12px 16px;
  background-color: #0f172a;
  border-top: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.editor-stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-icon {
  font-size: 12px;
  opacity: 0.7;
}

.stat-text {
  font-size: 12px;
  color: #94a3b8;
}

.editor-actions {
  display: flex;
  gap: 8px;
}

.view-mode {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s;
}

.view-mode:hover {
  background-color: rgba(148, 163, 184, 0.05);
}

.default-view {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
}

.view-icon {
  font-size: 16px;
}

.view-text {
  font-size: 14px;
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