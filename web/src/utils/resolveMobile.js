import { defineAsyncComponent } from 'vue'
import { useViewportRef } from '@/composables/useIsMobile'

/**
 * 路由级动态 import 工具（桌面/移动双栈核心）
 *
 * 用法：
 *   // router/index.js
 *   import { resolveMobileComponent } from '@/utils/resolveMobile'
 *
 *   {
 *     path: 'chat',
 *     component: resolveMobileComponent('chat/ChatViewSSE', 'chat/MobileChatView'),
 *   }
 *
 * 实现细节：
 * - 初次调用时根据 window.innerWidth 选择桌面/移动版本
 * - 旋转屏幕时 useAdaptiveRoute 会触发 router.replace，
 *   此时 resolveMobileComponent 会重新评估并选新版本
 * - SSR-safe：window 不存在时默认桌面版（不会报错）
 */

const MOBILE_BREAKPOINT = 768

function isCurrentlyMobile() {
  if (typeof window === 'undefined') return false
  // 优先用 useViewportRef（如果已 attach），否则直接读 window
  try {
    const ref = useViewportRef()
    if (ref?.value?.width !== undefined) {
      return ref.value.width < MOBILE_BREAKPOINT
    }
  } catch {
    /* ignore */
  }
  return window.innerWidth < MOBILE_BREAKPOINT
}

/**
 * 动态加载桌面版或移动版组件
 *
 * @param {string} desktopPath - 相对 @/views/ 的路径，如 'chat/ChatViewSSE'
 * @param {string} mobilePath - 相对 @/views/mobile/ 的路径，如 'chat/MobileChatView'
 * @returns {Function} defineAsyncComponent 包装的动态组件
 */
export function resolveMobileComponent(desktopPath, mobilePath) {
  return defineAsyncComponent(() => {
    const isMobile = isCurrentlyMobile()
    const target = isMobile && mobilePath
      ? `@/views/mobile/${mobilePath}.vue`
      : `@/views/${desktopPath}.vue`
    return import(/* @vite-ignore */ target)
  })
}

/**
 * 仅移动端组件（如果移动端不存在对应组件，路由 fallback 到桌面版）
 * 用于桌面组件无需移动版的场景
 *
 * @param {string} desktopPath - 相对 @/views/ 的路径
 * @returns {Function}
 */
export function resolveComponent(desktopPath) {
  return defineAsyncComponent(() => {
    return import(/* @vite-ignore */ `@/views/${desktopPath}.vue`)
  })
}

/**
 * 仅移动端组件（桌面版缺失时显示占位）
 *
 * @param {string} mobilePath - 相对 @/views/mobile/ 的路径
 * @returns {Function}
 */
export function resolveMobileOnly(mobilePath) {
  return defineAsyncComponent(() => {
    return import(/* @vite-ignore */ `@/views/mobile/${mobilePath}.vue`)
  })
}

export default resolveMobileComponent