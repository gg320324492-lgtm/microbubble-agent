/**
 * useNow.test.js — 墙钟单一入口 composable 单测
 *
 * 覆盖 (7 case):
 * 1. 缺省参数 (不传 clock) 落回真实墙钟, 返回值落在调用前后区间内 (不钉死时刻)
 * 2. 注入固定 clock → now.value 精确等于该时刻
 * 3. intervalMs = 0 → 不起定时器 (vi.getTimerCount() === 0)
 * 4. intervalMs > 0 → fake timer 推进后 now.value 更新为新时刻
 * 5. tick() 手动刷新能更新值 (不依赖定时器)
 * 6. 组件卸载 → onUnmounted 清 timer (vi.getTimerCount() 1 → 0, clearInterval 被调用)
 * 7. 卸载后再推进时间不再更新 (timer 真的没了, 不是空转)
 *
 * 风格对齐 useKbMonitor.test.js / useSearchLogs.test.js:
 * vitest + jsdom, beforeEach 开 fake timers, afterEach 还原,
 * mock 写在 import 被测模块之前。
 *
 * 生命周期说明: composable 在 setup 外被调用时 onUnmounted 不触发 ——
 * case 1-5/7 因此直接调返回的 tick() (同 useKbMonitor.test.js 调 refresh() 的做法),
 * 只有 case 6 用 mount 挂真组件证明 onUnmounted 真的注册上了。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

import { useNow } from '../useNow'

const FIXED_ISO = '2026-10-05T10:00:00'
const fixedClock = () => new Date(FIXED_ISO)

describe('useNow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('1. 缺省参数 (不传 clock) 落回真实墙钟, 不钉死具体时刻', () => {
    // 本 case 要验证"真墙钟", 必须先摘掉 fake timers
    vi.useRealTimers()
    const before = Date.now()
    const { now } = useNow()
    const after = Date.now()

    expect(now.value).toBeInstanceOf(Date)
    expect(now.value.getTime()).toBeGreaterThanOrEqual(before)
    expect(now.value.getTime()).toBeLessThanOrEqual(after)
  })

  it('2. 注入固定 clock → now.value 精确等于该时刻', () => {
    const { now } = useNow(0, fixedClock)

    expect(now.value).toBeInstanceOf(Date)
    expect(now.value.toISOString()).toBe(new Date(FIXED_ISO).toISOString())
    expect(now.value.getTime()).toBe(new Date(FIXED_ISO).getTime())
  })

  it('3. intervalMs = 0 → 不起任何定时器', () => {
    expect(vi.getTimerCount()).toBe(0)
    const { now } = useNow(0, fixedClock)
    expect(vi.getTimerCount()).toBe(0)

    // 推进很久也不该有任何变化
    vi.advanceTimersByTime(60 * 60 * 1000)
    expect(now.value.getTime()).toBe(new Date(FIXED_ISO).getTime())
  })

  it('4. intervalMs > 0 → fake timer 推进后 now.value 更新为新时刻', () => {
    // fake timers 下 new Date() 跟随系统时间, 故固定 clock 用 new Date() 跟随推进
    vi.setSystemTime(new Date(FIXED_ISO))
    const { now } = useNow(1000, () => new Date())

    expect(now.value.getTime()).toBe(new Date(FIXED_ISO).getTime())

    vi.advanceTimersByTime(5000)  // 5 个 tick
    expect(now.value.getTime()).toBe(new Date(FIXED_ISO).getTime() + 5000)
  })

  it('5. tick() 手动刷新能更新值 (不起定时器也可用)', () => {
    let current = new Date('2026-10-05T10:00:00')
    const { now, tick } = useNow(0, () => new Date(current))

    expect(now.value.getTime()).toBe(current.getTime())

    current = new Date('2026-10-05T23:59:59')
    expect(now.value.getTime()).toBe(new Date('2026-10-05T10:00:00').getTime())  // tick 前没变

    tick()
    expect(now.value.getTime()).toBe(new Date('2026-10-05T23:59:59').getTime())
  })

  it('6. 组件卸载 → onUnmounted 清 timer (clearInterval 被调用, timer 归零)', () => {
    const clearSpy = vi.spyOn(globalThis, 'clearInterval')

    const Host = defineComponent({
      setup() {
        useNow(1000, () => new Date())
        return () => h('div')
      },
    })

    const wrapper = mount(Host)
    expect(vi.getTimerCount()).toBe(1)   // timer 确实起来了

    wrapper.unmount()
    expect(clearSpy).toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)   // 真的清掉了

    clearSpy.mockRestore()
  })

  it('7. 卸载后推进时间不再更新 (timer 真清, 非空转)', () => {
    vi.setSystemTime(new Date(FIXED_ISO))
    let captured = null

    const Host = defineComponent({
      setup() {
        const { now } = useNow(1000, () => new Date())
        captured = now
        return () => h('div')
      },
    })

    const wrapper = mount(Host)
    vi.advanceTimersByTime(2000)
    const afterTick = captured.value.getTime()
    expect(afterTick).toBe(new Date(FIXED_ISO).getTime() + 2000)

    wrapper.unmount()
    vi.advanceTimersByTime(10 * 60 * 1000)   // 卸载后再推进 10min
    expect(captured.value.getTime()).toBe(afterTick)  // 值冻结, timer 已清
  })
})