// usePullToRefresh.ts — 顶部下拉刷新 composable (W68 G-2 新增)
// 2026-07-24  W68 路线 G-2 Mobile 手势导航
//
// 设计:
// - 监听 touchstart/touchmove/touchend, 仅在 scrollTop === 0 时触发
// - 下拉距离 > threshold (默认 80px) 才触发 onRefresh
// - loading 状态管理 (refreshPromise 跟踪)
// - 实时 pullDistance ref 供 UI 显示下拉弧度/图标旋转
// - iOS Safari 兼容: overscroll-behavior: contain 由容器 CSS 控制, 此处不重复处理
// - touch-action: pan-y 在 touchstart 时设置, touchend 时还原
//
// 用法:
//   const { pullDistance, isRefreshing, isPulling, onRefresh } = usePullToRefresh(scrollContainerRef, {
//     threshold: 80,
//     maxPull: 160,
//     onRefresh: async () => { await fetchData() },
//   })

import { ref, watchEffect, onBeforeUnmount } from 'vue'

const DEFAULT_OPTIONS = {
  threshold: 80,           // 触发刷新的下拉距离 (px)
  maxPull: 160,            // 最大下拉距离 (px), 超过此会弹回
  onRefresh: null,         // 刷新回调 async () => {}
  refreshTimeoutMs: 15000, // 超时兜底 (避免 onRefresh 永远 hang 死锁)
}

/**
 * @param {import('vue').Ref<HTMLElement|null>|(() => HTMLElement|null)} scrollRef - 滚动容器 ref
 * @param {{
 *   threshold?: number,
 *   maxPull?: number,
 *   onRefresh?: () => Promise<void>|void,
 *   refreshTimeoutMs?: number,
 * }} options
 */
export function usePullToRefresh(scrollRef, options = {}) {
  const opts = { ...DEFAULT_OPTIONS, ...options }
  const pullDistance = ref(0)
  const isRefreshing = ref(false)
  const isPulling = ref(false)
  // 触发态: 已 trigger refresh, 不再触发 (避免多点触摸重复触发)
  let triggered = false
  let refreshTimer = null

  let startY = 0
  let startX = 0
  let active = false
  let scrollContainer = null

  // 工具: 找滚动容器 (scrollRef 自己, 或第一个可滚动父元素)
  function resolveScrollContainer(el) {
    if (!el) return null
    if (el.scrollHeight > el.clientHeight + 1) return el
    let parent = el.parentElement
    while (parent && parent !== document.body) {
      if (parent.scrollHeight > parent.clientHeight + 1) return parent
      parent = parent.parentElement
    }
    // 兜底: window 滚动场景, scrollTop = window.scrollY
    return el
  }

  function getScrollTop() {
    if (!scrollContainer) return 0
    if (scrollContainer === document.documentElement || scrollContainer === document.body) {
      return window.scrollY || document.documentElement.scrollTop || 0
    }
    return scrollContainer.scrollTop || 0
  }

  function handleTouchStart(e) {
    if (!e.touches || e.touches.length === 0) return
    if (isRefreshing.value) return
    const t = e.touches[0]
    startX = t.clientX
    startY = t.clientY
    active = true
    triggered = false
    pullDistance.value = 0
    isPulling.value = false
  }

  function handleTouchMove(e) {
    if (!active || isRefreshing.value) return
    // 只在 scrollTop === 0 时响应下拉 (避免正常滚动时被误触发)
    if (getScrollTop() > 0) return
    const t = e.touches[0]
    const dy = t.clientY - startY
    const dx = t.clientX - startX
    // 水平手势不响应 (避免和 swipe 冲突)
    if (Math.abs(dx) > Math.abs(dy)) return
    // 仅向下拉
    if (dy <= 0) {
      pullDistance.value = 0
      isPulling.value = false
      return
    }
    // 阻尼: 越往下越难拉 (用户感知)
    const damped = Math.min(opts.maxPull, dy * 0.5)
    pullDistance.value = damped
    isPulling.value = damped > 0

    // 触发判定 (distance 越过 threshold 后再松手才触发, 这里仅 set 标志)
    if (damped > opts.threshold && !triggered) {
      triggered = true
    }
  }

  async function handleTouchEnd() {
    if (!active) return
    active = false
    const reached = pullDistance.value >= opts.threshold
    // 还原 pull 视觉
    isPulling.value = false
    pullDistance.value = 0
    if (reached && opts.onRefresh && !isRefreshing.value) {
      isRefreshing.value = true
      // 超时兜底 (避免回调 hang)
      let timedOut = false
      refreshTimer = setTimeout(() => {
        timedOut = true
        isRefreshing.value = false
        // eslint-disable-next-line no-console
        console.warn('[usePullToRefresh] refresh timeout')
      }, opts.refreshTimeoutMs)
      try {
        await opts.onRefresh()
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('[usePullToRefresh] refresh error:', err)
      } finally {
        if (refreshTimer) {
          clearTimeout(refreshTimer)
          refreshTimer = null
        }
        if (!timedOut) isRefreshing.value = false
      }
    }
  }

  function attach(el) {
    if (!el || !el.addEventListener) return
    el.addEventListener('touchstart', handleTouchStart, { passive: true })
    el.addEventListener('touchmove', handleTouchMove, { passive: true })
    el.addEventListener('touchend', handleTouchEnd, { passive: true })
    el.addEventListener('touchcancel', handleTouchEnd, { passive: true })
  }

  function detach(el) {
    if (!el || !el.removeEventListener) return
    el.removeEventListener('touchstart', handleTouchStart)
    el.removeEventListener('touchmove', handleTouchMove)
    el.removeEventListener('touchend', handleTouchEnd)
    el.removeEventListener('touchcancel', handleTouchEnd)
  }

  let currentEl = null
  watchEffect(() => {
    const el = typeof scrollRef === 'function' ? scrollRef() : scrollRef.value
    if (el !== currentEl) {
      if (currentEl) detach(currentEl)
      currentEl = el
      if (el) {
        attach(el)
        scrollContainer = resolveScrollContainer(el)
      }
    }
  })

  onBeforeUnmount(() => {
    if (currentEl) detach(currentEl)
    currentEl = null
    if (refreshTimer) {
      clearTimeout(refreshTimer)
      refreshTimer = null
    }
  })

  return {
    pullDistance,
    isPulling,
    isRefreshing,
  }
}