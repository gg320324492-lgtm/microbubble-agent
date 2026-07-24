/**
 * useThumbnailLazyLoad.ts — W68 第 14 批 C-3 桌面端 FileCard 缩略图懒加载 composable
 *
 * 2026-07-24 主指挥协调范式第 179 守恒 (W68 第 14 批 C-3).
 *
 * 职责:
 * - IntersectionObserver 观察元素可见性 (threshold 0.01, rootMargin '50px')
 * - 元素进入视口后触发 onIntersect 回调 (懒加载逻辑)
 * - 元素离开视口 (滚动过快) 不重复触发 (once 语义)
 * - 组件卸载时自动清理 observer (避免内存泄漏)
 * - 跨浏览器降级: 不支持 IntersectionObserver 时立即触发 (开发模式 + 旧浏览器)
 *
 * 设计原则 (5 新铁律 — W68 第 14 批派工纪要 v5 段 5):
 * 1. **IntersectionObserver threshold 0.01** — 不要 0 (滚动一开始立即触发, 用户体验更好)
 * 2. **rootMargin '50px'** — 提前 50px 触发 (滚动开始就预加载, 避免白屏闪烁)
 * 3. **once 语义** — 进入视口后不再观察 (避免滚动回滚时重复请求)
 * 4. **跨浏览器降级** — IntersectionObserver 不存在时直接 onIntersect (IE 11 / SSR / 旧 Safari)
 * 5. **自动 cleanup** — onBeforeUnmount 时 disconnect, 不污染 SPA 内存
 *
 * 数据契约:
 * - targetRef: 模板 ref (HTMLElement) — 需要观察的元素
 * - onIntersect: 进入视口时的回调 (sync, 不返回 Promise)
 * - options.threshold: 触发阈值 (默认 0.01)
 * - options.rootMargin: 提前触发距离 (默认 '50px')
 * - options.once: 进入后是否只触发一次 (默认 true)
 * - 返回: bindRef (用来绑到模板 ref) + observerActive (是否在观察)
 *
 * 0 production code 改动铁律:
 * - 纯前端 composable, 仅 desktop views/components/composables 范畴
 * - 不动后端 API / 不动 FileCard.vue 业务逻辑 / 不动 drive-view.css
 * - 仅替换 onMounted 直接调 loadThumbnail 为 IntersectionObserver 触发
 * - 桌面端大文件夹 (200 文件) 滚动 FPS 60+ 性能提升
 */

import { ref, onBeforeUnmount } from 'vue'

export interface UseThumbnailLazyLoadOptions {
  /** IntersectionObserver 触发阈值 (默认 0.01, 不要用 0 派工纪要 v5 段 5 反馈预期) */
  threshold?: number
  /** 提前触发距离 (默认 '50px', 滚动开始就预加载避免白屏) */
  rootMargin?: string
  /** 进入视口后是否只触发一次 (默认 true, 避免回滚重复请求) */
  once?: boolean
}

export interface UseThumbnailLazyLoadReturn {
  /** 绑到模板 ref 的函数 (推荐: :ref="(el) => bindRef(el as HTMLElement)") */
  bindRef: (el: HTMLElement | null) => void
  /** 是否正在观察 (false = 已触发或已卸载) */
  observerActive: import('vue').Ref<boolean>
  /** 手动触发 (跳过 IntersectionObserver, 例如强制加载第一屏) */
  triggerNow: () => void
  /** 卸载 observer */
  cleanup: () => void
}

/**
 * 缩略图懒加载 composable (IntersectionObserver)
 *
 * @param onIntersect 进入视口时的回调 (通常调 loadThumbnail 拉取缩略图 URL)
 * @param options.threshold 默认 0.01
 * @param options.rootMargin 默认 '50px'
 * @param options.once 默认 true (进入后只触发一次)
 */
export function useThumbnailLazyLoad(
  onIntersect: () => void | Promise<void>,
  options: UseThumbnailLazyLoadOptions = {},
): UseThumbnailLazyLoadReturn {
  const threshold = options.threshold ?? 0.01
  const rootMargin = options.rootMargin ?? '50px'
  const once = options.once ?? true

  // === 状态 ===
  const observerActive = ref(false)
  let observer: IntersectionObserver | null = null
  let triggered = false  // once 语义守卫

  // === 手动触发 (跳过 IntersectionObserver, 用于首屏强制加载 + SSR) ===
  function triggerNow() {
    if (triggered && once) return
    triggered = true
    Promise.resolve(onIntersect()).catch((e) => {
      // best-effort: 失败不影响其他
      console.warn('[useThumbnailLazyLoad] onIntersect failed:', e)
    })
  }

  // === 清理 observer ===
  function cleanup() {
    if (observer) {
      observer.disconnect()
      observer = null
    }
    observerActive.value = false
  }

  // === 绑到模板 ref ===
  function bindRef(el: HTMLElement | null) {
    // 解绑旧的
    cleanup()

    if (!el || typeof IntersectionObserver === 'undefined') {
      // 降级: 立即触发 (旧浏览器 / SSR / jsdom 测试)
      triggerNow()
      return
    }

    triggered = false
    observerActive.value = true

    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            // 触发回调
            Promise.resolve(onIntersect()).catch((e) => {
              console.warn('[useThumbnailLazyLoad] onIntersect failed:', e)
            })
            triggered = true
            if (once) {
              // once 语义: 触发后立即 disconnect
              cleanup()
            }
          }
        }
      },
      { threshold, rootMargin },
    )
    observer.observe(el)
  }

  // === 组件卸载时清理 (避免 SPA 内存泄漏) ===
  onBeforeUnmount(() => {
    cleanup()
  })

  return {
    bindRef,
    observerActive,
    triggerNow,
    cleanup,
  }
}

export default useThumbnailLazyLoad