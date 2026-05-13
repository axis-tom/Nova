import { defineStore } from 'pinia'
import { ref } from 'vue'

interface ModelItem {
  id?: string | number
  name?: string
  [key: string]: unknown
}

interface FolderItem {
  id?: string | number
  name?: string
  [key: string]: unknown
}

export const useModelStore = defineStore('models', () => {
  const currentPath = ref<string>('')
  const folders = ref<FolderItem[]>([])
  const models = ref<ModelItem[]>([])
  const loading = ref<boolean>(false)

  const changeDirectory = (path: string): void => {
    currentPath.value = path
  }

  return {
    currentPath,
    folders,
    models,
    loading,
    changeDirectory,
  }
})