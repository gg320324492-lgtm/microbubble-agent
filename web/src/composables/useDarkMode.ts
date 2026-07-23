/**
 * useDarkMode.ts — 暗色模式增强 composable（W68 路线 C 移动端暗色精修）
 *
 * 在 `useThemeStore`（light / dark + accent 双轴）基础上，补齐 4 个能力：
 *   1. prefers-color-scheme 系统偏好检测（system / light / dark / auto）
 *   2. localStorage 持久化（与 useThemeStore 共用 `theme` key，新增 `theme_pref` 记录偏好模式）
 *   3. 跨标签页同步（监听 storage 事件，A 标签切主题 B 标签自动跟随）
 *   4. 时段自动切换（auto 模式下，夜晚 19:00–07:00 自动 dark，白天自动 light）
 *
 * 设计要点：
 *   - 4 种偏好模式（pref）：
 *       'light'  — 强制亮色
 *       'dark'   — 强制暗色
 *       'system' — 跟随操作系统 prefers-color-scheme
 *       'auto'   — 跟随时段（夜晚 dark / 白天 light）
 *   - pref 决定"如何选出" mode（'light' | 'dark'），mode 才真正写入 <html data-theme>。
 *   - 与 useThemeStore 解耦：本 composable 只负责"偏好 → mode"决策 + 副作用应用，
 *     不重复维护 accent。若项目引入 useThemeStore，可选传入其 setter 保持单一数据源。
 *
 * 用法：
 *   import { useDarkMode } from '@/composables/useDarkMode'
 *   const { pref, isDark, setPref, toggle } = useDarkMode()
 *   setPref('system')   // 跟随系统
 *   setPref('auto')     // 跟随时段
 *   toggle()            // 在 light / dark 间硬切（转为强制模式）
 */

import { ref, computed, onMounted, onBeforeUnmount, watch, type Ref, type ComputedRef } from 'vue'

export type ThemePref = 'light' | 'dark' | 'system' | 'auto'
export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY_MODE = 'theme'        // 与 useThemeStore 共用：最终生效的 light/dark
const STORAGE_KEY_PREF = 'theme_pref'   // 新增：用户偏好模式（light/dark/system/auto）

// 时段自动切换阈值（本地时间）
const NIGHT_START_HOUR = 19  // 19:00 起视为夜晚
const NIGHT_END_HOUR = 7     // 07:00 前视为夜晚

// 全局单例状态（所有 useDarkMode() 调用共享，避免重复监听）
const pref: Ref<ThemePref> = ref(readInitialPref())
const systemPrefersDark = ref(readSystemPrefersDark())
const now = ref(Date.now())

let initialized = false
let mql: MediaQueryList | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null

function readInitialPref(): ThemePref {
  if (typeof localStorage === 'undefined') return 'light'
  const saved = localStorage.getItem(STORAGE_KEY_PREF)
  if (saved === 'light' || saved === 'dark' || saved === 'system' || saved === 'auto') {
    return saved
  }
  // 无偏好记录时，回退到已存在的 theme（兼容 useThemeStore 旧数据），否则 light
  const legacy = localStorage.getItem(STORAGE_KEY_MODE)
  if (legacy === 'dark' || legacy === 'light') return legacy
  return 'light'
}

