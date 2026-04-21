<template>
  <div class="run-console-container">
    <div class="console-header">
      <h3>AI执行控制台</h3>
      <p class="console-subtitle">统一AI执行入口 - 所有AI行为必须通过此入口执行</p>
    </div>

    <div class="console-content">
      <!-- 执行表单 -->
      <el-form
        ref="runFormRef"
        :model="runForm"
        :rules="runFormRules"
        label-width="120px"
        label-position="top"
        class="run-form"
      >
        <el-form-item label="场景选择" prop="scenario">
          <el-select
            v-model="runForm.scenario"
            placeholder="请选择执行场景"
            style="width: 100%;"
            @change="onScenarioChange"
          >
            <el-option
              v-for="scenario in scenarios"
              :key="scenario.scenario"
              :label="scenario.scenario"
              :value="scenario.scenario"
            >
              <div class="scenario-option">
                <span class="scenario-name">{{ scenario.scenario }}</span>
                <span class="scenario-desc">{{ scenario.description }}</span>
              </div>
            </el-option>
          </el-select>
          <div class="form-hint">
            选择要执行的Graph场景，不同场景对应不同的AI工作流
          </div>
        </el-form-item>

        <el-form-item label="执行环境" prop="env">
          <el-radio-group v-model="runForm.env">
            <el-radio label="sandbox">沙箱环境</el-radio>
            <el-radio label="production">生产环境</el-radio>
          </el-radio-group>
          <div class="form-hint">
            沙箱环境用于测试，生产环境将产生实际效果
          </div>
        </el-form-item>

        <el-form-item label="输入参数" prop="input">
          <div class="input-editor-container">
            <div class="editor-toolbar">
              <el-button-group size="small">
                <el-button @click="insertTemplate('empty')">空对象</el-button>
                <el-button @click="insertTemplate('email')">邮件模板</el-button>
                <el-button @click="insertTemplate('report')">报告模板</el-button>
              </el-button-group>
              <el-button
                size="small"
                icon="el-icon-refresh"
                @click="formatJson"
              >
                格式化
              </el-button>
            </div>
            <div class="editor-wrapper">
              <textarea
                v-model="runForm.inputJson"
                class="json-editor"
                placeholder='输入JSON格式的参数，例如：{"data": "your data here"}'
                @input="onInputJsonChange"
              ></textarea>
              <div v-if="jsonError" class="json-error">
                <i class="el-icon-warning"></i>
                {{ jsonError }}
              </div>
            </div>
          </div>
          <div class="form-hint">
            输入Graph执行所需的参数，必须是有效的JSON格式
          </div>
        </el-form-item>

        <el-form-item label="自定义配置" prop="graph_config">
          <el-input
            v-model="runForm.graph_config"
            type="textarea"
            :rows="3"
            placeholder='自定义Graph配置（可选），JSON格式'
          />
          <div class="form-hint">
            可选的Graph自定义配置，将覆盖默认配置
          </div>
        </el-form-item>

        <!-- 执行控制 -->
        <div class="execution-controls">
          <el-button
            type="primary"
            size="large"
            :loading="executing"
            :disabled="!canExecute"
            @click="executeGraph"
            class="run-button"
          >
            <template #icon>
              <i class="el-icon-video-play"></i>
            </template>
            {{ executing ? '执行中...' : '执行Graph' }}
          </el-button>

          <el-button
            type="danger"
            size="large"
            :disabled="!executing"
            @click="cancelExecution"
            class="cancel-button"
          >
            <template #icon>
              <i class="el-icon-switch-button"></i>
            </template>
            取消执行
          </el-button>
        </div>
      </el-form>

      <!-- 执行结果 -->
      <div v-if="executionResult" class="execution-result">
        <div class="result-header">
          <h4>执行结果</h4>
          <el-button
            type="text"
            icon="el-icon-copy-document"
            @click="copyResult"
          >
            复制
          </el-button>
        </div>
        
        <div class="result-summary">
          <div class="summary-item">
            <label>执行状态:</label>
            <span class="status-badge" :class="executionResult.success ? 'success' : 'error'">
              {{ executionResult.success ? '成功' : '失败' }}
            </span>
          </div>
          <div v-if="executionResult.trace_id" class="summary-item">
            <label>Trace ID:</label>
            <span class="trace-id">{{ executionResult.trace_id }}</span>
            <el-button
              type="text"
              size="small"
              icon="el-icon-link"
              @click="viewTraceDetails"
            >
              查看详情
            </el-button>
          </div>
          <div v-if="executionResult.execution_path" class="summary-item">
            <label>执行路径:</label>
            <span>{{ executionResult.execution_path.join(' → ') }}</span>
          </div>
        </div>

        <div class="result-details">
          <el-tabs v-model="activeResultTab">
            <el-tab-pane label="结果数据" name="result">
              <pre class="result-json">{{ JSON.stringify(executionResult.result, null, 2) }}</pre>
            </el-tab-pane>
            <el-tab-pane label="原始响应" name="raw">
              <pre class="result-json">{{ JSON.stringify(executionResult, null, 2) }}</pre>
            </el-tab-pane>
            <el-tab-pane v-if="executionResult.error" label="错误信息" name="error">
              <div class="error-message">
                <i class="el-icon-warning"></i>
                <span>{{ executionResult.error }}</span>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>

      <!-- 执行历史 -->
      <div v-if="executionHistory.length > 0" class="execution-history">
        <div class="history-header">
          <h4>执行历史</h4>
          <el-button
            type="text"
            icon="el-icon-delete"
            @click="clearHistory"
          >
            清空
          </el-button>
        </div>
        
        <div class="history-list">
          <div
            v-for="item in executionHistory"
            :key="item.timestamp"
            class="history-item"
            @click="loadHistoryItem(item)"
          >
            <div class="history-main">
              <span class="history-scenario">{{ item.scenario }}</span>
              <span class="history-time">{{ formatTime(item.timestamp) }}</span>
            </div>
            <div class="history-details">
              <span class="history-status" :class="item.success ? 'success' : 'error'">
                {{ item.success ? '成功' : '失败' }}
              </span>
              <span v-if="item.trace_id" class="history-trace">
                Trace: {{ item.trace_id.substring(0, 8) }}...
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { runGraph, listScenarios } from '@/api/graph.js'
import { ElMessage, ElMessageBox } from 'element-plus'

