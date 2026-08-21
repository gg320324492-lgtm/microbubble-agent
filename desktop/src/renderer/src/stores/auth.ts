// auth Pinia store —— 唯一活 access_token 内存 + 调用入口。
//
// 设计原则：
// - access_token 仅活内存（refresh 后或 close app 后清空，Phase 1 restore 重生）
// - 所有 login/logout/restore 通过 IPC 委托 main
// - profile 单独存 user store（关注分离）
// - isAuthenticated getter 简单基于 token 是否存在 + 未过期
//
// 不直接持有 refresh_token（主进程持有 vault，永不进 renderer）。

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, logout as apiLogout, restore as apiRestore } from '../api/auth'
import { useUserStore } from './user'
import type { AuthRestoreResult } from '@shared/auth-types'

export const useAuthStore = defineStore('auth', () => {
  // 是否有 token + profile 都 ok
  const hasSession = ref(false)
  // access_token 过期 epoch ms（仅用于 UI 提示，不参与业务校验）
  const expiresAt = ref(0)
  // 启动时是否尝试过 restore（防止 LoginView 在 restore 失败前重复跳）
  const restoreAttempted = ref(false)

  const isAuthenticated = computed(() => hasSession.value)

  function applyRestore(result: AuthRestoreResult): void {
    const userStore = useUserStore()
    hasSession.value = true
    expiresAt.value = Date.now() + result.tokenPair.expires_in * 1000
    userStore.setProfile(result.profile)
  }

  function clearSession(): void {
    const userStore = useUserStore()
    hasSession.value = false
    expiresAt.value = 0
    userStore.clearProfile()
  }

  async function login(username: string, password: string): Promise<
    { success: true } | { success: false; error: { code: string; message: string; status?: number } }
  > {
    const result = await apiLogin({ username, password })
    if (result.success) {
      const userStore = useUserStore()
      hasSession.value = true
      expiresAt.value = Date.now() + result.data.expiresIn * 1000
      userStore.setProfile(result.data.profile)
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
    try {
      const result = await apiRestore()
      if (result) {
        applyRestore(result)
        return true
      }
      clearSession()
      return false
    } catch (_err) {
      clearSession()
      return false
    }
  }

  return {
    hasSession,
    expiresAt,
    restoreAttempted,
    isAuthenticated,
    login,
    logout,
    attemptRestore,
    clearSession
  }
})
