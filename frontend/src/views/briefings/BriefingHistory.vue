<template>
  <div class="briefing-history">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">简报历史</span>
          <el-button type="primary" :icon="Plus" @click="generateBriefing">生成简报</el-button>
        </div>
      </template>

      <el-table :data="briefings" v-loading="loading" stripe>
        <el-table-column prop="created_at" label="日期" width="120" sortable>
          <template #default="{ row }">
            {{ formatDate(row.created_at, 'YYYY-MM-DD') }}
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="content" label="摘要" min-width="300" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.content ? row.content.slice(0, 100) + (row.content.length > 100 ? '...' : '') : '' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetail(row)">查看</el-button>
            <el-button link type="danger" @click="deleteBriefing(row)">删除</el-button>
            <el-button link type="primary" @click="exportBriefing(row)">导出</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchBriefings"
        @current-change="fetchBriefings"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus } from '@element-plus/icons-vue';
import { formatDate } from '@/utils/format';
import { getBriefings, deleteBriefing as apiDeleteBriefing, generateBriefing as apiGenerateBriefing } from '@/api/briefings';

const router = useRouter();

const briefings = ref([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const loading = ref(false);

const fetchBriefings = async () => {
  loading.value = true;
  try {
    // 注意：后端可能需要 skip 和 limit，根据实际情况调整
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    };
    const res = await getBriefings(params);
    // 假设后端返回 { items: [], total: number }，如果直接返回数组则需调整
    if (Array.isArray(res)) {
      briefings.value = res;
      total.value = res.length; // 如果后端不分页，可只显示全部
    } else {
      briefings.value = res.items || [];
      total.value = res.total || briefings.value.length;
    }
  } catch (error) {
    ElMessage.error('加载简报列表失败：' + (error.message || '未知错误'));
  } finally {
    loading.value = false;
  }
};

const viewDetail = (briefing) => {
  router.push(`/briefings/${briefing.id}`);
};

const deleteBriefing = async (briefing) => {
  try {
    await ElMessageBox.confirm(`确定要删除简报“${briefing.title}”吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    await apiDeleteBriefing(briefing.id);
    ElMessage.success('删除成功');
    fetchBriefings(); // 刷新列表
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('删除失败');
  }
};

const generateBriefing = async () => {
  loading.value = true;
  try {
    await apiGenerateBriefing();
    ElMessage.success('简报生成请求已发送，请稍后刷新查看');
    // 等待2秒后刷新列表
    setTimeout(() => fetchBriefings(), 2000);
  } catch (error) {
    ElMessage.error('生成简报失败：' + (error.message || '未知错误'));
  } finally {
    loading.value = false;
  }
};

const exportBriefing = (briefing) => {
  // 简单导出为文本文件
  const content = `${briefing.title}\n\n${briefing.content}\n\n生成时间：${formatDate(briefing.created_at)}`;
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${briefing.title}.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
};

onMounted(() => {
  fetchBriefings();
});
</script>

<style scoped>
.briefing-history {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header .title {
  font-size: 16px;
  font-weight: 500;
}
</style>