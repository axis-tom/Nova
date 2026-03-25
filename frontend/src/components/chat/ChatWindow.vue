<template>
  <div class="chat-window">
    <!-- 消息列表区域（带滚动条） -->
    <el-scrollbar ref="scrollbarRef" class="chat-messages" @scroll="onScroll">
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="3" animated />
      </div>
      <div v-else-if="messages.length === 0" class="empty-state">
        <el-empty description="暂无消息，开始对话吧" />
      </div>
      <div v-else class="messages-container">
        <MessageBubble
          v-for="msg in messages"
          :key="msg.id"
          :message="msg"
          :is-user="msg.role === 'user'"
          :user-avatar="userAvatar"
          :ai-avatar="aiAvatar"
        />
      </div>
    </el-scrollbar>

    <!-- 输入区域 -->
    <div class="chat-input-area">
      <InputArea
        :disabled="sending"
        :placeholder="inputPlaceholder"
        @send="handleSend"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue';
import { ElScrollbar, ElSkeleton, ElEmpty } from 'element-plus';
import MessageBubble from './MessageBubble.vue';
import InputArea from './InputArea.vue';
import { wsManager } from '@/utils/websocket';
import { useAuthStore } from '@/stores/auth';

const props = defineProps({
  // 消息列表（从外部传入，支持双向绑定）
  messages: {
    type: Array,
    default: () => []
  },
  // 是否正在加载历史消息
  loading: {
    type: Boolean,
    default: false
  },
  // 是否正在发送
  sending: {
    type: Boolean,
    default: false
  },
  // 用户头像
  userAvatar: {
    type: String,
    default: ''
  },
  // AI 头像
  aiAvatar: {
    type: String,
    default: ''
  },
  // 输入框占位符
  inputPlaceholder: {
    type: String,
    default: '输入消息...'
  },
  // WebSocket 连接地址（如果提供则自动连接，否则使用 props 发送）
  wsUrl: {
    type: String,
    default: ''
  },
  // 当前对话 ID（用于 WebSocket 订阅）
  conversationId: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['send', 'load-more', 'message-received']);

const authStore = useAuthStore();
const scrollbarRef = ref(null);
const isAtBottom = ref(true);

// 监听消息变化，自动滚动到底部
watch(
  () => props.messages.length,
  () => {
    if (isAtBottom.value) {
      nextTick(() => scrollToBottom());
    }
  },
  { flush: 'post' }
);

// 滚动到底部
const scrollToBottom = () => {
  if (scrollbarRef.value) {
    const wrap = scrollbarRef.value.wrapRef;
    if (wrap) {
      wrap.scrollTop = wrap.scrollHeight;
    }
  }
};

// 滚动事件处理，检测是否滚动到底部
const onScroll = ({ scrollTop, scrollHeight, clientHeight }) => {
  isAtBottom.value = scrollTop + clientHeight >= scrollHeight - 50;
  // 如果滚动到顶部且正在加载历史，触发加载更多
  if (scrollTop === 0 && !props.loading) {
    emit('load-more');
  }
};

// 发送消息
const handleSend = (text) => {
  if (!text.trim()) return;
  emit('send', text);
};

// WebSocket 集成（如果提供了 wsUrl）
let wsHandler = null;

const setupWebSocket = () => {
  if (!props.wsUrl) return;
  
  // 获取 token
  const token = authStore.token;
  wsManager.connect(props.wsUrl, token);
  
  // 订阅消息
  wsHandler = (data) => {
    // 判断消息是否属于当前对话
    if (data.conversationId === props.conversationId) {
      emit('message-received', data);
    }
  };
  wsManager.on('message', wsHandler);
};

const cleanupWebSocket = () => {
  if (wsHandler) {
    wsManager.off('message', wsHandler);
    wsHandler = null;
  }
};

onMounted(() => {
  setupWebSocket();
  // 初始滚动到底部
  nextTick(() => scrollToBottom());
});

// 组件卸载时清理 WebSocket 监听
import { onBeforeUnmount } from 'vue';
onBeforeUnmount(() => {
  cleanupWebSocket();
});
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  padding: 16px;
  background-color: #f9fafb;
}

.loading-container {
  padding: 20px;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.messages-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chat-input-area {
  padding: 16px;
  border-top: 1px solid #e5e7eb;
  background-color: #fff;
}
</style>