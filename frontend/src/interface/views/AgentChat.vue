<template>
  <div class="agent-chat">
    <el-container class="chat-layout">
      <!-- 左侧：会话列表 -->
      <el-aside width="260px" class="conversation-sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">对话</span>
          <el-button size="small" type="primary" plain @click="handleNewChat">
            + 新对话
          </el-button>
        </div>
        <div class="conversation-list">
          <div
            v-for="conv in store.conversations"
            :key="conv.id"
            class="conversation-item"
            :class="{ active: conv.id === store.currentConversationId }"
            @click="handleSelectConversation(conv.id)"
          >
            <div class="conv-title">{{ conv.title }}</div>
            <div class="conv-meta">
              <span>{{ conv.message_count }} 条消息</span>
              <el-dropdown trigger="click" @command="(cmd: string) => handleConvAction(cmd, conv)">
                <span class="conv-more" @click.stop>...</span>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="rename">重命名</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
          <div v-if="store.conversations.length === 0" class="no-conversations">
            暂无对话记录
          </div>
        </div>
      </el-aside>

      <!-- 中间：聊天区域 -->
      <el-main class="chat-main">
        <!-- 消息列表 -->
        <div class="messages" ref="messagesRef" v-loading="isLoading">
          <!-- 空状态：推荐问题 -->
          <div v-if="messages.length === 0 && !isLoading" class="empty-state">
            <div class="welcome-section">
              <h2 class="welcome-title">Nova Agent</h2>
              <p class="welcome-desc">电商选品分析助手，试试以下问题：</p>
              <div class="quick-actions">
                <div
                  v-for="action in quickActions"
                  :key="action.text"
                  class="quick-action-card"
                  @click="handleQuickAction(action.text)"
                >
                  <span class="action-icon">{{ action.icon }}</span>
                  <span class="action-text">{{ action.label }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 消息 -->
          <div v-for="msg in messages" :key="msg.id" class="message-wrapper">
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" class="message user">
              <div class="avatar">👤</div>
              <div class="bubble user-bubble">
                <div class="content" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>

            <!-- Assistant 消息 -->
            <div v-else-if="msg.role === 'assistant'" class="message assistant">
              <div class="avatar">🤖</div>
              <div class="bubble assistant-bubble">
                <div class="content" v-html="renderMarkdown(msg.content)"></div>
                <div class="message-meta">
                  <span v-if="msg.tokenUsage" class="token-usage">
                    ⚡ {{ msg.tokenUsage }} tokens
                  </span>
                </div>
              </div>
            </div>

            <!-- 工具调用提示 -->
            <div v-else-if="msg.role === 'tool'" class="message tool">
              <div class="tool-badge">🔧 {{ msg.toolName || '工具' }}</div>
              <div v-if="msg.content" class="tool-result">
                <pre>{{ msg.content.slice(0, 300) }}{{ msg.content.length > 300 ? '...' : '' }}</pre>
              </div>
            </div>
          </div>

          <!-- 流式输出中的当前消息 -->
          <div v-if="streamingContent" class="message assistant">
            <div class="avatar">🤖</div>
            <div class="bubble assistant-bubble streaming">
              <div class="content" v-html="renderMarkdown(streamingContent)"></div>
              <div class="cursor-blink">▍</div>
            </div>
          </div>

          <!-- 简报可视化图表 -->
          <BriefingCard v-if="briefingData" :data="briefingData" />

          <!-- 状态提示 -->
          <div v-if="currentStatus && !streamingContent" class="status-indicator">
            <el-icon class="is-loading"><Loading /></el-icon>
            {{ currentStatus }}
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
          <!-- 快捷指令菜单 -->
          <div v-if="showCommandMenu" class="command-menu">
            <div
              v-for="opt in commandOptions"
              :key="opt.command"
              class="command-item"
              @click="selectCommand(opt.command)"
            >
              <span class="cmd-name">{{ opt.command }}</span>
              <span class="cmd-desc">{{ opt.desc }}</span>
            </div>
          </div>
          <div class="input-wrapper">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="2"
              placeholder="输入你的问题，或输入 / 查看快捷指令..."
              :disabled="isSending"
              @keydown.enter.prevent="handleEnter"
              @keydown.shift.enter="handleShiftEnter"
              @input="handleInputChange"
            />
            <div class="input-actions">
              <el-button
                v-if="isSending"
                type="danger"
                plain
                :icon="Close"
                @click="cancelStream"
              >
                停止
              </el-button>
              <el-button
                v-else
                type="primary"
                :disabled="!inputText.trim()"
                @click="sendMessage"
              >
                发送
              </el-button>
            </div>
          </div>
        </div>
      </el-main>

      <!-- 右侧：选品分析树面板 -->
      <el-aside width="360px" class="tree-panel">
        <div class="tree-header">
          <h3>🌳 选品分析树</h3>
          <span v-if="treeBranches.length > 0" class="tree-round-badge">
            第 {{ treeRound }} 轮
          </span>
        </div>

        <div class="tree-content">
          <!-- 空状态 -->
          <div v-if="treeBranches.length === 0" class="tree-empty">
            <el-empty description="发送选品分析请求后，这里将实时展示分析树" :image-size="60" />
          </div>

          <!-- 分析树 -->
          <div v-else class="tree-list">
            <div
              v-for="branch in treeBranches"
              :key="branch.branch_id"
              class="tree-branch"
              :class="branch.status"
            >
              <!-- 分支头部 -->
              <div class="branch-header">
                <div class="branch-status-icon">
                  <span v-if="branch.status === 'running'" class="status-spinner"></span>
                  <span v-else-if="branch.status === 'completed'">✅</span>
                  <span v-else-if="branch.status === 'error'">❌</span>
                  <span v-else-if="branch.status === 'partial'">⚠️</span>
                  <span v-else>⬜</span>
                </div>
                <span class="branch-label">{{ branch.label }}</span>
                <div class="branch-actions">
                  <el-tooltip content="追加维度" placement="top">
                    <el-button
                      link
                      size="small"
                      @click="handleAppendDimension(branch)"
                      :disabled="isSending"
                    >
                      +维度
                    </el-button>
                  </el-tooltip>
                  <el-tooltip content="回溯至此" placement="top">
                    <el-button
                      link
                      size="small"
                      @click="handleBacktrack(branch.invocations[branch.invocations.length - 1])"
                      :disabled="isSending"
                    >
                      回溯
                    </el-button>
                  </el-tooltip>
                </div>
              </div>

              <!-- 分支下的 invocation 节点 -->
              <div class="branch-invocations">
                <div
                  v-for="inv in branch.invocations"
                  :key="inv.invocation_id"
                  class="tree-invocation"
                  :class="inv.status"
                >
                  <div class="inv-header">
                    <span class="inv-status-icon">
                      <span v-if="inv.status === 'running'" class="status-spinner-sm"></span>
                      <span v-else-if="inv.status === 'completed'">✅</span>
                      <span v-else>❌</span>
                    </span>
                    <div class="inv-dimensions">
                      <span
                        v-for="dim in inv.dimensions"
                        :key="dim"
                        class="dim-tag"
                      >{{ dim }}</span>
                      <span v-if="inv.dimensions.length === 0" class="dim-tag dim-default">
                        {{ inv.branch_label }}
                      </span>
                    </div>
                  </div>
                  <div v-if="inv.result_summary" class="inv-summary">
                    {{ inv.result_summary }}
                  </div>
                  <div v-if="inv.error_message" class="inv-error">
                    {{ inv.error_message }}
                  </div>
                  <div class="inv-meta">
                    <span v-if="inv.started_at" class="inv-time">
                      {{ formatTimeStr(inv.started_at) }}
                    </span>
                    <el-tooltip content="回溯到此节点" placement="top">
                      <el-button
                        link
                        size="small"
                        class="inv-backtrack-btn"
                        @click="handleBacktrack(inv)"
                        :disabled="isSending"
                      >
                        回溯
                      </el-button>
                    </el-tooltip>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-aside>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Close } from '@element-plus/icons-vue'
