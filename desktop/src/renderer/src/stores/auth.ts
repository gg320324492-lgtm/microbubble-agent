// auth Pinia store —— 唯一活 access_token 内存 + 调用入口。
//
// 设计原则：
// - access_token 永不入 renderer 持久化层（仅主进程内存）
//   renderer store 只保存 expiresAt 时间戳 + isAuthenticated boolean (UI 用)
// - 所有 login/logout/restore 通过 IPC 委托主进程
// - user 单独存 user store
// - isAuthenticated getter 同时考虑 user 与 expiresAt
//
// 不直接持有 refresh_token / access_token。

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  login as apiLogin,
  logout as apiLogout,
  restore as apiRestore
} from '../api/auth'
import { useUserStore } from './user'
import type { AuthRestoreResult, UserInfo, AuthErrorPayload } from '@shared/auth-types'

export const useAuthStore = defineStore('auth', () => {
  const hasSession = ref(false)
  const expiresAt = ref(0)
  const restoreAttempted = ref(false)

  /**
   * 计算属性：现在是否仍在有效期内（未过期）。
   * 用于 UI 显示"会话即将到期"提示。
   */
  const isAuthenticated = computed(() => {
    if (!hasSession.value) return false
    if (expiresAt.value <= 0) return false
    return Date.now() < expiresAt.value
  })

  function setSessionFromAuth(expiresAtMs: number, user: UserInfo): void {
    hasSession.value = true
    expiresAt.value = expiresAtMs
    // user store 关注分离 —— 同时 set profile
    const userStore = useUserStore()
    userStore.setProfile(user)
  }

  function clearSession(): void {
    hasSession.value = false
    expiresAt.value = 0
    const userStore = useUserStore()
    userStore.clearProfile()
  }

  async function login(username: string, password: string): Promise<
    { success: true } | { success: false; error: AuthErrorPayload }
  > {
    const result = await apiLogin({ username, password })
    if (result.success) {
      setSessionFromAuth(result.data.expiresAt, result.data.user)
      return { success: true }
    }
    return result
  }

  async function logout(): Promise<void> {
    await apiLogout()
    clearSession()
  }

  /**
   * 应用启动时调用一次。任何失败清空 state。
   */
  async function attemptRestore(): Promise<boolean> {
    restoreAttempted.value = true
    let result: AuthRestoreResult | null = null
    try {
      result = await apiRestore()
    } catch (_err) {
      result = null
    }
    if (!result) {
      clearSession()
      return false
    }
    hasSession.value = true
    expiresAt.value = result.expiresAt
    const userStore = useUserStore()
    userStore.setProfile(result.user)
    return true
  }

  /**
   * 主进程强制清场回调（refresh 失败 / 服务端禁用）—— 调用此清空 state。
   */
  function onSessionExpired(): void {
    clearSession()
  }

  return {
    hasSession,
    expiresAt,
    restoreAttempted,
    isAuthenticated,
    login,
    logout,
    attemptRestore,
    clearSession,
    onSessionExpired
  }
})
