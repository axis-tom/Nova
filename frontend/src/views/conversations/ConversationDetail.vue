<template>
  <div class="conversation-detail">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>对话详情</span>
          <el-button type="primary" @click="goBack">返回</el-button>
        </div>
      </template>

      <div class="messages">
        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['message', msg.role]"
        >
          <div class="role">{{ msg.role === 'user' ? '我' : 'Nova' }}</div>
          <div class="content">{{ msg.content }}</div>
          <div class="time">{{ formatDate(msg.timestamp) }}</div>
        </div>
      </div>

      <div class="input-area" v-if="!readonly">
        <el-input
          v-model="newMessage"
          type="textarea"
          :rows="3"
          placeholder="输入你的问题..."
        />
        <el-button type="primary" :loading="sending" @click="sendMessage">
          发送
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getConversationMessages, sendMessage } from '@/api/conversation'
import { formatDate } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const sending = ref(false)
const readonly = ref(false) // 可根据权限或页面模式设置
const messages = ref([])
const newMessage = ref('')

const fetchMessages = async () => {
  const id = route.params.id
  if (!id) {
    ElMessage.error('缺少对话ID')
    return
  }
  loading.value = true
  try {
    const res = await getConversationMessages(id)
    messages.value = res.messages
  } catch (error) {
    ElMessage.error(error.message || '获取对话记录失败')
  } finally {
    loading.value = false
  }
}

const sendMessageHandler = async () => {
  if (!newMessage.value.trim()) return
  sending.value = true
  try {
    const res = await sendMessage({
      conversationId: route.params.id,
      content: newMessage.value
    })
    // 将新消息添加到列表（或重新拉取）
    messages.value.push({
      id: Date.now(),
      role: 'user',
      content: newMessage.value,
      timestamp: new Date().toISOString()
    })
    messages.value.push({
      id: Date.now() + 1,
      role: 'assistant',
      content: res.reply,
      timestamp: new Date().toISOString()
    })
    newMessage.value = ''
  } catch (error) {
    ElMessage.error(error.message || '发送失败')
  } finally {
    sending.value = false
  }
}

const goBack = () => {
  router.push('/conversations')
}

onMounted(() => {
  fetchMessages()
})
</script>

<style scoped>
.conversation-detail {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.messages {
  max-height: 60vh;
  overflow-y: auto;
  margin-bottom: 20px;
}
.message {
  margin-bottom: 16px;
  padding: 12px;
  border-radius: 8px;
}
.message.user {
  background-color: #ecf5ff;
  text-align: right;
}
.message.assistant {
  background-color: #f5f7fa;
}
.role {
  font-weight: bold;
  margin-bottom: 4px;
}
.time {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.input-area {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}
.input-area .el-textarea {
  flex: 1;
}
</style>