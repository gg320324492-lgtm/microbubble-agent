import { ref, computed, onUnmounted } from 'vue'

/**
 * 统一 viewport 状态 composable (W83 B-2 P1-2, BREAKPOINTS 收敛)
 *
 * 派工依据:
 * - W82 A-2 Survey 3 §6 P1: useIsMobile.js + useResponsive.js BREAKPOINTS 重复
 * - W83 B-2 P1-2: 收敛为单一 viewport store, 2 套断点统一
 * - W82 B-2 拦截铁律: 分步走, 先建 useViewport.js 兼容层, 再删老文件 (W84 再删)
 *
 * 设计:
 * - 监听 resize + orientationchange 事件 (debounce 100ms / 200ms 二次确认)
 * - 统一断点 (sm 768 / md 1024 / lg 1280, 3 段)
 * - 横屏 / 竖屏 + 设备像素比 (DPR) 检测
 * - 全局单例: 所有 useViewport() 调用共享同一份状态
 * - matchMedia 精确断点检测 (跨断点时立即通知)
 *
 * 用法:
 *   const { width, height, dpr, bp, isMobile, isTablet, isDesktop, isPortrait, isLandscape, isRetina } = useViewport()
 *   if (isMobile.value) { ... }
 *   if (bp.value === 'mobile') { ... }
 */

// 统一断点 (W83 B-2 P1-2, 派工 v6 段 5 推荐 3 段):
//   mobile < 768   (iPhone 主流屏 + iPad mini 竖屏)
//   tablet 768-1023 (iPad 横屏)
//   desktop >= 1024 (桌面端)
export const BREAKPOINTS = Object.freeze({
  mobile: 768,
  tablet: 1024,
  desktop: 1280,
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
    // 精确断点边界: 768 / 1024 / 1280
    const bpBoundaries = [
      BREAKPOINTS.mobile,   // 768
      BREAKPOINTS.tablet,   // 1024
      BREAKPOINTS.desktop,  // 1280
    ]
    for (let i = 0; i < bpBoundaries.length - 1; i++) {
      const lower = bpBoundaries[i]
      const upper = bpBoundaries[i + 1]
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
export function refreshViewport() {
  updateViewport()
}

/**
 * 销毁全局监听 (应用卸载时调用, 一般不需要)
 */
export function disposeViewport() {
  detach()
}

/**
 * @returns {{
 *   width: import('vue').ComputedRef<number>,
 *   height: import('vue').ComputedRef<number>,
 *   dpr: import('vue').ComputedRef<number>,
 *   bp: import('vue').ComputedRef<'mobile'|'tablet'|'desktop'>,
 *   isMobile: import('vue').ComputedRef<boolean>,
 *   isTablet: import('vue').ComputedRef<boolean>,
 *   isDesktop: import('vue').ComputedRef<boolean>,
 *   isPortrait: import('vue').ComputedRef<boolean>,
 *   isLandscape: import('vue').ComputedRef<boolean>,
 *   isRetina: import('vue').ComputedRef<boolean>,
 * }}
 */
export function useViewport() {
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
    if (w < BREAKPOINTS.mobile) return 'mobile'      // < 768
    if (w < BREAKPOINTS.desktop) return 'tablet'     // 768-1279
    return 'desktop'                                  // >= 1280
  })

  const isMobile = computed(() => width.value < BREAKPOINTS.tablet)
  const isTablet = computed(
    () => width.value >= BREAKPOINTS.tablet && width.value < BREAKPOINTS.desktop
  )
  const isDesktop = computed(() => width.value >= BREAKPOINTS.desktop)

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
 * 暴露单例 ref 给路由级 dynamic import 使用 (resolveMobile.js / useAdaptiveRoute.js)
 * 兼容 useIsMobile.js / useResponsive.js 老 API
 */
export function useViewportRef() {
  return viewport
}

export default useViewport
