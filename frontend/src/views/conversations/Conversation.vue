<template>
  <div class="conversation">
    <el-container class="chat-container">
      <!-- 左侧树形侧边栏 -->
      <el-aside width="320px" class="tree-sidebar">
        <div class="sidebar-header">
          <h2><i class="fas fa-comment-dots"></i> 对话工坊</h2>
          <el-button type="primary" link @click="createProject">
            <i class="el-icon-plus"></i> 新建项目
          </el-button>
        </div>
        <div class="tree-container">
          <el-tree
            :data="treeData"
            node-key="id"
            :props="{ label: 'name', children: 'children' }"
            :expand-on-click-node="false"
            :highlight-current="true"
            :current-node-key="currentNodeKey"
            @node-click="onNodeClick"
          >
            <template #default="{ node, data }">
              <span class="tree-node">
                <span class="node-label">
                  <i :class="data.type === 'project' ? 'el-icon-folder-opened' : 'el-icon-chat-dot-round'"></i>
                  {{ data.name }}
                </span>
                <span class="node-actions">
                  <el-button
                    v-if="data.type === 'project'"
                    link
                    size="small"
                    @click.stop="addConversation(data)"
                  >
                    <i class="el-icon-plus"></i>
                  </el-button>
                  <el-button link size="small" @click.stop="editNode(data)">
                    <i class="el-icon-edit"></i>
                  </el-button>
                  <el-button link size="small" type="danger" @click.stop="deleteNode(data)">
                    <i class="el-icon-delete"></i>
                  </el-button>
                </span>
              </span>
            </template>
          </el-tree>
          <el-empty v-if="!loadingTree && treeData.length === 0" description="暂无项目，点击上方新建" :image-size="80" />
        </div>
      </el-aside>

      <!-- 右侧聊天区域 -->
      <el-main class="chat-main">
        <!-- 消息列表 -->
        <div class="messages" ref="messagesContainer" v-loading="loading">
          <div
            v-for="msg in messages"
            :key="msg.id"
            :class="['message', msg.role]"
          >
            <div class="message-content">
              <div class="content">{{ msg.content }}</div>
              <div class="meta">
                <span v-if="msg.scene_id">
                  <i class="el-icon-collection-tag"></i> {{ getSceneName(msg.scene_id) }}
                </span>
                <span v-if="msg.function">
                  <i class="el-icon-cpu"></i> {{ getFunctionLabel(msg.function) }}
                </span>
                <span v-if="msg.model_id">
                  <i class="el-icon-mic"></i> {{ getModelName(msg.model_id) }}
                </span>
                <span><i class="el-icon-time"></i> {{ formatTime(msg.created_at) }}</span>
              </div>
            </div>
          </div>
          <div v-if="sending" class="message assistant loading">
            <div class="message-content">
              <div class="content typing-indicator">正在思考...</div>
            </div>
          </div>
        </div>

        <!-- 输入区域 + 参数栏 -->
        <div class="input-area">
          <div class="params-bar">
            <el-select
              v-model="currentScene"
              placeholder="场景商店"
              size="small"
              clearable
              :disabled="sending || !currentConversation"
            >
              <el-option
                v-for="scene in installedScenes"
                :key="scene.id"
                :label="scene.name"
                :value="scene.id"
              />
            </el-select>
            <el-select
              v-model="currentFunction"
              placeholder="AI功能"
              size="small"
              clearable
              :disabled="sending || !currentConversation"
            >
              <el-option
                v-for="func in functionOptions"
                :key="func.value"
                :label="func.label"
                :value="func.value"
              />
            </el-select>
            <el-select
              v-model="currentModelId"
              placeholder="本地AI模型"
              size="small"
              clearable
              :disabled="sending || !currentConversation"
            >
              <el-option
                v-for="model in localModels"
                :key="model.id"
                :label="model.name"
                :value="model.id"
              />
            </el-select>
          </div>

          <div class="message-input-wrapper">
            <el-input
              v-model="newMessage"
              type="textarea"
              :rows="3"
              placeholder="输入你的问题... (Enter 发送，Shift+Enter 换行)"
              :disabled="sending || !currentConversation"
              @keydown.enter.prevent="handleEnter"
              @keydown.shift.enter="handleShiftEnter"
            />
            <el-button
              type="primary"
              :loading="sending"
              :disabled="!newMessage.trim() || !currentModelId || !currentScene || !currentConversation"
              @click="sendMessage"
            >
              发送
            </el-button>
          </div>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
