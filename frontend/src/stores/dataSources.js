import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getDataSources, createDataSource, updateDataSource, deleteDataSource, testDataSource } from '@/api/dataSources';

export const useDataSourceStore = defineStore('dataSources', () => {
  const sources = ref([]);
  const loading = ref(false);
  const error = ref(null);

  // 加载所有数据源（后端直接返回数组）
  const fetchAll = async () => {
    loading.value = true;
    error.value = null;
    try {
      const data = await getDataSources();  // data 就是数组
      sources.value = data;                 // 直接赋值
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 新增（后端返回创建的数据源对象）
  const add = async (data) => {
    loading.value = true;
    try {
      const newSource = await createDataSource(data);
      sources.value.push(newSource);
      return newSource;
    } finally {
      loading.value = false;
    }
  };

  // 更新（后端返回更新后的数据源对象）
  const update = async (id, data) => {
    loading.value = true;
    try {
      const updated = await updateDataSource(id, data);
      const index = sources.value.findIndex(s => s.id === id);
      if (index !== -1) sources.value[index] = updated;
      return updated;
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

  // 测试连接（直接返回结果）
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