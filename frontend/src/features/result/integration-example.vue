<template>
  <div class="result-system-example">
    <!-- 示例标题 -->
    <div class="example-header">
      <h1 class="example-title">🎯 S5 Result渲染系统集成示例</h1>
      <p class="example-description">
        展示如何将Result系统集成到现有Nova应用中，实现Graph输出 → 可编辑结果 → Graph重算的完整闭环
      </p>
    </div>
    
    <!-- 系统架构图 -->
    <div class="architecture-section">
      <h2 class="section-title">🏗️ 系统架构</h2>
      <div class="architecture-diagram">
        <div class="arch-row">
          <div class="arch-node" @click="simulateGraphOutput('text')">
            <div class="arch-icon">🧠</div>
            <div class="arch-label">Graph引擎</div>
            <div class="arch-desc">生成原始输出</div>
          </div>
          <div class="arch-arrow">→</div>
          <div class="arch-node">
            <div class="arch-icon">🔧</div>
            <div class="arch-label">ResultParser</div>
            <div class="arch-desc">结构化解析</div>
          </div>
          <div class="arch-arrow">→</div>
          <div class="arch-node" @click="showResultContainer = true">
            <div class="arch-icon">📦</div>
            <div class="arch-label">ResultContainer</div>
            <div class="arch-desc">状态管理</div>
          </div>
        </div>
        
        <div class="arch-row">
          <div class="arch-node" @click="showRendererDemo = true">
            <div class="arch-icon">🎨</div>
            <div class="arch-label">ResultRenderer</div>
            <div class="arch-desc">动态分发</div>
          </div>
          <div class="arch-arrow">↕️</div>
          <div class="arch-node" @click="showEditorDemo = true">
            <div class="arch-icon">✏️</div>
            <div class="arch-label">InlineEditor</div>
            <div class="arch-desc">可编辑能力</div>
          </div>
          <div class="arch-arrow">↕️</div>
          <div class="arch-node" @click="simulateGraphRecalc">
            <div class="arch-icon">🔄</div>
            <div class="arch-label">Graph重算</div>
            <div class="arch-desc">双向数据流</div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 实时演示区域 -->
    <div class="demo-section">
      <h2 class="section-title">🎬 实时演示</h2>
      
      <div class="demo-controls">
        <div class="control-group">
          <label class="control-label">选择结果类型:</label>
          <div class="type-selector">
            <button 
              v-for="type in resultTypes" 
              :key="type.value"
              class="type-btn"
              :class="{ 'active': selectedType === type.value }"
              @click="selectResultType(type.value)"
            >
              <span class="type-icon">{{ type.icon }}</span>
              <span class="type-name">{{ type.label }}</span>
            </button>
          </div>
        </div>
        
        <div class="control-group">
          <label class="control-label">操作:</label>
          <div class="action-buttons">
            <button class="action-btn primary" @click="simulateGraphOutput(selectedType)">
              <span class="action-icon">🚀</span>
              <span>模拟Graph输出</span>
            </button>
            <button class="action-btn" @click="toggleEditable">
              <span class="action-icon">{{ isEditable ? '🔒' : '🔓' }}</span>
              <span>{{ isEditable ? '禁用编辑' : '启用编辑' }}</span>
            </button>
            <button class="action-btn" @click="clearResults">
              <span class="action-icon">🗑️</span>
              <span>清除结果</span>
            </button>
          </div>
        </div>
      </div>
      
      <!-- ResultContainer演示 -->
      <div class="demo-container" v-if="showResultContainer">
        <div class="demo-header">
          <h3 class="demo-title">📦 ResultContainer演示</h3>
          <button class="close-btn" @click="showResultContainer = false">×</button>
        </div>
        <div class="demo-content">
          <ResultContainer ref="resultContainerRef" />
        </div>
      </div>
      
      <!-- 渲染器演示 -->
      <div class="demo-container" v-if="showRendererDemo">
        <div class="demo-header">
          <h3 class="demo-title">🎨 渲染器类型演示</h3>
          <button class="close-btn" @click="showRendererDemo = false">×</button>
        </div>
        <div class="renderer-grid">
          <div 
            v-for="renderer in rendererExamples" 
            :key="renderer.type"
            class="renderer-card"
            @click="previewRenderer(renderer)"
          >
            <div class="renderer-icon">{{ renderer.icon }}</div>
            <div class="renderer-name">{{ renderer.name }}</div>
            <div class="renderer-desc">{{ renderer.description }}</div>
            <div class="renderer-status">
              <span class="status-badge" :class="{ 'available': renderer.available }">
                {{ renderer.available ? '可用' : '占位符' }}
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 编辑器演示 -->
      <div class="demo-container" v-if="showEditorDemo">
        <div class="demo-header">
          <h3 class="demo-title">✏️ 编辑器演示</h3>
          <button class="close-btn" @click="showEditorDemo = false">×</button>
        </div>
        <div class="editor-demo">
          <div class="editor-types">
            <button 
              v-for="editor in editorTypes" 
              :key="editor.type"
              class="editor-type-btn"
              :class="{ 'active': activeEditor === editor.type }"
              @click="activeEditor = editor.type"
            >
              <span class="editor-icon">{{ editor.icon }}</span>
              <span class="editor-name">{{ editor.name }}</span>
            </button>
          </div>
          
          <div class="editor-preview">
            <InlineEditor 
              v-model="editorContent"
              :type="activeEditor"
              :editable="true"
              :placeholder="getEditorPlaceholder(activeEditor)"
              @edit="handleEditorEdit"
              @save="handleEditorSave"
              @cancel="handleEditorCancel"
            />
          </div>
        </div>
      </div>
    </div>
    
    <!-- 代码示例 -->
    <div class="code-section">
      <h2 class="section-title">💻 集成代码示例</h2>
      
      <div class="code-tabs">
        <button 
          v-for="tab in codeTabs" 
          :key="tab.id"
          class="code-tab"
          :class="{ 'active': activeCodeTab === tab.id }"
          @click="activeCodeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>
      
      <div class="code-content">
        <pre v-if="activeCodeTab === 'container'"><code>{{ codeExamples.container }}</code></pre>
        <pre v-if="activeCodeTab === 'renderer'"><code>{{ codeExamples.renderer }}</code></pre>
        <pre v-if="activeCodeTab === 'event'"><code>{{ codeExamples.event }}</code></pre>
        <pre v-if="activeCodeTab === 'integration'"><code>{{ codeExamples.integration }}</code></pre>
      </div>
    </div>
    
    <!-- 状态监控 -->
    <div class="status-section">
      <h2 class="section-title">📊 系统状态</h2>
      
      <div class="status-grid">
        <div class="status-card">
          <div class="status-icon">📡</div>
          <div class="status-info">
            <div class="status-label">事件总线</div>
            <div class="status-value">{{ eventBusStatus }}</div>
          </div>
        </div>
        
        <div class="status-card">
          <div class="status-icon">🎯</div>
          <div class="status-info">
            <div class="status-label">当前结果</div>
            <div class="status-value">{{ currentResultType || '无' }}</div>
          </div>
        </div>
        
        <div class="status-card">
          <div class="status-icon">✏️</div>
          <div class="status-info">
            <div class="status-label">编辑状态</div>
            <div class="status-value">{{ isEditable ? '启用' : '禁用' }}</div>
          </div>
        </div>
        
        <div class="status-card">
          <div class="status-icon">🔄</div>
          <div class="status-info">
            <div class="status-label">数据流</div>
            <div class="status-value">{{ dataFlowStatus }}</div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 操作日志 -->
    <div class="log-section">
      <h2 class="section-title">📝 操作日志</h2>
      <div class="log-container">
        <div 
          v-for="(log, index) in operationLogs" 
          :key="index"
          class="log-entry"
          :class="log.type"
        >
          <span class="log-time">{{ log.time }}</span>
          <span class="log-icon">{{ log.icon }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import eventBus from './voe/eventBus.js'
import * as eventTypes from './voe/eventTypes.js'
import ResultContainer from './ResultContainer.vue'
import InlineEditor from './editor/InlineEditor.vue'

// 响应式数据
const selectedType = ref('text')
const isEditable = ref(true)
const showResultContainer = ref(true)
const showRendererDemo = ref(false)
const showEditorDemo = ref(false)
const activeEditor = ref('text')
const editorContent = ref('')
const activeCodeTab = ref('container')
const currentResultType = ref('')
const eventBusStatus = ref('已连接')
const dataFlowStatus = ref('正常')
const operationLogs = ref([])
const resultContainerRef = ref(null)

// 结果类型选项
const resultTypes = [
  { value: 'text', label: '文本', icon: '📄' },
  { value: 'markdown', label: 'Markdown', icon: '📝' },
  { value: 'table', label: '表格', icon: '📊' },
  { value: 'chart', label: '图表', icon: '📈' },
  { value: 'image', label: '图片', icon: '🖼️' }
]

// 渲染器示例
const rendererExamples = [
  { type: 'text', name: '文本渲染器', icon: '📄', description: '纯文本显示和编辑', available: true },
  { type: 'markdown', name: 'Markdown渲染器', icon: '📝', description: 'Markdown解析和预览', available: true },
  { type: 'table', name: '表格渲染器', icon: '📊', description: '结构化数据表格', available: true },
  { type: 'chart', name: '图表渲染器', icon: '📈', description: '数据可视化图表', available: true },
  { type: 'image', name: '图片渲染器', icon: '🖼️', description: '图片对比和查看', available: true }
]

// 编辑器类型
const editorTypes = [
  { type: 'text', name: '文本编辑器', icon: '📄' },
  { type: 'markdown', name: 'Markdown编辑器', icon: '📝' },
  { type: 'json', name: 'JSON编辑器', icon: '{}' }
]

// 代码示例
const codeExamples = {
  container: `// 在Vue组件中使用ResultContainer
<template>
  <div class="workspace">
    <!-- 其他组件... -->
    <ResultContainer />
  </div>
</template>

<script setup>
import ResultContainer from '@/workspace/result/ResultContainer.vue'

// ResultContainer会自动：
// 1. 监听RESULT_UPDATE事件
// 2. 解析Graph输出
// 3. 显示可编辑结果
// 4. 处理用户编辑并触发重算
<\/script>`,

  renderer: `// 自定义渲染器示例
// src/workspace/result/renderers/CustomRenderer.vue
<template>
  <div class="custom-renderer">
    <!-- 自定义渲染逻辑 -->
  </div>
</template>

<script setup>
// 必须实现的props
const props = defineProps({
  result: { type: Object, required: true },
  editable: { type: Boolean, default: true }
})

// 必须触发的事件
const emit = defineEmits(['edit', 'save', 'cancel'])

// 渲染器会自动被ResultRenderer发现和使用
<\/script>`,

  event: `// 发送结果更新事件
import eventBus from '@/workspace/voe/eventBus.js'
import * as eventTypes from '@/workspace/voe/eventTypes.js'

// Graph节点执行完成后
const graphOutput = {
  type: 'text',
  content: { text: '处理结果...' },
  meta: { sourceNode: 'ai_analyzer' }
}

// 发送到Result系统
eventBus.emit(eventTypes.RESULT_UPDATE, {
  action: 'graph_output',
  result: graphOutput,
  timestamp: Date.now()
})

// 用户编辑后触发重算
eventBus.emit(eventTypes.RESULT_UPDATE, {
  action: 'user_edit',
  result: updatedResult,
  originalResult: previousResult,
  timestamp: Date.now()
})`,

  integration: `// 完整集成示例
// 1. 在main.js或App.vue中确保导入
import '@/workspace/result/'

// 2. 在Workspace布局中包含ResultContainer
<template>
  <div class="workspace-layout">
    <LeftPanel />
    <ExecutionCanvas />
    <ResultContainer />  <!-- 结果展示区域 -->
  </div>
</template>

// 3. Graph引擎集成
class GraphEngine {
  async executeNode(node) {
    const result = await node.run()
    
    // 发送结果到Result系统
    eventBus.emit(eventTypes.RESULT_UPDATE, {
      action: 'node_completed',
      result: this.formatResult(result),
      nodeId: node.id
    })
    
    return result
  }
  
  formatResult(rawResult) {
    // 转换为标准Result格式
    return {
      id: \`result_\${Date.now()}\`,
      type: this.detectResultType(rawResult),
      content: this.extractContent(rawResult),
      editable: this.isEditable(rawResult),
      meta: {
        sourceNode: 'graph_engine',
        timestamp: Date.now()
      }
    }
  }
}`
}

// 方法
const selectResultType = (type) => {
  selectedType.value = type
  addLog('info', '🔧', `选择结果类型: ${type}`)
}

const simulateGraphOutput = (type) => {
  const testResults = {
    text: {
      id: `result_${Date.now()}`,
      type: 'text',
      content: {
        title: 'AI分析结果',
        text: '根据数据分析，用户行为模式显示...\n建议优化策略：\n1. 提升用户体验\n2. 增加个性化推荐\n3. 优化转化路径'
      },
      editable: true,
      meta: {
        sourceNode: 'ai_analyzer',
        timestamp: Date.now()
      }
    },
    markdown: {
      id: `result_${Date.now()}`,
      type: 'markdown',
      content: {
        title: '项目报告',
        text: '# 项目分析报告\n\n## 执行摘要\n\n项目进展顺利，关键指标达成。\n\n### 关键发现\n\n- **用户增长**: 月环比增长15%\n- **转化率**: 提升至3.2%\n- **用户满意度**: 4.5/5.0\n\n### 建议\n\n1. 继续优化用户体验\n2. 加强数据监控\n3. 扩展功能模块'
      },
      editable: true,
      meta: {
        sourceNode: 'report_generator',
        timestamp: Date.now()
      }
    },
    table: {
      id: `result_${Date.now()}`,
      type: 'table',
      content: {
        title: '销售数据',
        columns: [
          { key: 'month', title: '月份' },
          { key: 'revenue', title: '收入' },
          { key: 'growth', title: '增长率' },
          { key: 'target', title: '目标' }
        ],
        data: [
          { month: '一月', revenue: '¥120,000', growth: '+12%', target: '¥110,000' },
          { month: '二月', revenue: '¥145,000', growth: '+21%', target: '¥120,000' },
          { month: '三月', revenue: '¥168,000', growth: '+16%', target: '¥140,000' },
          { month: '四月', revenue: '¥192