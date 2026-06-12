/**
 * useLongPress.js — 长按手势（纯 touchstart/touchend，无第三方依赖）
 *
 * PR #3: MobileChatView 消息气泡 600ms 长按弹出 ActionSheet（复制/删除）
 *
 * 用法：
 *   const { bind, isPressing } = useLongPress(600, (event) => {
 *     // 长按回调
 *   })
 *
 *   <div v-bind="bind">长按我</div>
 */

import { ref } from 'vue'

export function useLongPress(delay = 600, onLongPress, options = {}) {
  const {
    onPressStart,    // 短按开始（可选）
    onPressEnd,      // 短按结束（可选）
    moveThreshold = 10, // 移动超过 px 视为取消
  } = options

  const isPressing = ref(false)
  let timer = null
  let startX = 0
  let startY = 0
  let triggered = false

  function onTouchStart(e) {
    if (e.touches.length !== 1) return
    isPressing.value = true
    triggered = false
    startX = e.touches[0].clientX
    startY = e.touches[0].clientY
    onPressStart?.(e)

    timer = setTimeout(() => {
      triggered = true
      // 触觉反馈（如果可用）
      if (navigator.vibrate) {
        try { navigator.vibrate(10) } catch { /* ignore */ }
      }
      onLongPress?.(e)
    }, delay)
  }

  function onTouchMove(e) {
    if (!isPressing.value) return
    const dx = Math.abs(e.touches[0].clientX - startX)
    const dy = Math.abs(e.touches[0].clientY - startY)
    // 移动超过阈值 → 取消长按
    if (dx > moveThreshold || dy > moveThreshold) {
      clearTimeout(timer)
      timer = null
      isPressing.value = false
    }
  }

  function onTouchEnd(e) {
    clearTimeout(timer)
    timer = null
    isPressing.value = false
    onPressEnd?.(e, triggered)
  }

  function onTouchCancel() {
    clearTimeout(timer)
    timer = null
    isPressing.value = false
  }

  const bind = {
    onTouchstart: onTouchStart,
    onTouchmove: onTouchMove,
    onTouchend: onTouchEnd,
    onTouchcancel: onTouchCancel,
  }

  return { bind, isPressing }
}

export default useLongPress