// API 导入（根据实际项目路径修改）
import {
  getConversationTree,
  createConversation as apiCreateConversation,
  updateConversation as apiUpdateConversation,
  deleteConversation as apiDeleteConversation,
  getConversationHistory,
  sendMessage as apiSendMessage
} from '@/api/conversation'

import {
  getProjects,
  createProject as apiCreateProject,
  updateProject as apiUpdateProject,
  deleteProject as apiDeleteProject
} from '@/api/project'
import { getInstalledScenes } from '@/api/scenes'
import { getLocalModels } from '@/api/models'

// ==================== 响应式数据 ====================
const loading = ref(false)
const sending = ref(false)
const loadingTree = ref(false)
const messages = ref([])
const newMessage = ref('')
const messagesContainer = ref(null)

// 树形数据
const treeData = ref([])
const currentNodeKey = ref(null)

// 当前选中的项目/对话
const currentProject = ref(null)
const currentConversation = ref(null)

// 场景
const installedScenes = ref([])
const currentScene = ref('')

// 功能
const functionOptions = ref([
  { label: '🔍 联网搜索', value: 'web_search' },
  { label: '📎 文件上传', value: 'file_upload' },
  { label: '🎙️ 语音输入', value: 'voice' },
  { label: '🧠 思维链', value: 'cot' },
  { label: '📈 图表生成', value: 'chart' }
])
const currentFunction = ref('')

// 本地模型
const localModels = ref([])
const currentModelId = ref('')

// ==================== 辅助函数 ====================
const getSceneName = (sceneId) => {
  const scene = installedScenes.value.find(s => s.id === sceneId)
  return scene ? scene.name : sceneId
}
const getFunctionLabel = (funcValue) => {
  const func = functionOptions.value.find(f => f.value === funcValue)
  return func ? func.label : funcValue
}
const getModelName = (modelId) => {
  const model = localModels.value.find(m => m.id === modelId)
  return model ? model.name : modelId
}
const formatTime = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// ==================== 树形数据加载与操作 ====================
const loadTreeData = async () => {
  loadingTree.value = true
  try {
    // 获取项目列表（或直接从 tree 接口获取）
    const projects = await getProjects()
    const tree = []
    for (const proj of projects) {
      // 获取该项目下的对话
      const convs = await getConversationTree({ project_id: proj.id }) // 根据实际接口调整
      const children = convs.map(conv => ({
        id: conv.id,
        name: conv.name,
        type: 'conversation'
      }))
      tree.push({
        id: proj.id,
        name: proj.name,
        type: 'project',
        children
      })
    }
    treeData.value = tree
  } catch (error) {
    ElMessage.error('加载项目列表失败')
    console.error(error)
  } finally {
    loadingTree.value = false
  }
}

const createProject = async () => {
  const { value } = await ElMessageBox.prompt('请输入项目名称', '新建项目', {
    confirmButtonText: '创建',
    cancelButtonText: '取消'
  })
  if (value) {
    try {
      const newProject = await createProject({ name: value })
      treeData.value.push({
        id: newProject.id,
        name: newProject.name,
        type: 'project',
        children: []
      })
      ElMessage.success('项目创建成功')
    } catch (error) {
      ElMessage.error('创建失败')
    }
  }
}

