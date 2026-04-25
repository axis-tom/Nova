<template>
  <div class="image-renderer">
    <div class="image-header">
      <div class="header-left">
        <span class="header-icon">🖼️</span>
        <span class="header-title">{{ result.content.title || '图片对比' }}</span>
        <span class="image-count" v-if="images.length > 0">
          {{ images.length }} 张图片
        </span>
      </div>
      <div class="header-right">
        <div class="header-actions">
          <button class="action-btn small" @click="handleDownloadAll" title="下载所有图片">
            <span class="action-icon">⬇️</span>
          </button>
          <button class="action-btn small" @click="toggleViewMode" title="切换视图模式">
            <span class="action-icon">🔄</span>
          </button>
        </div>
      </div>
    </div>
    
    <div class="image-container">
      <div v-if="images.length === 0" class="no-images">
        <div class="no-images-icon">🖼️</div>
        <div class="no-images-title">暂无图片</div>
        <div class="no-images-description">
          图片数据为空或格式不正确
        </div>
      </div>
      
      <div v-else-if="viewMode === 'grid'" class="image-grid">
        <div v-for="(image, index) in images" :key="index" class="image-item">
          <div class="image-wrapper">
            <img :src="getImageUrl(image)" :alt="`图片 ${index + 1}`" class="grid-image" />
            <div class="image-overlay">
              <div class="image-info">
                <span class="info-text">图片 {{ index + 1 }}</span>
                <span class="info-size" v-if="image.size">{{ formatSize(image.size) }}</span>
              </div>
              <div class="image-actions">
                <button class="action-btn small" @click="handleViewImage(index)" title="查看大图">
                  <span class="action-icon">👁️</span>
                </button>
                <button class="action-btn small" @click="handleDownloadImage(index)" title="下载图片">
                  <span class="action-icon">⬇️</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div v-else-if="viewMode === 'compare'" class="image-compare">
        <div class="compare-placeholder">
          <div class="placeholder-icon">⚖️</div>
          <div class="placeholder-title">图片对比视图</div>
          <div class="placeholder-description">
            这是一个图片对比渲染器占位符。实际实现需要集成图片对比库。
          </div>
          <div class="compare-info">
            <div class="info-item">
              <span class="info-label">对比模式:</span>
              <span class="info-value">滑块对比</span>
            </div>
            <div class="info-item">
              <span class="info-label">图片数量:</span>
              <span class="info-value">{{ images.length }}</span>
            </div>
            <div class="info-item" v-if="result.content.comparison">
              <span class="info-label">对比类型:</span>
              <span class="info-value">{{ result.content.comparison.type || '默认' }}</span>
            </div>
          </div>
        </div>
      </div>
      
      <div v-else class="image-slideshow">
        <div class="slideshow-placeholder">
          <div class="placeholder-icon">🎞️</div>
          <div class="placeholder-title">幻灯片视图</div>
          <div class="placeholder-description">
            这是一个幻灯片视图占位符。实际实现需要集成幻灯片组件。
          </div>
          <div class="slideshow-controls">
            <button class="action-btn" @click="prevImage" :disabled="currentSlide === 0">
              <span class="action-icon">⬅️</span>
              <span>上一张</span>
            </button>
            <div class="slide-info">
              第 {{ currentSlide + 1 }} / {{ images.length }} 张
            </div>
            <button class="action-btn" @click="nextImage" :disabled="currentSlide === images.length - 1">
              <span class="action-icon">➡️</span>
              <span>下一张</span>
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <div class="image-footer">
      <div class="footer-left">
        <div class="image-meta">
          <span class="meta-item">
            <span class="meta-icon">🖼️</span>
            <span class="meta-text">视图模式: {{ getViewModeLabel() }}</span>
          </span>
          <span class="meta-item" v-if="result.meta.sourceNode">
            <span class="meta-icon">📌</span>
            <span class="meta-text">来源: {{ result.meta.sourceNode }}</span>
          </span>
        </div>
      </div>
      <div class="footer-right">
        <div class="view-mode-selector">
          <button class="mode-btn" :class="{ 'active': viewMode === 'grid' }" @click="viewMode = 'grid'" title="网格视图">
            <span class="mode-icon">⏹️</span>
          </button>
          <button class="mode-btn" :class="{ 'active': viewMode === 'compare' }" @click="viewMode = 'compare'" title="对比视图">
            <span class="mode-icon">⚖️</span>
          </button>
          <button class="mode-btn" :class="{ 'active': viewMode === 'slideshow' }" @click="viewMode = 'slideshow'" title="幻灯片视图">
            <span class="mode-icon">🎞️</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

// 定义props
interface Props {
  result: Record<string, unknown>
  editable?: boolean
}


const props = defineProps<Props>()

