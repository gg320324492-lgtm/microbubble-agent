import { ref, computed, onMounted, onBeforeUnmount, watch, type Ref, type ComputedRef } from 'vue'

/**
 * useVirtualList.ts — 通用虚拟滚动 composable (W100 +45 P3-VIRTUAL RETRY)
 *
 * 设计原则 (5 铁律, 来自 W100 +45 派工 + 类 20.144 派工沉淀):
 * 1. **阈值守恒** —  元素 ≤ threshold 时直接全量渲染 (保留 v-for/TransitionGroup 行为)
 *    元素 > threshold 时改虚拟渲染 (仅 visibleBuffer + overscan)
 * 2. **固定 item 高度** — 用 itemHeight 单一参数 (默认 60px), 不做动态测量
 *    适用于 ChatMessage / SessionItem 这类高度大致固定的场景
 * 3. **scroll 监听 + overscan** — 默认 lookahead/lookbehind 5 条, 减少滚动白边
 * 4. **lifecycle 完整** — onMounted 监听 scroll, onBeforeUnmount 清理
 *    IntersectionObserver 完整释放 (避免内存泄漏)
 * 5. **autostick 兼容** — 暴露 scrollToBottom, 外部流式生成时可调
 *    messages.append 时若 useAppendStick=true 自动滚到底
 *
 * 0 production code 改动铁律:
 * - 纯前端 composables/ 范畴, 仅被 ChatViewSSE.messages + SessionSidebar.filteredSessions 集成
 * - 不动后端 API / 不动 useChatStream / 不动现有 watch(messages) sticky scroll
 *
 * 数据契约:
 * - items: Ref<T[]> — 数据源 (外部响应式)
 * - containerRef: 由调用方 template ref 提供, 必须是滚动容器
 * - itemHeight: 单条预估高度 (px), 默认 60
 * - threshold: 多少条以上启用虚拟化 (默认 50, ≤ 50 不启用)
 * - overscan: 上下预渲染条数 (默认 5)
 * - 返回: visibleItems / startIndex / endIndex / totalHeight / isVirtualized /
 *         scrollToBottom / scrollToIndex / measureNow
 */

export interface VirtualListOptions<T = unknown> {
  containerRef: Ref<HTMLElement | null>
  items: Ref<readonly T[]>
  itemHeight?: number
  threshold?: number
  overscan?: number
  /** 追加新元素时是否自动滚到底 (默认 false, 交由外部 ChatViewSSE.stickyScroll 控制) */
  useAppendStick?: boolean
}

export interface VirtualListReturn<T = unknown> {
  /** 当前应渲染的条目 (窗口内 + overscan) */
  visibleItems: ComputedRef<Array<{ item: T; index: number }>>
  /** 第一个可见元素的索引 */
  startIndex: Ref<number>
  /** 最后一个可见元素的索引 (exclusive) */
  endIndex: Ref<number>
  /** 容器总高度 (px, 用于撑出滚动条) */
  totalHeight: ComputedRef<number>
  /** 是否处于虚拟化模式 */
  isVirtualized: ComputedRef<boolean>
  /** 用户设置的元素高度 (px) */
  itemHeight: number
  /** 滚到底部 (新消息追加时调用) */
  scrollToBottom: () => void
  /** 滚动到指定索引 (0-based) */
  scrollToIndex: (index: number) => void
  /** 强制重测容器高度 (ResizeObserver 触发) */
  measureNow: () => void
  /** 调试用: 当前 scrollTop */
  scrollTop: Ref<number>
  /** 调试用: 容器可视高度 (px) */
  viewportHeight: Ref<number>
}

const DEFAULT_ITEM_HEIGHT = 60
const DEFAULT_THRESHOLD = 50
const DEFAULT_OVERSCAN = 5

