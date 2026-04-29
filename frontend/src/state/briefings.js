import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getBriefings, generateBriefing, deleteBriefing, getBriefingTaskStatus } from '@/api/briefings';

export const useBriefingStore = defineStore('briefings', () => {
  const items = ref([]);
  const total = ref(0);
  const currentPage = ref(1);
  const pageSize = ref(10);
  const loading = ref(false);
  const error = ref(null);
  const activeTask = ref(null); // 正在生成的任务ID

  // 获取列表
  const fetchList = async (page = currentPage.value, limit = pageSize.value) => {
    loading.value = true;
    error.value = null;
    try {
      const res = await getBriefings({ page, limit });
      items.value = res.items;
      total.value = res.total;
      currentPage.value = res.page;
      pageSize.value = res.limit;
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 生成新简报（异步）
  const generate = async (params) => {
    loading.value = true;
    try {
      const res = await generateBriefing(params);
      if (res.taskId) {
        activeTask.value = res.taskId;
        // 可在此轮询任务状态，但这里只返回 taskId，由组件决定轮询
      } else if (res.briefing) {
        // 同步返回
        items.value.unshift(res.briefing);
      }
      return res;
    } finally {
      loading.value = false;
    }
  };

  // 删除简报
  const remove = async (id) => {
    loading.value = true;
    try {
      await deleteBriefing(id);
      items.value = items.value.filter(b => b.id !== id);
    } finally {
      loading.value = false;
    }
  };

  // 轮询任务状态
  const pollTaskStatus = async (taskId, interval = 2000, maxAttempts = 30) => {
    let attempts = 0;
    return new Promise((resolve, reject) => {
      const timer = setInterval(async () => {
        attempts++;
        try {
          const res = await getBriefingTaskStatus(taskId);
          if (res.status === 'completed') {
            clearInterval(timer);
            items.value.unshift(res.briefing);
            activeTask.value = null;
            resolve(res.briefing);
          } else if (res.status === 'failed') {
            clearInterval(timer);
            activeTask.value = null;
            reject(new Error('生成简报失败'));
          } else if (attempts >= maxAttempts) {
            clearInterval(timer);
            activeTask.value = null;
            reject(new Error('生成超时'));
          }
        } catch (err) {
          clearInterval(timer);
          activeTask.value = null;
          reject(err);
        }
      }, interval);
    });
  };

  return {
    items,
    total,
    currentPage,
    pageSize,
    loading,
    error,
    activeTask,
    fetchList,
    generate,
    remove,
    pollTaskStatus,
  };
});