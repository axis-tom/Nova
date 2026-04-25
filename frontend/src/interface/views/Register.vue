<template>
  <div class="register-container">
    <el-card class="register-card">
      <template #header>
        <div class="register-header">
          <h2>注册 Nova 账号</h2>
          <p>智能体运营系统</p>
        </div>
      </template>
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="0"
        @submit.prevent="handleRegister"
      >
        <el-form-item prop="name">
          <el-input
            v-model="formData.name"
            placeholder="用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="email">
          <el-input
            v-model="formData.email"
            placeholder="邮箱"
            :prefix-icon="Message"
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
            @input="checkPasswordStrength"
          />
          <div v-if="passwordStrength" class="password-strength">
            <span :class="['strength-indicator', passwordStrength]">
              {{ passwordStrengthText }}
            </span>
          </div>
        </el-form-item>
        <el-form-item prop="confirmPassword">
          <el-input
            v-model="formData.confirmPassword"
            type="password"
            placeholder="确认密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item prop="company" class="optional-field">
          <el-input
            v-model="formData.company"
            placeholder="公司/组织名称（可选）"
            :prefix-icon="OfficeBuilding"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="phone" class="optional-field">
          <el-input
            v-model="formData.phone"
            placeholder="手机号码（可选）"
            :prefix-icon="Iphone"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="agreement">
          <el-checkbox v-model="formData.agreement">
            我已阅读并同意
            <el-link type="primary" @click="showAgreement">《用户协议》</el-link>
            和
            <el-link type="primary" @click="showPrivacy">《隐私政策》</el-link>
          </el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" @click="handleRegister" block>
            注册
          </el-button>
        </el-form-item>
        <el-form-item>
          <el-button link type="primary" @click="goToLogin">已有账号？立即登录</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 用户协议对话框 -->
    <el-dialog
      v-model="agreementVisible"
      title="用户协议"
      width="600px"
    >
      <div class="agreement-content">
        <!-- 这里可以放置用户协议内容 -->
        <p>欢迎使用 Nova 智能体运营系统...</p>
        <!-- 具体协议内容 -->
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="agreementVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 隐私政策对话框 -->
    <el-dialog
      v-model="privacyVisible"
      title="隐私政策"
      width="600px"
    >
      <div class="privacy-content">
        <!-- 这里可以放置隐私政策内容 -->
        <p>我们非常重视您的隐私保护...</p>
        <!-- 具体隐私政策内容 -->
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="privacyVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  User,
  Message,
  Lock,
  OfficeBuilding,
  Iphone
} from '@element-plus/icons-vue';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const authStore = useAuthStore();

const formRef = ref<HTMLElement | null>(null);
const loading = ref<boolean>(false);
const agreementVisible = ref<boolean>(false);
const privacyVisible = ref<boolean>(false);
const passwordStrength = ref<string>('');

interface FormDataType {
  name: string
  email: string
  password: string
  confirmPassword: string
  company: string
  phone: string
  agreement: boolean
}

const formData = reactive<FormDataType>({
  name: '',
  email: '',
  password: '',
  confirmPassword: '',
  company: '',
  phone: '',
  agreement: false
});

// 密码强度检查函数
const checkPasswordStrength = (password) => {
  if (!password) {
    passwordStrength.value = '';
    return;
  }

  let score = 0;
  if (password.length >= 8) score++;
  if (/[a-z]/.test(password)) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  if (score <= 2) {
    passwordStrength.value = 'weak';
  } else if (score <= 4) {
    passwordStrength.value = 'medium';
  } else {
    passwordStrength.value = 'strong';
  }
};

// 密码强度文本
const passwordStrengthText = computed(() => {
  switch (passwordStrength.value) {
    case 'weak': return '密码强度：弱';
    case 'medium': return '密码强度：中';
    case 'strong': return '密码强度：强';
    default: return '';
  }
});