// 定义事件
interface Emits {
  (e: 'edit', ...args: unknown[]): void
  (e: 'save', ...args: unknown[]): void
  (e: 'cancel', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

// 响应式数据
const viewMode = ref<string>('grid')
const currentSlide = ref<number>(0)

// 计算属性
const images = computed(() => {
  if (!props.result || !props.result.content) return []
  return props.result.content.images || []
})

// 方法
const getImageUrl = (image) => {
  if (typeof image === 'string') return image
  if (image && image.url) return image.url
  if (image && image.data) return `data:image/png;base64,${image.data}`
  return ''
}

const formatSize = (bytes) => {
  if (!bytes) return '未知大小'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const getViewModeLabel = () => {
  const modeLabels = {
    grid: '网格',
    compare: '对比',
    slideshow: '幻灯片'
  }
  return modeLabels[viewMode.value] || viewMode.value
}

const toggleViewMode = () => {
  const modes = ['grid', 'compare', 'slideshow']
  const currentIndex = modes.indexOf(viewMode.value)
  const nextIndex = (currentIndex + 1) % modes.length
  viewMode.value = modes[nextIndex]
}

const handleViewImage = (index) => {
  console.log('ImageCompareRenderer: 查看图片', index)
  const image = images.value[index]
  emit('edit', {
    type: 'image_view',
    imageIndex: index,
    imageData: image
  })
}

const handleDownloadImage = (index) => {
  const image = images.value[index]
  const url = getImageUrl(image)
  
  if (!url) {
    console.error('ImageCompareRenderer: 无法获取图片URL')
    return
  }
  
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = `image-${props.result.id || 'unknown'}-${index + 1}.png`
    a.click()
    console.log('ImageCompareRenderer: 图片已下载')
  } catch (error) {
    console.error('ImageCompareRenderer: 下载失败', error)
  }
}

const handleDownloadAll = () => {
  if (images.value.length === 0) return
  
  console.log('ImageCompareRenderer: 下载所有图片')
  // 实际实现中，这里可以批量下载所有图片
  alert('批量下载功能需要实际实现')
}

const prevImage = () => {
  if (currentSlide.value > 0) {
    currentSlide.value--
  }
}

const nextImage = () => {
  if (currentSlide.value < images.value.length - 1) {
    currentSlide.value++
  }
}

// 暴露方法
defineExpose({
  getViewMode: () => viewMode.value,
  getImageCount: () => images.value.length,
  switchViewMode: (mode) => {
    if (['grid', 'compare', 'slideshow'].includes(mode)) {
      viewMode.value = mode
    }
  }
})
</script>

<style scoped>
.image-renderer {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #1e293b;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.image-header {
  padding: 12px 16px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  font-size: 16px;
}

.header-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.image-count {
  font-size: 12px;
  color: #94a3b8;
  background-color: rgba(148, 163, 184, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.header-right {
  display: flex;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 4px;
}

.image-container {
  flex-grow: 1;
  overflow: auto;
  padding: 20px;
}

.no-images {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #94a3b8;
}

.no-images-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.no-images-title {
  font-size: 18px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.no-images-description {
  font-size: 14px;
  max-width: 300px;
  line-height: 1.5;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.image-item {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #334155;
  background-color: #0f172a;
}

.image-wrapper {
  position: relative;
  width: 100%;
  height: 200px;
}

.grid-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.8));
  padding: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.image-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-text {
  font-size: 12px;
  color: white;
}

.info-size {
  font-size: 11px;
  color: #cbd5e1;
}

.image-actions {
  display: flex;
  gap: 4px;
}

.compare-placeholder,
.slideshow-placeholder {
  text-align: center;
  color: #94a3b8;
  max-width: 400px;
  margin: 0 auto;
}

.placeholder-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.placeholder-title {
  font-size: 18px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.placeholder-description {
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 24px;
}

.compare-info,
.slideshow-controls {
  background-color: rgba(148, 163, 184, 0.1);
  border-radius: 6px;
  padding: 16px;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.info-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-label {
  font-size: 13px;
  color: #cbd5e1;
}

.info-value {
  font-size: 13px;
  color: #94a3b8;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.slideshow-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.slide-info {
  font-size: 14px;
  color: #cbd5e1;
  font-weight: 500;
}

.image-footer {
  padding: 12px 16px;
  background-color: #0f172a;
  border-top: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-left {
  flex-grow: 1;
}

.image-meta {
  display: flex;
  gap: 16px;
}

.meta-item {
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

.footer-right {
  display: flex;
  align-items: center;
}

.view-mode-selector {
  display: flex;
  background-color: #334155;
  border-radius: 6px;
  border: 1px solid #475569;
  overflow: hidden;
}

.mode-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background-color: transparent;
  border: none;
  color: #cbd5e1;
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
  font-size: 16px;
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

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn:disabled:hover {
  background-color: #334155;
  border-color: #475569;
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