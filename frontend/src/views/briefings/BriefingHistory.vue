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
        <el-table-column prop="date" label="日期" width="120" sortable>
          <template #default="{ row }">
            {{ formatDate(row.date, 'YYYY-MM-DD') }}
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="summary" label="摘要" min-width="300" show-overflow-tooltip />
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
import { useBriefingStore } from '@/stores/briefings';

const router = useRouter();
const briefingStore = useBriefingStore();

const briefings = ref([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const loading = ref(false);

const fetchBriefings = async () => {
  loading.value = true;
  try {
    const res = await briefingStore.fetchList(currentPage.value, pageSize.value);
    briefings.value = briefingStore.items;
    total.value = briefingStore.total;
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
    await briefingStore.remove(briefing.id);
    ElMessage.success('删除成功');
    fetchBriefings();
  } catch {
    // 取消
  }
};

const generateBriefing = () => {
  // 跳转到生成简报的页面或打开对话框
  router.push('/briefings/generate');
};

const exportBriefing = (briefing) => {
  // 调用导出 API
  console.log('导出简报', briefing);
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