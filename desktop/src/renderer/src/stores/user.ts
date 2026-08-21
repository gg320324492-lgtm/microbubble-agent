// user Pinia store —— 当前用户档案。
// 与 auth store 关注分离：auth 关心 token，user 关心档案。

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UserInfo } from '@shared/auth-types'

export const useUserStore = defineStore('user', () => {
  const profile = ref<UserInfo | null>(null)

  function setProfile(p: UserInfo): void {
    profile.value = p
  }

  function clearProfile(): void {
    profile.value = null
  }

  return { profile, setProfile, clearProfile }
})
