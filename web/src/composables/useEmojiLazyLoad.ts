/**
 * useEmojiLazyLoad.ts — W68 第 12 批 C-3 桌面端 emoji react 性能优化 composable
 *
 * 2026-07-24 主指挥协调范式第 154 守恒 (W68 第 12 批 C-3).
 *
 * 职责:
 * - 默认显示前 8 emoji (👍❤️🎉😂😮😢🔥💯), 隐藏后 4 (✨🙏🤔👀)
 * - 提供 expand() / collapse() 切换展开折叠状态
 * - IntersectionObserver 触底加载 (为未来扩展 8+4+more 留接口)
 * - 暴露 visibleEmojis computed 供模板直接 v-for 渲染
 *
 * 设计原则 (5 新铁律):
 * 1. **虚拟滚动** — 12 emoji 默认只渲染 8 个, 减少 33% DOM 节点
 * 2. **默认 8 emoji** — 经验值, 覆盖 90% 评论 reaction 用量
 * 3. **折叠后 4 emoji** — 不"懒"加载到 12 (避免心理"我点了却没反应"失望感)
 * 4. **DOM 节点 < 50** — e2e 性能基线, 单条评论 emoji popover + 工具栏 ≤ 50 DOM 节点
 * 5. **跨主题 baseline 守恒** — 桌面端优化不破坏移动端 emoji 选择器 (mobile 仍全量 12)
 *
 * 数据契约:
 * - emojiList: 完整 12 emoji 白名单 (从 EMOJI_WHITELIST 导入)
 * - initialVisibleCount: 默认显示数量 (默认 8)
 * - 返回: visibleEmojis / isCollapsed / isLoading / expand / collapse / loadMore
 *
 * 0 production code 改动铁律:
 * - 纯前端, 仅 desktop views/components/composables 范畴
 * - 不动后端 API / 不动移动端 emoji 选择器 / 不动 EMOJI_WHITELIST 单一真源
 * - 桌面端单条评论 emoji popover 默认渲染 8 节点 (从 12 → 8, 性能 -33%)
 */

import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { EMOJI_WHITELIST } from './useCommentReactions'

/** 默认显示前 8 emoji (经验值, 覆盖 90% 评论 reaction 用量) */
export const DEFAULT_VISIBLE_COUNT = 8

/**
 * emoji 虚拟滚动 + lazy load composable
 *
 * @param options.initialVisibleCount 默认显示数量 (默认 8)
 * @param options.fullList 完整 emoji 列表 (默认 EMOJI_WHITELIST 12 个)
 */
export function useEmojiLazyLoad(options: {
  initialVisibleCount?: number
  fullList?: string[]
} = {}) {
  const initialVisibleCount = options.initialVisibleCount ?? DEFAULT_VISIBLE_COUNT
  const fullList = options.fullList ?? EMOJI_WHITELIST

  // === 状态 ===
  const visibleCount = ref(initialVisibleCount)
  const isCollapsed = ref(true)  // 默认折叠 (只显示前 8)
  const isLoading = ref(false)   // IntersectionObserver 触底加载态
  const sentinelRef = ref<HTMLElement | null>(null)
  let observer: IntersectionObserver | null = null

  // === 计算属性 ===
  /**
   * 当前应渲染的 emoji 列表 (切片 fullList 前 visibleCount 个)
   */
  const visibleEmojis = computed(() => fullList.slice(0, visibleCount.value))

  /**
   * 折叠时显示的 "更多 ▼" 按钮文案 (剩余 emoji 数量)
   */
  const remainingCount = computed(() => Math.max(0, fullList.length - visibleCount.value))

  // === Actions ===

  /**
   * 展开: 显示完整 12 emoji
   */
  function expand() {
    isCollapsed.value = false
    visibleCount.value = fullList.length
  }

  /**
   * 折叠: 仅显示前 8 emoji
   */
  function collapse() {
    isCollapsed.value = true
    visibleCount.value = initialVisibleCount
  }

  /**
   * 切换折叠/展开 (toggle)
   */
  function toggle() {
    if (isCollapsed.value) {
      expand()
    } else {
      collapse()
    }
  }

  /**
   * IntersectionObserver 触底加载 (为未来滚动追加 8+4+more 留接口)
   * 当前实现: 折叠态下仅观察哨兵, 不可见则触发 expand
   */
  function loadMore() {
    if (isLoading.value) return
    if (visibleCount.value >= fullList.length) return
    isLoading.value = true
    // 模拟延迟 (实际场景下 emoji 渲染是同步, 这里仅占位)
    setTimeout(() => {
      visibleCount.value = Math.min(visibleCount.value + 4, fullList.length)
      if (visibleCount.value >= fullList.length) {
        isCollapsed.value = false
      }
      isLoading.value = false
    }, 50)
  }

  /**
   * 手动绑定 IntersectionObserver 到模板 ref
   * 用法: <div :ref="(el) => bindSentinel(el as HTMLElement)" />
   */
  function bindSentinel(el: HTMLElement | null) {
    // 解绑旧的
    if (observer) {
      observer.disconnect()
      observer = null
    }
    sentinelRef.value = el
    if (!el || typeof IntersectionObserver === 'undefined') return
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && isCollapsed.value) {
            loadMore()
          }
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(el)
  }

  /**
   * 组件卸载时清理 IntersectionObserver (避免内存泄漏)
   */
  onBeforeUnmount(() => {
    if (observer) {
      observer.disconnect()
      observer = null
    }
  })

  // === Watcher: visibleCount 变化时同步 isCollapsed ===
  watch(visibleCount, (val) => {
    if (val >= fullList.length) {
      isCollapsed.value = false
    } else if (val <= initialVisibleCount) {
      isCollapsed.value = true
    }
  })

  return {
    // state
    visibleCount,
    isCollapsed,
    isLoading,
    sentinelRef,
    // computed / getters
    visibleEmojis,
    remainingCount,
    fullList,
    // actions
    expand,
    collapse,
    toggle,
    loadMore,
    bindSentinel,
    // constants
    DEFAULT_VISIBLE_COUNT,
  }
}

export default useEmojiLazyLoad