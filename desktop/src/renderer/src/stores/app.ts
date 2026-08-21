// app Pinia store —— 应用层 UI 状态（与 auth/user 分离）。
// Phase 1 仅占位；Phase 2+ 业务模块使用（主题色 / 侧边栏折叠 / 字号等）。

import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const theme = ref<'light' | 'dark'>('dark')
  const sidebarCollapsed = ref(false)
  const backendUrl = ref('')

  function setTheme(t: 'light' | 'dark'): void {
    theme.value = t
  }

  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function setBackendUrl(url: string): void {
    backendUrl.value = url
  }

  return {
    theme,
    sidebarCollapsed,
    backendUrl,
    setTheme,
    toggleSidebar,
    setBackendUrl
  }
})
