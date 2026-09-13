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
 *   theme.toggle()           // light ↔ dark
 *   theme.isDark             // computed boolean
 *
 * 自动应用：watch 监听 mode，修改后立即 setAttribute + localStorage。
 * 防闪烁：main.js 在 import 时立即调用一次 apply()（用 init 函数）。
 *
 * 2026-09-13: 移除 accent 多主题色（orange/ocean/forest）—— 设置页外观区块已删，
 * 品牌色固定暖橙珊瑚。EP primary token 映射在 variables.css [data-theme] 块内。
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const STORAGE_KEY_THEME = 'theme'

function readInitialTheme() {
  if (typeof localStorage === 'undefined') return 'light'
  const saved = localStorage.getItem(STORAGE_KEY_THEME)
  if (saved === 'dark' || saved === 'light') return saved
  return 'light'
}

function applyThemeColor(mode) {
  // 注入 PWA 顶栏颜色（手机浏览器顶部栏）
  if (typeof document === 'undefined') return
  let meta = document.head.querySelector('meta[name="theme-color"]')
  if (!meta) {
    meta = document.createElement('meta')
    meta.setAttribute('name', 'theme-color')
    document.head.appendChild(meta)
  }
  // light: 暖橙；dark: 深灰
  meta.setAttribute('content', mode === 'dark' ? '#1a1d23' : '#FF7A5C')
}

function applyTheme(mode) {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', mode)
  applyThemeColor(mode)
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref(readInitialTheme())

  // 立即应用初始值（避免刷新时 brief flash）
  applyTheme(mode.value)

  // 监听 mode 变化：写入 localStorage + 更新 data-theme
  watch(mode, (v) => {
    try {
      localStorage.setItem(STORAGE_KEY_THEME, v)
    } catch { /* ignore */ }
    applyTheme(v)
  })

  const isDark = computed(() => mode.value === 'dark')
  const isLight = computed(() => mode.value === 'light')

  function toggle() {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  function set(modeValue) {
    if (modeValue === 'dark' || modeValue === 'light') {
      mode.value = modeValue
    }
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
