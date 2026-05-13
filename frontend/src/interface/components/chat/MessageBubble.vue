<template>
  <div :class="['message-bubble', { 'message-user': isUser, 'message-ai': !isUser }]">
    <div class="message-avatar">
      <el-avatar :size="36" :src="avatarUrl" :alt="isUser ? 'User' : 'AI'">
        {{ isUser ? userInitial : 'AI' }}
      </el-avatar>
    </div>
    <div class="message-content-wrapper">
      <div class="message-header">
        <span class="message-name">{{ isUser ? userName : aiName }}</span>
        <el-tooltip :content="formatFullTime(message.createdAt)" placement="top">
          <span class="message-time">{{ formatRelativeTime(message.createdAt) }}</span>
        </el-tooltip>
      </div>
      <div class="message-content" :class="{ 'message-content-user': isUser }">
        <div v-if="message.isMarkdown" class="markdown-body" v-html="renderedMarkdown"></div>
        <div v-else class="plain-text">{{ message.content }}</div>
      </div>
      <div v-if="message.attachments && message.attachments.length" class="message-attachments">
        <el-image
          v-for="(att, idx) in message.attachments"
          :key="idx"
          :src="att.url"
          :preview-src-list="[att.url]"
          fit="cover"
          class="attachment-image"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { ElAvatar, ElTooltip, ElImage } from 'element-plus';
import { formatDate, timeAgo } from '@/utils/format';

// 如果需要 Markdown 渲染，可以引入 marked 或简单处理
// 这里假设 message.isMarkdown 为 true 时使用 marked
import { marked } from 'marked';

interface Attachment {
  url: string
}

interface Message {
  id: string
  role: string
  content: string
  createdAt: string
  isMarkdown?: boolean
  attachments?: Attachment[]
}

interface Props {
  message: Message
  isUser?: boolean
  userAvatar?: string
  aiAvatar?: string
  userName?: string
  aiName?: string
}


const props = withDefaults(defineProps<Props>(), {
  userName: 'User',
  aiName: 'AI'
});


const avatarUrl = computed(() => (props.isUser ? props.userAvatar : props.aiAvatar));
const userInitial = computed(() => (props.userName || 'U').charAt(0).toUpperCase());

const formatRelativeTime = (dateStr: string) => {
  if (!dateStr) return '';
  return timeAgo(dateStr);
};

const formatFullTime = (dateStr: string) => {
  if (!dateStr) return '';
  return formatDate(dateStr, 'YYYY-MM-DD HH:mm:ss');
};

const renderedMarkdown = computed(() => {
  if (!props.message.isMarkdown) return '';
  return marked(props.message.content);
});


</script>

<style scoped>
.message-bubble {
  display: flex;
  gap: 12px;
  max-width: 80%;
  animation: fadeIn 0.2s ease;
}

.message-user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-ai {
  align-self: flex-start;
}

.message-avatar {
  flex-shrink: 0;
}

.message-content-wrapper {
  max-width: calc(100% - 48px);
}

.message-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 4px;
}

.message-name {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.message-time {
  font-size: 12px;
  color: #9ca3af;
}

.message-content {
  padding: 10px 14px;
  border-radius: 12px;
  background-color: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  word-break: break-word;
  line-height: 1.5;
  font-size: 14px;
}

.message-content-user {
  background-color: #3b82f6;
  color: white;
}

.message-content-user .plain-text {
  color: white;
}

/* Markdown 样式 */
.markdown-body {
  font-size: 14px;
}
.markdown-body :deep(p) {
  margin: 0 0 8px;
}
.markdown-body :deep(code) {
  background-color: #f3f4f6;
  padding: 2px 4px;
  border-radius: 4px;
  font-family: monospace;
}
.message-content-user .markdown-body :deep(code) {
  background-color: rgba(255, 255, 255, 0.2);
}

.message-attachments {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.attachment-image {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  cursor: pointer;
  object-fit: cover;
  border: 1px solid #e5e7eb;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>