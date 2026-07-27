import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'mnb:ui:showThinking'
const LEGACY_DEPTH_KEY = 'mnb:ui:useDeepThinking'
const MODE_STORAGE_KEY = 'mnb:ui:thinkingMode'
const NAV_RAIL_STORAGE_KEY = 'mnb:ui:navRailCollapsed'
const VALID_MODES = ['fast', 'balanced', 'deep']
const DEFAULT_MODE = 'balanced'

function readInitial() {
  try { return typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY) === '1' } catch { return false }
}
function readModeInitial() {
  try {
    if (typeof localStorage === 'undefined') return DEFAULT_MODE
    const value = localStorage.getItem(MODE_STORAGE_KEY)
    if (VALID_MODES.includes(value)) return value
    return localStorage.getItem(LEGACY_DEPTH_KEY) === '1' ? 'deep' : DEFAULT_MODE
  } catch { return DEFAULT_MODE }
}
function readNavRailInitial() {
  try { return typeof localStorage !== 'undefined' && localStorage.getItem(NAV_RAIL_STORAGE_KEY) === '1' } catch { return false }
}

export const useUiStore = defineStore('ui', () => {
  const showThinking = ref(readInitial())
  const thinkingMode = ref(readModeInitial())
  const navRailCollapsed = ref(readNavRailInitial())
  const lastModeInfo = ref({ mode: null, model: null, thinkingTokens: 0, durationMs: 0 })
  const useDeepThinking = ref(thinkingMode.value === 'deep')

  watch(showThinking, (v) => { try { localStorage.setItem(STORAGE_KEY, v ? '1' : '0') } catch {} })
  watch(thinkingMode, (v) => { try { localStorage.setItem(MODE_STORAGE_KEY, v); useDeepThinking.value = v === 'deep' } catch {} })
  watch(navRailCollapsed, (v) => { try { localStorage.setItem(NAV_RAIL_STORAGE_KEY, v ? '1' : '0') } catch {} })

  function toggleThinking() { showThinking.value = !showThinking.value }
  function setShowThinking(v) { showThinking.value = !!v }
  function setThinkingMode(v) { if (VALID_MODES.includes(v)) thinkingMode.value = v }
  function toggleNavRail() { navRailCollapsed.value = !navRailCollapsed.value }
  function setNavRailCollapsed(v) { navRailCollapsed.value = !!v }
  function setLastModeInfo(info) { lastModeInfo.value = { ...lastModeInfo.value, ...info } }
  function toggleDeepThinking() { setThinkingMode(useDeepThinking.value ? 'balanced' : 'deep') }
  function setUseDeepThinking(v) { setThinkingMode(v ? 'deep' : 'balanced') }

  return { showThinking, thinkingMode, navRailCollapsed, lastModeInfo, toggleThinking, setShowThinking, setThinkingMode, toggleNavRail, setNavRailCollapsed, setLastModeInfo, useDeepThinking, toggleDeepThinking, setUseDeepThinking }
})
export default useUiStore
