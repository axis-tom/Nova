import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getSettings,
  updateSettings,
  getNotificationPreferences,
  updateNotificationPreferences
} from '@/api/settings'

interface SettingsData {
  [key: string]: unknown
}

interface NotificationsData {
  [key: string]: unknown
}

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<SettingsData | null>(null)
  const notifications = ref<NotificationsData | null>(null)
  const loading = ref<boolean>(false)

  const fetchSettings = async (): Promise<void> => {
    loading.value = true
    try {
      const res = (await getSettings()) as { settings: SettingsData }
      settings.value = res.settings
    } finally {
      loading.value = false
    }
  }

  const saveSettings = async (data: SettingsData): Promise<void> => {
    loading.value = true
    try {
      const res = (await updateSettings(data)) as { settings: SettingsData }
      settings.value = res.settings
    } finally {
      loading.value = false
    }
  }

  const fetchNotifications = async (): Promise<void> => {
    loading.value = true
    try {
      const res = (await getNotificationPreferences()) as {
        notifications: NotificationsData
      }
      notifications.value = res.notifications
    } finally {
      loading.value = false
    }
  }

  const saveNotifications = async (data: NotificationsData): Promise<void> => {
    loading.value = true
    try {
      const res = (await updateNotificationPreferences(data)) as {
        notifications: NotificationsData
      }
      notifications.value = res.notifications
    } finally {
      loading.value = false
    }
  }

  return {
    settings,
    notifications,
    loading,
    fetchSettings,
    saveSettings,
    fetchNotifications,
    saveNotifications
  }
})