import {
  streamChat,
  type SSEEvent,
  type ToolCallData,
  type TreeBranchData,
  type TreeInvocation,
  type TreeNodeAddedData,
  type TreeNodeStatusData,
  type TreeFullData,
  getAnalysisTree,
  backtrackAnalysis,
  appendDimension,
} from '@/api/agentChat'
import { useAgentChatStore } from '@/state/agentChat'
import BriefingCard from '@/interface/components/charts/BriefingCard.vue'

const store = useAgentChatStore()

// ── 消息类型 ──

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  createdAt: string
  toolName?: string
  tokenUsage?: number
}

// ── 状态 ──

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const isSending = ref(false)
const isLoading = ref(false)
const streamingContent = ref('')
const currentStatus = ref('')
const conversationId = ref('')
const briefingData = ref<Record<string, any> | null>(null)

// ── 分析树状态 ──
const treeBranches = ref<TreeBranchData[]>([])
const treeRound = ref(0)
const pendingInvocations = ref<Map<string, TreeNodeStatusData>>(new Map())

let abortController: AbortController | null = null
let msgCounter = 0

const messagesRef = ref<HTMLElement | null>(null)

const quickActions = [
  { icon: '🎧', label: '分析蓝牙耳机市场趋势', text: '分析蓝牙耳机市场趋势' },
  { icon: '📊', label: '对比 Top 5 竞品品牌', text: '帮我对比蓝牙耳机类目 Top 5 竞品品牌的市场份额和定价策略' },
  { icon: '💰', label: '评估选品盈利空间', text: '评估蓝牙耳机选品的盈利空间，包括月收入和利润率' },
  { icon: '🔍', label: '寻找低竞争高需求机会', text: '帮我寻找低竞争高需求的电商选品机会' },
]

