<template>
  <div class="console-panel" :class="[customClass, { 'resizable': resizable }]" :style="panelStyle">
    <div v-if="showHeader" class="console-panel-header">
      <div class="panel-header-left">
        <h3 v-if="title" class="panel-title">{{ title }}</h3>
        <slot name="header-left"></slot>
      </div>
      <div class="panel-header-right">
        <slot name="header-right">
          <div v-if="collapsible" class="panel-actions">
            <el-button
              v-if="showCollapse"
              type="text"
              size="small"
              :icon="collapsed ? 'el-icon-arrow-down' : 'el-icon-arrow-up'"
              @click="toggleCollapse"
            />
            <el-button
              v-if="showClose"
              type="text"
              size="small"
              icon="el-icon-close"
              @click="$emit('close')"
            />
          </div>
        </slot>
      </div>
    </div>
    
    <div v-if="!collapsed" class="console-panel-content" :class="{ 'scrollable': scrollable }">
      <slot></slot>
    </div>
    
    <div v-if="resizable && !collapsed" class="panel-resize-handle" @mousedown="startResize"></div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  showHeader: {
    type: Boolean,
    default: true
  },
  collapsible: {
    type: Boolean,
    default: false
  },
  collapsed: {
    type: Boolean,
    default: false
  },
  showCollapse: {
    type: Boolean,
    default: true
  },
  showClose: {
    type: Boolean,
    default: false
  },
  resizable: {
    type: Boolean,
    default: false
  },
  width: {
    type: [String, Number],
    default: 'auto'
  },
  height: {
    type: [String, Number],
    default: 'auto'
  },
  minWidth: {
    type: [String, Number],
    default: '200px'
  },
  minHeight: {
    type: [String, Number],
    default: '100px'
  },
  maxWidth: {
    type: [String, Number],
    default: '100%'
  },
  maxHeight: {
    type: [String, Number],
    default: '100%'
  },
  scrollable: {
    type: Boolean,
    default: true
  },
  customClass: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:collapsed', 'close', 'resize'])

const isCollapsed = ref(props.collapsed)
const panelWidth = ref(props.width)
const panelHeight = ref(props.height)

const panelStyle = computed(() => {
  const style = {}
  
  if (panelWidth.value !== 'auto') {
    style.width = typeof panelWidth.value === 'number' ? `${panelWidth.value}px` : panelWidth.value
  }
  
  if (panelHeight.value !== 'auto') {
    style.height = typeof panelHeight.value === 'number' ? `${panelHeight.value}px` : panelHeight.value
  }
  
  if (props.minWidth !== 'auto') {
    style.minWidth = typeof props.minWidth === 'number' ? `${props.minWidth}px` : props.minWidth
  }
  
  if (props.minHeight !== 'auto') {
    style.minHeight = typeof props.minHeight === 'number' ? `${props.minHeight}px` : props.minHeight
  }
  
  if (props.maxWidth !== '100%') {
    style.maxWidth = typeof props.maxWidth === 'number' ? `${props.maxWidth}px` : props.maxWidth
  }
  
  if (props.maxHeight !== '100%') {
    style.maxHeight = typeof props.maxHeight === 'number' ? `${props.maxHeight}px` : props.maxHeight
  }
  
  return style
})

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
  emit('update:collapsed', isCollapsed.value)
}

const startResize = (e) => {
  e.preventDefault()
  const startX = e.clientX
  const startY = e.clientY
  const startWidth = panelWidth.value
  const startHeight = panelHeight.value
  
  const doResize = (moveEvent) => {
    const deltaX = moveEvent.clientX - startX
    const deltaY = moveEvent.clientY - startY
    
    if (props.width !== 'auto') {
      const newWidth = Math.max(
        parseInt(props.minWidth) || 200,
        (typeof startWidth === 'number' ? startWidth : parseInt(startWidth)) + deltaX
      )
      panelWidth.value = newWidth
    }
    
    if (props.height !== 'auto') {
      const newHeight = Math.max(
        parseInt(props.minHeight) || 100,
        (typeof startHeight === 'number' ? startHeight : parseInt(startHeight)) + deltaY
      )
      panelHeight.value = newHeight
    }
    
    emit('resize', { width: panelWidth.value, height: panelHeight.value })
  }
  
  const stopResize = () => {
    document.removeEventListener('mousemove', doResize)
    document.removeEventListener('mouseup', stopResize)
  }
  
  document.addEventListener('mousemove', doResize)
  document.addEventListener('mouseup', stopResize)
}
</script>

<style scoped>
.console-panel {
  background-color: var(--console-bg-surface);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-md);
  display: flex;
  flex-direction: column;
  position: relative;
  transition: all var(--console-transition-normal);
}

.console-panel.resizable {
  resize: both;
  overflow: auto;
}

.console-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--console-spacing-md);
  border-bottom: 1px solid var(--console-border-base);
  background-color: var(--console-bg-elevated);
  border-radius: var(--console-radius-md) var(--console-radius-md) 0 0;
}

.panel-header-left,
.panel-header-right {
  display: flex;
  align-items: center;
  gap: var(--console-spacing-sm);
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--console-text-primary);
  margin: 0;
}

.panel-actions {
  display: flex;
  gap: 4px;
}

.console-panel-content {
  flex: 1;
  padding: var(--console-spacing-md);
  overflow: hidden;
}

.console-panel-content.scrollable {
  overflow-y: auto;
}

.panel-resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 12px;
  height: 12px;
  cursor: se-resize;
  background: linear-gradient(135deg, transparent 50%, var(--console-border-light) 50%);
  border-radius: 0 0 var(--console-radius-sm) 0;
}

.panel-resize-handle:hover {
  background: linear-gradient(135deg, transparent 50%, var(--console-color-primary) 50%);
}

/* 滚动条样式 */
.console-panel-content::-webkit-scrollbar {
  width: 6px;
}

.console-panel-content::-webkit-scrollbar-track {
  background: var(--console-bg-surface);
  border-radius: 3px;
}

.console-panel-content::-webkit-scrollbar-thumb {
  background: var(--console-border-light);
  border-radius: 3px;
}

.console-panel-content::-webkit-scrollbar-thumb:hover {
  background: var(--console-border-lighter);
}
</style>