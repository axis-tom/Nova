<template>
  <div class="input-area">
    <el-input
      v-model="inputText"
      type="textarea"
      :rows="3"
      :placeholder="placeholder"
      :disabled="disabled"
      @keydown.ctrl.enter="sendMessage"
      @keydown.meta.enter="sendMessage"
      resize="none"
    />
    <div class="input-actions">
      <div class="left-actions">
        <el-upload
          v-if="showUpload"
          :before-upload="handleFileUpload"
          :show-file-list="false"
          accept="image/*"
        >
          <el-button :icon="Picture" text size="small">图片</el-button>
        </el-upload>
        <el-button v-if="showVoice" :icon="Microphone" text size="small">语音</el-button>
      </div>
      <el-button
        type="primary"
        :loading="sending"
        :disabled="!canSend"
        @click="sendMessage"
      >
        发送
        <el-icon class="send-icon"><Promotion /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElInput, ElButton, ElUpload, ElMessage } from 'element-plus';
import { Picture, Microphone, Promotion } from '@element-plus/icons-vue';

interface Props {
  disabled?: boolean
  placeholder?: string
  showUpload?: boolean
  showVoice?: boolean
}

const props = defineProps<Props>();

interface Emits {
  (e: 'send', ...args: unknown[]): void
}

const emit = defineEmits<Emits>();

const inputText = ref<string>('');
const sending = ref<boolean>(false);

const canSend = computed(() => {
  return inputText.value.trim().length > 0 && !props.disabled && !sending.value;
});

const sendMessage = () => {
  if (!canSend.value) return;
  const text = inputText.value.trim();
  emit('send', text);
  inputText.value = '';
};

const handleFileUpload = (file: { name: string }) => {
  // 这里可以处理图片上传逻辑，实际项目中可能需要调用上传接口
  // 简单演示，提示用户
  ElMessage.info(`准备上传: ${file.name}`);
  // 返回 false 阻止自动上传，由外部处理
  return false;
};

</script>

<style scoped>
.input-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.left-actions {
  display: flex;
  gap: 8px;
}

.send-icon {
  margin-left: 4px;
}
</style>