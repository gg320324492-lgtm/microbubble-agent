import { computed, onUnmounted } from 'vue'

/**
 * 移动端断点检测 composable (W83 B-2 P1-2 兼容层)
 *
 * 派工依据:
 * - W82 A-2 Survey 3 §6 P1: useIsMobile.js + useResponsive.js BREAKPOINTS 重复
 * - W83 B-2 P1-2 派工: 收敛为单一 viewport store
 * - W82 B-2 拦截铁律: 分步走, 先建 useViewport.js 兼容层, 再删老文件 (W84 再删)
 *
 * 设计:
 * - 本文件 (useIsMobile.js) 已改为 thin-shell 委派到 useViewport.js
 * - 保留原 BREAKPOINTS 命名 (xs/sm/md/lg) 兼容老调用方 (W85 清理)
 * - 注意: BREAKPOINTS 数值已统一为 useViewport.js 的 mobile/tablet/desktop 三档
 *   xs/sm 派生映射 (老语义): xs<768=mobile, sm 768-1023=tablet, md 1024-1279=tablet,
 *   lg>=1280=desktop (老 isMobile 判定 < 1024 保持)
 * - 全局单例: 所有 useIsMobile() 调用共享同一份状态 (useViewport 单例)
 * - 删除计划: W84 后续 batch 删 useIsMobile.js, 直接改为 `import from useViewport.js`
 *
 * 用法 (兼容老 API):
 *   const { isMobile, isMobileXS, isTablet, isDesktop, bp } = useIsMobile()
 *   if (isMobile.value) { ... }
 */

import { useViewport, useViewportRef } from './useViewport'

// 兼容老 BREAKPOINTS 导出 (派工 v6 段 5 推荐 3 段: 768/1024/1280)
// 老 ALS 4 档: xs<480 / sm<768 / md<1024 / lg<1280
// 数值映射与 useViewport 对齐: xs=mobile 768, sm=tablet 1024, md=desktop 1280
// 兼容老 isMobile (w<1024) / isDesktop (w>=1280) / isTablet (1024-1280)
export const BREAKPOINTS = Object.freeze({
  xs: 480,
  sm: 768,
  md: 1024,
  lg: 1280,
})

export function useIsMobile() {
  const {
    width,
    height,
    dpr,
    isMobile,
    isTablet,
    isDesktop,
    isPortrait,
  } = useViewport()

  // 兼容老 isMobileXS (w < 768, 原 W36 之前约定)
  const isMobileXS = computed(() => width.value < BREAKPOINTS.sm)

  // 兼容老 bp 返回 'xs' | 'sm' | 'md' | 'lg' (4 档)
  const bp = computed(() => {
    const w = width.value
    if (w < BREAKPOINTS.sm) return 'xs'
    if (w < BREAKPOINTS.md) return 'sm'
    if (w < BREAKPOINTS.lg) return 'md'
    return 'lg'
  })

  onUnmounted(() => {
    // 注意: 全局单例需要保持监听, 仅在应用卸载时才 detach
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
// 兼容老 API: useViewportRef() 直接从 useViewport re-export
export { useViewportRef }

// 手动重置 (兼容老 API)
export function refreshBreakpoint() {
  import('./useViewport').then((m) => m.refreshViewport())
}

export default useIsMobile
