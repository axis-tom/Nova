import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getSettings, updateSettings, getNotificationPreferences, updateNotificationPreferences } from '@/api/settings';

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref(null);
  const notifications = ref(null);
  const loading = ref(false);

  const fetchSettings = async () => {
    loading.value = true;
    try {
      const res = await getSettings();
      settings.value = res.settings;
    } finally {
      loading.value = false;
    }
  };

  const saveSettings = async (data) => {
    loading.value = true;
    try {
      const res = await updateSettings(data);
      settings.value = res.settings;
    } finally {
      loading.value = false;
    }
  };

  const fetchNotifications = async () => {
    loading.value = true;
    try {
      const res = await getNotificationPreferences();
      notifications.value = res.notifications;
    } finally {
      loading.value = false;
    }
  };

  const saveNotifications = async (data) => {
    loading.value = true;
    try {
      const res = await updateNotificationPreferences(data);
      notifications.value = res.notifications;
    } finally {
      loading.value = false;
    }
  };

  return {
    settings,
    notifications,
    loading,
    fetchSettings,
    saveSettings,
    fetchNotifications,
    saveNotifications,
  };
});