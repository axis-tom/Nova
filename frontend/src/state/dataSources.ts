import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useEnvironmentStore } from './environment'

interface DataSource {
  id: string | number
  name?: string
  [key: string]: unknown
}

export const useDataSourceStore = defineStore('dataSources', () => {
  const sources = ref<DataSource[]>([])
  const loading = ref<boolean>(false)
  const error = ref<string | null>(null)

  const envStore = useEnvironmentStore()

  const fetchAll = async (): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const { getDataSources } = await import('@/api/mockDataSources')
      const data = (await getDataSources()) as unknown as DataSource[]
      sources.value = data
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  const add = async (data: Record<string, unknown>): Promise<DataSource> => {
    loading.value = true
    try {
      const { createDataSource } = await import('@/api/mockDataSources')
      const newSource = await createDataSource(data)
      sources.value.push(newSource as unknown as DataSource)
      return newSource as unknown as DataSource
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  const update = async (
    id: string | number,
    data: Record<string, unknown>
  ): Promise<DataSource> => {
    loading.value = true
    try {
      const { updateDataSource } = await import('@/api/mockDataSources')
      const updated = await updateDataSource(id, data)
      const index = sources.value.findIndex((s) => s.id === id)
      if (index !== -1) {
        sources.value[index] = updated as unknown as DataSource
      }
      return updated as unknown as DataSource
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  const remove = async (id: string | number): Promise<void> => {
    loading.value = true
    try {
      const { deleteDataSource } = await import('@/api/mockDataSources')
      await deleteDataSource(id)
      sources.value = sources.value.filter((s) => s.id !== id)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  const test = async (config: Record<string, unknown>): Promise<unknown> => {
    loading.value = true
    try {
      const { testDataSource } = await import('@/api/mockDataSources')
      const result = await testDataSource(config)
      return result
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchTypes = async (): Promise<unknown> => {
    try {
      const { getDataSourceTypes } = await import('@/api/mockDataSources')
      const types = await getDataSourceTypes()
      return types
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      error.value = message
      throw err
    }
  }

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
  }
})