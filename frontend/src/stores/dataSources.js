import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getDataSources, createDataSource, updateDataSource, deleteDataSource, testDataSource } from '@/api/dataSources';

export const useDataSourceStore = defineStore('dataSources', () => {
  const sources = ref([]);
  const loading = ref(false);
  const error = ref(null);

  // 加载所有数据源
  const fetchAll = async () => {
    loading.value = true;
    error.value = null;
    try {
      const res = await getDataSources();
      sources.value = res.sources;
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 新增
  const add = async (data) => {
    loading.value = true;
    try {
      const res = await createDataSource(data);
      sources.value.push(res.source);
      return res.source;
    } finally {
      loading.value = false;
    }
  };

  // 更新
  const update = async (id, data) => {
    loading.value = true;
    try {
      const res = await updateDataSource(id, data);
      const index = sources.value.findIndex(s => s.id === id);
      if (index !== -1) sources.value[index] = res.source;
      return res.source;
    } finally {
      loading.value = false;
    }
  };

  // 删除
  const remove = async (id) => {
    loading.value = true;
    try {
      await deleteDataSource(id);
      sources.value = sources.value.filter(s => s.id !== id);
    } finally {
      loading.value = false;
    }
  };

  // 测试连接
  const test = async (config) => {
    loading.value = true;
    try {
      return await testDataSource(config);
    } finally {
      loading.value = false;
    }
  };

  return {
    sources,
    loading,
    error,
    fetchAll,
    add,
    update,
    remove,
    test,
  };
});