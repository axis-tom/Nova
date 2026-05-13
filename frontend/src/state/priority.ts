import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/** 优先级事项 */
interface PriorityItem {
  id?: string | number
  title?: string
  priority?: string
  [key: string]: unknown
}

export const usePriorityStore = defineStore('priority', () => {
  const items = ref<PriorityItem[]>([])
  const loading = ref<boolean>(false)
  const error = ref<string | null>(null)

  const highPriorityItems = computed<PriorityItem[]>(() =>
    items.value.filter((item) => item.priority === '高')
  )
  const mediumPriorityItems = computed<PriorityItem[]>(() =>
    items.value.filter((item) => item.priority === '中')
  )
  const lowPriorityItems = computed<PriorityItem[]>(() =>
    items.value.filter((item) => item.priority === '低')
  )

  const fetchItems = async (): Promise<void> => {
    loading.value = true
    try {
      const response = await fetch('/api/v1/priority')
      const data = (await response.json()) as { items?: PriorityItem[] }
      items.value = data.items ?? []
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      error.value = message
      console.error('获取优先级事项失败', err)
    } finally {
      loading.value = false
    }
  }

  return {
    items,
    loading,
    error,
    highPriorityItems,
    mediumPriorityItems,
    lowPriorityItems,
    fetchItems,
  }
})