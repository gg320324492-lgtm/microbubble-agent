// useSwipeGesture.test.js — 触摸滑动识别 composable 单元测试
// 2026-07-22  PR8 mobile 文件预览 swipe

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useSwipeGesture } from '../useSwipeGesture'

/**
 * 构造一个含 touches/changedTouches 的 TouchEvent-like Event
 * @param {string} type - 'touchstart' | 'touchmove' | 'touchend'
 * @param {Array<{x:number,y:number}>} touches - 当前触摸点列表
 */
function makeTouchEvent(type, touches) {
  const evt = new Event(type, { bubbles: true, cancelable: true })
  Object.defineProperty(evt, 'touches', { value: touches })
  Object.defineProperty(evt, 'targetTouches', { value: touches })
  Object.defineProperty(evt, 'changedTouches', { value: touches })
  return evt
}

function makeTouch(x, y) {
  return { clientX: x, clientY: y, identifier: 0 }
}

/**
 * 触发完整 swipe: touchstart → touchmove → touchend (elapsed 可控)
 *
 * 2026-10-01 修 flaky (原 "全量跑偶发红 / 单跑 3/3 过")。原实现只对 touchend 段
 * mock Date.now, touchstart/touchmove 段读的是**真时钟** → elapsed 可能是 0, 也可能 ≥1ms。
 * elapsed 一旦 ≥1 就进 W68 速度判定 (useSwipeGesture.js:100-120): 49px / 1ms = 49 px/ms
 * 远大于 velocity(0.3) → 提前触发 callback, "49px 不触发" 随机红。单跑时 elapsed 恰为 0
 * 侥幸躲开, 全量并发下必红。改为整段手势钉死时钟, 阈值判定/速度判定归谁由 elapsed 显式决定。
 */
function fireSwipe(el, { startX, startY, endX, endY, elapsed = 50 }) {
  const startTime = 1_000_000 // 固定基准, 避免依赖真实墙钟
  const nowSpy = vi.spyOn(Date, 'now')
  nowSpy.mockReturnValue(startTime)            // touchstart
  el.dispatchEvent(makeTouchEvent('touchstart', [makeTouch(startX, startY)]))

  nowSpy.mockReturnValue(startTime + elapsed) // touchmove (速度判定在这里)
  el.dispatchEvent(makeTouchEvent('touchmove', [makeTouch(endX, endY)]))

  nowSpy.mockReturnValue(startTime + elapsed) // touchend (阈值/超时判定在这里)
  el.dispatchEvent(makeTouchEvent('touchend', [makeTouch(endX, endY)]))

  nowSpy.mockRestore()
}

