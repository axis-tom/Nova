import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getCurrentUser, updateProfile } from '@/api/settings';

export const useUserStore = defineStore('user', () => {
  const profile = ref(null);
  const loading = ref(false);

  const fetchProfile = async () => {
    loading.value = true;
    try {
      const res = await getCurrentUser(); // 或者 getProfile 接口
      profile.value = res.user;
    } finally {
      loading.value = false;
    }
  };

  const updateProfileData = async (data) => {
    loading.value = true;
    try {
      const res = await updateProfile(data);
      profile.value = res.profile || res.user;
    } finally {
      loading.value = false;
    }
  };

  return {
    profile,
    loading,
    fetchProfile,
    updateProfileData,
  };
});