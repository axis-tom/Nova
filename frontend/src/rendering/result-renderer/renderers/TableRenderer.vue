<template>
  <div class="table-renderer">
    <!-- 表格头部 -->
    <div class="table-header">
      <div class="header-left">
        <span class="header-icon">📊</span>
        <span class="header-title">{{ result.content.title || '表格数据' }}</span>
        <span class="header-stats" v-if="tableData.length > 0">
          {{ tableData.length }} 行 × {{ columns.length }} 列
        </span>
      </div>
      <div class="header-right">
        <div class="header-actions">
          <button class="action-btn small" @click="handleExportCSV" title="导出CSV">
            <span class="action-icon">📥</span>
          </button>
          <button class="action-btn small" @click="handleCopyTable" title="复制表格">
            <span class="action-icon">📋</span>
          </button>
          <button class="action-btn small" @click="toggleSort" title="排序" v-if="tableData.length > 0">
            <span class="action-icon">🔢</span>
          </button>
        </div>
      </div>
    </div>
    
    <!-- 表格内容 -->
    <div class="table-container" v-if="tableData.length > 0">
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="col in columns" :key="col.key" 
                  :class="{ 'sortable': sortable, 'sorted': sortColumn === col.key }"
                  @click="sortable ? handleSort(col.key) : null">
                <div class="th-content">
                  <span class="th-title">{{ col.title || col.key }}</span>
                  <span class="sort-indicator" v-if="sortColumn === col.key">
                    {{ sortDirection === 'asc' ? '↑' : '↓' }}
                  </span>
                </div>
              </th>
              <th v-if="editable" class="actions-header">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in sortedData" :key="rowIndex">
              <td v-for="col in columns" :key="col.key" :title="getCellValue(row, col.key)">
                <div class="cell-content">
                  {{ formatCellValue(getCellValue(row, col.key)) }}
                </div>
              </td>
              <td v-if="editable" class="actions-cell">
                <button class="action-btn small" @click="handleEditRow(rowIndex)" title="编辑行">
                  <span class="action-icon">✏️</span>
                </button>
                <button class="action-btn small danger" @click="handleDeleteRow(rowIndex)" title="删除行">
                  <span class="action-icon">🗑️</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <!-- 空表格提示 -->
    <div v-else class="empty-table">
      <div class="empty-icon">📭</div>
      <div class="empty-title">暂无数据</div>
      <div class="empty-description">
        表格数据为空或格式不正确
      </div>
      <div class="empty-actions" v-if="editable">
        <button class="action-btn" @click="handleAddRow">
          <span class="action-icon">➕</span>
          <span>添加行</span>
        </button>
      </div>
    </div>
    
    <!-- 表格底部 -->
    <div class="table-footer" v-if="tableData.length > 0">
      <div class="footer-left">
        <div class="table-meta">
          <span class="meta-item">
            <span class="meta-icon">📊</span>
            <span class="meta-text">总计: {{ tableData.length }} 行</span>
          </span>
          <span class="meta-item" v-if="result.meta.sourceNode">
            <span class="meta-icon">📌</span>
            <span class="meta-text">来源: {{ result.meta.sourceNode }}</span>
          </span>
        </div>
      </div>
      <div class="footer-right" v-if="editable">
        <button class="action-btn secondary" @click="handleAddRow">
          <span class="action-icon">➕</span>
          <span>添加行</span>
        </button>
        <button class="action-btn primary" @click="handleSaveTable">
          <span class="action-icon">💾</span>
          <span>保存表格</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

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
const sortColumn = ref<string>('')
const sortDirection = ref<string>('asc')
const sortable = ref<boolean>(true)

// 计算属性
const tableData = computed(() => {
  if (!props.result || !props.result.content) return []
  return props.result.content.data || []
})

const columns = computed(() => {
  if (!props.result || !props.result.content) return []
  
  // 如果有预定义的列，使用它们
  if (props.result.content.columns && props.result.content.columns.length > 0) {
    return props.result.content.columns
  }
  
  // 否则从数据中推断列
  if (tableData.value.length > 0) {
    const firstRow = tableData.value[0]
    return Object.keys(firstRow).map(key => ({
      key,
      title: formatColumnTitle(key)
    }))
  }
  
  return []
})

const sortedData = computed(() => {
  if (!sortColumn.value || !sortable.value) {
    return tableData.value
  }
  
  return [...tableData.value].sort((a, b) => {
    const aValue = getCellValue(a, sortColumn.value)
    const bValue = getCellValue(b, sortColumn.value)
    
    if (aValue === bValue) return 0
    
    const comparison = aValue < bValue ? -1 : 1
    return sortDirection.value === 'asc' ? comparison : -comparison
  })
})

// 方法
const getCellValue = (row, key) => {
  return row[key] !== undefined ? row[key] : ''
}

const formatCellValue = (value) => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const formatColumnTitle = (key) => {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, str => str.toUpperCase())
    .trim()
}

const handleSort = (columnKey) => {
  if (sortColumn.value === columnKey) {
    // 切换排序方向
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    // 新列排序
    sortColumn.value = columnKey
    sortDirection.value = 'asc'
  }
}

