import { watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useIsMobile, useViewportRef } from './useIsMobile'

/**
 * 路由级响应式：断点变化时自动 router.replace 触发 dynamic import 重选组件
 *
 * 用法：在 App.vue setup() 中调用一次
 *   useAdaptiveRoute()
 *
 * 实现细节：
 * - 监听 useViewportRef() 的 width 变化
 * - 跨断点（mobile ↔ desktop）时 router.replace 同一 fullPath
 * - debounce 300ms 防止拖拽浏览器边缘反复触发
 */

const MOBILE_BREAKPOINT = 768

export function useAdaptiveRoute() {
  const router = useRouter()
  const route = useRoute()
  const viewport = useViewportRef()

  let timer = null
  let lastIsMobile = viewport.value.width < MOBILE_BREAKPOINT

  watch(
    () => viewport.value.width,
    (newWidth) => {
      const newIsMobile = newWidth < MOBILE_BREAKPOINT
      if (newIsMobile === lastIsMobile) return // 同一端，无需重选

      // 跨断点：debounce 后触发 router.replace
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => {
        lastIsMobile = newIsMobile
        // router.replace 触发 lazy import 重选组件
        // 用 replace 不污染 history 栈
        try {
          router.replace({
            path: route.path,
            query: route.query,
            hash: route.hash,
          }).catch((err) => {
            // NavigationDuplicated 忽略（同一路径不应触发）
            if (err?.name !== 'NavigationDuplicated') {
              console.warn('[useAdaptiveRoute] replace failed:', err)
            }
          })
        } catch (e) {
          console.warn('[useAdaptiveRoute] replace error:', e)
        }
      }, 300)
    }
  )
}

export default useAdaptiveRoute