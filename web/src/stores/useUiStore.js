/**
 * useUiStore.js — 通用 UI 偏好（2026-06-14 收官新增，2026-07-13 #P1 扩展三档模式）
 *
 * 收纳所有 "用户偏好" 类开关到独立 store，避免散落 localStorage 调用。
 * 字段：
 * - showThinking — 控制 ChatViewSSE 是否渲染 agent 内部 trace (intent/critique/retry)，默认 false
 * - thinkingMode — 2026-07-13 #P1 三档推理模式: 'fast' | 'balanced' | 'deep', 默认 'balanced'
 *   - 历史 boolean 兼容: 老 key 'mnb:ui:useDeepThinking'='1' → 视为 'deep'
 *   - 新 key 'mnb:ui:thinkingMode' 存字符串 'fast'/'balanced'/'deep'
 * - lastModeInfo — 2026-07-13 #P1 SSE done 事件回填 (mode/model/thinkingTokens/durationMs)
 *   - 前端 ChatInputBar 右下角 mode badge 实时显示
 *
 * 用法：
 *   import { useUiStore } from '@/stores/useUiStore'
 *
 *   const ui = useUiStore()
 *   ui.thinkingMode // ref<'fast'|'balanced'|'deep'>
 *   ui.setThinkingMode('deep')
 *
 * localStorage key 命名空间：'mnb:ui:*'，与 useThemeStore 的 'theme' 错开。
 */

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'mnb:ui:showThinking'
const LEGACY_DEPTH_KEY = 'mnb:ui:useDeepThinking'  // 旧版 boolean 深度思考开关
const MODE_STORAGE_KEY = 'mnb:ui:thinkingMode'  // 2026-07-13 #P1 三档 (string)

const VALID_MODES = ['fast', 'balanced', 'deep']
const DEFAULT_MODE = 'balanced'

function readInitial() {
  if (typeof localStorage === 'undefined') return false
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function readModeInitial() {
  if (typeof localStorage === 'undefined') return DEFAULT_MODE
  try {
    // 优先读新 key
    const v = localStorage.getItem(MODE_STORAGE_KEY)
    if (VALID_MODES.includes(v)) return v
    // 2026-07-13 迁移: 老 boolean key 映射 mode
    // - '1' = 老 deep 开启 → 'deep'
    // - '0' 或 null = 老 deep 关闭 → 'fast' (因为老版没 balanced 概念, deep off ≈ 当时没有 thinking)
    const legacy = localStorage.getItem(LEGACY_DEPTH_KEY)
    if (legacy === '1') return 'deep'
    return DEFAULT_MODE
  } catch {
    return DEFAULT_MODE
  }
}

export const useUiStore = defineStore('ui', () => {
  const showThinking = ref(readInitial())
  // 2026-07-13 #P1: 旧 boolean useDeepThinking 替换为三档 string thinkingMode
  // 保留 useDeepThinking boolean getter/setter 兼容旧消费方 (建议新代码用 thinkingMode)
  const thinkingMode = ref(readModeInitial())
  // 2026-07-13 #P1: SSE done 事件回填 (前端 badge 显示)
  const lastModeInfo = ref({
    mode: null,
    model: null,
    thinkingTokens: 0,
    durationMs: 0,
  })

  watch(showThinking, (v) => {
    try {
      localStorage.setItem(STORAGE_KEY, v ? '1' : '0')
    } catch { /* ignore */ }
  })

  watch(thinkingMode, (v) => {
    try {
      localStorage.setItem(MODE_STORAGE_KEY, v)
    } catch { /* ignore */ }
  })

  function toggleThinking() {
    showThinking.value = !showThinking.value
  }

  function setShowThinking(v) {
    showThinking.value = !!v
  }

  function setThinkingMode(v) {
    if (VALID_MODES.includes(v)) thinkingMode.value = v
  }

  function setLastModeInfo(info) {
    lastModeInfo.value = { ...lastModeInfo.value, ...info }
  }

  // ===== 兼容层: 旧 useDeepThinking boolean API (建议新代码用 thinkingMode) =====
  // read-only computed: thinkingMode === 'deep'
  const useDeepThinking = ref(thinkingMode.value === 'deep')
  watch(thinkingMode, (v) => {
    useDeepThinking.value = v === 'deep'
  })

  function toggleDeepThinking() {
    setThinkingMode(useDeepThinking.value ? 'balanced' : 'deep')
  }

  function setUseDeepThinking(v) {
    setThinkingMode(v ? 'deep' : 'balanced')
  }

  return {
    showThinking,
    thinkingMode,        // 2026-07-13 #P1 新 API (推荐)
    lastModeInfo,        // 2026-07-13 #P1 SSE done 反馈
    toggleThinking,
    setShowThinking,
    setThinkingMode,
    setLastModeInfo,
    // 兼容旧 API (boolean)
    useDeepThinking,
    toggleDeepThinking,
    setUseDeepThinking,
  }
})

export default useUiStore