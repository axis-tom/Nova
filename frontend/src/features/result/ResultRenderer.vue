<template>
  <div class="result-renderer">
    <!-- 动态组件渲染 -->
    <component
      :is="rendererComponent"
      v-if="rendererComponent && result"
      :result="result"
      :editable="result.editable"
      @edit="handleEdit"
      @save="handleSave"
      @cancel="handleCancel"
    />
    
    <!-- 未知类型提示 -->
    <div v-else-if="result" class="unknown-type">
      <div class="unknown-icon">❓</div>
      <div class="unknown-title">未知结果类型</div>
      <div class="unknown-message">
        无法渲染类型为 "{{ result.type }}" 的结果
      </div>
      <div class="unknown-actions">
        <button class="action-btn" @click="handleViewRaw">
          <span class="action-icon">👁️</span>
          <span>查看原始数据</span>
        </button>
      </div>
    </div>
    
    <!-- 加载状态 -->
    <div v-else class="loading">
      <div class="loading-spinner"></div>
      <div class="loading-text">加载渲染器...</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, defineAsyncComponent } from 'vue'

// 定义props
const props = defineProps({
  result: {
    type: Object,
    required: true
  }
})

// 定义事件
const emit = defineEmits(['edit', 'save', 'cancel'])

// 渲染器映射
const rendererMap = {
  text: defineAsyncComponent(() => import('./renderers/TextRenderer.vue')),
  markdown: defineAsyncComponent(() => import('./renderers/MarkdownRenderer.vue')),
  table: defineAsyncComponent(() => import('./renderers/TableRenderer.vue')),
  chart: defineAsyncComponent(() => import('./renderers/ChartRenderer.vue')),
  image: defineAsyncComponent(() => import('./renderers/ImageCompareRenderer.vue')),
  composite: defineAsyncComponent(() => import('./renderers/CompositeRenderer.vue')),
  json: defineAsyncComponent(() => import('./renderers/JsonRenderer.vue'))
}

// 计算属性
const rendererComponent = computed(() => {
  if (!props.result || !props.result.type) {
    return null
  }
  
  const type = props.result.type.toLowerCase()
  return rendererMap[type] || null
})

// 监听结果变化
watch(() => props.result, (newResult) => {
  if (newResult) {
    console.log(`ResultRenderer: 渲染类型 "${newResult.type}" 的结果`)
  }
}, { immediate: true })

// 事件处理
const handleEdit = (editData) => {
  console.log('ResultRenderer: 编辑请求', editData)
  emit('edit', editData)
}

const handleSave = (savedData) => {
  console.log('ResultRenderer: 保存请求', savedData)
  emit('save', savedData)
}

const handleCancel = () => {
  console.log('ResultRenderer: 取消编辑')
  emit('cancel')
}

const handleViewRaw = () => {
  if (!props.result) return
  
  console.log('ResultRenderer: 查看原始数据', props.result)
  
  // 在新窗口或弹窗中显示原始数据
  const rawData = JSON.stringify(props.result, null, 2)
  const blob = new Blob([rawData], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `result-${props.result.id}-raw.json`
  a.click()
  URL.revokeObjectURL(url)
}

// 获取支持的渲染器类型
const getSupportedTypes = () => {
  return Object.keys(rendererMap)
}

// 暴露方法
defineExpose({
  getSupportedTypes
})
</script>

<style scoped>
.result-renderer {
  height: 100%;
  width: 100%;
}

.unknown-type {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #94a3b8;
  padding: 40px;
}

.unknown-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.unknown-title {
  font-size: 18px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.unknown-message {
  font-size: 14px;
  max-width: 400px;
  line-height: 1.5;
  margin-bottom: 20px;
  background-color: rgba(148, 163, 184, 0.1);
  padding: 12px;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.unknown-actions {
  margin-top: 16px;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #94a3b8;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(148, 163, 184, 0.3);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
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

.action-icon {
  font-size: 14px;
}
</style>