function handleQuickAction(text: string) {
  inputText.value = text
  sendMessage()
}

// ── 快捷指令菜单 ──

const showCommandMenu = ref(false)
const commandOptions = [
  { command: '/选品', label: '选品分析', desc: '输入关键词开始选品' },
  { command: '/竞品', label: '竞品对比', desc: '分析竞品品牌格局' },
  { command: '/报告', label: '生成报告', desc: '生成完整选品简报' },
  { command: '/成本', label: '查看成本', desc: '查看 AI 调用成本' },
]

function handleInputChange() {
  showCommandMenu.value = inputText.value === '/'
}

function selectCommand(cmd: string) {
  inputText.value = cmd + ' '
  showCommandMenu.value = false
}

// ── 核心方法 ──

function sendMessage() {
  const content = inputText.value.trim()
  if (!content || isSending.value) return

  // 添加用户消息
  messages.value.push({
    id: `msg-${++msgCounter}`,
    role: 'user',
    content,
    createdAt: new Date().toISOString(),
  })
  inputText.value = ''
  isSending.value = true
  streamingContent.value = ''
  currentStatus.value = '🤖 开始分析...'

  scrollToBottom()

  // 发起 SSE 请求
  abortController = streamChat(
    content,
    conversationId.value || undefined,
    handleSSEEvent,
  )
}

