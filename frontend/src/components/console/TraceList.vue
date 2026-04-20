<template>
  <div class="trace-list">
    <div class="trace-list-header">
      <h3 class="trace-list-title">Trace观察</h3>
      <div class="trace-list-actions">
        <el-button size="small" type="text" icon="el-icon-refresh" @click="$emit('refresh')">刷新</el-button>
        <el-button size="small" type="text" icon="el-icon-filter" @click="showFilter = !showFilter">筛选</el-button>
        <el-button size="small" type="text" icon="el-icon-download" @click="$emit('export')">导出</el-button>
      </div>
    </div>
    
    <div v-if="showFilter" class="trace-filter">
      <el-input
        v-model="filterText"
        placeholder="搜索Trace..."
        size="small"
        prefix-icon="el-icon-search"
        clearable
        @input="$emit('filter', filterText)"
      />
      <div class="filter-options">
        <el-select
          v-model="filterStatus"
          placeholder="状态筛选"
          size="small"
          clearable
          @change="$emit('status-filter', filterStatus)"
        >
          <el-option label="全部" value="" />
          <el-option label="运行中" value="running" />
          <el-option label="成功" value="success" />
          <el-option label="失败" value="error" />
          <el-option label="等待中" value="pending" />
        </el-select>
      </div>
    </div>
    
    <div class="trace-list-content">
      <div v-if="loading" class="trace-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      
      <div v-else-if="filteredTraces.length === 0" class="trace-empty">
        <el-icon><Document /></el-icon>
        <p>暂无Trace数据</p>
      </div>
      
      <div v-else class="trace-items">
        <div
          v-for="trace in filteredTraces"
          :key="trace.id"
          class="trace-item"
          :class="{ 'selected': selectedTraceId === trace.id, [trace.status]: true }"
          @click="$emit('select', trace)"
        >
          <div class="trace-item-header">
            <div class="trace-name">
              <span class="trace-icon">
                <el-icon v-if="trace.status === 'success'"><CircleCheck /></el-icon>
                <el-icon v-else-if="trace.status === 'running'"><Loading /></el-icon>
                <el-icon v-else-if="trace.status === 'error'"><CircleClose /></el-icon>
                <el-icon v-else><Clock /></el-icon>
              </span>
              <span class="trace-title">{{ trace.name }}</span>
            </div>
            <span class="trace-status" :class="trace.status">{{ getStatusText(trace.status) }}</span>
          </div>
          
          <div class="trace-item-content">
            <div class="trace-desc" v-if="trace.description">{{ trace.description }}</div>
            
            <div class="trace-meta">
              <div class="trace-meta-item">
                <el-icon><Timer /></el-icon>
                <span>{{ trace.time }}</span>
              </div>
              <div class="trace-meta-item">
                <el-icon><Clock /></el-icon>
                <span>{{ trace.duration }}</span>
              </div>
              <div v-if="trace.nodeCount" class="trace-meta-item">
                <el-icon><Connection /></el-icon>
                <span>{{ trace.nodeCount }} 节点</span>
              </div>
            </div>
            
            <div v-if="trace.progress !== undefined" class="trace-progress">
              <el-progress
                :percentage="trace.progress"
                :stroke-width="3"
                :show-text="false"
              />
              <span class="progress-text">{{ trace.progress }}%</span>
            </div>
          </div>
          
          <div class="trace-item-actions">
            <el-button
              size="mini"
              type="text"
              icon="el-icon-view"
              @click.stop="openTraceViewer(trace.trace_id || trace.id)"
            >详情</el-button>
            <el-button
              size="mini"
              type="text"
              icon="el-icon-bug"
              @click.stop="openDebugPanel(trace.trace_id || trace.id)"
            >调试</el-button>
            <el-button
              size="mini"
              type="text"
              icon="el-icon-copy-document"
              @click.stop="$emit('clone', trace)"
            >克隆</el-button>
            <el-button
              v-if="trace.status === 'running'"
              size="mini"
              type="text"
              icon="el-icon-switch-button"
              @click.stop="$emit('stop', trace)"
            >停止</el-button>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="showPagination" class="trace-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        small
        @size-change="$emit('page-size-change', pageSize)"
        @current-change="$emit('page-change', currentPage)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  Loading,
  Document,
  CircleCheck,
  CircleClose,
  Clock,
  Timer,
  Connection
} from '@element-plus/icons-vue'

const props = defineProps({
  traces: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  selectedTraceId: {
    type: [String, Number],
    default: null
  },
  showPagination: {
    type: Boolean,
    default: false
  },
  total: {
    type: Number,
    default: 0
  },
  pageSize: {
    type: Number,
    default: 10
  },
  currentPage: {
    type: Number,
    default: 1
  }
})

const emit = defineEmits([
  'select',
  'refresh',
  'export',
  'filter',
  'status-filter',
  'view-details',
  'clone',
  'stop',
  'page-size-change',
  'page-change'
])

const filterText = ref('')
const filterStatus = ref('')
const showFilter = ref(false)

