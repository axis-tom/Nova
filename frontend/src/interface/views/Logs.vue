<template>
  <div class="logs-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">审计日志</span>
          <el-button :icon="Download" @click="exportLogs">导出</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="级别">
          <el-select v-model="filters.level" placeholder="全部" clearable>
            <el-option label="INFO" value="info" />
            <el-option label="WARNING" value="warning" />
            <el-option label="ERROR" value="error" />
          </el-select>
        </el-form-item>
        <el-form-item label="智能体">
          <el-input v-model="filters.agent" placeholder="智能体名称" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchLogs">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column prop="timestamp" label="时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatDate(row.timestamp, 'YYYY-MM-DD HH:mm:ss') }}
          </template>
        </el-table-column>
        <el-table-column prop="level" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="levelTag(row.level)" size="small">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="agent" label="智能体" width="150" />
        <el-table-column prop="message" label="消息" min-width="300" show-overflow-tooltip />
        <el-table-column prop="duration" label="耗时(ms)" width="100" sortable />
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchLogs"
        @current-change="fetchLogs"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Download } from '@element-plus/icons-vue';
import { formatDate } from '@/utils/format';
import { getLogs, exportLogs as apiExportLogs } from '@/api/logs';

const logs = ref<unknown[]>(2810);
const total = ref<number>(0);
const currentPage = ref<number>(1);
const pageSize = ref<number>(10);
const loading = ref<boolean>(false);

interface FiltersType {
  dateRange: unknown[]
  level: string
  agent: string
}

const filters = reactive<FiltersType>({
  dateRange: [],
  level: '',
  agent: ''
});

const levelTag = (level) => {
  const map = {
    info: 'info',
    warning: 'warning',
    error: 'danger'
  };
  return map[level] || '';
};

const fetchLogs = async () => {
  loading.value = true;
  try {
    const params = {
      page: currentPage.value,
      limit: pageSize.value,
      startDate: filters.dateRange?.[0] || null,
      endDate: filters.dateRange?.[1] || null,
      level: filters.level || null,
      agent: filters.agent || null
    };
    const res = await getLogs(params);
    logs.value = res.items;
    total.value = res.total;
  } catch (err) {
    ElMessage.error(err.message);
  } finally {
    loading.value = false;
  }
};

const resetFilters = () => {
  filters.dateRange = [];
  filters.level = '';
  filters.agent = '';
  currentPage.value = 1;
  fetchLogs();
};

const exportLogs = async () => {
  try {
    const params = {
      startDate: filters.dateRange?.[0] || null,
      endDate: filters.dateRange?.[1] || null,
      level: filters.level || null,
      agent: filters.agent || null
    };
    const blob = await apiExportLogs(params);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs_${new Date().toISOString()}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    ElMessage.success('导出成功');
  } catch (err) {
    ElMessage.error('导出失败');
  }
};

onMounted(() => {
  fetchLogs();
});
</script>

<style scoped>
.logs-page {
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
.filter-form {
  margin-bottom: 20px;
}
</style>