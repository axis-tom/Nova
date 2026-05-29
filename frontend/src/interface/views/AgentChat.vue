<template>
  <div class="agent-chat">
    <!-- 左侧：会话列表 -->
    <div v-show="showSidebar" class="panel panel-left" :style="{ width: sidebarWidth + 'px' }">
      <div class="sidebar-header">
        <span class="sidebar-title">对话</span>
        <div class="sidebar-header-actions">
          <el-button size="small" type="primary" plain @click="handleNewChat">
            + 新对话
          </el-button>
          <el-button size="small" circle @click="showSidebar = false">
            ✕
          </el-button>
        </div>
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
      <!-- 拖拽手柄 -->
      <div class="resize-handle" @mousedown.stop="(e: MouseEvent) => startResize(e, 'sidebar')"></div>
    </div>

    <!-- 中间：聊天区域 -->
    <div class="panel panel-center">
      <!-- 显示/隐藏侧栏按钮 -->
      <button v-if="!showSidebar" class="sidebar-toggle-btn" @click="showSidebar = true">
        ☰
      </button>
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

        <!-- 简报可视化图表（兼容旧数据格式） -->
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
      <!-- 拖拽手柄 -->
      <div class="resize-handle" @mousedown.stop="(e: MouseEvent) => startResize(e, 'cockpit')"></div>
    </div>

    <!-- 右侧：多维驾驶舱 -->
    <div class="panel panel-right" :style="{ width: cockpitWidth + 'px' }">
      <CockpitPanel
        :categories="cockpitCategories"
        @set-priority="handleCockpitSetPriority"
        @toggle-dimension="handleCockpitToggleDimension"
        @follow-up="handleCockpitFollowUp"
        @supplement="handleCockpitSupplement"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Close } from '@element-plus/icons-vue'
import { marked } from 'marked'
import {
  streamChat,
  type SSEEvent,
  type ToolCallData,
  type CockpitCategory,
  type CockpitUpdateData,
  type CockpitDimension,
} from '@/api/agentChat'
import { useAgentChatStore } from '@/state/agentChat'
import CockpitPanel from '@/interface/components/cockpit/CockpitPanel.vue'
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

// ── 可拖拽面板状态 ──
const sidebarWidth = ref(240)
const cockpitWidth = ref(420)
const minPanelWidth = 180
const showSidebar = ref(true)
let isResizing = false
let currentResizeTarget: 'sidebar' | 'cockpit' | null = null
let startX = 0
let startWidth = 0

function startResize(e: MouseEvent, target: 'sidebar' | 'cockpit') {
  isResizing = true
  currentResizeTarget = target
  startX = e.clientX
  startWidth = target === 'sidebar' ? sidebarWidth.value : cockpitWidth.value
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', stopResize)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onMouseMove(e: MouseEvent) {
  if (!isResizing || !currentResizeTarget) return
  const delta = e.clientX - startX
  if (currentResizeTarget === 'sidebar') {
    const newWidth = Math.max(minPanelWidth, Math.min(500, startWidth + delta))
    sidebarWidth.value = newWidth
  } else if (currentResizeTarget === 'cockpit') {
    // 驾驶舱从右边缘拖动
    const newWidth = Math.max(minPanelWidth, Math.min(600, startWidth - delta))
    cockpitWidth.value = newWidth
  }
}

