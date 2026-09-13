import { useViewportRef } from '@/composables/useIsMobile'

/**
 * 路由级动态 import 工具（桌面/移动双栈核心）
 *
 * PR #3 关键修复：用 import.meta.glob 替代 @vite-ignore
 * - 旧版用动态字符串路径 + @vite-ignore：Vite 静态分析无法识别 → mobile 文件未被任何 chunk 引用 → 不打包
 * - 新版用 import.meta.glob 通配符：Vite 把所有匹配文件都打包进 chunks
 *   桌面 chunk 包含桌面组件（按需），mobile chunk 包含所有 mobile 组件（按需）
 *   运行时再按 isMobile 状态选择
 *
 * 用法：
 *   import { resolveMobileComponent } from '@/utils/resolveMobile'
 *
 *   {
 *     path: 'chat',
 *     component: resolveMobileComponent('chat/ChatViewSSE', 'chat/MobileChatView'),
 *   }
 */

const MOBILE_BREAKPOINT = 768

// Vite 静态分析：glob 会让所有匹配文件都被打包
const desktopModules = import.meta.glob('@/views/**/*.vue')
const mobileModules = import.meta.glob('@/views/mobile/**/*.vue')

function isCurrentlyMobile() {
  if (typeof window === 'undefined') return false
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

function resolveKey(prefix, path) {
  // 把 'chat/ChatViewSSE' 转成 '/src/views/chat/ChatViewSSE.vue'
  return `/src/views/${prefix}${path}.vue`
}

/**
 * 动态加载桌面版或移动版组件
 *
 * @param {string} desktopPath - 相对 @/views/ 的路径，如 'chat/ChatViewSSE'
 * @param {string} mobilePath - 相对 @/views/mobile/ 的路径，如 'chat/MobileChatView'
 * @returns {Function} 异步加载函数 () => Promise<Component>
 *   (2026-09-13 起不再用 defineAsyncComponent 包装: Vue Router 对 route component
 *   期望 `() => import()` 形式, 传 defineAsyncComponent 会每条路由刷一次
 *   "Component defined using defineAsyncComponent()" 警告)
 */
export function resolveMobileComponent(desktopPath, mobilePath) {
  return async () => {
    const isMobile = isCurrentlyMobile()
    const target = isMobile && mobilePath
      ? mobileModules[resolveKey('mobile/', mobilePath)]
      : desktopModules[resolveKey('', desktopPath)]
    if (!target) {
      console.warn(
        `[resolveMobile] 未找到组件: ${isMobile ? 'mobile' : 'desktop'} ${isMobile ? mobilePath : desktopPath}`
      )
      // fallback 到 desktop
      return desktopModules[resolveKey('', desktopPath)]()
    }
    return target()
  }
}

/**
 * 仅桌面端组件
 */
export function resolveComponent(desktopPath) {
  return async () => {
    return desktopModules[resolveKey('', desktopPath)]()
  }
}

/**
 * 仅移动端组件（桌面版缺失时显示占位）
 */
export function resolveMobileOnly(mobilePath) {
  return async () => {
    return mobileModules[resolveKey('mobile/', mobilePath)]()
  }
}

export default resolveMobileComponent