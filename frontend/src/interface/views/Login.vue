<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="login-header">
          <h2>Nova</h2>
          <p>智能体运营系统</p>
        </div>
      </template>
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="0"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="email">
          <el-input
            v-model="formData.email"
            placeholder="邮箱"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="formData.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" @click="handleLogin" block>
            登录
          </el-button>
        </el-form-item>
        <el-form-item>
          <el-button link type="primary" @click="goToRegister">还没有账号？立即注册</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { User, Lock } from '@element-plus/icons-vue';
import { useAuthStore } from '@/state/auth';

const router = useRouter();
const authStore = useAuthStore();

const formRef = ref<HTMLElement | null>(null);
const loading = ref<boolean>(false);
interface FormDataType {
  email: string
  password: string
}

const formData = reactive<FormDataType>({
  email: '',
  password: ''
});

const formRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' }
  ]
};

const handleLogin = async () => {
  try {
    await formRef.value.validate();
    loading.value = true;
    await authStore.login({ email: formData.email, password: formData.password });
    ElMessage.success('登录成功');
    router.push('/workspace');
  } catch (err) {
    ElMessage.error(err.message || '登录失败');
  } finally {
    loading.value = false;
  }
};

const goToRegister = () => {
  router.push('/register');
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 400px;
  border-radius: 12px;
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.login-header {
  text-align: center;
}
.login-header h2 {
  margin: 0;
  font-size: 28px;
  color: #3b82f6;
}
.login-header p {
  margin: 8px 0 0;
  color: #6b7280;
}
</style>