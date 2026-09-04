/**
 * debounce.test.js — ②-5 搜索接线配套 (批次② 新增)
 * 覆盖: trailing 只保留最后一次 / 未到 wait 不触发 / cancel 阻止触发
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { debounce } from '@/utils/debounce'

describe('utils/debounce', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('300ms 内连续调用只执行最后一次 (trailing)', () => {
    const fn = vi.fn()
    const d = debounce(fn, 300)
    d('a')
    d('ab')
    d('abc')
    expect(fn).not.toHaveBeenCalled()
    vi.advanceTimersByTime(299)
    expect(fn).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(fn).toHaveBeenCalledTimes(1)
    expect(fn).toHaveBeenCalledWith('abc')
  })

  it('两次间隔超过 wait 的调用各自触发', () => {
    const fn = vi.fn()
    const d = debounce(fn, 300)
    d(1)
    vi.advanceTimersByTime(300)
    d(2)
    vi.advanceTimersByTime(300)
    expect(fn).toHaveBeenCalledTimes(2)
    expect(fn).toHaveBeenNthCalledWith(1, 1)
    expect(fn).toHaveBeenNthCalledWith(2, 2)
  })

  it('cancel() 阻止未触发的调用', () => {
    const fn = vi.fn()
    const d = debounce(fn, 300)
    d('x')
    d.cancel()
    vi.advanceTimersByTime(1000)
    expect(fn).not.toHaveBeenCalled()
  })
})