export function useVirtualList<T = unknown>(options: VirtualListOptions<T>): VirtualListReturn<T> {
  const {
    containerRef,
    items,
    itemHeight: rawItemHeight = DEFAULT_ITEM_HEIGHT,
    threshold: rawThreshold = DEFAULT_THRESHOLD,
    overscan: rawOverscan = DEFAULT_OVERSCAN,
    useAppendStick = false,
  } = options

  // 强制取整为正数, 防御性 literal
  const itemHeight = Math.max(1, Math.floor(rawItemHeight))
  const threshold = Math.max(1, Math.floor(rawThreshold))
  const overscan = Math.max(0, Math.floor(rawOverscan))

  // ===== 状态 =====
  const scrollTop = ref(0)
  const viewportHeight = ref(0)
  let resizeObserver: ResizeObserver | null = null

  // ===== 派生 =====
  const isVirtualized = computed(() => items.value.length > threshold)

  const totalHeight = computed(() => items.value.length * itemHeight)

  /** 第一个可见条目的索引 (向下取整) */
  const startIndex = computed(() => {
    if (!isVirtualized.value) return 0
    return Math.max(0, Math.floor(scrollTop.value / itemHeight) - overscan)
  })

  /** 最后一个可见条目的索引 (exclusive) */
  const endIndex = computed(() => {
    if (!isVirtualized.value) return items.value.length
    // viewportHeight ≤ 0 时 (未挂载 / 不可见) 不渲染任何条
    if (viewportHeight.value <= 0) return 0
    const visible = Math.ceil(viewportHeight.value / itemHeight) + 1
    const end = startIndex.value + visible + overscan * 2
    return Math.min(items.value.length, end)
  })

  /** 当前应渲染的条目 (含原始 index, 用于 :key) */
  const visibleItems = computed(() => {
    const start = startIndex.value
    const end = endIndex.value
    const slice = items.value.slice(start, end)
    return slice.map((item, offset) => ({ item, index: start + offset }))
  })

  // ===== 滚动处理 =====
  const handleScroll = (event: Event) => {
    const target = event.target as HTMLElement
    if (!target) return
    scrollTop.value = target.scrollTop
  }

  /** 主动提供的外部 scroll hook (供 ChatViewSSE 复用 onMessagesScroll) */
  const updateScrollTop = (newScrollTop: number, newViewportHeight?: number) => {
    scrollTop.value = newScrollTop
    if (typeof newViewportHeight === 'number') viewportHeight.value = newViewportHeight
  }

  // ===== 生命周期 =====
  const measureNow = () => {
    const el = containerRef.value
    if (!el) return
    viewportHeight.value = el.clientHeight
    scrollTop.value = el.scrollTop
  }

  const attachListeners = () => {
    const el = containerRef.value
    if (!el) return
    el.addEventListener('scroll', handleScroll, { passive: true })
    viewportHeight.value = el.clientHeight
    scrollTop.value = el.scrollTop
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        viewportHeight.value = el.clientHeight
      })
      resizeObserver.observe(el)
    }
  }

  const detachListeners = () => {
    const el = containerRef.value
    if (el) {
      el.removeEventListener('scroll', handleScroll)
    }
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  }

  onMounted(() => {
    attachListeners()
  })

  onBeforeUnmount(() => {
    detachListeners()
  })

  // ===== Actions =====
  const scrollToBottom = () => {
    const el = containerRef.value
    if (!el) return
    // 下一帧滚到底, 让新元素先入 DOM 再算 scrollHeight
    requestAnimationFrame(() => {
      if (!el) return
      const maxScroll = Math.max(0, el.scrollHeight - el.clientHeight)
      el.scrollTop = maxScroll
      scrollTop.value = el.scrollTop
    })
  }

  const scrollToIndex = (index: number) => {
    const el = containerRef.value
    if (!el) return
    const target = Math.max(0, Math.min(items.value.length - 1, index))
    el.scrollTop = target * itemHeight
    scrollTop.value = el.scrollTop
  }

  // ===== 自动粘底 (可选) =====
  if (useAppendStick) {
    watch(
      () => items.value.length,
      (newLen, oldLen) => {
        if (newLen > oldLen) scrollToBottom()
      },
    )
  }

  // ===== 容器 ref 延后绑定 (v-if 渲染时初始为 null) =====
  watch(
    containerRef,
    (el, prevEl) => {
      if (prevEl) detachListeners()
      if (el) attachListeners()
    },
  )

  return {
    visibleItems,
    startIndex,
    endIndex,
    totalHeight,
    isVirtualized,
    itemHeight,
    scrollToBottom,
    scrollToIndex,
    measureNow,
    scrollTop,
    viewportHeight,
    // 暴露给外部调用复用 (如 ChatViewSSE onMessagesScroll)
    _updateScroll: updateScrollTop,
  } as VirtualListReturn<T> & { _updateScroll: (top: number, height?: number) => void }
}

export default useVirtualList
