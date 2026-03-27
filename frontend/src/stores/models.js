import { defineStore } from 'pinia';
import { ref } from 'vue';
import * as api from '@/api/models';

export const useModelStore = defineStore('models', () => {
  const currentPath = ref('');
  const folders = ref([]);
  const models = ref([]);
  const loading = ref(false);

  const loadData = async () => {
    loading.value = true;
    try {
      const res = await api.listModels(currentPath.value);
      folders.value = res.folders;
      models.value = res.models;
    } finally {
      loading.value = false;
    }
  };

  const createFolder = async (name) => {
    await api.createFolder(name, currentPath.value);
    await loadData();
  };

  const renameFolder = async (oldPath, newName) => {
    await api.renameFolder(oldPath, newName);
    await loadData();
  };

  const deleteFolder = async (folderPath) => {
    await api.deleteFolder(folderPath);
    await loadData();
  };

  const deleteModel = async (modelPath) => {
    await api.deleteModel(modelPath);
    await loadData();
  };

  const downloadModel = async (modelName) => {
    await api.downloadModel(modelName, currentPath.value);
    await loadData();
  };

  const changeDirectory = (path) => {
    currentPath.value = path;
    loadData();
  };

  return {
    currentPath,
    folders,
    models,
    loading,
    loadData,
    createFolder,
    renameFolder,
    deleteFolder,
    deleteModel,
    downloadModel,
    changeDirectory,
  };
});