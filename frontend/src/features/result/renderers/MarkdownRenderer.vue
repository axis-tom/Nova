<template>
  <div class="markdown-renderer" :class="{ 'editing': isEditing }">
    <!-- 模式切换工具栏 -->
    <div class="mode-toolbar">
      <div class="toolbar-left">
        <span class="toolbar-icon">📝</span>
        <span class="toolbar-title">{{ result.content.title || 'Markdown内容' }}</span>
      </div>
      <div class="toolbar-right">
        <div class="mode-switch">
          <button 
            class="mode-btn" 
            :class="{ 'active': !isEditing }"
            @click="switchToView"
            title="预览模式"
          >
            <span class="mode-icon">👁️</span>
            <span class="mode-text">预览</span>
          </button>
          <button 
            class="mode-btn" 
            :class="{ 'active': isEditing }"
            @click="switchToEdit"
            title="编辑模式"
            v-if="editable"
          >
            <span class="mode-icon">✏️</span>
            <span class="mode-text">编辑</span>
          </button>
        </div>
        <div class="toolbar-actions" v-if="!isEditing">
          <button class="action-btn small" @click="handleCopy" title="复制">
            <span class="action-icon">📋</span>
          </button>
          <button class="action-btn small" @click="handleExport" title="导出">
            <span class="action-icon">⬇️</span>
          </button>
        </div>
      </div>
    </div>
    
    <!-- 编辑模式 -->
    <div v-if="isEditing" class="edit-mode">
      <div class="edit-container">
        <div class="edit-header">
          <span class="edit-icon">✏️</span>
          <span class="edit-title">编辑Markdown</span>
          <div class="edit-help">
            <button class="help-btn" @click="showHelp = !showHelp" title="Markdown语法帮助">
              <span class="help-icon">❓</span>
            </button>
          </div>
        </div>
        
        <!-- Markdown语法帮助 -->
        <div v-if="showHelp" class="markdown-help">
          <div class="help-content">
            <h4>Markdown语法参考</h4>
            <ul>
              <li><code># 标题</code> - 一级标题</li>
              <li><code>## 标题</code> - 二级标题</li>
              <li><code>**粗体**</code> - 粗体文本</li>
              <li><code>*斜体*</code> - 斜体文本</li>
              <li><code>`代码`</code> - 行内代码</li>
              <li><code>- 列表项</code> - 无序列表</li>
              <li><code>1. 列表项</code> - 有序列表</li>
              <li><code>[链接](url)</code> - 超链接</li>
              <li><code>![图片](url)</code> - 图片</li>
            </ul>
          </div>
        </div>
        
        <textarea
          ref="markdownAreaRef"
          v-model="editMarkdown"
          class="markdown-edit-area"
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
    </div>
    
    <!-- 预览模式 -->
    <div v-else class="view-mode">
      <div class="markdown-preview" v-html="renderedMarkdown"></div>
      <div class="preview-footer" v-if="result.meta">
        <span class="preview-meta">
          <span class="meta-icon">📏</span>
          <span class="meta-text">{{ markdownLength }} 字符</span>
        </span>
        <span class="preview-meta">
          <span class="meta-icon">🔄</span>
          <span class="meta-text">实时渲染</span>
        </span>
        <span class="preview-meta" v-if="result.meta.sourceNode">
          <span class="meta-icon">📌</span>
          <span class="meta-text">来源: {{ result.meta.sourceNode }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 配置marked
marked.setOptions({
  breaks: true,
  gfm: true,
  headerIds: true,
  mangle: false
})

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
const editMarkdown = ref('')
const showHelp = ref(false)
const markdownAreaRef = ref(null)

// 计算属性
const displayMarkdown = computed(() => {
  if (!props.result || !props.result.content) return ''
  return props.result.content.text || ''
})

const renderedMarkdown = computed(() => {
  const markdown = displayMarkdown.value
  if (!markdown) return '<p>暂无内容</p>'
  
  try {
    const html = marked(markdown)
    return DOMPurify.sanitize(html)
  } catch (error) {
    console.error('Markdown渲染错误:', error)
    return `<pre>${markdown}</pre>`
  }
})

const markdownLength = computed(() => {
  return displayMarkdown.value.length
})

const placeholder = computed(() => {
  return `输入Markdown内容...\n\n# 标题\n## 子标题\n\n**粗体** *斜体*\n\n- 列表项1\n- 列表项2\n\n\`代码\` [链接](https://example.com)`
})

// 监听结果变化
watch(() => props.result, (newResult) => {
  if (newResult && newResult.content) {
    editMarkdown.value = newResult.content.text || ''
  }
}, { immediate: true })

// 方法
const switchToEdit = () => {
  if (!props.editable) return
  
  editMarkdown.value = displayMarkdown.value
  isEditing.value = true
  showHelp.value = false
  
  // 聚焦到Markdown区域
  nextTick(() => {
    if (markdownAreaRef.value) {
      markdownAreaRef.value.focus()
      markdownAreaRef.value.select()
    }
  })
  
  // 发射编辑事件
  emit('edit', {
    type: 'markdown',
    originalText: displayMarkdown.value,
    editText: editMarkdown.value
  })
}

const switchToView = () => {
  isEditing.value = false
  showHelp.value = false
}

const handleSave = () => {
  if (!editMarkdown.value.trim()) {
    alert('Markdown内容不能为空')
    return
  }
  
  const savedData = {
    text: editMarkdown.value,
    title: props.result.content.title || 'Markdown内容',
    format: 'markdown'
  }
  
  isEditing.value = false
  showHelp.value = false
  
  // 发射保存事件
  emit('save', savedData)
}

const handleCancel = () => {
  isEditing.value = false
  showHelp.value = false
  editMarkdown.value = displayMarkdown.value
  
  // 发射取消事件
  emit('cancel')
}

const handleCopy = () => {
  if (!displayMarkdown.value) return
  
  try {
    navigator.clipboard.writeText(displayMarkdown.value)
    console.log('MarkdownRenderer: Markdown已复制到剪贴板')
    
    // 可以添加复制成功的提示
    // alert('Markdown已复制到剪贴板')
  } catch (error) {
    console.error('MarkdownRenderer: 复制失败', error)
  }
}

const handleExport = () => {
  if (!displayMarkdown.value) return
  
  try {
    const blob = new Blob([displayMarkdown.value], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `markdown-${props.result.id || 'content'}.md`
    a.click()
    URL.revokeObjectURL(url)
    
    console.log('MarkdownRenderer: Markdown已导出')
  } catch (error) {
    console.error('MarkdownRenderer: 导出失败', error)
  }
}

// 格式化Markdown（如果需要）
const formatMarkdown = (markdown) => {
  if (!markdown) return ''
  
  // 这里可以添加Markdown格式化逻辑
  // 例如：自动格式化标题、列表等
  
  return markdown
}

// 暴露方法
defineExpose({
  startEdit: switchToEdit,
  switchToView,
  copyMarkdown: handleCopy,
  exportMarkdown: handleExport,
  getMarkdownLength: () => markdownLength.value
})
</script>

<style scoped>
.markdown-renderer {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #1e293b;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.markdown-renderer.editing {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.5);
}

.mode-toolbar {
  padding: 12px 16px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-icon {
  font-size: 16px;
}

.toolbar-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mode-switch {
  display: flex;
  background-color: #334155;
  border-radius: 6px;
  border: 1px solid #475569;
  overflow: hidden;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background-color: transparent;
  border: none;
  color: #cbd5e1;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn:hover {
  background-color: #475569;
}

.mode-btn.active {
  background-color: #3b82f6;
  color: white;
}

.mode-icon {
  font-size: 14px;
}

.mode-text {
  font-size: 12px;
}

.toolbar-actions {
  display: flex;
  gap: 4px;
}

.edit-mode {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.edit-container {
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
  justify-content: space-between;
}

.edit-icon {
  font-size: 16px;
}

.edit-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
  flex-grow: 1;
  margin-left: 8px;
}

.edit-help {
  display: flex;
  align-items: center;
}

.help-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background-color: #334155;
  border: 1px solid #475569;
  border-radius: 4px;
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.2s;
}

.help-btn:hover {
  background-color: #475569;
  border-color: #64748b;
}

.help-icon {
  font-size: 14px;
}

.markdown-help {
  padding: 12px 16px;
  background-color: rgba(59, 130, 246, 0.1);
  border-bottom: 1px solid rgba(59, 130, 246, 0.3);
}

.help-content {
  font-size: 12px;
  color: #cbd5e1;
}

.help-content h4 {
  margin: 0 0 8px 0;
  font-size: 12px;
  font-weight: 600;
  color: #e2e8f0;
}

.help-content ul {
  margin: 0;
  padding-left: 16px;
}

.help-content li {
  margin-bottom: 4px;
}

.help-content code {
  background-color: rgba(148, 163, 184, 0.2);
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 11px;
}

.markdown-edit-area {
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

.markdown-edit-area:focus {
  outline: none;
}

.markdown-edit-area::placeholder {
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
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.markdown-preview {
  flex-grow: 1;
  padding: 16px;
  overflow-y: auto;
  color: #cbd5e1;
  font-size: 14px;
  line-height: 1.6;
}

.markdown-preview :deep(h1) {
  font-size: 24px;
  font-weight: 600;
  color: #e2e8f0;
  margin: 24px 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #334155;
}

.markdown-preview :deep(h2) {
  font-size: 20px;
  font-weight: 600;
  color: #e2e8f0;
  margin: 20px 0 12px 0;
}

.markdown-preview :deep(h3) {
  font-size: 18px;
  font-weight: 600;
  color: #e2e8f0;
  margin: 16px 0 10px 0;
}

.markdown-preview :deep(p) {
  margin: 0 0 16px 0;
}

.markdown-preview :deep(ul),
.markdown-preview :deep(ol) {
  margin: 0 0 16px 0;
  padding-left: 20px;
}

.markdown-preview :deep(li) {
  margin-bottom: 8px;
}

.markdown-preview :deep(strong) {
  font-weight: 600;
  color: #e2e8f0;
}

.markdown-preview :deep(em) {
  font-style: italic;
}

.markdown-preview :deep(code) {
  background-color: rgba(148, 163, 184, 0.2);
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
}

.markdown-preview :deep(pre) {
  background-color: #0f172a;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #334155;
  margin: 16px 0;
  overflow-x: auto;
}

.markdown-preview :deep(pre code) {
  background-color: transparent;
  padding: 0;
  border-radius: 0;
}

.markdown-preview :deep(a) {
  color: #3b82f6;
  text-decoration: none;
}

.markdown-preview :deep(a:hover) {
  text-decoration: underline;
}

.markdown-preview :deep(blockquote) {
  border-left: 4px solid #3b82f6;
  margin: 16px 0;
  padding-left: 16px;
  color: #94a3b8;
  font-style: italic;
}

.preview-footer {
  padding: 8px 16px;
  background-color: #0f172a;
  border-top: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-meta {
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
 