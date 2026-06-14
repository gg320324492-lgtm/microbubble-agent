/**
 * useUiStore.js — 通用 UI 偏好（2026-06-14 收官新增）
 *
 * 收纳所有 "用户偏好" 类开关到独立 store，避免散落 localStorage 调用。
 * 第一个开关：showThinking — 控制 ChatViewSSE 是否渲染 agent 内部 trace
 * （intent/critique/retry 标签），默认 false。
 *
 * 用法：
 *   import { useUiStore } from '@/stores/useUiStore'
 *
 *   const ui = useUiStore()
 *   ui.showThinking  // ref<boolean>
 *   ui.toggleThinking()
 *
 * localStorage key 命名空间：'mnb:ui:*'，与 useThemeStore 的 'theme' 错开。
 */

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'mnb:ui:showThinking'

function readInitial() {
  if (typeof localStorage === 'undefined') return false
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export const useUiStore = defineStore('ui', () => {
  const showThinking = ref(readInitial())

  watch(showThinking, (v) => {
    try {
      localStorage.setItem(STORAGE_KEY, v ? '1' : '0')
    } catch { /* ignore */ }
  })

  function toggleThinking() {
    showThinking.value = !showThinking.value
  }

  function setShowThinking(v) {
    showThinking.value = !!v
  }

  return {
    showThinking,
    toggleThinking,
    setShowThinking,
  }
})

export default useUiStore
