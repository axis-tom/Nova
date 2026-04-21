<template>
  <el-card class="data-source-config">
    <template #header>
      <div class="card-header">
        <span class="title">数据源管理 (UI-7: Mock实现)</span>
        <el-button type="primary" :icon="Plus" @click="handleAdd">添加数据源</el-button>
      </div>
    </template>

    <el-table :data="dataSources" v-loading="loading" stripe>
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="type" label="类型" width="120">
        <template #default="{ row }">
          <el-tag :type="typeTag(row.type)" size="small">{{ getTypeName(row.type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="enabled" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'danger'" size="small">
            {{ row.enabled ? '已启用' : '已禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="lastSync" label="最后同步" width="160">
        <template #default="{ row }">
          {{ row.lastSync ? formatDate(row.lastSync, 'YYYY-MM-DD HH:mm') : '未同步' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
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
      width="550px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="110px"
        label-position="right"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入数据源名称" />
        </el-form-item>

        <el-form-item label="类型" prop="type">
          <el-select v-model="formData.type" placeholder="请选择类型" style="width: 100%" @change="onTypeChange">
            <el-option
              v-for="(def, key) in dataSourceTypes"
              :key="key"
              :label="def.name"
              :value="key"
            />
          </el-select>
        </el-form-item>

        <!-- 动态字段：根据当前类型渲染（邮箱只显示关键字段） -->
        <template v-if="currentTypeDef">
          <el-form-item
            v-for="field in visibleFields"
            :key="field.name"
            :label="field.label"
            :prop="`config.${field.name}`"
          >
            <template v-if="field.type === 'password'">
              <el-input
                v-model="formData.config[field.name]"
                type="password"
                show-password
                :placeholder="getPasswordPlaceholder()"
              />
              <div class="field-hint">
                <el-icon><InfoFilled /></el-icon> {{ getPasswordHint() }}
              </div>
            </template>

            <el-input
              v-else-if="field.type === 'text'"
              v-model="formData.config[field.name]"
              :placeholder="field.placeholder"
            />

            <el-input-number
              v-else-if="field.type === 'number'"
              v-model="formData.config[field.name]"
              :placeholder="field.placeholder"
              controls-position="right"
            />

            <el-select
              v-else-if="field.type === 'select'"
              v-model="formData.config[field.name]"
              :placeholder="field.placeholder"
              style="width: 100%"
            >
              <el-option
                v-for="opt in field.options"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>

            <el-checkbox v-else-if="field.type === 'checkbox'" v-model="formData.config[field.name]">
              {{ field.label }}
            </el-checkbox>

            <el-input
              v-else-if="field.type === 'textarea'"
              v-model="formData.config[field.name]"
              type="textarea"
              :rows="3"
              :placeholder="field.placeholder"
            />

            <div v-if="field.hint && field.type !== 'password'" class="field-hint">
              <el-icon><InfoFilled /></el-icon> {{ field.hint }}
            </div>
          </el-form-item>
        </template>

        <!-- 测试连接按钮区域 -->
        <div class="test-section" v-if="currentTypeDef">
          <el-button type="primary" @click="testConnection" :loading="testing">
            测试连接 (仅console.log)
          </el-button>
          <span v-if="testSuccess" class="test-success">
            <el-icon><CircleCheckFilled /></el-icon> 连接成功 (模拟)
          </span>
          <span v-if="testError" class="test-error">
            <el-icon><CircleCloseFilled /></el-icon> {{ testError }}
          </span>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting" :disabled="!isFormValid">
          确定 (模拟提交)
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, InfoFilled, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import { formatDate } from '@/utils/format'
import { useDataSourceStore } from '@/stores/dataSources'

const props = defineProps({
  dataSources: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['add', 'update', 'delete', 'test'])

// 使用数据源store
const dataSourceStore = useDataSourceStore()

// 本地状态（用于表单，不直接修改 props）
const dataSourceTypes = ref({})
const dialogVisible = ref(false)
const editingId = ref(null)
const submitting = ref(false)
const testing = ref(false)
const testSuccess = ref(false)
const testError = ref('')
const formRef = ref(null)

const formData = reactive({
  name: '',
  type: '',
  config: {}
})

// 当前类型定义
const currentTypeDef = computed(() => dataSourceTypes.value[formData.type])

// 可见字段（对于邮箱，隐藏技术字段）
const visibleFields = computed(() => {
  if (!currentTypeDef.value) return []
  if (formData.type === 'email') {
    return currentTypeDef.value.fields.filter(field => 
      ['provider', 'email', 'password'].includes(field.name)
    )
  }
  return currentTypeDef.value.fields
})

// 动态表单验证规则
const formRules = computed(() => {
  const rules = {
    name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
    type: [{ required: true, message: '请选择类型', trigger: 'change' }]
  }
  if (currentTypeDef.value) {
    visibleFields.value.forEach(field => {
      if (field.required) {
        rules[`config.${field.name}`] = [
          { required: true, message: `${field.label}不能为空`, trigger: 'blur' }
        ]
      }
    })
  }
  return rules
})

const dialogTitle = computed(() => (editingId.value ? '编辑数据源' : '添加数据源'))

// 保存按钮是否可用（新建或配置改变时必须测试成功）
const isFormValid = computed(() => {
  if (!editingId.value) return testSuccess.value
  // 编辑时：如果配置未改变，允许保存；否则需要测试成功
  const original = props.dataSources.find(s => s.id === editingId.value)
  if (!original) return testSuccess.value
  const configChanged = original.name !== formData.name || 
                        original.type !== formData.type ||
                        JSON.stringify(original.config) !== JSON.stringify(formData.config)
  return !configChanged || testSuccess.value
})

const typeTag = (type) => {
  const map = {
    email: 'primary',
    rss: 'success',
    weibo: 'warning',
    xiaohongshu: 'danger',
    financial: 'info',
    competitor: ''
  }
  return map[type] || ''
}

const getTypeName = (type) => dataSourceTypes.value[type]?.name || type

const getPasswordPlaceholder = () => {
  const provider = formData.config.provider
  if (provider === 'qq') return '请输入授权码（16位）'
  if (provider === 'gmail') return '请输入应用专用密码'
  if (provider === '163') return '请输入邮箱密码'
  if (provider === 'outlook') return '请输入邮箱密码'
  return '请输入密码/授权码'
}

const getPasswordHint = () => {
  const provider = formData.config.provider
  if (provider === 'qq') return '登录QQ邮箱 → 设置 → 账户 → 开启IMAP/SMTP服务 → 生成授权码'
  if (provider === 'gmail') return '需开启两步验证，在Google账户中生成应用专用密码'
  if (provider === '163') return '使用邮箱密码即可'
  if (provider === 'outlook') return '使用邮箱密码即可'
  return '请输入正确的密码/授权码'
}

const fetchTypes = async () => {
  try {
    console.log('[UI-7] 加载数据源类型（mock）');
    const res = await dataSourceStore.fetchTypes();
    dataSourceTypes.value = res;
    console.log('[UI-7] 数据源类型加载完成:', Object.keys(res).length, '种类型');
  } catch (error) {
    console.error('[UI-7] 加载数据源类型失败:', error);
    ElMessage.error('加载数据源类型失败');
  }
}

const onTypeChange = () => {
  testSuccess.value = false
  testError.value = ''
  formData.config = {}
  if (currentTypeDef.value) {
    visibleFields.value.forEach(field => {
      if (field.type === 'checkbox') formData.config[field.name] = false
      else if (field.type === 'number') formData.config[field.name] = null
      else if (field.type === 'select') {
        if (field.name === 'provider') formData.config[field.name] = 'qq'
        else formData.config[field.name] = ''
      } else formData.config[field.name] = ''
    })
  }
  formRef.value?.clearValidate()
}

const testConnection = async () => {
  try {
    await formRef.value.validateField('name')
    await formRef.value.validateField('type')
    for (const field of visibleFields.value) {
      if (field.required) {
        await formRef.value.validateField(`config.${field.name}`)
      }
    }
  } catch {
    ElMessage.warning('请先填写完整信息')
    return
  }

  testing.value = true
  testError.value = ''
  testSuccess.value = false
  try {
    console.log('[UI-7] 测试连接按钮点击（仅console.log）');
    console.log('[UI-7] 表单数据:', formData);
    
    // 使用store的test方法（仅console.log）
    const res = await dataSourceStore.test({ type: formData.type, config: formData.config })
    
    if (res.success) {
      testSuccess.value = true
      ElMessage.success('连接测试成功（模拟）')
    } else {
      testError.value = res.message || '连接失败'
      ElMessage.error(testError.value)
    }
  } catch (error) {
    testError.value = error.message || '网络错误'
    ElMessage.error(testError.value)
  } finally {
    testing.value = false
  }
}

const handleAdd = () => {
  editingId.value = null
  formData.name = ''
  formData.type = ''
  formData.config = {}
  testSuccess.value = false
  testError.value = ''
  dialogVisible.value = true
}

const handleEdit = (row) => {
  editingId.value = row.id
  formData.name = row.name
  formData.type = row.type
  formData.config = { ...row.config }
  if (currentTypeDef.value) {
    visibleFields.value.forEach(field => {
      if (formData.config[field.name] === undefined) {
        formData.config[field.name] = field.type === 'checkbox' ? false : ''
      }
    })
  }
  testSuccess.value = false
  testError.value = ''
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除数据源"${row.name}"吗？（模拟操作）`, '提示', { 
      type: 'warning',
      confirmButtonText: '删除（模拟）',
      cancelButtonText: '取消'
    })
    console.log(`[UI-7] 删除数据源: ${row.name} (ID: ${row.id})`);
    emit('delete', row.id)
  } catch { 
    console.log('[UI-7] 删除操作取消');
    /* 取消 */ 
  }
}

const handleTest = async (row) => {
  try {
    console.log(`[UI-7] 测试数据源连接: ${row.name} (ID: ${row.id})`);
    console.log('[UI-7] 数据源配置:', row.config);
    
    // 使用store的test方法（仅console.log）
    const res = await dataSourceStore.test({ type: row.type, config: row.config });
    
    if (res.success) {
      ElMessage.success('连接测试成功（模拟）');
    } else {
      ElMessage.error('连接测试失败（模拟）：' + (res.message || '未知错误'));
    }
  } catch (error) {
    console.error('[UI-7] 测试失败:', error);
    ElMessage.error('测试失败：' + error.message);
  }
};

const resetForm = () => {
  formData.name = ''
  formData.type = ''
  formData.config = {}
  testSuccess.value = false
  testError.value = ''
  formRef.value?.resetFields()
}

const submitForm = async () => {
  if (!editingId.value || hasConfigChanged()) {
    if (!testSuccess.value) {
      ElMessage.warning('请先测试连接并确保成功')
      return
    }
  }

  try {
    await formRef.value.validate()
    submitting.value = true
    
    const payload = {
      name: formData.name,
      type: formData.type,
      config: formData.config
    }
    
    console.log('[UI-7] 提交表单（模拟）:', payload);
    
    if (editingId.value) {
      console.log(`[UI-7] 更新数据源 ID: ${editingId.value}`);
      emit('update', { id: editingId.value, ...payload })
    } else {
      console.log('[UI-7] 添加新数据源');
      emit('add', payload)
    }
    
    dialogVisible.value = false
    ElMessage.success(editingId.value ? '更新成功（模拟）' : '添加成功（模拟）')
  } catch (error) {
    console.error('[UI-7] 表单提交失败:', error);
    if (error.response?.data?.detail) ElMessage.error(error.response.data.detail)
    else ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const hasConfigChanged = () => {
  if (!editingId.value) return true
  const original = props.dataSources.find(s => s.id === editingId.value)
  if (!original) return true
  return original.name !== formData.name || 
         original.type !== formData.type ||
         JSON.stringify(original.config) !== JSON.stringify(formData.config)
}

onMounted(() => {
  fetchTypes()
})
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
.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
}
.test-section {
  margin-top: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.test-success {
  color: #67c23a;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.test-error {
  color: #f56c6c;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
</style>