function handleSSEEvent(event: SSEEvent) {
  const { type, data, conversation_id } = event
  conversationId.value = conversation_id

  switch (type) {
    case 'status':
      currentStatus.value = data as string
      break

    case 'agent_start': {
      const info = data as unknown as { name: string; args: Record<string, unknown> }
      currentStatus.value = `⚙️ ${info.name} 执行中...`
      break
    }

    case 'agent_end': {
      const info = data as unknown as { name: string; elapsed_s: number | null }
      const elapsed = info.elapsed_s != null ? ` (${info.elapsed_s}s)` : ''
      currentStatus.value = `✓ ${info.name} 完成${elapsed}`
      break
    }

    case 'tool_call': {
      const tc = data as unknown as ToolCallData
      currentStatus.value = `🔧 调用 ${tc.name}...`
      break
    }

    case 'tool_result':
      currentStatus.value = data as string
      break

    case 'tree_node_status': {
      const statusData = data as unknown as TreeNodeStatusData
      handleTreeNodeStatus(statusData)
      break
    }

    case 'tree_node_added': {
      const addedData = data as unknown as TreeNodeAddedData
      handleTreeNodeAdded(addedData)
      break
    }

    case 'tree_full': {
      const treeData = data as unknown as TreeFullData
      handleTreeFull(treeData)
      break
    }

    case 'briefing_data':
      briefingData.value = data as unknown as Record<string, any>
      break

    case 'start_response':
      currentStatus.value = ''
      streamingContent.value = ''
      break

    case 'response_chunk':
      streamingContent.value += (data as string)
      scrollToBottom()
      break

    case 'done':
      if (streamingContent.value) {
        messages.value.push({
          id: `msg-${++msgCounter}`,
          role: 'assistant',
          content: streamingContent.value,
          createdAt: new Date().toISOString(),
          tokenUsage: undefined,
        })
        streamingContent.value = ''
      }
      isSending.value = false
      currentStatus.value = ''
      abortController = null
      store.setCurrentConversationId(conversationId.value)
      store.loadConversations()

      // 清空运行中的 invocation
      pendingInvocations.value.clear()

      scrollToBottom()
      break

    case 'error':
      ElMessage.error(data as string)
      isSending.value = false
      currentStatus.value = ''
      abortController = null
      break
  }
}

function cancelStream() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  isSending.value = false
  currentStatus.value = '已取消'
  streamingContent.value = ''
}

// ── 分析树面板 ──

function handleTreeNodeStatus(statusData: TreeNodeStatusData) {
  // 记录 pending invocation（状态为 running）
  pendingInvocations.value.set(statusData.invocation_id, statusData)

  // 查找或创建分支
  let branch = treeBranches.value.find(b => b.branch_id === statusData.agent_name)
  if (!branch) {
    branch = {
      branch_id: statusData.agent_name,
      agent_name: statusData.agent_name,
      label: statusData.branch_label,
      status: 'running',
      invocations: [],
    }
    treeBranches.value.push(branch)
  } else {
    branch.status = 'running'
  }

  // 添加运行中的 invocation
  const existing = branch.invocations.find(
    inv => inv.invocation_id === statusData.invocation_id
  )
  if (!existing) {
    branch.invocations.push({
      invocation_id: statusData.invocation_id,
      agent_name: statusData.agent_name,
      branch_label: statusData.branch_label,
      params: {},
      dimensions: statusData.dimensions,
      result_summary: '',
      status: 'running',
      parent_invocation_id: null,
      checkpoint_id: null,
      conversation_round: 0,
      started_at: new Date().toISOString(),
      completed_at: null,
      error_message: null,
    })
  }
}

function handleTreeNodeAdded(addedData: TreeNodeAddedData) {
  pendingInvocations.value.delete(addedData.invocation_id)

  // 查找分支
  let branch = treeBranches.value.find(b => b.branch_id === addedData.agent_name)
  if (!branch) {
    branch = {
      branch_id: addedData.agent_name,
      agent_name: addedData.agent_name,
      label: addedData.branch_label,
      status: addedData.status === 'completed' ? 'completed' : 'error',
      invocations: [],
    }
    treeBranches.value.push(branch)
  }

  // 查找或更新 invocation
  const existing = branch.invocations.find(
    inv => inv.invocation_id === addedData.invocation_id
  )
  if (existing) {
    existing.status = addedData.status
    existing.result_summary = addedData.result_summary
    existing.checkpoint_id = addedData.checkpoint_id
    existing.completed_at = addedData.completed_at
    existing.error_message = addedData.error_message
    existing.dimensions = addedData.dimensions
  } else {
    branch.invocations.push({
      invocation_id: addedData.invocation_id,
      agent_name: addedData.agent_name,
      branch_label: addedData.branch_label,
      params: {},
      dimensions: addedData.dimensions,
      result_summary: addedData.result_summary,
      status: addedData.status,
      parent_invocation_id: addedData.parent_invocation_id,
      checkpoint_id: addedData.checkpoint_id,
      conversation_round: addedData.conversation_round,
      started_at: addedData.started_at,
      completed_at: addedData.completed_at,
      error_message: addedData.error_message,
    })
  }

  // 更新分支状态
  updateBranchStatus(branch)
}

