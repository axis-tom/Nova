import { defineStore } from 'pinia';
import { ref } from 'vue';
import { useEnvironmentStore } from './environment';
import * as mockApi from '@/api/mockDataSources';

export const useDataSourceStore = defineStore('dataSources', () => {
  const sources = ref([]);
  const loading = ref(false);
  const error = ref(null);
  
  const envStore = useEnvironmentStore();

  // 加载所有数据源（使用mock数据）
  const fetchAll = async () => {
    loading.value = true;
    error.value = null;
    try {
      console.log('[UI-7] 加载数据源列表（mock数据）');
      const data = await mockApi.getDataSources();  // 使用mock API
      sources.value = data;
      console.log('[UI-7] 数据源列表加载完成:', data.length, '条记录');
    } catch (err) {
      error.value = err.message;
      console.error('[UI-7] 加载数据源失败:', err);
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 新增数据源（mock，不提交到真实后端）
  const add = async (data) => {
    loading.value = true;
    try {
      console.log('[UI-7] 添加数据源（mock）:', data);
      const newSource = await mockApi.createDataSource(data);
      
      // 模拟添加到本地列表
      sources.value.push(newSource);
      
      console.log('[UI-7] 数据源添加成功（模拟）:', newSource);
      console.log('[UI-7] 注意：这是mock操作，不会提交到真实后端');
      
      return newSource;
    } catch (err) {
      console.error('[UI-7] 添加数据源失败:', err);
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 更新数据源（mock，不提交到真实后端）
  const update = async (id, data) => {
    loading.value = true;
    try {
      console.log(`[UI-7] 更新数据源 ID: ${id}（mock）:`, data);
      const updated = await mockApi.updateDataSource(id, data);
      
      // 模拟更新本地列表
      const index = sources.value.findIndex(s => s.id === id);
      if (index !== -1) {
        sources.value[index] = updated;
      }
      
      console.log('[UI-7] 数据源更新成功（模拟）:', updated);
      console.log('[UI-7] 注意：这是mock操作，不会提交到真实后端');
      
      return updated;
    } catch (err) {
      console.error('[UI-7] 更新数据源失败:', err);
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 删除数据源（mock，不提交到真实后端）
  const remove = async (id) => {
    loading.value = true;
    try {
      console.log(`[UI-7] 删除数据源 ID: ${id}（mock）`);
      await mockApi.deleteDataSource(id);
      
      // 模拟从本地列表删除
      sources.value = sources.value.filter(s => s.id !== id);
      
      console.log(`[UI-7] 数据源 ${id} 删除成功（模拟）`);
      console.log('[UI-7] 注意：这是mock操作，不会提交到真实后端');
    } catch (err) {
      console.error('[UI-7] 删除数据源失败:', err);
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 测试连接（仅console.log，不调用真实API）
  const test = async (config) => {
    loading.value = true;
    try {
      console.log('[UI-7] 测试数据源连接（仅console.log）:', config);
      console.log('[UI-7] 当前环境:', envStore.currentEnv);
      console.log('[UI-7] 注意：这是测试连接按钮，仅输出日志，不调用真实API');
      
      // 使用mock API进行测试
      const result = await mockApi.testDataSource(config);
      
      console.log('[UI-7] 测试结果:', result);
      return result;
    } catch (err) {
      console.error('[UI-7] 测试连接失败:', err);
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // 获取数据源类型（mock）
  const fetchTypes = async () => {
    try {
      console.log('[UI-7] 获取数据源类型（mock）');
      const types = await mockApi.getDataSourceTypes();
      console.log('[UI-7] 数据源类型:', Object.keys(types).length, '种');
      return types;
    } catch (err) {
      console.error('[UI-7] 获取数据源类型失败:', err);
      throw err;
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
    fetchTypes,
  };
});
