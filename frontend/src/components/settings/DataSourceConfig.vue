<template>
  <el-card class="data-source-config">
    <template #header>
      <div class="card-header">
        <span class="title">数据源管理</span>
        <el-button type="primary" :icon="Plus" @click="handleAdd">添加数据源</el-button>
      </div>
    </template>

    <el-table :data="dataSources" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="type" label="类型" width="120">
        <template #default="{ row }">
          <el-tag :type="typeTag(row.type)" size="small">{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">
            {{ row.status === 'active' ? '已连接' : '未连接' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="lastSync" label="最后同步" width="160">
        <template #default="{ row }">
          {{ row.lastSync ? formatDate(row.lastSync, 'YYYY-MM-DD HH:mm') : '未同步' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          <el-button link type="primary" size="small" @click="handleTest(row)">测试</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
        label-position="right"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入数据源名称" />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-select v-model="formData.type" placeholder="请选择类型" style="width: 100%">
            <el-option label="邮件 (IMAP)" value="email" />
            <el-option label="RSS 订阅" value="rss" />
            <el-option label="社交媒体 (微博)" value="weibo" />
            <el-option label="社交媒体 (小红书)" value="xiaohongshu" />
            <el-option label="财务数据 (CSV)" value="financial" />
            <el-option label="竞品监控" value="competitor" />
          </el-select>
        </el-form-item>
        <el-form-item label="配置" prop="config">
          <el-input
            v-model="formData.config"
            type="textarea"
            :rows="4"
            placeholder='JSON 格式配置，如 {"url": "https://...", "username": "..."}'
          />
          <div class="config-tip">
            <el-text size="small" type="info">
              <el-icon><InfoFilled /></el-icon> 请以 JSON 格式填写配置
            </el-text>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, computed } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, InfoFilled } from '@element-plus/icons-vue';
import { formatDate } from '@/utils/format';

const props = defineProps({
  dataSources: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['add', 'update', 'delete', 'test']);

const dialogVisible = ref(false);
const editingId = ref(null);
const submitting = ref(false);
const formRef = ref(null);

const dialogTitle = computed(() => (editingId.value ? '编辑数据源' : '添加数据源'));

const formData = ref({
  name: '',
  type: '',
  config: ''
});

const formRules = {
  name: [{ required: true, message: '请输入数据源名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择数据源类型', trigger: 'change' }],
  config: [{ required: true, message: '请输入配置信息', trigger: 'blur' }]
};

const typeTag = (type) => {
  const map = {
    email: 'primary',
    rss: 'success',
    weibo: 'warning',
    xiaohongshu: 'danger',
    financial: 'info',
    competitor: ''
  };
  return map[type] || '';
};

const handleAdd = () => {
  editingId.value = null;
  resetForm();
  dialogVisible.value = true;
};

const handleEdit = (row) => {
  editingId.value = row.id;
  formData.value = {
    name: row.name,
    type: row.type,
    config: typeof row.config === 'object' ? JSON.stringify(row.config, null, 2) : row.config
  };
  dialogVisible.value = true;
};

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除数据源“${row.name}”吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    emit('delete', row.id);
  } catch {
    // 取消删除
  }
};

const handleTest = (row) => {
  emit('test', row);
};

const resetForm = () => {
  formData.value = {
    name: '',
    type: '',
    config: ''
  };
  formRef.value?.resetFields();
};

const submitForm = async () => {
  try {
    await formRef.value.validate();
    submitting.value = true;
    let configObj;
    try {
      configObj = JSON.parse(formData.value.config);
    } catch {
      ElMessage.error('配置 JSON 格式错误');
      return;
    }
    const payload = {
      name: formData.value.name,
      type: formData.value.type,
      config: configObj
    };
    if (editingId.value) {
      emit('update', { id: editingId.value, ...payload });
    } else {
      emit('add', payload);
    }
    dialogVisible.value = false;
    ElMessage.success(editingId.value ? '更新成功' : '添加成功');
  } catch (error) {
    console.error('表单验证失败', error);
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
.data-source-config {
  border-radius: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header .title {
  font-size: 16px;
  font-weight: 500;
  color: #1f2937;
}

.config-tip {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>