function handleTreeFull(treeData: TreeFullData) {
  treeBranches.value = treeData.branches
  treeRound.value = treeData.conversation_round
}

function updateBranchStatus(branch: TreeBranchData) {
  const statuses = branch.invocations.map(inv => inv.status)
  if (statuses.includes('running')) {
    branch.status = 'running'
  } else if (statuses.every(s => s === 'completed')) {
    branch.status = 'completed'
  } else if (statuses.every(s => s === 'error')) {
    branch.status = 'error'
  } else if (statuses.includes('completed')) {
    branch.status = 'partial'
  } else {
    branch.status = 'pending'
  }
}

async function handleBacktrack(inv: TreeInvocation) {
  if (!inv.invocation_id || !conversationId.value) return
  try {
    await ElMessageBox.confirm(
      `确定回溯到 [${inv.branch_label}] 节点？该节点之后的所有分析将被撤销。`,
      '回溯确认',
      { confirmButtonText: '确定回溯', cancelButtonText: '取消', type: 'warning' }
    )
    const result = await backtrackAnalysis(conversationId.value, inv.invocation_id)
    ElMessage.success(result.message)
    // 从树中移除该 invocation 之后的所有节点
    treeBranches.value.forEach(branch => {
      const idx = branch.invocations.findIndex(i => i.invocation_id === inv.invocation_id)
      if (idx >= 0) {
        branch.invocations = branch.invocations.slice(0, idx + 1)
      }
    })
    // 移除后面分支的所有 invocation
    const branchIdx = treeBranches.value.findIndex(b => b.branch_id === inv.agent_name)
    if (branchIdx >= 0) {
      // 标记后续分支为 pending
      for (let i = branchIdx + 1; i < treeBranches.value.length; i++) {
        treeBranches.value[i].status = 'pending'
        treeBranches.value[i].invocations = []
      }
    }
    // 更新分支状态
    treeBranches.value.forEach(b => updateBranchStatus(b))
  } catch {
    // 用户取消
  }
}

async function handleAppendDimension(branch: TreeBranchData) {
  if (!conversationId.value || branch.invocations.length === 0) return
  try {
    const { value: dimLabel } = await ElMessageBox.prompt(
      '请输入要追加的分析维度（例如："Q4旺季对比"、"价格弹性分析"）',
      `追加维度 - ${branch.label}`,
      { confirmButtonText: '追加', cancelButtonText: '取消' }
    )
    if (!dimLabel || !dimLabel.trim()) return
    const result = await appendDimension(
      conversationId.value,
      branch.agent_name,
      dimLabel.trim(),
    )
    ElMessage.success(result.message)
  } catch {
    // 用户取消
  }
}

// ── 工具函数 ──

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function handleEnter(e: KeyboardEvent) {
  if (!e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function handleShiftEnter() {
  // 默认换行
}

function formatTimeStr(isoStr: string) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&' + 'amp;',
    '<': '&' + 'lt;',
    '>': '&' + 'gt;',
  }
  return text.replace(/[&<>]/g, ch => map[ch])
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  
  // 第一步：先逃逸 HTML 特殊字符
  let html = escapeHtml(text)
  
  // 代码块 (```code```) — 必须在逃逸后执行
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  
  // 行内代码 (`code`)
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  
  // 粗体 **text**
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  
  // 无序列表
  html = html.replace(/^- (.*)$/gm, '<li>$1</li>')
  
  // 有序列表
  html = html.replace(/^\d+\.\s+(.*)$/gm, '<li>$1</li>')
  
  // 换行
  html = html.replace(/\n/g, '<br>')
  
  return html
}