// 响应式数据
const runFormRef = ref(null)
const runForm = ref({
  scenario: '',
  env: 'sandbox',
  input: {},
  inputJson: '{}',
  graph_config: ''
})

const scenarios = ref([])
const executing = ref(false)
const executionResult = ref(null)
const executionHistory = ref([])
const activeResultTab = ref('result')
const jsonError = ref('')

// 表单验证规则
const runFormRules = {
  scenario: [
    { required: true, message: '请选择执行场景', trigger: 'change' }
  ],
  env: [
    { required: true, message: '请选择执行环境', trigger: 'change' }
  ]
}

// 计算属性
const canExecute = computed(() => {
  return runForm.value.scenario && !jsonError.value
})

// 方法
const loadScenarios = async () => {
  try {
    const response = await listScenarios()
    scenarios.value = Object.entries(response.details).map(([name, details]) => ({
      scenario: name,
      description: details.description,
      node_count: details.nodes?.length || 0
    }))
  } catch (error) {
    ElMessage.error('加载场景列表失败: ' + error.message)
  }
}

const onScenarioChange = (scenario) => {
  // 可以根据场景自动填充一些默认参数
  if (scenario === 'email_briefing') {
    runForm.value.inputJson = JSON.stringify({
      email_content: "示例邮件内容",
      sender: "user@example.com",
      priority: "normal"
    }, null, 2)
    onInputJsonChange()
  } else if (scenario === 'daily_report') {
    runForm.value.inputJson = JSON.stringify({
      date_range: "2024-01-01 to 2024-01-31",
      metrics: ["revenue", "users", "engagement"],
      format: "detailed"
    }, null, 2)
    onInputJsonChange()
  }
}

const onInputJsonChange = () => {
  try {
    if (runForm.value.inputJson.trim()) {
      const parsed = JSON.parse(runForm.value.inputJson)
      runForm.value.input = parsed
      jsonError.value = ''
    } else {
      runForm.value.input = {}
      jsonError.value = ''
    }
  } catch (error) {
    jsonError.value = 'JSON格式错误: ' + error.message
  }
}

const insertTemplate = (template) => {
  const templates = {
    empty: '{}',
    email: JSON.stringify({
      email_content: "请在此输入邮件内容...",
      sender: "user@example.com",
      recipient: "recipient@example.com",
      subject: "邮件主题",
      priority: "normal",
      attachments: []
    }, null, 2),
    report: JSON.stringify({
      report_type: "daily",
      date: new Date().toISOString().split('T')[0],
      metrics: ["metric1", "metric2", "metric3"],
      include_charts: true,
      recipients: ["manager@example.com"]
    }, null, 2)
  }
  
  runForm.value.inputJson = templates[template] || '{}'
  onInputJsonChange()
}

const formatJson = () => {
  try {
    const parsed = JSON.parse(runForm.value.inputJson)
    runForm.value.inputJson = JSON.stringify(parsed, null, 2)
    jsonError.value = ''
  } catch (error) {
    jsonError.value = '无法格式化: ' + error.message
  }
}