const filteredTraces = computed(() => {
  let result = props.traces
  
  if (filterText.value) {
    const searchText = filterText.value.toLowerCase()
    result = result.filter(trace => 
      trace.name.toLowerCase().includes(searchText) ||
      (trace.description && trace.description.toLowerCase().includes(searchText))
    )
  }
  
  if (filterStatus.value) {
    result = result.filter(trace => trace.status === filterStatus.value)
  }
  
  return result
})

const getStatusText = (status) => {
  const statusMap = {
    'success': '成功',
    'running': '运行中',
    'error': '失败',
    'pending': '等待中'
  }
  return statusMap[status] || status
}

// 打开Trace Viewer
const openTraceViewer = (traceId) => {
  if (window.openTraceViewer) {
    window.openTraceViewer(traceId)
  } else {
    console.warn('openTraceViewer方法未找到，请确保Console.vue已正确加载')
    emit('view-details', { trace_id: traceId })
  }
}

// 打开Debug Panel
const openDebugPanel = (traceId) => {
  if (window.openDebugPanel) {
    window.openDebugPanel(traceId)
  } else {
    console.warn('openDebugPanel方法未找到，请确保Console.vue已正确加载')
    emit('view-details', { trace_id: traceId })
  }
}
</script>

<style scoped>
.trace-list {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.trace-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: var(--console-spacing-md);
  border-bottom: 1px solid var(--console-border-base);
  margin-bottom: var(--console-spacing-md);
}

.trace-list-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--console-text-primary);
  margin: 0;
}

.trace-list-actions {
  display: flex;
  gap: 4px;
}

.trace-filter {
  padding-bottom: var(--console-spacing-md);
  border-bottom: 1px solid var(--console-border-base);
  margin-bottom: var(--console-spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-sm);
}

.filter-options {
  display: flex;
  gap: var(--console-spacing-sm);
}

.trace-list-content {
  flex: 1;
  overflow-y: auto;
}

.trace-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--console-spacing-xl);
  color: var(--console-text-tertiary);
}

.trace-loading .el-icon {
  font-size: 24px;
  margin-bottom: var(--console-spacing-sm);
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.trace-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--console-spacing-xl);
  color: var(--console-text-tertiary);
  text-align: center;
}

.trace-empty .el-icon {
  font-size: 48px;
  margin-bottom: var(--console-spacing-md);
  opacity: 0.5;
}

.trace-items {
  display: flex;
  flex-direction: column;
  gap: var(--console-spacing-sm);
}

.trace-item {
  background-color: var(--console-bg-elevated);
  border: 1px solid var(--console-border-base);
  border-radius: var(--console-radius-sm);
  padding: var(--console-spacing-md);
  cursor: pointer;
  transition: all var(--console-transition-fast);
}

.trace-item:hover {
  background-color: var(--console-bg-hover);
  border-color: var(--console-border-light);
  transform: translateY(-1px);
  box-shadow: var(--console-shadow-sm);
}

.trace-item.selected {
  border-color: var(--console-color-primary);
  background-color: rgba(59, 130, 246, 0.1);
}

.trace-item.success {
  border-left: 3px solid var(--console-color-success);
}

.trace-item.running {
  border-left: 3px solid var(--console-color-info);
}

.trace-item.error {
  border-left: 3px solid var(--console-color-error);
}

.trace-item.pending {
  border-left: 3px solid var(--console-color-warning);
}

.trace-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--console-spacing-sm);
}

.trace-name {
  display: flex;
  align-items: center;
  gap: var(--console-spacing-sm);
}

.trace-icon {
  display: flex;
  align-items: center;
}

.trace-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--console-text-primary);
}

.trace-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 500;
}

.trace-status.success {
  background-color: rgba(16, 185, 129, 0.2);
  color: var(--console-color-success);
}

.trace-status.running {
  background-color: rgba(59, 130, 246, 0.2);
  color: var(--console-color-info);
}

.trace-status.error {
  background-color: rgba(239, 68, 68, 0.2);
  color: var(--console-color-error);
}

.trace-status.pending {
  background-color: rgba(245, 158, 11, 0.2);
  color: var(--console-color-warning);
}

.trace-item-content {
  margin-bottom: var(--console-spacing-sm);
}

.trace-desc {
  font-size: 12px;
  color: var(--console-text-tertiary);
  margin-bottom: var(--console-spacing-sm);
  line-height: 1.4;
}

.trace-meta {
  display: flex;
  gap: var(--console-spacing-md);
  margin-bottom: var(--console-spacing-sm);
}

.trace-meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--console-text-muted);
}

.trace-meta-item .el-icon {
  font-size: 12px;
}

.trace-progress {
  display: flex;
  align-items: center;
  gap: var(--console-spacing-sm);
}

.trace-progress .el-progress {
  flex: 1;
}

.progress-text {
  font-size: 11px;
  color: var(--console-text-tertiary);
  min-width: 30px;
}

.trace-item-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--console-spacing-sm);
  border-top: 1px solid var(--console-border-base);
  padding-top: var(--console-spacing-sm);
}

.trace-pagination {
  padding-top: var(--console-spacing-md);
  border-top: 1px solid var(--console-border-base);
  margin-top: var(--console-spacing-md);
  display: flex;
  justify-content: center;
}
</style>