import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getCurrentUser, updateProfile } from '@/api/settings'

interface UserProfile {
  id?: string | number
  name?: string
  email?: string
  [key: string]: unknown
}

export const useUserStore = defineStore('user', () => {
  const profile = ref<UserProfile | null>(null)
  const loading = ref<boolean>(false)

  const fetchProfile = async (): Promise<void> => {
    loading.value = true
    try {
      const res = (await getCurrentUser()) as { profile: UserProfile }
      profile.value = res.profile
    } finally {
      loading.value = false
    }
  }

  const updateProfileData = async (data: UserProfile): Promise<void> => {
    loading.value = true
    try {
      const res = (await updateProfile(data)) as {
        profile?: UserProfile
        user?: UserProfile
      }
      profile.value = res.profile ?? res.user ?? null
    } finally {
      loading.value = false
    }
  }

  return {
    profile,
    loading,
    fetchProfile,
    updateProfileData,
  }
})