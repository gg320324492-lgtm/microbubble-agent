import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useLongPress } from '../useLongPress.js'

describe('useLongPress - keyboard accessibility (W68 v3.r4)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it('600ms delay 触发长按回调（touch）', () => {
    const onLongPress = vi.fn()
    const { bind, isPressing } = useLongPress(600, onLongPress)

    const fakeEvent = { touches: [{ clientX: 100, clientY: 100 }] }
    bind.onTouchstart(fakeEvent)
    expect(isPressing.value).toBe(true)

    vi.advanceTimersByTime(599)
    expect(onLongPress).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1)
    expect(onLongPress).toHaveBeenCalledTimes(1)
    expect(onLongPress.mock.calls[0][0].source).toBe('touch')
  })

  it('keyboardHoldDelay (默认 1000ms) 触发键盘长按', () => {
    const onLongPress = vi.fn()
    const { bind, isPressing } = useLongPress(600, onLongPress, { keyboardHoldDelay: 1000 })

    const el = document.createElement('div')
    el.getBoundingClientRect = () => ({ left: 50, top: 50, right: 150, bottom: 100, width: 100, height: 50, x: 50, y: 50 })
    const keyEvent = { code: 'Space', currentTarget: el, target: el, preventDefault: vi.fn() }
    bind.onKeydown(keyEvent)
    expect(isPressing.value).toBe(true)

    vi.advanceTimersByTime(999)
    expect(onLongPress).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1)
    expect(onLongPress).toHaveBeenCalledTimes(1)
    expect(onLongPress.mock.calls[0][0].source).toBe('keyboard')
    expect(onLongPress.mock.calls[0][0].clientX).toBe(100)
    expect(onLongPress.mock.calls[0][0].clientY).toBe(75)
  })

  it('Enter 键也支持长按', () => {
    const onLongPress = vi.fn()
    const { bind } = useLongPress(600, onLongPress, { keyboardHoldDelay: 1000 })

    const el = document.createElement('div')
    el.getBoundingClientRect = () => ({ left: 0, top: 0, right: 10, bottom: 10, width: 10, height: 10, x: 0, y: 0 })
    bind.onKeydown({ code: 'Enter', currentTarget: el, target: el, preventDefault: vi.fn() })

    vi.advanceTimersByTime(1000)
    expect(onLongPress).toHaveBeenCalledTimes(1)
    expect(onLongPress.mock.calls[0][0].source).toBe('keyboard')
  })

  it('非 Space/Enter 键不触发长按', () => {
    const onLongPress = vi.fn()
    const { bind } = useLongPress(600, onLongPress)

    bind.onKeydown({ code: 'KeyA', preventDefault: vi.fn() })
    vi.advanceTimersByTime(2000)
    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('键盘 keyup 提前取消', () => {
    const onLongPress = vi.fn()
    const { bind, isPressing } = useLongPress(600, onLongPress, { keyboardHoldDelay: 1000 })

    const el = document.createElement('div')
    el.getBoundingClientRect = () => ({ left: 0, top: 0, right: 10, bottom: 10, width: 10, height: 10, x: 0, y: 0 })
    bind.onKeydown({ code: 'Space', currentTarget: el, target: el, preventDefault: vi.fn() })
    expect(isPressing.value).toBe(true)

    vi.advanceTimersByTime(500)
    bind.onKeyup({ code: 'Space' })
    expect(isPressing.value).toBe(false)

    vi.advanceTimersByTime(1000)
    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('移动 >10px 取消长按（moveThreshold）', () => {
    const onLongPress = vi.fn()
    const { bind, isPressing } = useLongPress(600, onLongPress)

    bind.onTouchstart({ touches: [{ clientX: 100, clientY: 100 }] })
    expect(isPressing.value).toBe(true)

    bind.onTouchmove({ touches: [{ clientX: 115, clientY: 100 }] }) // 移动 15px > 10
    expect(isPressing.value).toBe(false)

    vi.advanceTimersByTime(700)
    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('touch 触发不依赖 navigator.vibrate 抛错', () => {
    const original = navigator.vibrate
    Object.defineProperty(navigator, 'vibrate', { value: () => { throw new Error('test') }, configurable: true })

    const onLongPress = vi.fn()
    const { bind } = useLongPress(600, onLongPress)

    bind.onTouchstart({ touches: [{ clientX: 0, clientY: 0 }] })
    vi.advanceTimersByTime(600)
    expect(onLongPress).toHaveBeenCalledTimes(1)

    if (original === undefined) {
      // 还原
    } else {
      Object.defineProperty(navigator, 'vibrate', { value: original, configurable: true })
    }
  })

  it('cancel() 主动清除计时器', () => {
    const onLongPress = vi.fn()
    const { bind, cancel, isPressing } = useLongPress(600, onLongPress)

    bind.onTouchstart({ touches: [{ clientX: 0, clientY: 0 }] })
    cancel()
    expect(isPressing.value).toBe(false)

    vi.advanceTimersByTime(700)
    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('pressPoint 返回触发坐标', () => {
    const onLongPress = vi.fn()
    const { bind, pressPoint } = useLongPress(600, onLongPress)
    bind.onTouchstart({ touches: [{ clientX: 250, clientY: 350 }] })
    expect(pressPoint.value).toEqual({ x: 250, y: 350, source: 'touch' })
  })
})