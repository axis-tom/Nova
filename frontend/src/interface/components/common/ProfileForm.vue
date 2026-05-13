<template>
  <el-card class="profile-form">
    <template #header>
      <div class="card-header">
        <span class="title">个人资料</span>
      </div>
    </template>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-width="100px"
      label-position="right"
      class="profile-form-content"
    >
      <el-form-item label="头像">
        <div class="avatar-upload">
          <el-avatar :size="80" :src="avatarPreview" />
          <el-button type="primary" size="small" @click="handleUploadAvatar">更换头像</el-button>
          <input
            ref="avatarInput"
            type="file"
            accept="image/*"
            style="display: none"
            @change="onAvatarChange"
          />
        </div>
      </el-form-item>

      <el-form-item label="姓名" prop="name">
        <el-input v-model="formData.name" placeholder="请输入姓名" />
      </el-form-item>

      <el-form-item label="邮箱" prop="email">
        <el-input v-model="formData.email" placeholder="请输入邮箱" disabled />
        <el-button link type="primary" size="small" @click="handleChangeEmail">修改邮箱</el-button>
      </el-form-item>

      <el-form-item label="手机号" prop="phone">
        <el-input v-model="formData.phone" placeholder="请输入手机号" />
      </el-form-item>

      <el-form-item label="公司/组织" prop="company">
        <el-input v-model="formData.company" placeholder="请输入公司/组织名称" />
      </el-form-item>

      <el-form-item label="职位" prop="title">
        <el-input v-model="formData.title" placeholder="请输入职位" />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="submitForm" :loading="submitting">保存修改</el-button>
        <el-button @click="resetForm">重置</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue';
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus';

interface Props {
  profile?: Record<string, unknown>
}

const props = defineProps<Props>()

interface Emits {

  (e: 'update', ...args: unknown[]): void
  (e: 'change-email', ...args: unknown[]): void
}

const emit = defineEmits<Emits>();

const formRef = ref<FormInstance | null>(null);
const submitting = ref<boolean>(false);
const avatarInput = ref<HTMLElement | null>(null);
const avatarPreview = ref<string>((props.profile && typeof props.profile === 'object' && 'avatar' in props.profile) ? String((props.profile as Record<string, unknown>).avatar) : '');


// 表单数据，保持与 prop 同步
interface FormDataType {
  name: string
  email: string
  phone: string
  company: string
  title: string
}

const formData = reactive<FormDataType>({
  name: '',
  email: '',
  phone: '',
  company: '',
  title: ''
});

// 监听 prop 变化，更新表单
watch(
  () => props.profile,
  (newProfile) => {
    if (newProfile) {
      const p = newProfile as Record<string, unknown>;
      formData.name = String(p.name || '');
      formData.email = String(p.email || '');
      formData.phone = String(p.phone || '');
      formData.company = String(p.company || '');
      formData.title = String(p.title || '');
      avatarPreview.value = String(p.avatar || '');
    }
  },
  { immediate: true, deep: true }
);


const formRules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' }
  ]
};

const handleUploadAvatar = () => {
  avatarInput.value?.click();
};


const onAvatarChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;
  if (!file.type.startsWith('image/')) {
    ElMessage.error('请选择图片文件');
    return;
  }
  // 本地预览
  const reader = new FileReader();
  reader.onload = (e: ProgressEvent<FileReader>) => {
    avatarPreview.value = String(e.target?.result || '');
    // 实际项目中，这里应该上传到服务器，然后获取新头像 URL
    // 这里简化，直接通过 emit 传递文件，由父组件处理上传
    emit('update', { ...formData, avatarFile: file });
  };
  reader.readAsDataURL(file);
  // 清空 input，允许重新选择相同文件
  target.value = '';
};


const handleChangeEmail = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入新邮箱', '修改邮箱', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /^[^\s@]+@([^\s@]+\.)+[^\s@]+$/,
      inputErrorMessage: '邮箱格式不正确'
    });
    // 通知父组件发起修改邮箱请求
    emit('change-email', value);
  } catch {
    // 取消
  }
};

const submitForm = async () => {
  try {
    await formRef.value?.validate();
    submitting.value = true;
    // 构建提交数据，排除 avatarFile 等字段
    const { avatarFile, ...profileData } = formData as FormDataType & { avatarFile?: File };
    emit('update', profileData);
    ElMessage.success('保存成功');
  } catch (error) {
    console.error('表单验证失败', error);
  } finally {
    submitting.value = false;
  }
};


const resetForm = () => {
  formRef.value?.resetFields();
  // 重置数据到原始 profile
  const p = (props.profile || {}) as Record<string, unknown>;
  formData.name = String(p.name || '');
  formData.email = String(p.email || '');
  formData.phone = String(p.phone || '');
  formData.company = String(p.company || '');
  formData.title = String(p.title || '');
  avatarPreview.value = String(p.avatar || '');
};

</script>

<style scoped>
.profile-form {
  border-radius: 12px;
}

.card-header .title {
  font-size: 16px;
  font-weight: 500;
  color: #1f2937;
}

.profile-form-content {
  max-width: 500px;
}

.avatar-upload {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
</style>