const addConversation = async (projectNode) => {
  const { value } = await ElMessageBox.prompt('对话名称', '新建对话', {
    inputValue: '新对话'
  })
  if (value) {
    try {
      const newConv = await apiCreateConversation({
        project_id: projectNode.id,
        name: value,
        scene_id: currentScene.value,
        model_id: currentModelId.value
      })
      if (!projectNode.children) projectNode.children = []
      projectNode.children.push({
        id: newConv.id,
        name: newConv.name,
        type: 'conversation'
      })
      ElMessage.success('对话创建成功')
    } catch (error) {
      ElMessage.error('创建失败')
    }
  }
}

const editNode = async (node) => {
  const oldName = node.name
  const { value } = await ElMessageBox.prompt('重命名', '编辑', {
    inputValue: oldName
  })
  if (value && value !== oldName) {
    try {
      if (node.type === 'project') {
        await apiUpdateProject(node.id, { name: value })
      } else {
        await apiUpdateConversation(node.id, { name: value })
      }
      node.name = value
      ElMessage.success('更新成功')
    } catch (error) {
      ElMessage.error('更新失败')
    }
  }
}

const deleteNode = async (node) => {
  const confirmMsg = node.type === 'project'
    ? `确定删除项目“${node.name}”及其所有对话吗？`
    : `确定删除对话“${node.name}”吗？`
  try {
    await ElMessageBox.confirm(confirmMsg, '警告', { type: 'warning' })
    if (node.type === 'project') {
      await  apiDeleteProject(node.id)
      const index = treeData.value.findIndex(p => p.id === node.id)
      if (index !== -1) treeData.value.splice(index, 1)
      if (currentProject.value?.id === node.id) {
        currentProject.value = null
        currentConversation.value = null
        messages.value = []
      }
    } else {
      await apiDeleteConversation(node.id)
      const parent = findParentProject(node.id)
      if (parent) {
        const idx = parent.children.findIndex(c => c.id === node.id)
        if (idx !== -1) parent.children.splice(idx, 1)
      }
      if (currentConversation.value?.id === node.id) {
        currentConversation.value = null
        messages.value = []
      }
    }
    ElMessage.success('删除成功')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

// 辅助：根据对话id找到所属项目
const findParentProject = (convId) => {
  for (const project of treeData.value) {
    if (project.children?.some(c => c.id === convId)) {
      return project
    }
  }
  return null
}

// ==================== 节点点击（切换对话） ====================
const onNodeClick = async (data) => {
  if (data.type === 'conversation') {
    currentConversation.value = data
    currentProject.value = findParentProject(data.id)
    currentNodeKey.value = data.id
    await loadMessages(data.id)
  } else if (data.type === 'project') {
    currentProject.value = data
    if (data.children?.length) {
      const firstConv = data.children[0]
      onNodeClick(firstConv)
    } else {
      currentConversation.value = null
      messages.value = []
    }
  }
}

// ==================== 加载对话消息 ====================
const loadMessages = async (conversationId) => {
  if (!conversationId) return
  loading.value = true
  try {
    const res = await getConversationHistory(conversationId)
    messages.value = res.messages || []
    // 如果有当前对话保存的场景/模型，则同步到下拉框
    if (currentConversation.value) {
      if (currentConversation.value.scene_id) currentScene.value = currentConversation.value.scene_id
      if (currentConversation.value.model_id) currentModelId.value = currentConversation.value.model_id
    }
    scrollToBottom()
  } catch (error) {
    ElMessage.error('加载消息失败')
  } finally {
    loading.value = false
  }
}

// ==================== 发送消息 ====================
const sendMessage = async () => {
  const content = newMessage.value.trim()
  if (!content) return
  if (!currentConversation.value) {
    ElMessage.warning('请先选择一个对话')
    return
  }
  if (!currentModelId.value) {
    ElMessage.warning('请选择一个本地模型')
    return
  }
  if (!currentScene.value && installedScenes.value.length) {
    ElMessage.warning('请选择一个场景')
    return
  }

  sending.value = true
  // 乐观添加用户消息
  const tempUserMsg = {
    id: Date.now(),
    role: 'user',
    content,
    created_at: new Date().toISOString(),
    scene_id: currentScene.value,
    function: currentFunction.value,
    model_id: currentModelId.value
  }
  messages.value.push(tempUserMsg)
  newMessage.value = ''
  scrollToBottom()

  try {
    const payload = {
      conversation_id: currentConversation.value.id,
      content,
      scene_id: currentScene.value,
      function: currentFunction.value || undefined,
      model_id: currentModelId.value
    }
    const res = await apiSendMessage(payload)
    // 添加助手消息
    messages.value.push({
      id: Date.now() + 1,
      role: 'assistant',
      content: res.reply,
      created_at: new Date().toISOString(),
      scene_id: currentScene.value,
      function: currentFunction.value,
      model_id: currentModelId.value
    })
    scrollToBottom()
  } catch (error) {
    ElMessage.error(error.message || '发送失败')
    // 移除乐观添加的用户消息
    messages.value.pop()
  } finally {
    sending.value = false
  }
}

// 处理 Enter 发送，Shift+Enter 换行
const handleEnter = (event) => {
  if (!event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}
const handleShiftEnter = (event) => {
  // 默认行为是换行，无需额外代码
}

// ==================== 加载基础数据（场景/模型） ====================
const loadBaseData = async () => {
  try {
    const scenes = await getInstalledScenes()
    installedScenes.value = scenes
    if (!currentScene.value && installedScenes.value.length) {
      currentScene.value = installedScenes.value[0].id
    }
  } catch (error) {
    // 降级模拟数据
    installedScenes.value = [
      { id: 'ecommerce', name: '电商运营助手' },
      { id: 'content', name: '自媒体内容管家' },
      { id: 'finance', name: '财务管理小助手' }
    ]
    if (!currentScene.value) currentScene.value = installedScenes.value[0].id
  }

  try {
    const models = await getLocalModels()
    localModels.value = models
    if (!currentModelId.value && localModels.value.length) {
      currentModelId.value = localModels.value[0].id
    }
  } catch (error) {
    localModels.value = [
      { id: 'gpt35', name: 'GPT-3.5 Turbo' },
      { id: 'llama3', name: 'Llama 3 70B' }
    ]
    if (!currentModelId.value) currentModelId.value = localModels.value[0].id
  }
}

onMounted(() => {
  loadBaseData()
  loadTreeData()
})
</script>

<style scoped>
.conversation {
  height: 100%;
  background-color: #f5f7fa;
}
.chat-container {
  height: 100%;
}
.chat-main {
  background: white;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  border-right: 1px solid #e4e7ed;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.message {
  margin-bottom: 20px;
  display: flex;
}
.message.user {
  justify-content: flex-end;
}
.message-content {
  max-width: 80%;
  padding: 12px 18px;
  border-radius: 20px;
  background-color: #f1f5f9;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  transition: all 0.2s;
}
.message.user .message-content {
  background-color: #3b82f6;
  color: white;
  border-bottom-right-radius: 4px;
}
.message.assistant .message-content {
  background-color: #ffffff;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 4px;
}
.content {
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.meta {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  font-size: 11px;
  color: #64748b;
}
.message.user .meta {
  color: #cbd5e1;
}
.typing-indicator {
  color: #909399;
  font-style: italic;
}
.input-area {
  padding: 16px 24px;
  border-top: 1px solid #e4e7ed;
  background: white;
}
.params-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.message-input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}
.message-input-wrapper .el-textarea {
  flex: 1;
}
.tree-sidebar {
  background: white;
  border-left: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
}
.sidebar-header h2 {
  font-size: 1.2rem;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.sidebar-header h2 i {
  color: #3b82f6;
}
.tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.tree-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  font-size: 14px;
  padding: 4px 8px;
}
.node-label {
  display: flex;
  align-items: center;
  gap: 8px;
}
.node-actions {
  visibility: hidden;
  display: flex;
  gap: 4px;
}
.tree-node:hover .node-actions {
  visibility: visible;
}
:deep(.el-tree-node__content) {
  border-radius: 8px;
  margin: 2px 0;
}
:deep(.el-tree-node__expand-icon) {
  padding: 0 8px;
}
</style>