const toggleSort = () => {
  sortable.value = !sortable.value
  if (!sortable.value) {
    sortColumn.value = ''
  }
}

const handleEditRow = (rowIndex) => {
  if (!props.editable) return
  
  const rowData = sortedData.value[rowIndex]
  emit('edit', {
    type: 'table_row',
    rowIndex,
    rowData,
    action: 'edit'
  })
}

const handleDeleteRow = (rowIndex) => {
  if (!props.editable) return
  
  if (confirm('确定要删除这一行吗？')) {
    const newData = [...tableData.value]
    newData.splice(rowIndex, 1)
    
    emit('save', {
      data: newData,
      columns: columns.value,
      title: props.result.content.title || '表格数据'
    })
  }
}

const handleAddRow = () => {
  if (!props.editable) return
  
  // 创建新行（所有列都为空）
  const newRow = {}
  columns.value.forEach(col => {
    newRow[col.key] = ''
  })
  
  const newData = [...tableData.value, newRow]
  
  emit('save', {
    data: newData,
    columns: columns.value,
    title: props.result.content.title || '表格数据'
  })
}

const handleSaveTable = () => {
  if (!props.editable) return
  
  emit('save', {
    data: tableData.value,
    columns: columns.value,
    title: props.result.content.title || '表格数据'
  })
}

const handleExportCSV = () => {
  if (tableData.value.length === 0) return
  
  try {
    // 创建CSV内容
    const headers = columns.value.map(col => `"${col.title || col.key}"`).join(',')
    const rows = tableData.value.map(row => {
      return columns.value.map(col => {
        const value = getCellValue(row, col.key)
        // 转义CSV特殊字符
        const escapedValue = String(value).replace(/"/g, '""')
        return `"${escapedValue}"`
      }).join(',')
    })
    
    const csvContent = [headers, ...rows].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `table-${props.result.id || 'data'}.csv`
    a.click()
    URL.revokeObjectURL(url)
    
    console.log('TableRenderer: 表格已导出为CSV')
  } catch (error) {
    console.error('TableRenderer: CSV导出失败', error)
  }
}

const handleCopyTable = () => {
  if (tableData.value.length === 0) return
  
  try {
    // 创建表格文本表示
    const headers = columns.value.map(col => col.title || col.key).join('\t')
    const rows = tableData.value.map(row => {
      return columns.value.map(col => getCellValue(row, col.key)).join('\t')
    })
    
    const tableText = [headers, ...rows].join('\n')
    navigator.clipboard.writeText(tableText)
    console.log('TableRenderer: 表格已复制到剪贴板')
  } catch (error) {
    console.error('TableRenderer: 复制失败', error)
  }
}

// 暴露方法
defineExpose({
  sortBy: handleSort,
  addRow: handleAddRow,
  exportCSV: handleExportCSV,
  copyTable: handleCopyTable,
  getTableStats: () => ({
    rows: tableData.value.length,
    columns: columns.value.length,
    sortColumn: sortColumn.value,
    sortDirection: sortDirection.value
  })
})
</script>

<style scoped>
.table-renderer {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #1e293b;
  border-radius: 8px;
  border: 1px solid #334155;
  overflow: hidden;
}

.table-header {
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

.header-stats {
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

.table-container {
  flex-grow: 1;
  overflow: hidden;
}

.table-scroll {
  height: 100%;
  overflow: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th {
  padding: 12px 16px;
  background-color: #0f172a;
  border-bottom: 1px solid #334155;
  text-align: left;
  font-weight: 600;
  color: #e2e8f0;
  position: sticky;
  top: 0;
  z-index: 10;
}

.data-table th.sortable {
  cursor: pointer;
  transition: background-color 0.2s;
}

.data-table th.sortable:hover {
  background-color: #1e293b;
}

.data-table th.sorted {
  background-color: rgba(59, 130, 246, 0.2);
}

.th-content {
  display: flex;
  align-items: center;
  gap: 6px;
}

.th-title {
  flex-grow: 1;
}

.sort-indicator {
  font-size: 12px;
  color: #3b82f6;
}

.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid #334155;
  color: #cbd5e1;
  vertical-align: top;
}

.data-table tr:hover td {
  background-color: rgba(148, 163, 184, 0.05);
}

.cell-content {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions-header {
  width: 80px;
  text-align: center;
}

.actions-cell {
  text-align: center;
  white-space: nowrap;
}

.empty-table {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #94a3b8;
  padding: 40px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-title {
  font-size: 18px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.empty-description {
  font-size: 14px;
  max-width: 300px;
  line-height: 1.5;
  margin-bottom: 20px;
}

.empty-actions {
  margin-top: 16px;
}

.table-footer {
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

.table-meta {
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
  gap: 8px;
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

.action-btn.danger {
  background-color: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.action-btn.danger:hover {
  background-color: rgba(239, 68, 68, 0.3);
  border-color: rgba(239, 68, 68, 0.4);
}

.action-icon {
  font-size: 14px;
}
</style>