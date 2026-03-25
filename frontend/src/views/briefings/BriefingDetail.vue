<template>
  <div class="briefing-detail">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>简报详情</span>
          <el-button type="primary" @click="goBack">返回</el-button>
        </div>
      </template>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="标题">
          {{ briefing.title }}
        </el-descriptions-item>
        <el-descriptions-item label="生成时间">
          {{ formatDate(briefing.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="内容">
          <div class="content" v-html="briefing.content"></div>
        </el-descriptions-item>
        <el-descriptions-item label="来源数据">
          <pre>{{ briefing.source_data }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getBriefing } from '@/api/briefings'
import { formatDate } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const briefing = ref({
  id: null,
  title: '',
  content: '',
  created_at: '',
  source_data: {}
})

// 获取简报详情
const fetchBriefing = async () => {
  const id = route.params.id
  if (!id) {
    ElMessage.error('缺少简报ID')
    return
  }
  loading.value = true
  try {
    const res = await getBriefing(id)
    briefing.value = res.briefing
  } catch (error) {
    ElMessage.error(error.message || '获取简报详情失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push('/briefings')
}

onMounted(() => {
  fetchBriefing()
})
</script>

<style scoped>
.briefing-detail {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.content {
  line-height: 1.6;
  white-space: pre-wrap;
}
pre {
  background-color: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
}
</style>