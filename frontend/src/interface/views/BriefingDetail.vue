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
          <div class="content" v-html="formattedContent"></div>
        </el-descriptions-item>
        <el-descriptions-item label="来源数据">
          <pre>{{ formattedSourceData }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { getBriefing } from '@/api/briefings';
import { formatDate } from '@/utils/format';

const route = useRoute();
const router = useRouter();

const loading = ref<boolean>(false);
const briefing = ref({
  id: null,
  title: '',
  content: '',
  created_at: '',
  source_data: {}
});

const formattedContent = computed(() => {
  // 将纯文本换行转为 <br>，以便在 HTML 中显示
  return briefing.value.content ? briefing.value.content.replace(/\n/g, '<br>') : '';
});

const formattedSourceData = computed(() => {
  try {
    return JSON.stringify(briefing.value.source_data, null, 2);
  } catch {
    return briefing.value.source_data;
  }
});

const fetchBriefing = async () => {
  const id = route.params.id;
  if (!id) {
    ElMessage.error('缺少简报ID');
    router.push('/briefings');
    return;
  }
  loading.value = true;
  try {
    const res = await getBriefing(id);
    // 后端可能直接返回对象，也可能包装在 briefing 字段中
    if (res && res.briefing) {
      briefing.value = res.briefing;
    } else if (res && res.id) {
      briefing.value = res;
    } else {
      throw new Error('返回数据格式错误');
    }
  } catch (error) {
    ElMessage.error('获取简报详情失败：' + (error.message || '未知错误'));
    router.push('/briefings');
  } finally {
    loading.value = false;
  }
};

const goBack = () => {
  router.push('/briefings');
};

onMounted(() => {
  fetchBriefing();
});
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