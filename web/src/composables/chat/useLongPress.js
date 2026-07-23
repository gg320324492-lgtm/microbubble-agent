/**
 * useLongPress.js — 长按手势（纯 touchstart/touchend + 键盘 hold，零第三方依赖）
 *
 * W68 第 1 批路线 C (Agent 4): Mobile 长按菜单 v3.r4
 *
 * 设计：
 * - 600ms 触发长按（delay 可配）
 * - 移动 >10px 取消（moveThreshold 可配）
 * - 触觉反馈 navigator.vibrate(10)（CLAUDE.md 2026-06-27 教训：mobile long-press 必带 vibrate）
 * - 键盘支持：Space / Enter 长按 1s 触发（accessibility，长按菜单需键盘可达）
 * - 返回 bind 事件 + isPressing ref + 长按坐标 clientX/clientY（供 Menu 定位）
 *
 * 用法：
 *   const { bind, isPressing, pressPoint } = useLongPress(600, (event) => {
 *     // 长按回调，event.detail 含 clientX/clientY/touchOrKey
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
    keyboardHoldDelay = 1000, // 键盘 Space/Enter 长按触发阈值
    enabled = true,  // 总开关（外部 disabled 场景）
  } = options

  const isPressing = ref(false)
  /** 触发长按的位置（touch / key 客户端坐标），供 Menu 弹出定位 */
  const pressPoint = ref({ x: 0, y: 0, source: null })

  let timer = null
  let startX = 0
  let startY = 0
  let triggered = false
  let activeKeyboard = false // 当前是否处于键盘 hold 状态
  let keyboardRepeatTimer = null

  function _triggerLongPress(source) {
    triggered = true
    // 触觉反馈（CLAUDE.md 2026-06-27 教训：mobile long-press 必带 vibrate）
    if (source !== 'keyboard' && typeof navigator !== 'undefined' && navigator.vibrate) {
      try { navigator.vibrate(10) } catch { /* iOS Safari 安全错误 */ }
    }
    onLongPress?.({
      clientX: pressPoint.value.x,
      clientY: pressPoint.value.y,
      source, // 'touch' | 'keyboard'
    })
  }

  function _cancelTimer() {
    if (timer) { clearTimeout(timer); timer = null }
  }

  function _cancelKeyboard() {
    if (keyboardRepeatTimer) { clearTimeout(keyboardRepeatTimer); keyboardRepeatTimer = null }
    activeKeyboard = false
  }

  // =================== Touch handlers ===================
  function onTouchStart(e) {
    if (!enabled) return
    if (!e.touches || e.touches.length !== 1) return
    _cancelKeyboard()
    isPressing.value = true
    triggered = false
    startX = e.touches[0].clientX
    startY = e.touches[0].clientY
    pressPoint.value = { x: startX, y: startY, source: 'touch' }
    onPressStart?.(e)

    _cancelTimer()
    timer = setTimeout(() => _triggerLongPress('touch'), delay)
  }

  function onTouchMove(e) {
    if (!enabled) return
    if (!isPressing.value || triggered) return
    if (!e.touches || e.touches.length === 0) return
    const dx = Math.abs(e.touches[0].clientX - startX)
    const dy = Math.abs(e.touches[0].clientY - startY)
    // 移动超过阈值 → 取消长按
    if (dx > moveThreshold || dy > moveThreshold) {
      _cancelTimer()
      isPressing.value = false
    }
  }

  function onTouchEnd(e) {
    if (!enabled) return
    _cancelTimer()
    isPressing.value = false
    onPressEnd?.(e, triggered)
  }

  function onTouchCancel() {
    _cancelTimer()
    isPressing.value = false
  }

  // =================== Keyboard handlers ===================
  // 长按 Space / Enter 触发（accessibility — 长按菜单需键盘可达）
  // 实现：keydown 后启动 hold 计时，按住不松手 1s 后触发；keyup 立即清除
  function _isLongPressKey(code) {
    return code === 'Space' || code === 'Enter'
  }

  function onKeyDown(e) {
    if (!enabled) return
    if (activeKeyboard) return // 已经在 hold 中（避免按键重复触发）
    if (!_isLongPressKey(e.code)) return
    // 单击行为留给 click：长按需区分；这里要求 keydown 持续 1s 才触发
    e.preventDefault()
    activeKeyboard = true
    triggered = false
    isPressing.value = true
    // 用元素中心作为键盘触发的坐标（Menu 默认底部弹出）
    try {
      const el = e.currentTarget || e.target
      if (el && el.getBoundingClientRect) {
        const rect = el.getBoundingClientRect()
        pressPoint.value = {
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
          source: 'keyboard',
        }
      }
    } catch { /* ignore */ }
    onPressStart?.(e)

    keyboardRepeatTimer = setTimeout(() => {
      if (activeKeyboard) {
        _triggerLongPress('keyboard')
      }
    }, keyboardHoldDelay)
  }

  function onKeyUp(e) {
    if (!enabled) return
    if (!_isLongPressKey(e.code)) return
    _cancelKeyboard()
    isPressing.value = false
    onPressEnd?.(e, triggered)
  }

  /**
   * 主动取消长按（外部场景：菜单关闭时复位）
   */
  function cancel() {
    _cancelTimer()
    _cancelKeyboard()
    isPressing.value = false
    triggered = false
  }

  const bind = {
    onTouchstart: onTouchStart,
    onTouchmove: onTouchMove,
    onTouchend: onTouchEnd,
    onTouchcancel: onTouchCancel,
    onKeydown: onKeyDown,
    onKeyup: onKeyUp,
  }

  return { bind, isPressing, pressPoint, cancel }
}

export default useLongPress