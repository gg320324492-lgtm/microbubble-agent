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

function readInitial() {
  if (typeof localStorage === 'undefined') return 'light'
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'dark' || saved === 'light') return saved
  // 默认 light；如需 follow system 可改：return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  return 'light'
}

function apply(mode) {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', mode)

  // 动态注入 theme-color meta（不在 index.html 静态声明，避免 webhint 报 Firefox 不支持）
  // - 首次调用：createElement + appendChild 到 <head>
  // - 后续调用：直接 setAttribute('content', ...) 更新
  // - Firefox 不实现该属性，JS 注入无副作用
  let meta = document.head.querySelector('meta[name="theme-color"]')
  if (!meta) {
    meta = document.createElement('meta')
    meta.setAttribute('name', 'theme-color')
    document.head.appendChild(meta)
  }
  meta.setAttribute('content', mode === 'dark' ? '#1a1d23' : '#FF7A5C')
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref(readInitial())

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

  function set(modeValue) {
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