// ── 生命周期 ──

onMounted(() => {
  store.loadConversations()
})

// ── 会话管理 ──

function handleNewChat() {
  store.newConversation()
  messages.value = []
  conversationId.value = ''
  treeBranches.value = []
  treeRound.value = 0
  pendingInvocations.value.clear()
  briefingData.value = null
}

async function handleSelectConversation(convId: string) {
  await store.selectConversation(convId)
  conversationId.value = convId
  messages.value = store.messages.map((m, i) => ({
    id: `msg-${i}`,
    role: m.role as ChatMessage['role'],
    content: m.content,
    createdAt: m.createdAt,
  }))
  // 加载该对话的树
  loadTreeForConversation(convId)
  scrollToBottom()
}

async function loadTreeForConversation(convId: string) {
  try {
    const res = await getAnalysisTree(convId)
    if (res.tree) {
      treeBranches.value = res.tree.branches
      treeRound.value = res.tree.conversation_round
    } else {
      treeBranches.value = []
      treeRound.value = 0
    }
    pendingInvocations.value.clear()
  } catch {
    treeBranches.value = []
    treeRound.value = 0
  }
}

function handleConvAction(cmd: string, conv: { id: string; title: string }) {
  if (cmd === 'rename') {
    ElMessageBox.prompt('输入新标题', '重命名', {
      inputValue: conv.title,
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    }).then(({ value }) => {
      if (value?.trim()) {
        store.renameConversation(conv.id, value.trim())
      }
    }).catch(() => {})
  } else if (cmd === 'delete') {
    ElMessageBox.confirm('确定删除该对话？', '删除', {
      type: 'warning',
    }).then(() => {
      store.removeConversation(conv.id)
      if (conversationId.value === conv.id) {
        handleNewChat()
      }
    }).catch(() => {})
  }
}

// ── 清理 ──

onBeforeUnmount(() => {
  if (abortController) {
    abortController.abort()
  }
})
</script>

<style scoped>
.agent-chat {
  height: calc(100vh - 60px);
  background-color: #f5f7fa;
}

.chat-layout {
  height: 100%;
}

/* ── 会话侧边栏 ── */

.conversation-sidebar {
  background: #fff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.sidebar-title {
  font-size: 15px;
  font-weight: 600;
  color: #334155;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conversation-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
}

.conversation-item:hover {
  background: #f1f5f9;
}

