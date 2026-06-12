/**
 * useThemeStore.js — 全局主题（light / dark）Pinia store
 *
 * 替代 ChatViewSSE.vue:99-106 散落的 localStorage.getItem('theme') + document.documentElement.setAttribute 逻辑。
 * 所有视图（桌面 + 移动）共享一个主题状态。
 *
 * 用法：
 *   import { useThemeStore } from '@/stores/useThemeStore'
 *
 *   const theme = useThemeStore()
 *   theme.toggle()  // light ↔ dark
 *   theme.isDark    // computed boolean
 *
 * 自动应用：watch 监听 mode，修改后立即 setAttribute + localStorage。
 * 防闪烁：main.js 在 import 时立即调用一次 apply()（用 init 函数）。
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const STORAGE_KEY = 'theme'

function readInitial(): 'light' | 'dark' {
  if (typeof localStorage === 'undefined') return 'light'
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'dark' || saved === 'light') return saved
  // 默认 light；如需 follow system 可改：return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  return 'light'
}

function apply(mode: 'light' | 'dark') {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', mode)
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<'light' | 'dark'>(readInitial())

  // 立即应用初始值（避免刷新时 brief flash）
  apply(mode.value)

  // 监听 mode 变化：写入 localStorage + 更新 data-theme
  watch(mode, (v) => {
    try {
      localStorage.setItem(STORAGE_KEY, v)
    } catch { /* ignore */ }
    apply(v)
  })

  const isDark = computed(() => mode.value === 'dark')
  const isLight = computed(() => mode.value === 'light')

  function toggle() {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  function set(modeValue: 'light' | 'dark') {
    mode.value = modeValue
  }

  return {
    mode,
    isDark,
    isLight,
    toggle,
    set,
  }
})

export default useThemeStore