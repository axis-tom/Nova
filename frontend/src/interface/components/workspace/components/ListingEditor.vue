<template>
  <div class="listing-editor">
    <!-- 编辑器头部 -->
    <div class="editor-header">
      <div class="header-left">
        <span class="header-icon">📝</span>
        <div class="header-info">
          <div class="header-title">Listing编辑器</div>
          <div class="header-subtitle">编辑AI生成的电商文案</div>
        </div>
      </div>
      <div class="header-right">
        <div class="editor-stats">
          <span class="stat-item">
            <span class="stat-icon">📏</span>
            <span class="stat-text">{{ characterCount }} 字</span>
          </span>
          <span class="stat-item">
            <span class="stat-icon">⏱️</span>
            <span class="stat-text">{{ wordCount }} 词</span>
          </span>
        </div>
      </div>
    </div>

    <!-- 编辑器工具栏 -->
    <div class="editor-toolbar">
      <div class="toolbar-group">
        <button 
          v-for="format in textFormats" 
          :key="format.name"
          class="toolbar-btn"
          :class="{ active: activeFormat === format.name }"
          @click="handleFormat(format.name)"
          :title="format.title"
        >
          <span class="toolbar-icon">{{ format.icon }}</span>
        </button>
      </div>
      <div class="toolbar-group">
        <button 
          class="toolbar-btn"
          @click="handleAIEnhance"
          title="AI增强"
        >
          <span class="toolbar-icon">✨</span>
          <span class="toolbar-text">AI增强</span>
        </button>
        <button 
          class="toolbar-btn"
          @click="handleSEOOptimize"
          title="SEO优化"
        >
          <span class="toolbar-icon">🔍</span>
          <span class="toolbar-text">SEO优化</span>
        </button>
      </div>
    </div>

    <!-- 编辑器主体 -->
    <div class="editor-main">
      <div class="editor-area">
        <textarea
          ref="textareaRef"
          v-model="localContent"
          class="editor-textarea"
          placeholder="在这里编辑Listing文案..."
          @input="handleInput"
          @keydown="handleKeydown"
        ></textarea>
        
        <!-- 实时预览 -->
        <div class="editor-preview" v-if="showPreview">
          <div class="preview-header">
            <span class="preview-icon">👁️</span>
            <span class="preview-title">实时预览</span>
          </div>
          <div class="preview-content" v-html="formattedPreview"></div>
        </div>
      </div>

      <!-- 编辑器侧边栏 -->
      <div class="editor-sidebar">
        <!-- SEO建议 -->
        <div class="sidebar-section">
          <div class="section-header">
            <span class="section-icon">🔍</span>
            <span class="section-title">SEO建议</span>
          </div>
          <div class="section-content">
            <div class="seo-score">
              <div class="score-circle" :style="seoScoreStyle">
                <span class="score-value">{{ seoScore }}</span>
              </div>
              <div class="score-label">SEO评分</div>
            </div>
            <div class="seo-suggestions">
              <div 
                v-for="suggestion in seoSuggestions" 
                :key="suggestion.id"
                class="suggestion-item"
                :class="{ completed: suggestion.completed }"
              >
                <span class="suggestion-icon">{{ suggestion.completed ? '✅' : '📌' }}</span>
                <span class="suggestion-text">{{ suggestion.text }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 关键词分析 -->
        <div class="sidebar-section">
          <div class="section-header">
            <span class="section-icon">🏷️</span>
            <span class="section-title">关键词分析</span>
          </div>
          <div class="section-content">
            <div class="keyword-list">
              <div 
                v-for="keyword in keywords" 
                :key="keyword.word"
                class="keyword-item"
                :class="{ primary: keyword.type === 'primary' }"
              >
                <span class="keyword-word">{{ keyword.word }}</span>
                <span class="keyword-count">{{ keyword.count }}次</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑器底部 -->
    <div class="editor-footer">
      <div class="footer-left">
        <div class="editor-options">
          <label class="option-item">
            <input type="checkbox" v-model="autoSave" />
            <span class="option-text">自动保存</span>
          </label>
          <label class="option-item">
            <input type="checkbox" v-model="showPreview" />
            <span class="option-text">实时预览</span>
          </label>
        </div>
      </div>
      <div class="footer-right">
        <button class="footer-btn secondary" @click="handleReset">
          <span class="btn-icon">↩️</span>
          <span class="btn-text">重置</span>
        </button>
        <button class="footer-btn primary" @click="handleSave">
          <span class="btn-icon">💾</span>
          <span class="btn-text">保存更改</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'

interface Props {
  content?: string
}

const props = defineProps<Props>()

interface Emits {
  (e: 'update', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

// 响应式数据
const localContent = ref(
  props.content !== null && typeof props.content === 'object'
    ? JSON.stringify(props.content, null, 2)
    : String(props.content || '')
)
const activeFormat = ref<HTMLElement | null>(null)
const showPreview = ref<boolean>(true)
const autoSave = ref<boolean>(true)

// 引用
const textareaRef = ref<HTMLElement | null>(null)

// 文本格式选项
const textFormats = [
  { name: 'bold', icon: 'B', title: '加粗' },
  { name: 'italic', icon: 'I', title: '斜体' },
  { name: 'underline', icon: 'U', title: '下划线' },
  { name: 'heading', icon: 'H', title: '标题' },
  { name: 'bullet', icon: '•', title: '列表' }
]

// 计算属性
const characterCount = computed(() => {
  return localContent.value.length
})

const wordCount = computed(() => {
  return localContent.value.trim().split(/\s+/).filter(word => word.length > 0).length
})

const seoScore = computed(() => {
  // 简单的SEO评分逻辑
  const score = Math.min(100, 
    Math.floor(wordCount.value / 2) + 
    (localContent.value.includes('$') ? 10 : 0) +
    (localContent.value.includes('%') ? 10 : 0) +
    (localContent.value.match(/[A-Z]/g)?.length || 0)
  )
  return Math.max(0, score)
})

const seoScoreStyle = computed(() => {
  const hue = seoScore.value * 1.2 // 0-100分对应0-120度色相
  return {
    background: `conic-gradient(#10b981 0% ${seoScore.value}%, #334155 ${seoScore.value}% 100%)`
  }
})

const seoSuggestions = computed(() => {
  const suggestions = [
    { id: 1, text: '添加主要关键词', completed: localContent.value.length > 50 },
    { id: 2, text: '包含价格信息', completed: localContent.value.includes('$') },
    { id: 3, text: '添加CTA（行动号召）', completed: /(立即|马上|点击|购买)/.test(localContent.value) },
    { id: 4, text: '优化标题长度', completed: localContent.value.split('\n')[0]?.length > 10 && localContent.value.split('\n')[0]?.length < 60 },
    { id: 5, text: '添加产品特性', completed: (localContent.value.match(/[•\-*]/g) || []).length >= 3 }
  ]
  return suggestions
})

const keywords = computed(() => {
  // 简单的关键词提取逻辑
  const words = localContent.value.toLowerCase().match(/\b\w{3,}\b/g) || []
  const frequency = {}
  words.forEach(word => {
    frequency[word] = (frequency[word] || 0) + 1
  })
  
  const sorted = Object.entries(frequency)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([word, count], index) => ({
      word,
      count,
      type: index < 2 ? 'primary' : 'secondary'
    }))
  
  return sorted
})

const formattedPreview = computed(() => {
  let html = localContent.value
  
  // 简单的格式化转换
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>')
  html = html.replace(/_(.*?)_/g, '<u>$1</u>')
  html = html.replace(/^# (.*)$/gm, '<h3>$1</h3>')
  html = html.replace(/^- (.*)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>)/g, '<ul>$1</ul>')
  html = html.replace(/\n/g, '<br>')
  
  return html
})

// 方法
const handleInput = () => {
  if (autoSave.value) {
    emit('update', localContent.value)
  }
}

const handleKeydown = (event) => {
  // 快捷键支持
  if (event.ctrlKey || event.metaKey) {
    switch (event.key) {
      case 'b':
        event.preventDefault()
        handleFormat('bold')
        break
      case 'i':
        event.preventDefault()
        handleFormat('italic')
        break
      case 'u':
        event.preventDefault()
        handleFormat('underline')
        break
      case 's':
        event.preventDefault()
        handleSave()
        break
    }
  }
}

const handleFormat = (format) => {
  if (!textareaRef.value) return
  
  const textarea = textareaRef.value
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const selectedText = localContent.value.substring(start, end)
  
  let formattedText = selectedText
  let newCursorPos = end
  
  switch (format) {
    case 'bold':
      formattedText = `**${selectedText}**`
      newCursorPos = start + formattedText.length
      break
    case 'italic':
      formattedText = `*${selectedText}*`
      newCursorPos = start + formattedText.length
      break
    case 'underline':
      formattedText = `_${selectedText}_`
      newCursorPos = start + formattedText.length
      break
    case 'heading':
      formattedText = `# ${selectedText}`
      newCursorPos = start + formattedText.length
      break
    case 'bullet':
      formattedText = `- ${selectedText}`
      newCursorPos = start + formattedText.length
      break
  }
  
  localContent.value = 
    localContent.value.substring(0, start) + 
    formattedText + 
    localContent.value.substring(end)
  
  // 恢复光标位置
  nextTick(() => {
    textarea.focus()
    textarea.setSelectionRange(newCursorPos, newCursorPos)
  })
  
  activeFormat.value = format
  emit('update', localContent.value)
}

const handleAIEnhance = () => {
  // 模拟AI增强
  const enhanced = localContent.value + '\n\n✨ AI增强：优化了表达方式和结构，提升了可读性和转化率。'
  localContent.value = enhanced
  emit('update', localContent.value)
}

const handleSEOOptimize = () => {
  // 模拟SEO优化
  const optimized = localContent.value + '\n\n🔍 SEO优化：添加了相关关键词，优化了标题和描述。'
  localContent.value = optimized
  emit('update', localContent.value)
}

const handleSave = () => {
  emit('update', localContent.value)
  // 可以添加保存成功的反馈
  console.log('内容已保存')
}

const handleReset = () => {
  localContent.value = props.content
  emit('update', localContent.value)
}

// 监听props变化
watch(() => props.content, (newContent) => {
  if (newContent !== localContent.value) {
    localContent.value = newContent
  }
})
</script>

<style scoped>
.listing-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #0f172a;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.editor-header {
  padding: 12px 16px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  font-size: 20px;
}

.header-info {
  display: flex;
  flex-direction: column;
}

.header-title {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 2px;
}

.header-subtitle {
  font-size: 12px;
  color: #94a3b8;
}

.header-right {
  display: flex;
  align-items: center;
}

.editor-stats {
  display: flex;
  gap: 12px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background-color: #0f172a;
  border-radius: 4px;
  border: 1px solid #334155;
}

.stat-icon {
  font-size: 12px;
}

.stat-text {
  font-size: 11px;
  color: #94a3b8;
}

.editor-toolbar {
  padding: 8px 16px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
  display: flex;
  gap: 16px;
}

.toolbar-group {
  display: flex;
  gap: 4px;
  align-items: center;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  background-color: #2d3748;
  border-color: #475569;
  color: #cbd5e1;
}

.toolbar-btn.active {
  background-color: #3b82f6;
  border-color: #3b82f6;
  color: white;
}

.toolbar-icon {
  font-size: 12px;
  font-weight: 500;
}

.toolbar-text {
  font-size: 11px;
}

.editor-main {
  flex-grow: 1;
  display: flex;
  overflow: hidden;
}

.editor-area {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 16px;
  overflow: hidden;
}

.editor-textarea {
  flex-grow: 1;
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 12px;
  color: #e2e8f0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
}

.editor-textarea:focus {
  border-color: #3b82f6;
}

.editor-textarea::placeholder {
  color: #64748b;
}

.editor-preview {
  flex-shrink: 0;
  max-height: 200px;
  overflow-y: auto;
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 12px;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.preview-icon {
  font-size: 14px;
}

.preview-title {
  font-size: 12px;
  font-weight: 500;
  color: #94a3b8;
}

.preview-content {
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.5;
}

.preview-content :deep(h3) {
  font-size: 16px;
  font-weight: 600;
  color: #e2e8f0;
  margin: 8px 0;
}

.preview-content :deep(strong) {
  font-weight: 600;
  color: #f1f5f9;
}

.preview-content :deep(em) {
  font-style: italic;
}

.editor-sidebar {
  width: 260px;
  padding: 16px;
  border-left: 1px solid #334155;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.sidebar-section {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
}

.section-header {
  padding: 10px 14px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-icon {
  font-size: 14px;
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  color: #e2e8f0;
}

.section-content {
  padding: 14px;
}

.seo-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 16px;
}

.score-circle {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: conic-gradient(#10b981 0%, #334155 0%);
  margin-bottom: 8px;
}

.score-value {
  font-size: 24px;
  font-weight: 700;
  color: #e2e8f0;
  background-color: #0f172a;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.score-label {
  font-size: 12px;
  color: #94a3b8;
}

.seo-suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.suggestion-item.completed {
  color: #10b981;
}

.suggestion-icon {
  font-size: 12px;
}

.suggestion-text {
  flex: 1;
}

.keyword-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.keyword-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #334155;
  font-size: 12px;
}

.keyword-item.primary .keyword-word {
  color: #3b82f6;
  font-weight: 500;
}

.keyword-word {
  color: #cbd5e1;
}

.keyword-count {
  color: #94a3b8;
}

.editor-footer {
  padding: 12px 16px;
  background-color: #1e293b;
  border-top: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-left {
  display: flex;
  align-items: center;
}

.editor-options {
  display: flex;
  gap: 16px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.option-item input[type="checkbox"] {
  accent-color: #3b82f6;
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.option-text {
  font-size: 12px;
  color: #94a3b8;
}

.footer-right {
  display: flex;
  gap: 8px;
}

.footer-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.footer-btn.primary {
  background-color: #3b82f6;
  color: white;
  border-color: #2563eb;
}

.footer-btn.primary:hover {
  background-color: #2563eb;
}

.footer-btn.secondary {
  background-color: #0f172a;
  border-color: #334155;
  color: #cbd5e1;
}

.footer-btn.secondary:hover {
  background-color: #1e293b;
  border-color: #475569;
}

.btn-icon {
  font-size: 12px;
}

.btn-text {
  font-size: 12px;
}
</style>