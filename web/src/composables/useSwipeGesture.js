// useSwipeGesture.js — 触摸滑动识别 composable
// 2026-07-22  PR8 mobile 文件预览 swipe
//
// 设计:
// - 监听 touchstart/touchmove/touchend
// - 计算水平/垂直位移 + 总耗时
// - 阈值检测: 距离 > 50px 且 时间 < 300ms 才算 swipe
// - 返回 4 个方向回调 + currentSwipe 实时方向 ref
//
// 用法:
//   const { onSwipeLeft, onSwipeRight } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
//   onSwipeLeft(() => goNext())
//   onSwipeRight(() => goPrev())

import { ref, watchEffect, onBeforeUnmount } from 'vue'

const DEFAULT_OPTIONS = {
  threshold: 50,        // 位移阈值 (px), 低于此不算 swipe
  timeout: 300,         // 时间阈值 (ms), 超过此不算 swipe (避免长按后拖拽被误判)
}

/**
 * @param {import('vue').Ref<HTMLElement|null>|(() => HTMLElement|null)} targetRef - 绑定的 DOM ref
 * @param {{ threshold?: number, timeout?: number }} options
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

  function handleTouchStart(e) {
    if (!e.touches || e.touches.length === 0) return
    const t = e.touches[0]
    startX = t.clientX
    startY = t.clientY
    startTime = Date.now()
    active = true
    currentSwipe.value = null
  }

  function handleTouchMove(e) {
    if (!active) return
    const t = e.touches[0]
    const dx = t.clientX - startX
    const dy = t.clientY - startY
    // 实时更新方向供 UI 反馈 (光标/动画)
    if (Math.abs(dx) > Math.abs(dy)) {
      currentSwipe.value = dx < 0 ? 'left' : 'right'
    } else {
      currentSwipe.value = dy < 0 ? 'up' : 'down'
    }
  }

  function handleTouchEnd(e) {
    if (!active) return
    active = false
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