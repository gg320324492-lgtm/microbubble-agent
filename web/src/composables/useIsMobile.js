import { ref, computed, onMounted, onUnmounted } from 'vue'

/**
 * 移动端断点检测 composable
 *
 * 4 档断点（mobile-first 渐进增强）：
 *   xs  < 480px    iPhone SE 一代等极小屏
 *   sm  < 768px    iPhone 主流屏
 *   md  < 1024px   iPad mini / iPad Pro 竖屏
 *   lg  >= 1024px  桌面端
 *
 * 全局单例：所有 useIsMobile() 调用共享同一份状态，避免每个组件重复监听 resize。
 *
 * 用法：
 *   const { isMobile, isMobileXS, isTablet, isDesktop, bp } = useIsMobile()
 *   if (isMobile.value) { ... }
 */

// 断点阈值（CSS @media 数值必须硬写，但 JS 可变量化统一维护）
export const BREAKPOINTS = Object.freeze({
  xs: 480,
  sm: 768,
  md: 1024,
  lg: 1280,
})

// 全局单例状态（所有 useIsMobile() 调用共享）
const viewport = ref({
  width: typeof window !== 'undefined' ? window.innerWidth : 1280,
  height: typeof window !== 'undefined' ? window.innerHeight : 720,
  dpr: typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1,
})

let initialized = false
let resizeTimer = null
let orientationTimer = null

function update() {
  if (typeof window === 'undefined') return
  viewport.value = {
    width: window.innerWidth,
    height: window.innerHeight,
    dpr: window.devicePixelRatio || 1,
  }
}

function onResize() {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(update, 100)
}

function onOrientationChange() {
  // iOS 横竖屏切换时 innerHeight 改变有延迟，需要二次确认
  if (orientationTimer) clearTimeout(orientationTimer)
  orientationTimer = setTimeout(update, 200)
}

function attach() {
  if (initialized || typeof window === 'undefined') return
  initialized = true
  update()
  window.addEventListener('resize', onResize, { passive: true })
  window.addEventListener('orientationchange', onOrientationChange)
}

function detach() {
  if (typeof window === 'undefined') return
  window.removeEventListener('resize', onResize)
  window.removeEventListener('orientationchange', onOrientationChange)
  initialized = false
}

/**
 * 手动重置（用于 SPA 路由切换或强制刷新检测）
 * 一般不需要调用，除非是 HMR 场景
 */
export function refreshBreakpoint() {
  update()
}

export function useIsMobile() {
  // 在 setup 阶段就调用 attach（HMR 友好：HMR 时组件会重新 setup）
  attach()

  onUnmounted(() => {
    // 注意：不在 unmounted 时 detach，因为全局单例需要保持监听
    // 只有在应用卸载时（极少见）才需要 detach
  })

  const width = computed(() => viewport.value.width)
  const height = computed(() => viewport.value.height)
  const dpr = computed(() => viewport.value.dpr)

  const isMobileXS = computed(() => width.value < BREAKPOINTS.sm)
  const isMobile = computed(() => width.value < BREAKPOINTS.md)
  const isTablet = computed(
    () => width.value >= BREAKPOINTS.md && width.value < BREAKPOINTS.lg
  )
  const isDesktop = computed(() => width.value >= BREAKPOINTS.lg)
  const isPortrait = computed(() => height.value >= width.value)

  const bp = computed(() => {
    const w = width.value
    if (w < BREAKPOINTS.sm) return 'xs'
    if (w < BREAKPOINTS.md) return 'sm'
    if (w < BREAKPOINTS.lg) return 'md'
    return 'lg'
  })

  return {
    width,
    height,
    dpr,
    bp,
    isMobileXS,
    isMobile,
    isTablet,
    isDesktop,
    isPortrait,
  }
}

// 暴露单例 ref 给路由级 dynamic import 使用（resolveMobile.js）
export function useViewportRef() {
  return viewport
}

export default useIsMobile