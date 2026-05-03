import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  login as apiLogin,
  register as apiRegister,
  getCurrentUser,
  logout as apiLogout,
  changePassword,
} from '@/api/auth'

/** 开发模式：上线前改为 false */
const isDevMode = true
// const isDevMode = false

interface UserProfile {
  id: string | number
  name: string
  email: string
  [key: string]: unknown
}

interface LoginCredentials {
  email: string
  password: string
}

interface RegisterData {
  name: string
  email: string
  password: string
}

interface ChangePasswordData {
  oldPassword: string
  newPassword: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('nova_token') || null)
  const user = ref<UserProfile | null>(null)
  const loading = ref<boolean>(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed<boolean>(() => {
    if (isDevMode) return true
    return !!token.value
  })

  const userName = computed<string>(() => user.value?.name || '')
  const userEmail = computed<string>(() => user.value?.email || '')

  const init = async (): Promise<void> => {
    if (isDevMode) {
      user.value = {
        id: 'dev-user',
        name: '开发者',
        email: 'dev@nova.local',
      }
      token.value = 'dev-token'
      return
    }

    if (!token.value) return
    try {
      const res = (await getCurrentUser()) as { user: UserProfile }
      user.value = res.user
    } catch {
      token.value = null
      localStorage.removeItem('nova_token')
    }
  }

  const login = async (credentials: LoginCredentials) => {
    loading.value = true
    error.value = null
    try {
      const res = (await apiLogin(credentials)) as {
        token: string
        user: UserProfile
      }
      token.value = res.token
      user.value = res.user
      localStorage.setItem('nova_token', res.token)
      return res
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  const register = async (userData: RegisterData) => {
    loading.value = true
    error.value = null
    try {
      const res = (await apiRegister(userData)) as {
        token: string
        user: UserProfile
      }
      token.value = res.token
      user.value = res.user
      localStorage.setItem('nova_token', res.token)
      return res
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  const logout = async (): Promise<void> => {
    loading.value = true
    try {
      await apiLogout()
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      token.value = null
      user.value = null
      localStorage.removeItem('nova_token')
      loading.value = false
    }
  }

  const updatePassword = async (data: ChangePasswordData): Promise<void> => {
    loading.value = true
    try {
      await changePassword(data)
    } finally {
      loading.value = false
    }
  }

  return {
    token,
    user,
    loading,
    error,
    isAuthenticated,
    userName,
    userEmail,
    init,
    login,
    register,
    logout,
    updatePassword,
  }
})