// 表单验证规则
const formRules = {
  name: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度在 2 到 20 个字符', trigger: 'blur' },
    { pattern: /^[\u4e00-\u9fa5a-zA-Z0-9_]+$/, message: '用户名只能包含中文、英文、数字和下划线', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' },
    { 
      validator: (rule, value, callback) => {
        if (!value) {
          callback();
          return;
        }
        if (!/[a-z]/.test(value)) {
          callback(new Error('密码必须包含小写字母'));
        } else if (!/[A-Z]/.test(value)) {
          callback(new Error('密码必须包含大写字母'));
        } else if (!/[0-9]/.test(value)) {
          callback(new Error('密码必须包含数字'));
        } else {
          callback();
        }
      },
      trigger: 'blur'
    }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== formData.password) {
          callback(new Error('两次输入的密码不一致'));
        } else {
          callback();
        }
      },
      trigger: 'blur'
    }
  ],
  phone: [
    {
      validator: (rule, value, callback) => {
        if (!value) {
          callback();
          return;
        }
        if (!/^1[3-9]\d{9}$/.test(value)) {
          callback(new Error('请输入正确的手机号码'));
        } else {
          callback();
        }
      },
      trigger: 'blur'
    }
  ],
  agreement: [
    {
      validator: (rule, value, callback) => {
        if (!value) {
          callback(new Error('请阅读并同意用户协议和隐私政策'));
        } else {
          callback();
        }
      },
      trigger: 'change'
    }
  ]
};

// 注册处理函数
const handleRegister = async () => {
  try {
    await formRef.value.validate();
    loading.value = true;

    // 准备发送给后端的数据
    const registerData = {
      name: formData.name,
      email: formData.email,
      password: formData.password
    };

    // 可选字段：如果有值才发送
    if (formData.company) {
      registerData.company = formData.company;
    }
    if (formData.phone) {
      registerData.phone = formData.phone;
    }

    // 调用注册接口
    await authStore.register(registerData);
    
    ElMessage.success('注册成功！正在跳转到工作台...');
    
    // 注册成功后自动登录，跳转到工作台
    router.push('/workspace');
    
  } catch (err) {
    console.error('注册失败:', err);
    let errorMessage = '注册失败';
    
    if (err.message) {
      errorMessage = err.message;
    } else if (err.data?.detail) {
      errorMessage = err.data.detail;
    } else if (err.response?.data?.detail) {
      errorMessage = err.response.data.detail;
    }
    
    ElMessage.error(errorMessage);
  } finally {
    loading.value = false;
  }
};

// 显示用户协议
const showAgreement = () => {
  agreementVisible.value = true;
};

// 显示隐私政策
const showPrivacy = () => {
  privacyVisible.value = true;
};

// 跳转到登录页
const goToLogin = () => {
  router.push('/login');
};
</script>

<style scoped>
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.register-card {
  width: 450px;
  border-radius: 12px;
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.register-header {
  text-align: center;
}
.register-header h2 {
  margin: 0;
  font-size: 24px;
  color: #3b82f6;
}
.register-header p {
  margin: 8px 0 0;
  color: #6b7280;
}

.password-strength {
  margin-top: 8px;
  font-size: 12px;
}

.strength-indicator {
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.strength-indicator.weak {
  background-color: #fee2e2;
  color: #dc2626;
}

.strength-indicator.medium {
  background-color: #fef3c7;
  color: #d97706;
}

.strength-indicator.strong {
  background-color: #d1fae5;
  color: #059669;
}

.optional-field :deep(.el-form-item__label) {
  color: #9ca3af;
}

.agreement-content,
.privacy-content {
  max-height: 400px;
  overflow-y: auto;
  line-height: 1.6;
  color: #4b5563;
}

.agreement-content p,
.privacy-content p {
  margin-bottom: 16px;
}

@media (max-width: 480px) {
  .register-card {
    width: 100%;
    max-width: 400px;
  }
}
</style>