const executeGraph = async () => {
  if (!runFormRef.value) return
  
  try {
    // 验证表单
    await runFormRef.value.validate()
    
    if (jsonError.value) {
      ElMessage.error('请输入有效的JSON参数')
      return
    }
    
    // 准备请求数据
    const requestData = {
      scenario: runForm.value.scenario,
      input: runForm.value.input,
      env: runForm.value.env
    }
    
    // 添加自定义配置（如果存在）
    if (runForm.value.graph_config.trim()) {
      try {
        requestData.graph_config = JSON.parse(runForm.value.graph_config)
      } catch (error) {
        ElMessage.error('自定义配置JSON格式错误')
        return
      }
    }
    
    // 开始执行
    executing.value = true
    executionResult.value = null
    
    ElMessage.info('开始执行Graph...')
    
    const response = await runGraph(requestData)
    
    // 保存执行结果
    executionResult.value = response
    
    // 保存到历史记录
    const historyItem = {
      timestamp: Date.now(),
      scenario: runForm.value.scenario,
      success: response.success,
      trace_id: response.trace_id,
      result: response.result
    }
    
    executionHistory.value.unshift(historyItem)
    
    // 限制历史记录数量
    if (executionHistory.value.length > 10) {
      executionHistory.value = executionHistory.value.slice(0, 10)
    }
    
    // 保存到localStorage
    localStorage.setItem('graph_execution_history', JSON.stringify(executionHistory.value))
    
    if (response.success) {
      ElMessage.success(`Graph执行成功！Trace ID: ${response.trace_id}`)
    } else {
      ElMessage.error(`Graph执行失败: ${response.error}`)
    }
    
  } catch (error) {
    console.error('Graph执行错误:', error)
    ElMessage.error('Graph执行失败: ' + (error.message || '未知错误'))
    
    // 保存错误结果
    executionResult.value = {
      success: false,
      error: error.message || '未知错误',
      result: {},
      trace_id: null,
      execution_path: []
    }
  } finally {
    executing.value = false
  }
}

const cancelExecution = () => {
  ElMessageBox.confirm(
    '确定要取消当前执行吗？',
    '取消执行',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    executing.value = false
    ElMessage.info('执行已取消')
  }).catch(() => {
    // 用户取消
  })
}

const copyResult = () => {
  if (!executionResult.value) return
  
  const text = JSON.stringify(executionResult.value, null, 2)
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('结果已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

const viewTraceDetails = () => {
  if (!executionResult.value?.trace_id) return
  
  ElMessage.info(`查看Trace详情: ${executionResult.value.trace_id}`)
  // 这里可以跳转到Trace详情页面或打开Trace查看器
}

const loadHistoryItem = (item) => {
  runForm.value.scenario = item.scenario
  runForm.value.input = item.result
  runForm.value.inputJson = JSON.stringify(item.result, null, 2)
  executionResult.value = item
}

const clearHistory = () => {
  ElMessageBox.confirm(
    '确定要清空执行历史吗？',
    '清空历史',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    executionHistory.value = []
    localStorage.removeItem('graph_execution_history')
    ElMessage.success('历史记录已清空')
  }).catch(() => {
    // 用户取消
  })
}

const formatTime = (timestamp) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 生命周期
onMounted(() => {
  loadScenarios()
  
  // 加载历史记录
  try {
    const savedHistory = localStorage.getItem('graph_execution_history')
    if (savedHistory) {
      executionHistory.value = JSON.parse(savedHistory)
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
  }
})
</script>

<style scoped>
.run-console-container {
  background-color: #1e293b;
  border-radius: 8px;
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.console-header {
  margin-bottom: 24px;
}

.console-header h3 {
  margin: 0;
  color: #f8fafc;
  font-size: 20px;
}

.console-subtitle {
  margin: 8px 0 0;
  color: #94a3b8;
  font-size: 14px;
}

.console-content {
  flex: 1;
  overflow-y: auto;
}

.run-form {
  margin-bottom: 24px;
}

.scenario-option {
  display: flex;
  flex-direction: column;
}

.scenario-name {
  font-weight: 500;
  color: #f1f5f9;
}

.scenario-desc {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.form-hint {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.input-editor-container {
  border: 1px solid #334155;
  border-radius: 4px;
  overflow: hidden;
}

.editor-toolbar {
  padding: 8px 12px;
  background-color: #334155;
  border-bottom: 1px solid #475569;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.editor-wrapper {
  position: relative;
}

.json-editor {
  width: 100%;
  min-height: 120px;
  padding: 12px;
  background-color: #0f172a;
  color: #cbd5e1;
  border: none;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 