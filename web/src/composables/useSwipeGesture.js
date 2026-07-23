// useSwipeGesture.js — 触摸滑动识别 composable (W68 G-2 升级)
// 2026-07-22  PR8 mobile 文件预览 swipe (初始版本)
// 2026-07-24  W68 路线 G-2 升级: 速度判定 + 阻止默认滚动冲突 + iOS 边缘手势兼容
//
// 设计:
// - 监听 touchstart/touchmove/touchend
// - 计算水平/垂直位移 + 总耗时
// - 阈值检测: 距离 > 50px 且 时间 < 300ms 才算 swipe
// - 速度判定: velocity > 0.3 px/ms 即使距离不足阈值也立即触发 (W68 新增)
// - 阻止默认滚动冲突: touchmove 期间 dynamic touch-action: pan-y (W68 新增)
// - iOS Safari 边缘手势: overscroll-behavior: contain 容器 CSS (W68 新增, 见 MobileSwipeNavigation)
// - 返回 4 个方向回调 + currentSwipe 实时方向 ref
//
// 用法:
//   const { onSwipeLeft, onSwipeRight, currentSwipe } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300, velocity: 0.3 })
//   onSwipeLeft(() => goNext())
//   onSwipeRight(() => goPrev())

import { ref, watchEffect, onBeforeUnmount } from 'vue'

const DEFAULT_OPTIONS = {
  threshold: 50,        // 位移阈值 (px), 低于此不算 swipe
  timeout: 300,         // 时间阈值 (ms), 超过此不算 swipe (避免长按后拖拽被误判)
  velocity: 0.3,        // 速度阈值 (px/ms), 高于此即使 |distance| < threshold 也立即触发 (W68 新增)
  preventScrollConflict: true,  // touchmove 时给 target 设 touch-action: pan-y 防默认滚动冲突 (W68 新增)
  restoreTouchAction: true,     // touchend 时还原 touch-action (默认行为, false = 永久 pan-y)
}

/**
 * @param {import('vue').Ref<HTMLElement|null>|(() => HTMLElement|null)} targetRef - 绑定的 DOM ref
 * @param {{
 *   threshold?: number,
 *   timeout?: number,
 *   velocity?: number,
 *   preventScrollConflict?: boolean,
 *   restoreTouchAction?: boolean,
 * }} options
 * @returns {{
 *   onSwipeLeft: (cb: () => void) => void,
 *   onSwipeRight: (cb: () => void) => void,
 *   onSwipeUp: (cb: () => void) => void,
 *   onSwipeDown: (cb: () => void) => void,
 *   currentSwipe: import('vue').Ref<'left'|'right'|'up'|'down'|null>,
 * }}
 */
export function useSwipeGesture(targetRef, options = {}) {
  const opts = { ...DEFAULT_OPTIONS, ...options }
  const callbacks = { left: [], right: [], up: [], down: [] }
  const currentSwipe = ref(null)

  let startX = 0
  let startY = 0
  let startTime = 0
  let active = false
  // 触发态: 已被 velocity 触发后, 不再触发 callback (避免重复)
  let triggered = false
  // 保存原始 touch-action 用于还原
  let originalTouchAction = ''

  function handleTouchStart(e) {
    if (!e.touches || e.touches.length === 0) return
    const t = e.touches[0]
    startX = t.clientX
    startY = t.clientY
    startTime = Date.now()
    active = true
    triggered = false
    currentSwipe.value = null

    // W68 新增: touchstart 时设置 touch-action: pan-y 防水平滚动冲突
    // 仅当开启 preventScrollConflict (默认 true)
    if (opts.preventScrollConflict && e.currentTarget && e.currentTarget.style) {
      originalTouchAction = e.currentTarget.style.touchAction || ''
      try {
        // pan-y = 允许垂直滚动 + 禁用水平滚动 (浏览器水平 swipe 不再 scroll 父容器)
        e.currentTarget.style.touchAction = 'pan-y'
      } catch (err) {
        // 某些旧 Safari 不支持 style.touchAction 写入, 静默降级
      }
    }
  }

  function handleTouchMove(e) {
    if (!active) return
    const t = e.touches[0]
    const dx = t.clientX - startX
    const dy = t.clientY - startY
    const elapsed = Date.now() - startTime
    const absDx = Math.abs(dx)
    const absDy = Math.abs(dy)

    // 实时更新方向供 UI 反馈 (光标/动画)
    if (absDx > absDy) {
      currentSwipe.value = dx < 0 ? 'left' : 'right'
    } else {
      currentSwipe.value = dy < 0 ? 'up' : 'down'
    }

    // W68 新增: 速度判定 — 高 velocity 即使距离不足阈值也立即触发
    if (!triggered && elapsed > 0 && opts.velocity > 0) {
      const vx = absDx / elapsed
      const vy = absDy / elapsed
      const maxV = Math.max(vx, vy)
      if (maxV > opts.velocity) {
        triggered = true
        let direction = null
        if (absDx > absDy) {
          direction = dx < 0 ? 'left' : 'right'
        } else {
          direction = dy < 0 ? 'up' : 'down'
        }
        if (direction && callbacks[direction]) {
          callbacks[direction].forEach((cb) => {
            try { cb() } catch (err) { console.error('[useSwipeGesture] callback error:', err) }
          })
        }
        // 触发后保留 currentSwipe 一会儿, 让 UI 反馈显示完
        setTimeout(() => { currentSwipe.value = null }, 50)
      }
    }
  }

  function handleTouchEnd(e) {
    if (!active) return
    active = false

    // W68 新增: touchend 时还原 touch-action
    if (opts.preventScrollConflict && opts.restoreTouchAction && e.currentTarget && e.currentTarget.style) {
      try {
        e.currentTarget.style.touchAction = originalTouchAction
      } catch (err) {
        // 静默
      }
    }

    // 如果 velocity 已经触发, 不重复
    if (triggered) {
      currentSwipe.value = null
      return
    }

    const elapsed = Date.now() - startTime
    if (elapsed > opts.timeout) {
      currentSwipe.value = null
      return
    }
    // changedTouches 在 touchend 中才有最终位置
    const t = (e.changedTouches && e.changedTouches[0]) || null
    if (!t) {
      currentSwipe.value = null
      return
    }
    const dx = t.clientX - startX
    const dy = t.clientY - startY
    const absDx = Math.abs(dx)
    const absDy = Math.abs(dy)

    let direction = null
    if (absDx > absDy && absDx > opts.threshold) {
      direction = dx < 0 ? 'left' : 'right'
    } else if (absDy > absDx && absDy > opts.threshold) {
      direction = dy < 0 ? 'up' : 'down'
    }

    if (direction && callbacks[direction]) {
      callbacks[direction].forEach((cb) => {
        try { cb() } catch (err) { console.error('[useSwipeGesture] callback error:', err) }
      })
    }
    // 短延迟清方向 (让 CSS transition 跑完)
    setTimeout(() => { currentSwipe.value = null }, 50)
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
    const el = typeof targetRef === 'function' ? targetRef() : targetRef.value
    if (el !== currentEl) {
      if (currentEl) detach(currentEl)
      currentEl = el
      if (el) attach(el)
    }
  })

  onBeforeUnmount(() => {
    if (currentEl) detach(currentEl)
    currentEl = null
  })

  return {
    onSwipeLeft: (cb) => callbacks.left.push(cb),
    onSwipeRight: (cb) => callbacks.right.push(cb),
    onSwipeUp: (cb) => callbacks.up.push(cb),
    onSwipeDown: (cb) => callbacks.down.push(cb),
    currentSwipe,
  }
}