function stopResize() {
  isResizing = false
  currentResizeTarget = null
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// ── 消息类型 ──
const inputText = ref('')
const isSending = ref(false)
const isLoading = ref(false)
const streamingContent = ref('')
const currentStatus = ref('')
const conversationId = ref('')
const briefingData = ref<Record<string, any> | null>(null)
const messages = ref<ChatMessage[]>([])

// ── 多维驾驶舱状态 ──
const cockpitCategories = ref<CockpitCategory[]>([])

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

    case 'cockpit_update': {
      const cockpitData = data as unknown as CockpitUpdateData
      handleCockpitUpdate(cockpitData)
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

function cancelStream() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  isSending.value = false
  currentStatus.value = '已取消'
  streamingContent.value = ''
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  return marked.parse(text, { breaks: true, gfm: true }) as string
}

// ── 多维驾驶舱 ──

function handleCockpitUpdate(data: CockpitUpdateData) {
  const idx = cockpitCategories.value.findIndex(c => c.agent_name === data.agent_name)
  if (idx >= 0) {
    const existing = cockpitCategories.value[idx]
    for (const newDim of data.dimensions) {
      const dimIdx = existing.dimensions.findIndex(d => d.dimension_id === newDim.dimension_id)
      if (dimIdx >= 0) {
        existing.dimensions[dimIdx] = { ...existing.dimensions[dimIdx], ...newDim }
      } else {
        existing.dimensions.push(newDim)
      }
    }
  } else {
    cockpitCategories.value.push({
      agent_name: data.agent_name,
      category_label: data.category_label,
      priority: false,
      collapsed: false,
      dimensions: data.dimensions,
    })
  }
}

// ── 驾驶舱交互 ──

function handleCockpitSetPriority(agentName: string) {
  const cat = cockpitCategories.value.find(c => c.agent_name === agentName)
  if (cat) {
    cat.priority = !cat.priority
    // 可扩展：发送 API 请求通知后端
  }
}

function handleCockpitToggleDimension(agentName: string, dimId: string) {
  const cat = cockpitCategories.value.find(c => c.agent_name === agentName)
  if (!cat) return
  const dim = cat.dimensions.find(d => d.dimension_id === dimId)
  if (dim) {
    dim.enabled = !dim.enabled
    // 可扩展：发送 POST /api/dimension/disable
  }
}

function handleCockpitFollowUp(agentName: string, _dimId: string) {
  const cat = cockpitCategories.value.find(c => c.agent_name === agentName)
  if (cat) {
    cat.priority = true
    // 可扩展：在输入框预填"继续分析 {category_label}"
  }
}

function handleCockpitSupplement(agentName: string, _dimId: string) {
  // 可扩展：触发文件上传
  ElMessage.info('补充数据功能开发中')
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
  cockpitCategories.value = []
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
  height: 100vh;
  background-color: #f5f7fa;
  display: flex;
  overflow: hidden;
}

/* ── 三栏 flex 布局 ── */

.panel {
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.panel-left {
  background: #fff;
  border-right: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.panel-center {
  background: white;
  flex: 1;
  min-width: 0;
}

.panel-right {
  background: #fafbfc;
  border-left: 1px solid #e2e8f0;
  flex-shrink: 0;
}

/* ── 拖拽手柄 ── */

.resize-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 5px;
  cursor: col-resize;
  z-index: 10;
  transition: background 0.15s;
}
.resize-handle:hover {
  background: #3b82f6;
}
.panel-left .resize-handle {
  right: -3px;
}
.panel-center .resize-handle {
  right: -3px;
}

/* ── 会话侧边栏 ── */

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.sidebar-header-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.sidebar-title {
  font-size: 15px;
  font-weight: 600;
  color: #334155;
}

/* 侧栏显示/隐藏按钮 */
.sidebar-toggle-btn {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 10;
  width: 32px;
  height: 32px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: white;
  color: #64748b;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.sidebar-toggle-btn:hover {
  background: #f1f5f9;
  border-color: #3b82f6;
  color: #3b82f6;
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

/* GitHub-flavored Markdown 样式 */
.content :deep(h1),
.content :deep(h2),
.content :deep(h3),
.content :deep(h4) {
  margin: 14px 0 8px;
  font-weight: 600;
  color: #1e293b;
}
.content :deep(h1) { font-size: 18px; border-bottom: 1px solid #e8ecf1; padding-bottom: 6px; }
.content :deep(h2) { font-size: 16px; border-bottom: 1px solid #e8ecf1; padding-bottom: 4px; }
.content :deep(h3) { font-size: 14px; }
.content :deep(p) { margin: 6px 0; line-height: 1.7; }
.content :deep(ul),
.content :deep(ol) { padding-left: 20px; margin: 6px 0; }
.content :deep(li) { margin: 3px 0; }
.content :deep(code) {
  background: #f1f3f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: #d63384;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Consolas, monospace;
}
.content :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 10px 0;
  font-size: 13px;
  line-height: 1.5;
}
.content :deep(pre code) {
  background: none;
  color: inherit;
  padding: 0;
  font-size: inherit;
}
.content :deep(table) {
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 13px;
  width: 100%;
}
.content :deep(th),
.content :deep(td) {
  border: 1px solid #d0d5dd;
  padding: 6px 10px;
  text-align: left;
}
.content :deep(th) {
  background: #f8fafc;
  font-weight: 600;
}
.content :deep(blockquote) {
  border-left: 4px solid #3b82f6;
  padding-left: 14px;
  color: #64748b;
  margin: 8px 0;
}
.content :deep(hr) {
  border: none;
  border-top: 1px solid #e8ecf1;
  margin: 16px 0;
}
.content :deep(img) {
  max-width: 100%;
  border-radius: 6px;
}
.content :deep(a) {
  color: #3b82f6;
  text-decoration: none;
}
.content :deep(a:hover) {
  text-decoration: underline;
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