<template>
  <div class="dashboard">
    <!-- 统计卡片行 -->
    <el-row :gutter="20">
      <el-col :xs="24" :sm="12" :lg="6" v-for="stat in statsData" :key="stat.title">
        <StatsCard
          :title="stat.title"
          :value="stat.value"
          :unit="stat.unit"
          :icon="stat.icon"
          :trend="stat.trend"
          :trend-type="stat.trendType"
        />
      </el-col>
    </el-row>

    <!-- 优先级列表和简报预览 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :xs="24" :md="12">
        <PriorityList
          :items="priorityItems"
          :loading="priorityLoading"
          @item-click="handlePriorityClick"
          @complete="handleComplete"
          @more="goToPriorityList"
        />
      </el-col>
      <el-col :xs="24" :md="12">
        <BriefingPreview
          :briefing="latestBriefing"
          :loading="briefingLoading"
          @view-detail="goToBriefing"
          @export="exportBriefing"
          @more="goToBriefings"
        />
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import StatsCard from '@/components/dashboard/StatsCard.vue';
import PriorityList from '@/components/dashboard/PriorityList.vue';
import BriefingPreview from '@/components/dashboard/BriefingPreview.vue';
import { useBriefingStore } from '@/stores/briefings';
import { usePriorityStore } from '@/stores/priority'; // 假设有优先级 store

const router = useRouter();
const briefingStore = useBriefingStore();
const priorityStore = usePriorityStore();

// 统计卡片数据（实际应从 API 获取）
const statsData = ref([
  { title: '今日简报', value: 3, unit: '份', icon: 'Document', trend: '+20%', trendType: 'success' },
  { title: '待处理事项', value: 5, unit: '个', icon: 'Flag', trend: '-2', trendType: 'danger' },
  { title: '对话次数', value: 12, unit: '次', icon: 'ChatLineSquare', trend: '+30%', trendType: 'success' },
  { title: '风险预警', value: 1, unit: '条', icon: 'Warning', trend: '持平', trendType: 'warning' }
]);

const priorityItems = ref([]);
const priorityLoading = ref(false);
const latestBriefing = ref(null);
const briefingLoading = ref(false);

const loadPriorityItems = async () => {
  priorityLoading.value = true;
  try {
    // 从 store 获取待处理事项（优先级列表）
    await priorityStore.fetchItems();
    priorityItems.value = priorityStore.items.slice(0, 5); // 只取前5条
  } finally {
    priorityLoading.value = false;
  }
};

const loadLatestBriefing = async () => {
  briefingLoading.value = true;
  try {
    await briefingStore.fetchList(1, 1);
    latestBriefing.value = briefingStore.items[0] || null;
  } finally {
    briefingLoading.value = false;
  }
};

const handlePriorityClick = (item) => {
  router.push(`/priority/${item.id}`);
};

const handleComplete = async (item) => {
  await priorityStore.completeItem(item.id);
  loadPriorityItems(); // 刷新列表
};

const goToPriorityList = () => {
  router.push('/priority');
};

const goToBriefing = (briefing) => {
  router.push(`/briefings/${briefing.id}`);
};

const exportBriefing = (briefing) => {
  // 调用导出 API
  console.log('导出简报', briefing);
};

const goToBriefings = () => {
  router.push('/briefings');
};

onMounted(() => {
  loadPriorityItems();
  loadLatestBriefing();
});
</script>

<style scoped>
.dashboard {
  padding: 20px;
}
</style>