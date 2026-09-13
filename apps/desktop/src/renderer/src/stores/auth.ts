// 认证状态 — 桥接 window.api 与路由守卫；renderer 只持 user 对象（token 永不落 renderer）
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { AuthSession, LocalUser } from '@shared/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<LocalUser | null>(null)
  const expiresAt = ref(0)
  const ready = ref(false)
  const userCount = ref(-1) // -1 = 尚未查询

  let initPromise: Promise<void> | null = null

  async function init(): Promise<void> {
    if (initPromise) return initPromise
    initPromise = (async () => {
      try {
        const [restored, status] = await Promise.all([window.api.auth.restore(), window.api.auth.status()])
        if (restored) {
          user.value = restored.user
          expiresAt.value = restored.expiresAt
        }
        userCount.value = status.userCount
      } catch {
        userCount.value = -1
      } finally {
        ready.value = true
      }
    })()
    return initPromise
  }

  async function login(username: string, password: string): Promise<void> {
    const s: AuthSession = await window.api.auth.login({ username, password })
    user.value = s.user
    expiresAt.value = s.expiresAt
  }

  async function registerAdmin(username: string, displayName: string, password: string): Promise<void> {
    const s: AuthSession = await window.api.auth.registerAdmin({ username, displayName, password })
    user.value = s.user
    expiresAt.value = s.expiresAt
    userCount.value = Math.max(userCount.value, 1)
  }

  async function logout(): Promise<void> {
    try {
      await window.api.auth.logout()
    } finally {
      user.value = null
      expiresAt.value = 0
    }
  }

  const isAuthenticated = computed(() => user.value !== null)
  const needsSetup = computed(() => ready.value && userCount.value === 0)

  return {
    user,
    expiresAt,
    ready,
    userCount,
    isAuthenticated,
    needsSetup,
    init,
    login,
    registerAdmin,
    logout
  }
})
