/**
 * useThemeStore.js — 全局主题（light / dark + 6 套 accent）Pinia store
 *
 * 替代 ChatViewSSE.vue:99-106 散落的 localStorage.getItem('theme') + document.documentElement.setAttribute 逻辑。
 * 所有视图（桌面 + 移动）共享一个主题状态。
 *
 * 用法：
 *   import { useThemeStore } from '@/stores/useThemeStore'
 *
 *   const theme = useThemeStore()
 *   theme.toggle()           // light ↔ dark
 *   theme.setAccent('ocean') // 切主色
 *   theme.isDark             // computed boolean
 *   theme.accent             // ref: 'orange' | 'ocean' | 'forest'
 *
 * 自动应用：watch 监听 mode 和 accent，修改后立即 setAttribute + localStorage。
 * 防闪烁：main.js 在 import 时立即调用一次 apply()（用 init 函数）。
 *
 * v69 P1: 新增 accent 字段，支持 6 套主题（3 主色 × 2 明暗）。
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const STORAGE_KEY_THEME = 'theme'
const STORAGE_KEY_ACCENT = 'accent'

const ACCENT_OPTIONS = ['orange', 'ocean', 'forest']

function readInitialTheme() {
  if (typeof localStorage === 'undefined') return 'light'
  const saved = localStorage.getItem(STORAGE_KEY_THEME)
  if (saved === 'dark' || saved === 'light') return saved
  return 'light'
}

function readInitialAccent() {
  if (typeof localStorage === 'undefined') return 'orange'
  const saved = localStorage.getItem(STORAGE_KEY_ACCENT)
  if (ACCENT_OPTIONS.includes(saved)) return saved
  return 'orange'
}

function applyThemeColor(mode) {
  // 主色由 data-accent 决定；此函数仅注入 PWA 顶栏颜色（手机浏览器顶部栏）
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

function applyTheme(mode, accent) {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', mode)
  document.documentElement.setAttribute('data-accent', accent)
  applyThemeColor(mode)
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref(readInitialTheme())
  const accent = ref(readInitialAccent())

  // 立即应用初始值（避免刷新时 brief flash）
  applyTheme(mode.value, accent.value)

  // 监听 mode 变化：写入 localStorage + 更新 data-theme
  watch(mode, (v) => {
    try {
      localStorage.setItem(STORAGE_KEY_THEME, v)
    } catch { /* ignore */ }
    applyTheme(v, accent.value)
  })

  // 监听 accent 变化：写入 localStorage + 更新 data-accent
  watch(accent, (v) => {
    try {
      localStorage.setItem(STORAGE_KEY_ACCENT, v)
    } catch { /* ignore */ }
    applyTheme(mode.value, v)
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

  function setAccent(accentValue) {
    if (ACCENT_OPTIONS.includes(accentValue)) {
      accent.value = accentValue
    }
  }

  return {
    mode,
    accent,
    isDark,
    isLight,
    toggle,
    set,
    setAccent,
    ACCENT_OPTIONS,
  }
})

export default useThemeStore
