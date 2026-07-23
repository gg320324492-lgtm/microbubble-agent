// useResponsive.js — 响应式断点 + 方向 + DPR 统一 composable
// 2026-07-24  W68 第 1 批 路线 C Agent 5 派工
//
// 设计:
// - 监听 resize + orientationchange 事件 (debounce 100ms / 200ms 二次确认)
// - 断点检测 (sm 320, md 768, lg 1024, xl 1280)
// - 横屏 / 竖屏 + 设备像素比 (DPR) 检测
// - 全局单例: 所有 useResponsive() 共享同一份状态
//
// 用法:
//   const { width, height, dpr, bp, isPortrait, isLandscape } = useResponsive()
//   if (bp.value === 'sm') { ... }

import { ref, computed, onUnmounted } from 'vue'

/**
 * 断点阈值 (与 useIsMobile.js BREAKPOINTS 对齐但对齐 CSS 设计令牌规范)
 *   sm  < 640px    iPhone SE 主流屏 (CSS @media min-width 阈值)
 *   md  < 768px    iPad mini 竖屏
 *   lg  < 1024px   iPad Pro / 笔记本
 *   xl  >= 1024px  桌面端
 *   2xl >= 1280px  大屏
 */
export const BREAKPOINTS = Object.freeze({
  sm: 320,
  md: 768,
  lg: 1024,
  xl: 1280,
})

// SSR 安全默认值
const viewport = ref({
  width: typeof window !== 'undefined' ? window.innerWidth : 1280,
  height: typeof window !== 'undefined' ? window.innerHeight : 720,
  dpr: typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1,
})

let initialized = false
let resizeTimer = null
let orientationTimer = null
let mediaQueryLists = null
let mediaHandlers = []

function updateViewport() {
  if (typeof window === 'undefined') return
  viewport.value = {
    width: window.innerWidth,
    height: window.innerHeight,
    dpr: window.devicePixelRatio || 1,
  }
}

function onResizeDebounced() {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(updateViewport, 100)
}

function onOrientationChange() {
  // iOS 横竖屏切换时 innerHeight 改变有延迟, 需要二次确认
  if (orientationTimer) clearTimeout(orientationTimer)
  orientationTimer = setTimeout(updateViewport, 200)
}

function attach() {
  if (initialized || typeof window === 'undefined') return
  initialized = true
  updateViewport()
  window.addEventListener('resize', onResizeDebounced, { passive: true })
  window.addEventListener('orientationchange', onOrientationChange)

  // 注册 matchMedia 监听 - 当跨断点时立即通知 (不依赖 resize 事件)
  // 用于精确断点检测, 避免尺寸微调 (浏览器工具栏显隐) 误判
  if (typeof window.matchMedia === 'function') {
    mediaQueryLists = []
    const bpEntries = Object.entries(BREAKPOINTS)
    for (let i = 0; i < bpEntries.length - 1; i++) {
      const [, lower] = bpEntries[i]
      const [, upper] = bpEntries[i + 1]
      const mql = window.matchMedia(`(min-width: ${lower}px) and (max-width: ${upper - 1}px)`)
      const handler = () => updateViewport()
      if (mql.addEventListener) {
        mql.addEventListener('change', handler)
      } else if (mql.addListener) {
        mql.addListener(handler)
      }
      mediaQueryLists.push(mql)
      mediaHandlers.push(() => {
        if (mql.removeEventListener) mql.removeEventListener('change', handler)
        else if (mql.removeListener) mql.removeListener(handler)
      })
    }
  }
}

function detach() {
  if (typeof window === 'undefined') return
  window.removeEventListener('resize', onResizeDebounced)
  window.removeEventListener('orientationchange', onOrientationChange)
  mediaHandlers.forEach((fn) => { try { fn() } catch (_) { /* ignore */ } })
  mediaHandlers = []
  mediaQueryLists = null
  initialized = false
}

/**
 * 手动刷新 (用于 HMR / 路由切换场景)
 */
export function refreshResponsive() {
  updateViewport()
}

/**
 * 销毁全局监听 (应用卸载时调用, 一般不需要)
 */
export function disposeResponsive() {
  detach()
}

/**
 * @returns {{
 *   width: import('vue').ComputedRef<number>,
 *   height: import('vue').ComputedRef<number>,
 *   dpr: import('vue').ComputedRef<number>,
 *   bp: import('vue').ComputedRef<'sm'|'md'|'lg'|'xl'>,
 *   isMobile: import('vue').ComputedRef<boolean>,
 *   isTablet: import('vue').ComputedRef<boolean>,
 *   isDesktop: import('vue').ComputedRef<boolean>,
 *   isPortrait: import('vue').ComputedRef<boolean>,
 *   isLandscape: import('vue').ComputedRef<boolean>,
 *   isRetina: import('vue').ComputedRef<boolean>,
 * }}
 */
export function useResponsive() {
  attach()

  onUnmounted(() => {
    // 注意: 全局单例需要保持监听, 仅在应用卸载时才 detach
  })

  const width = computed(() => viewport.value.width)
  const height = computed(() => viewport.value.height)
  const dpr = computed(() => viewport.value.dpr)

  const isPortrait = computed(() => height.value >= width.value)
  const isLandscape = computed(() => width.value > height.value)
  const isRetina = computed(() => dpr.value >= 2)

  const bp = computed(() => {
    const w = width.value
    if (w < BREAKPOINTS.md) return 'sm'      // < 768
    if (w < BREAKPOINTS.lg) return 'md'      // 768-1023
    if (w < BREAKPOINTS.xl) return 'lg'      // 1024-1279
    return 'xl'                              // >= 1280
  })

  const isMobile = computed(() => width.value < BREAKPOINTS.md)
  const isTablet = computed(
    () => width.value >= BREAKPOINTS.md && width.value < BREAKPOINTS.lg
  )
  const isDesktop = computed(() => width.value >= BREAKPOINTS.lg)

  return {
    width,
    height,
    dpr,
    bp,
    isMobile,
    isTablet,
    isDesktop,
    isPortrait,
    isLandscape,
    isRetina,
  }
}

/**
 * 暴露单例 ref 给路由级 dynamic import 使用
 */
export function useViewportRef() {
  return viewport
}

export default useResponsive