describe('useSwipeGesture', () => {
  let container
  let elementRef

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    elementRef = ref(container)
  })

  // composable 的监听挂在 DOM 上而非组件生命周期内, 容器必须逐例摘掉, 否则残留到后续用例
  afterEach(() => {
    container.remove()
    vi.restoreAllMocks()
  })

  it('向左 swipe (dx < 0, |dx| > threshold) 触发 onSwipeLeft 回调', async () => {
    const { onSwipeLeft } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cb = vi.fn()
    onSwipeLeft(cb)
    await nextTick()

    fireSwipe(container, { startX: 200, startY: 100, endX: 100, endY: 100 }) // dx = -100
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('向右 swipe (dx > 0, |dx| > threshold) 触发 onSwipeRight 回调', async () => {
    const { onSwipeRight } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cb = vi.fn()
    onSwipeRight(cb)
    await nextTick()

    fireSwipe(container, { startX: 100, startY: 100, endX: 200, endY: 100 }) // dx = +100
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('向上 swipe 触发 onSwipeUp 回调', async () => {
    const { onSwipeUp } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cb = vi.fn()
    onSwipeUp(cb)
    await nextTick()

    fireSwipe(container, { startX: 100, startY: 200, endX: 100, endY: 100 }) // dy = -100
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('向下 swipe 触发 onSwipeDown 回调', async () => {
    const { onSwipeDown } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cb = vi.fn()
    onSwipeDown(cb)
    await nextTick()

    fireSwipe(container, { startX: 100, startY: 100, endX: 100, endY: 200 }) // dy = +100
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('边界: 位移 49px 不触发 (低于 threshold 50px)', async () => {
    const { onSwipeLeft, onSwipeRight } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cbL = vi.fn()
    const cbR = vi.fn()
    onSwipeLeft(cbL)
    onSwipeRight(cbR)
    await nextTick()

    // 必须同时慢到不过速度判定: 49px / 200ms = 0.245 px/ms < velocity(0.3),
    // 且 200ms <= timeout(300) 让 touchend 走到阈值分支 → 只有 threshold 挡得住
    fireSwipe(container, { startX: 100, startY: 100, endX: 51, endY: 100, elapsed: 200 })  // dx = -49
    fireSwipe(container, { startX: 51, startY: 100, endX: 100, endY: 100, elapsed: 200 })  // dx = +49
    expect(cbL).not.toHaveBeenCalled()
    expect(cbR).not.toHaveBeenCalled()
  })

  it('W68 速度判定: 位移不足 threshold 但够快 (> velocity 0.3 px/ms) 照样触发', async () => {
    const { onSwipeLeft } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cb = vi.fn()
    onSwipeLeft(cb)
    await nextTick()

    // 49px / 50ms = 0.98 px/ms > 0.3 → touchmove 阶段就触发 (设计上就是如此, 不是回归)
    fireSwipe(container, { startX: 100, startY: 100, endX: 51, endY: 100, elapsed: 50 })
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('边界: 位移 51px 触发 (刚好高于 threshold)', async () => {
    const { onSwipeLeft } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cb = vi.fn()
    onSwipeLeft(cb)
    await nextTick()

    fireSwipe(container, { startX: 100, startY: 100, endX: 49, endY: 100 }) // dx = -51
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('时间边界: elapsed > 300ms 不触发 (timeout 超时)', async () => {
    const { onSwipeLeft } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cb = vi.fn()
    onSwipeLeft(cb)
    await nextTick()

    fireSwipe(container, { startX: 200, startY: 100, endX: 100, endY: 100, elapsed: 400 })
    expect(cb).not.toHaveBeenCalled()
  })

  it('时间边界: elapsed = 200ms 触发 (低于 timeout)', async () => {
    const { onSwipeLeft } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cb = vi.fn()
    onSwipeLeft(cb)
    await nextTick()

    fireSwipe(container, { startX: 200, startY: 100, endX: 100, endY: 100, elapsed: 200 })
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('currentSwipe ref 在 touchmove 期间实时更新方向', async () => {
    const { currentSwipe } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    await nextTick()

    container.dispatchEvent(makeTouchEvent('touchstart', [makeTouch(100, 100)]))
    container.dispatchEvent(makeTouchEvent('touchmove', [makeTouch(150, 100)])) // 向右
    await nextTick()
    expect(currentSwipe.value).toBe('right')

    container.dispatchEvent(makeTouchEvent('touchmove', [makeTouch(100, 150)])) // 向下
    await nextTick()
    expect(currentSwipe.value).toBe('down')
  })

  it('对角线 swipe: 水平方向占优时触发左右 swipe, 不触发上下', async () => {
    const { onSwipeLeft, onSwipeUp } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cbL = vi.fn()
    const cbU = vi.fn()
    onSwipeLeft(cbL)
    onSwipeUp(cbU)
    await nextTick()

    // dx = -100, dy = +20 → 水平方向占优 → 触发 left
    fireSwipe(container, { startX: 200, startY: 100, endX: 100, endY: 120 })
    expect(cbL).toHaveBeenCalledTimes(1)
    expect(cbU).not.toHaveBeenCalled()
  })

  it('多回调注册: onSwipeLeft 注册 2 个, 触发时 2 个都跑', async () => {
    const { onSwipeLeft } = useSwipeGesture(elementRef, { threshold: 50, timeout: 300 })
    const cb1 = vi.fn()
    const cb2 = vi.fn()
    onSwipeLeft(cb1)
    onSwipeLeft(cb2)
    await nextTick()

    fireSwipe(container, { startX: 200, startY: 100, endX: 100, endY: 100 })
    expect(cb1).toHaveBeenCalledTimes(1)
    expect(cb2).toHaveBeenCalledTimes(1)
  })
})