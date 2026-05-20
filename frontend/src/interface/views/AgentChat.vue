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

      <!-- 右侧：工具轨迹面板 -->
      <el-aside width="360px" class="trace-panel">
        <div class="trace-header">
          <h3><el-icon><Monitor /></el-icon> 工具执行轨迹</h3>
          <el-button
            v-if="traceLogs.length > 0"
            link
            size="small"
            @click="clearTrace"
          >
            清空
          </el-button>
        </div>

        <div class="trace-content">
          <!-- 空状态 -->
          <div v-if="traceLogs.length === 0" class="trace-empty">
            <el-empty description="暂无工具调用记录" :image-size="60" />
          </div>

          <!-- 轨迹时间线 -->
          <div v-else class="trace-timeline">
            <div
              v-for="(log, index) in traceLogs"
              :key="index"
              class="trace-item"
              :class="log.type"
            >
              <div class="trace-dot">
                <el-icon v-if="log.type === 'tool_call'"><Cpu /></el-icon>
                <el-icon v-else-if="log.type === 'tool_result'"><Select /></el-icon>
                <el-icon v-else-if="log.type === 'error'"><WarningFilled /></el-icon>
                <el-icon v-else><InfoFilled /></el-icon>
              </div>
              <div class="trace-body">
                <div class="trace-title">{{ log.title }}</div>
                <div v-if="log.detail" class="trace-detail">
                  <pre>{{ log.detail }}</pre>
                </div>
                <div v-if="log.args" class="trace-args">
                  <el-collapse accordion>
                    <el-collapse-item title="查看参数" name="1">
                      <pre>{{ JSON.stringify(log.args, null, 2) }}</pre>
                    </el-collapse-item>
                  </el-collapse>
                </div>
                <div class="trace-time">{{ formatTime(log.timestamp) }}</div>
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
import { Loading, Close, Monitor, Cpu, Select, WarningFilled, InfoFilled } from '@element-plus/icons-vue'
import { streamChat, type SSEEvent, type ToolCallData } from '@/api/agentChat'
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

interface TraceLog {
  type: 'status' | 'tool_call' | 'tool_result' | 'error'
  title: string
  detail?: string
  args?: Record<string, unknown>
  timestamp: number
}

// ── 状态 ──

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const isSending = ref(false)
const isLoading = ref(false)
const streamingContent = ref('')
const currentStatus = ref('')
const traceLogs = ref<TraceLog[]>([])
const conversationId = ref('')
const briefingData = ref<Record<string, any> | null>(null)

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
      addTraceLog('status', data as string)
      break

    case 'agent_start': {
      const info = data as unknown as { name: string; args: Record<string, unknown> }
      currentStatus.value = `⚙️ ${info.name} 执行中...`
      addTraceLog('tool_call', `▶ ${info.name} 开始执行`, info.args)
      break
    }

    case 'agent_end': {
      const info = data as unknown as { name: string; elapsed_s: number | null }
      const elapsed = info.elapsed_s != null ? ` (${info.elapsed_s}s)` : ''
      addTraceLog('tool_result', `✓ ${info.name} 完成${elapsed}`)
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
      // 完成，将流式内容转为正式消息
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

// ── 轨迹面板 ──

function addTraceLog(type: TraceLog['type'], title: string, args?: Record<string, unknown>) {
  traceLogs.value.push({
    type,
    title,
    args,
    timestamp: Date.now(),
  })
  // 最多保留 50 条
  if (traceLogs.value.length > 50) {
    traceLogs.value.splice(0, traceLogs.value.length - 50)
  }
}

function clearTrace() {
  traceLogs.value = []
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

function formatTime(ts: number) {
  const d = new Date(ts)
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
  traceLogs.value = []
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
  traceLogs.value = []
  scrollToBottom()
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

/* ── 轨迹面板 ── */

.trace-panel {
  background: #fafbfc;
  border-left: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.trace-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.trace-header h3 {
  margin: 0;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #334155;
}

.trace-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.trace-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.trace-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.trace-item {
  display: flex;
  gap: 12px;
  padding: 12px 8px;
  border-left: 2px solid #e2e8f0;
  margin-left: 8px;
  position: relative;
}

.trace-item:last-child {
  border-left-color: transparent;
}

.trace-dot {
  position: absolute;
  left: -9px;
  top: 14px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: white;
  border: 2px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
}

.trace-item.tool_call .trace-dot {
  border-color: #3b82f6;
  color: #3b82f6;
}

.trace-item.tool_result .trace-dot {
  border-color: #22c55e;
  color: #22c55e;
}

.trace-item.error .trace-dot {
  border-color: #ef4444;
  color: #ef4444;
}

.trace-body {
  flex: 1;
  min-width: 0;
}

.trace-title {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  margin-bottom: 4px;
}

.trace-detail {
  margin-top: 4px;
}

.trace-detail pre {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  white-space: pre-wrap;
  word-break: break-word;
}

.trace-args {
  margin-top: 4px;
}

.trace-args :deep(.el-collapse-item__header) {
  font-size: 12px;
  padding: 4px 0;
}

.trace-args :deep(.el-collapse-item__content) {
  padding: 8px;
  background: #f1f5f9;
  border-radius: 4px;
}

.trace-args pre {
  margin: 0;
  font-size: 11px;
  white-space: pre-wrap;
}

.trace-time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
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