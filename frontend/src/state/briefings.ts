import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getBriefings,
  generateBriefing,
  deleteBriefing,
  getBriefingTaskStatus
} from '@/api/briefings'

interface BriefingItem {
  id?: string | number
  title?: string
  [key: string]: unknown
}

interface PaginatedResponse {
  items: BriefingItem[]
  total: number
  page: number
  limit: number
}

interface GenerateResponse {
  taskId?: string
  briefing?: BriefingItem
}

interface TaskStatusResponse {
  status: string
  briefing: BriefingItem
}

export const useBriefingStore = defineStore('briefings', () => {
  const items = ref<BriefingItem[]>([])
  const total = ref<number>(0)
  const currentPage = ref<number>(1)
  const pageSize = ref<number>(10)
  const loading = ref<boolean>(false)
  const error = ref<string | null>(null)
  const activeTask = ref<string | null>(null)

  const fetchList = async (
    page: number = currentPage.value,
    limit: number = pageSize.value
  ): Promise<void> => {
    loading.value = true
    error.value = null
    try {
      const res = (await getBriefings({ page, limit })) as unknown as PaginatedResponse
      items.value = res.items
      total.value = res.total
      currentPage.value = res.page
      pageSize.value = res.limit
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  const generate = async (params: Record<string, unknown>): Promise<GenerateResponse> => {
    loading.value = true
    try {
      const res = (await generateBriefing(params)) as unknown as GenerateResponse
      if (res.taskId) {
        activeTask.value = res.taskId
      } else if (res.briefing) {
        items.value.unshift(res.briefing)
      }
      return res
    } finally {
      loading.value = false
    }
  }

  const remove = async (id: string | number): Promise<void> => {
    loading.value = true
    try {
      await deleteBriefing(id)
      items.value = items.value.filter((b) => b.id !== id)
    } finally {
      loading.value = false
    }
  }

  const pollTaskStatus = (
    taskId: string,
    interval: number = 2000,
    maxAttempts: number = 30
  ): Promise<BriefingItem> => {
    return new Promise((resolve, reject) => {
      let attempts = 0
      const timer = setInterval(async () => {
        attempts++
        try {
          const res = (await getBriefingTaskStatus(taskId)) as unknown as TaskStatusResponse
          if (res.status === 'completed') {
            clearInterval(timer)
            items.value.unshift(res.briefing)
            activeTask.value = null
            resolve(res.briefing)
          } else if (res.status === 'failed') {
            clearInterval(timer)
            activeTask.value = null
            reject(new Error('生成简报失败'))
          } else if (attempts >= maxAttempts) {
            clearInterval(timer)
            activeTask.value = null
            reject(new Error('生成超时'))
          }
        } catch (err) {
          clearInterval(timer)
          activeTask.value = null
          reject(err)
        }
      }, interval)
    })
  }

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
  }
})