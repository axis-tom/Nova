<template>
  <div class="image-compare">
    <div class="compare-header">
      <span class="header-icon">🖼️</span>
      <span class="header-title">图片对比</span>
      <div class="header-actions">
        <button class="action-btn" @click="toggleLayout">
          <span class="action-icon">{{ layout === 'side-by-side' ? '📱' : '🖥️' }}</span>
          <span class="action-text">{{ layout === 'side-by-side' ? '垂直布局' : '并排布局' }}</span>
        </button>
      </div>
    </div>

    <div class="compare-container" :class="layout">
      <!-- 图片对比区域 -->
      <div class="compare-area">
        <div class="image-container" v-for="(image, index) in images" :key="index">
          <div class="image-header">
            <span class="image-label">版本 {{ index + 1 }}</span>
            <span class="image-meta">{{ getImageMeta(image) }}</span>
          </div>
          <div class="image-wrapper">
            <img :src="image.url || getPlaceholderUrl(index)" :alt="`图片版本 ${index + 1}`" class="compare-image" />
            <div class="image-overlay" v-if="selectedImage === index">
              <span class="overlay-text">已选择</span>
            </div>
          </div>
          <div class="image-actions">
            <button class="image-btn" @click="selectImage(index)" :class="{ active: selectedImage === index }">
              <span class="btn-icon">✅</span>
              <span class="btn-text">选择</span>
            </button>
            <button class="image-btn" @click="downloadImage(image)">
              <span class="btn-icon">⬇️</span>
              <span class="btn-text">下载</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 对比控制 -->
      <div class="compare-controls">
        <div class="control-group">
          <label class="control-label">缩放级别</label>
          <div class="control-slider">
            <input type="range" min="50" max="200" v-model="zoomLevel" class="slider" />
            <span class="slider-value">{{ zoomLevel }}%</span>
          </div>
        </div>
        
        <div class="control-group">
          <label class="control-label">显示网格</label>
          <label class="toggle-switch">
            <input type="checkbox" v-model="showGrid" />
            <span class="toggle-slider"></span>
          </label>
        </div>

        <div class="control-group">
          <label class="control-label">高亮差异</label>
          <label class="toggle-switch">
            <input type="checkbox" v-model="highlightDifferences" />
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>

      <!-- 图片信息 -->
      <div class="image-info" v-if="selectedImage !== null">
        <div class="info-header">
          <span class="info-icon">📋</span>
          <span class="info-title">图片信息</span>
        </div>
        <div class="info-content">
          <div class="info-item">
            <span class="info-label">尺寸:</span>
            <span class="info-value">{{ getSelectedImageSize() }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">格式:</span>
            <span class="info-value">{{ getSelectedImageFormat() }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">质量评分:</span>
            <span class="info-value">{{ getQualityScore() }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">生成时间:</span>
            <span class="info-value">{{ getGenerationTime() }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="compare-actions">
      <button class="action-btn secondary" @click="handleRegenerate">
        <span class="btn-icon">🔄</span>
        <span class="btn-text">重新生成</span>
      </button>
      <button class="action-btn primary" @click="handleConfirm">
        <span class="btn-icon">✅</span>
        <span class="btn-text">确认选择</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  images?: unknown[]
}

const props = defineProps<Props>()

interface Emits {
  (e: 'select', ...args: unknown[]): void
  (e: 'regenerate', ...args: unknown[]): void
  (e: 'confirm', ...args: unknown[]): void
}

const emit = defineEmits<Emits>()

// 响应式数据
const layout = ref<string>('side-by-side') // 'side-by-side' 或 'vertical'
const selectedImage = ref<number>(0)
const zoomLevel = ref<number>(100)
const showGrid = ref<boolean>(false)
const highlightDifferences = ref<boolean>(true)

// 计算属性
const displayedImages = computed(() => {
  return props.images.length > 0 ? props.images : [
    { url: null, meta: { width: 800, height: 600, format: 'png' } },
    { url: null, meta: { width: 800, height: 600, format: 'png' } }
  ]
})

// 方法
const toggleLayout = () => {
  layout.value = layout.value === 'side-by-side' ? 'vertical' : 'side-by-side'
}

const selectImage = (index) => {
  selectedImage.value = index
  emit('select', index)
}

const downloadImage = (image) => {
  if (image.url) {
    const a = document.createElement('a')
    a.href = image.url
    a.download = `image-${Date.now()}.${image.meta?.format || 'png'}`
    a.click()
  } else {
    console.log('无图片可下载')
  }
}

const getPlaceholderUrl = (index) => {
  // 返回占位图片URL
  return `https://via.placeholder.com/800x600/1e293b/94a3b8?text=图片+${index + 1}`
}

const getImageMeta = (image) => {
  if (image.meta) {
    return `${image.meta.width}×${image.meta.height} ${image.meta.format?.toUpperCase()}`
  }
  return '800×600 PNG'
}

const getSelectedImageSize = () => {
  const image = displayedImages.value[selectedImage.value]
  if (image?.meta) {
    return `${image.meta.width}×${image.meta.height}`
  }
  return '800×600'
}

const getSelectedImageFormat = () => {
  const image = displayedImages.value[selectedImage.value]
  return image?.meta?.format?.toUpperCase() || 'PNG'
}

const getQualityScore = () => {
  // 简单的质量评分逻辑
  const scores = ['优秀', '良好', '一般', '较差']
  return scores[selectedImage.value % scores.length]
}

const getGenerationTime = () => {
  const times = ['2.3秒', '1.8秒', '3.1秒', '2.5秒']
  return times[selectedImage.value % times.length]
}

const handleRegenerate = () => {
  emit('regenerate', selectedImage.value)
}

const handleConfirm = () => {
  emit('confirm', selectedImage.value)
}
</script>

<style scoped>
.image-compare {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #0f172a;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.compare-header {
  padding: 12px 16px;
  background-color: #1e293b;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-icon {
  font-size: 20px;
  margin-right: 8px;
}

.header-title {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  flex-grow: 1;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
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

.action-btn:hover {
  background-color: #475569;
  border-color: #64748b;
}

.action-icon {
  font-size: 12px;
}

.action-text {
  font-weight: 500;
}

.compare-container {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 16px;
  overflow: auto;
}

.compare-container.side-by-side .compare-area {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.compare-container.vertical .compare-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.compare-area {
  flex-grow: 1;
}

.image-container {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
}

.image-header {
  padding: 10px 12px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.image-label {
  font-size: 13px;
  font-weight: 500;
  color: #e2e8f0;
}

.image-meta {
  font-size: 11px;
  color: #94a3b8;
  background-color: #334155;
  padding: 2px 6px;
  border-radius: 3px;
}

.image-wrapper {
  position: relative;
  padding: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
  background-color: #0f172a;
}

.compare-image {
  max-width: 100%;
  max-height: 300px;
  border-radius: 4px;
  transition: transform 0.3s;
}

.compare-image:hover {
  transform: scale(1.02);
}

.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(59, 130, 246, 0.1);
  border: 2px solid #3b82f6;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.overlay-text {
  background-color: #3b82f6;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.image-actions {
  padding: 10px 12px;
  background-color: #0f172a;
  border-top: 1px solid #334155;
  display: flex;
  gap: 8px;
}

.image-btn {
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
  flex: 1;
  justify-content: center;
}

.image-btn:hover {
  background-color: #475569;
  border-color: #64748b;
}

.image-btn.active {
  background-color: #3b82f6;
  border-color: #3b82f6;
  color: white;
}

.btn-icon {
  font-size: 12px;
}

.btn-text {
  font-weight: 500;
}

.compare-controls {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 16px;
}

.control-group {
  margin-bottom: 12px;
}

.control-group:last-child {
  margin-bottom: 0;
}

.control-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.control-slider {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider {
  flex-grow: 1;
  height: 4px;
  background-color: #334155;
  border-radius: 2px;
  outline: none;
  -webkit-appearance: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background-color: #3b82f6;
  border-radius: 50%;
  cursor: pointer;
}

.slider-value {
  font-size: 12px;
  color: #94a3b8;
  min-width: 40px;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 20px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #334155;
  border-radius: 20px;
  transition: .4s;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background-color: #cbd5e1;
  border-radius: 50%;
  transition: .4s;
}

input:checked + .toggle-slider {
  background-color: #3b82f6;
}

input:checked + .toggle-slider:before {
  transform: translateX(20px);
}

.image-info {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 16px;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.info-icon {
  font-size: 16px;
}

.info-title {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
}

.info-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  font-size: 12px;
  color: #94a3b8;
}

.info-value {
  font-size: 12px;
  font-weight: 500;
  color: #cbd5e1;
}

.compare-actions {
  padding: 12px 16px;
  background-color: #1e293b;
  border-top: 1px solid #334155;
  display: flex;
  gap: 8px;
}

.action-btn.secondary {
  background-color: #475569;
  color: #e2e8f0;
}

.action-btn.secondary:hover {
  background-color: #64748b;
}

.action-btn.primary {
  background-color: #3b82f6;
  color: white;
}

.action-btn.primary:hover {
  background-color: #2563eb;
}
</style>