function readSystemPrefersDark(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

/** 依据本地时间判断当前是否处于"夜晚"时段 */
function isNightTime(ts: number): boolean {
  const h = new Date(ts).getHours()
  return h >= NIGHT_START_HOUR || h < NIGHT_END_HOUR
}

/** 由偏好模式解析出最终生效的 light/dark */
function resolveMode(p: ThemePref, sysDark: boolean, ts: number): ThemeMode {
  switch (p) {
    case 'dark':
      return 'dark'
    case 'light':
      return 'light'
    case 'system':
      return sysDark ? 'dark' : 'light'
    case 'auto':
      return isNightTime(ts) ? 'dark' : 'light'
    default:
      return 'light'
  }
}

/** 应用 data-theme + PWA 顶栏颜色（与 useThemeStore.applyThemeColor 保持一致的深灰/暖橙） */
function applyMode(mode: ThemeMode): void {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', mode)
  let meta = document.head.querySelector('meta[name="theme-color"]') as HTMLMetaElement | null
  if (!meta) {
    meta = document.createElement('meta')
    meta.setAttribute('name', 'theme-color')
    document.head.appendChild(meta)
  }
  meta.setAttribute('content', mode === 'dark' ? '#1a1d23' : '#FF7A5C')
}

function persist(p: ThemePref, mode: ThemeMode): void {
  try {
    localStorage.setItem(STORAGE_KEY_PREF, p)
    localStorage.setItem(STORAGE_KEY_MODE, mode)
  } catch {
    /* ignore quota / private mode */
  }
}

// ---- 事件处理（模块级，保证跨标签同步 + 系统偏好监听的单例）----

function onSystemChange(e: MediaQueryListEvent): void {
  systemPrefersDark.value = e.matches
}

function onStorage(e: StorageEvent): void {
  // 跨标签页同步：另一个标签改了偏好或最终 mode 时，本标签跟随
  if (e.key === STORAGE_KEY_PREF && e.newValue) {
    if (['light', 'dark', 'system', 'auto'].includes(e.newValue)) {
      pref.value = e.newValue as ThemePref
    }
  } else if (e.key === STORAGE_KEY_MODE && e.newValue) {
    // 另一标签是 light/dark 强制切换（无 pref 变化时也要跟随）
    if ((e.newValue === 'dark' || e.newValue === 'light') && (pref.value === 'light' || pref.value === 'dark')) {
      pref.value = e.newValue as ThemePref
    }
  }
}

function attach(): void {
  if (initialized || typeof window === 'undefined') return
  initialized = true

  // 系统偏好监听
  if (typeof window.matchMedia === 'function') {
    mql = window.matchMedia('(prefers-color-scheme: dark)')
    // Safari < 14 只有 addListener
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', onSystemChange)
    } else if (typeof mql.addListener === 'function') {
      mql.addListener(onSystemChange)
    }
  }

  // 跨标签页同步
  window.addEventListener('storage', onStorage)

  // 时段自动切换：每分钟 tick 一次，驱动 auto 模式重算
  clockTimer = setInterval(() => {
    now.value = Date.now()
  }, 60 * 1000)
}

function detach(): void {
  if (typeof window === 'undefined') return
  if (mql) {
    if (typeof mql.removeEventListener === 'function') {
      mql.removeEventListener('change', onSystemChange)
    } else if (typeof mql.removeListener === 'function') {
      mql.removeListener(onSystemChange)
    }
    mql = null
  }
  window.removeEventListener('storage', onStorage)
  if (clockTimer) {
    clearInterval(clockTimer)
    clockTimer = null
  }
  initialized = false
}

// 最终生效 mode（响应式：pref / 系统偏好 / 时间任一变化都重算）
const mode: ComputedRef<ThemeMode> = computed(() =>
  resolveMode(pref.value, systemPrefersDark.value, now.value)
)

// 立即应用一次（模块 import 即执行，防止刷新闪烁 FOUC）
applyMode(mode.value)

// 单例 watch：mode 变化 → 应用 + 持久化
let watcherBound = false
function bindWatcher(): void {
  if (watcherBound) return
  watcherBound = true
  watch(
    mode,
    (m) => {
      applyMode(m)
      persist(pref.value, m)
    },
    { immediate: true }
  )
}

export function useDarkMode() {
  attach()
  bindWatcher()

  onMounted(() => {
    // 挂载时补一次系统偏好 + 时间读取（SSR / 初次 hydration 兜底）
    systemPrefersDark.value = readSystemPrefersDark()
    now.value = Date.now()
  })

  onBeforeUnmount(() => {
    // 全局单例：一般不 detach（保持监听），仅极端场景手动调用 detach()
  })

  const isDark = computed(() => mode.value === 'dark')
  const isLight = computed(() => mode.value === 'light')
  const followsSystem = computed(() => pref.value === 'system')
  const followsTime = computed(() => pref.value === 'auto')

  function setPref(p: ThemePref): void {
    if (p === 'light' || p === 'dark' || p === 'system' || p === 'auto') {
      pref.value = p
    }
  }

  /** 在 light / dark 间硬切（自动转为对应的强制模式） */
  function toggle(): void {
    pref.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  return {
    pref,
    mode,
    isDark,
    isLight,
    followsSystem,
    followsTime,
    systemPrefersDark,
    setPref,
    toggle,
  }
}

// 供外部（极端场景）手动释放监听
export function teardownDarkMode(): void {
  detach()
}

export default useDarkMode
