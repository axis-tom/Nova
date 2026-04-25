<template>
  <div class="priority-detail">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>优先级事项详情</span>
          <el-button type="primary" @click="goBack">返回</el-button>
        </div>
      </template>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="事项名称">
          {{ priority.title }}
        </el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :type="priorityTagType">{{ priority.priority }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTagType">{{ priority.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="截止日期">
          {{ formatDate(priority.deadline) }}
        </el-descriptions-item>
        <el-descriptions-item label="描述">
          {{ priority.description }}
        </el-descriptions-item>
        <el-descriptions-item label="关联简报">
          <el-link type="primary" @click="viewBriefing(priority.briefing_id)">
            {{ priority.briefing_title }}
          </el-link>
        </el-descriptions-item>
      </el-descriptions>

      <div class="actions">
        <el-button type="success" @click="markCompleted">标记完成</el-button>
        <el-button type="danger" @click="deleteItem">删除事项</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPriority, updatePriority, deletePriority } from '@/api/priority' // 假设有 priority API
import { formatDate } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const loading = ref<boolean>(false)
const priority = ref({
  id: null,
  title: '',
  priority: '',
  status: '',
  deadline: '',
  description: '',
  briefing_id: null,
  briefing_title: ''
})

const priorityTagType = computed(() => {
  const map = {
    '高': 'danger',
    '中': 'warning',
    '低': 'info'
  }
  return map[priority.value.priority] || ''
})

const statusTagType = computed(() => {
  const map = {
    '待处理': 'warning',
    '进行中': 'primary',
    '已完成': 'success',
    '已取消': 'info'
  }
  return map[priority.value.status] || ''
})

const fetchPriority = async () => {
  const id = route.params.id
  if (!id) {
    ElMessage.error('缺少事项ID')
    return
  }
  loading.value = true
  try {
    const res = await getPriority(id)
    priority.value = res.priority
  } catch (error) {
    ElMessage.error(error.message || '获取事项详情失败')
  } finally {
    loading.value = false
  }
}

const markCompleted = async () => {
  try {
    await updatePriority(priority.value.id, { status: '已完成' })
    ElMessage.success('已标记为完成')
    fetchPriority() // 刷新
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const deleteItem = async () => {
  try {
    await ElMessageBox.confirm('确定要删除此事项吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deletePriority(priority.value.id)
    ElMessage.success('删除成功')
    router.push('/priority')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const viewBriefing = (id) => {
  if (id) {
    router.push(`/briefings/${id}`)
  }
}

const goBack = () => {
  router.push('/priority')
}

onMounted(() => {
  fetchPriority()
})
</script>

<style scoped>
.priority-detail {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}
</style>