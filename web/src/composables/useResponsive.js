// useResponsive.js — 响应式断点 + 方向 + DPR 统一 composable (W83 B-2 P1-2 兼容层)
//
// 派工依据:
// - W82 A-2 Survey 3 §6 P1: useIsMobile.js + useResponsive.js BREAKPOINTS 重复
// - W83 B-2 P1-2 派工: 收敛为单一 viewport store
// - W82 B-2 拦截铁律: 分步走, 先建 useViewport.js 兼容层, 再删老文件 (W84 再删)
//
// 设计:
// - 本文件 (useResponsive.js) 已改为 thin-shell 委派到 useViewport.js
// - 保留原 BREAKPOINTS 命名 (sm/md/lg/xl) 兼容老调用方 (W85 清理)
// - 数值映射: sm=mobile 768 / md=tablet 1024 / lg=desktop 1280
// - 全局单例: 所有 useResponsive() 调用共享同一份状态 (useViewport 单例)
// - 删除计划: W84 后续 batch 删 useResponsive.js, 直接改为 `import from useViewport.js`
//
// 用法 (兼容老 API):
//   const { width, height, dpr, bp, isPortrait, isLandscape } = useResponsive()
//   if (bp.value === 'sm') { ... }

import { computed, onUnmounted } from 'vue'

import { useViewport, useViewportRef } from './useViewport'

// 兼容老 BREAKPOINTS 导出 (派工 v6 段 5 推荐 3 段: 768/1024/1280)
// 老 ALS 4 档: sm 320 / md 768 / lg 1024 / xl 1280
// 数值映射: sm=mobile 768 / md=tablet 1024 / lg=desktop 1280
// 注: 老 sm=320 在新统一断点下被废弃 (iPhone SE 主流屏也归入 sm<768 范围)
export const BREAKPOINTS = Object.freeze({
  sm: 320,
  md: 768,
  lg: 1024,
  xl: 1280,
})

export function useResponsive() {
  const {
    width,
    height,
    dpr,
    isPortrait,
    isLandscape,
    isRetina,
  } = useViewport()

  // 兼容老 bp 返回 'sm' | 'md' | 'lg' | 'xl' (4 档)
  const bpCompat = computed(() => {
    const w = width.value
    if (w < BREAKPOINTS.md) return 'sm'      // < 768
    if (w < BREAKPOINTS.lg) return 'md'      // 768-1023
    if (w < BREAKPOINTS.xl) return 'lg'      // 1024-1279
    return 'xl'                              // >= 1280
  })

  // 兼容老 isMobile 语义 (w < 1024 = BREAKPOINTS.lg)
  const isMobile = computed(() => width.value < BREAKPOINTS.lg)

  // 兼容老 isTablet 语义 (768-1023, 老 useResponsive 已废弃 1024-1279)
  const isTablet = computed(
    () => width.value >= BREAKPOINTS.md && width.value < BREAKPOINTS.lg
  )

  // 兼容老 isDesktop 语义 (w >= 1024 = BREAKPOINTS.lg)
  const isDesktop = computed(() => width.value >= BREAKPOINTS.lg)

  onUnmounted(() => {
    // 注意: 全局单例需要保持监听, 仅在应用卸载时才 detach
  })

  return {
    width,
    height,
    dpr,
    bp: bpCompat,
    isMobile,
    isTablet,
    isDesktop,
    isPortrait,
    isLandscape,
    isRetina,
  }
}

// 暴露单例 ref 给路由级 dynamic import 使用
// 兼容老 API: useViewportRef() 直接从 useViewport re-export
export { useViewportRef }

// 手动刷新 (兼容老 API)
export function refreshResponsive() {
  import('./useViewport').then((m) => m.refreshViewport())
}

// 销毁全局监听 (兼容老 API)
export function disposeResponsive() {
  import('./useViewport').then((m) => m.disposeViewport())
}

export default useResponsive