.conversation-item.active {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.conv-title {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
}

.conv-more {
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: bold;
  letter-spacing: 1px;
}

.conv-more:hover {
  background: #e2e8f0;
}

.no-conversations {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 24px 0;
}

/* ── 聊天主区域 ── */

.chat-main {
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  background: white;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.message-wrapper {
  margin-bottom: 16px;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 16px;
  line-height: 1.6;
  font-size: 14px;
}

.user-bubble {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white;
  border-bottom-right-radius: 4px;
}

.assistant-bubble {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 4px;
  color: #1e293b;
}

.assistant-bubble.streaming {
  border-color: #93c5fd;
}

.content {
  word-break: break-word;
  white-space: pre-wrap;
}

.content :deep(pre.code-block) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.4;
}

.content :deep(code) {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: #dc2626;
}

.content :deep(strong) {
  font-weight: 600;
}

.content :deep(li) {
  margin: 4px 0;
  padding-left: 8px;
}

.cursor-blink {
  display: inline;
  animation: blink 1s step-end infinite;
  color: #3b82f6;
}

@keyframes blink {
  50% { opacity: 0; }
}

.message-meta {
  margin-top: 8px;
  font-size: 11px;
  color: #94a3b8;
}

/* 工具消息 */
.message.tool {
  justify-content: center;
  gap: 8px;
}

.tool-badge {
  background: #fef3c7;
  color: #92400e;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.tool-result {
  max-width: 60%;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 12px;
  margin: 0 auto;
}

.tool-result pre {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 状态指示器 */
.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  color: #64748b;
  font-size: 13px;
  justify-content: center;
}

/* ── 输入区域 ── */

.input-area {
  position: relative;
  padding: 16px 24px;
  border-top: 1px solid #e2e8f0;
  background: white;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
}

/* ── 分析树面板 ── */

.tree-panel {
  background: #fafbfc;
  border-left: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.tree-header h3 {
  margin: 0;
  font-size: 15px;
  color: #334155;
}

.tree-round-badge {
  font-size: 12px;
  color: #64748b;
  background: #e2e8f0;
  padding: 2px 8px;
  border-radius: 10px;
}

.tree-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.tree-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.tree-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Tree Branch ── */

.tree-branch {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 0.2s;
}

.tree-branch.running {
  border-color: #93c5fd;
  box-shadow: 0 0 0 1px #bfdbfe;
}

.tree-branch.completed {
  border-color: #86efac;
}

.tree-branch.error {
  border-color: #fca5a5;
}

.branch-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #f8fafc;
  border-bottom: 1px solid #f1f5f9;
}

.branch-status-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.branch-label {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  flex: 1;
}

.branch-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

.tree-branch:hover .branch-actions {
  opacity: 1;
}

/* ── Tree Invocation ── */

.branch-invocations {
  padding: 6px 12px 6px 24px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tree-invocation {
  padding: 8px 10px;
  border-radius: 6px;
  background: #f8fafc;
  border-left: 3px solid #e2e8f0;
  transition: border-color 0.2s;
}

.tree-invocation.running {
  border-left-color: #3b82f6;
  background: #eff6ff;
}

.tree-invocation.completed {
  border-left-color: #22c55e;
}

.tree-invocation.error {
  border-left-color: #ef4444;
  background: #fef2f2;
}

.inv-header {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.inv-status-icon {
  font-size: 12px;
  flex-shrink: 0;
  margin-top: 1px;
}

.inv-dimensions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex: 1;
}

.dim-tag {
  font-size: 11px;
  padding: 1px 6px;
  background: #dbeafe;
  color: #1e40af;
  border-radius: 4px;
  white-space: nowrap;
}

.dim-tag.dim-default {
  background: #f1f5f9;
  color: #64748b;
}

.inv-summary {
  margin-top: 6px;
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}

.inv-error {
  margin-top: 4px;
  font-size: 12px;
  color: #dc2626;
}

.inv-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
}

.inv-time {
  font-size: 11px;
  color: #94a3b8;
}

.inv-backtrack-btn {
  font-size: 11px;
  opacity: 0;
  transition: opacity 0.15s;
}

.tree-invocation:hover .inv-backtrack-btn {
  opacity: 1;
}

/* ── Status Spinner ── */

.status-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.status-spinner-sm {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── 推荐问题卡片 ── */

.welcome-section {
  text-align: center;
  padding: 48px 24px;
}

.welcome-title {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 8px;
}

.welcome-desc {
  color: #64748b;
  font-size: 14px;
  margin-bottom: 24px;
}

.quick-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  max-width: 500px;
  margin: 0 auto;
}

.quick-action-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.quick-action-card:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
  transform: translateY(-1px);
}

.action-icon {
  font-size: 20px;
}

.action-text {
  font-size: 13px;
  color: #334155;
  text-align: left;
}

/* ── 快捷指令菜单 ── */

.command-menu {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  margin-bottom: 8px;
  z-index: 10;
}

.command-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.1s;
}

.command-item:hover {
  background: #f1f5f9;
}

.command-item:first-child {
  border-radius: 8px 8px 0 0;
}

.command-item:last-child {
  border-radius: 0 0 8px 8px;
}

.cmd-name {
  font-weight: 600;
  font-size: 13px;
  color: #3b82f6;
  min-width: 50px;
}

.cmd-desc {
  font-size: 12px;
  color: #64748b;
}
</style>