/**
 * useKbMonitor.test.js — W2 T4 P2-C (2026-07-20) KB polling 30s timeout 防御
 *
 * 覆盖 (3 case):
 * 1. timeout 配置正确传给 axios.get (timeout: 30000)
 * 2. timeout 触发 (ECONNABORTED) → 进 catch + error 写入 + 保留旧 data (不闪烁)
 * 3. setInterval 启动 + onUnmounted 清理 (基本生命周期不变)
 *
 * 跟 W2 T2 useDriveFiles.integration.test.js 风格对齐 (jsdom + axios mock),
 * 不改 useKbMonitor.js 实现。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'

const mockAxiosGet = vi.fn()

vi.mock('axios', () => ({
  default: {
    get: (...args) => mockAxiosGet(...args),
  },
}))

import { useKbMonitor } from '../useKbMonitor'

describe('useKbMonitor (W2 T4 P2-C KB polling 30s timeout)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('axios.get 必须传 timeout: 30000 (后端 hang 防御)', async () => {
    mockAxiosGet.mockResolvedValueOnce({
      data: { today_intake: 0, weekly_intake: [0, 0, 0, 0, 0, 0, 0], hit_rate: 0, negative_feedback_rate: 0, rollback_warnings: [] },
    })
    const { refresh } = useKbMonitor()
    await refresh()

    expect(mockAxiosGet).toHaveBeenCalledTimes(1)
    const callArgs = mockAxiosGet.mock.calls[0]
    expect(callArgs[0]).toBe('/api/v1/knowledge/auto-intake-summary')
    expect(callArgs[1]).toMatchObject({ timeout: 30000 })
  })

  it('timeout 触发 (ECONNABORTED): 进 catch + error 写入 + 保留旧 data (不闪烁)', async () => {
    // 第一次成功 → 有 data
    mockAxiosGet.mockResolvedValueOnce({
      data: { today_intake: 5, weekly_intake: [1, 2, 3, 4, 5, 6, 5], hit_rate: 0.8, negative_feedback_rate: 0.1, rollback_warnings: [] },
    })
    const monitor = useKbMonitor()
    await monitor.refresh()
    expect(monitor.summary.value.today_intake).toBe(5)
    expect(monitor.error.value).toBeNull()

    // 第二次超时 → 进 catch, 旧 data 保留 (W5 T5.4 教训)
    const timeoutError = new Error('timeout of 30000ms exceeded')
    timeoutError.code = 'ECONNABORTED'
    mockAxiosGet.mockRejectedValueOnce(timeoutError)
    await monitor.refresh()

    expect(monitor.error.value).toContain('timeout of 30000ms exceeded')
    // 关键断言: 旧 data 保留, UI 不闪烁
    expect(monitor.summary.value.today_intake).toBe(5)
    expect(monitor.summary.value.hit_rate).toBe(0.8)
  })

  it('startPolling 启动 setInterval + stopPolling 清理 (基本生命周期不变)', async () => {
    mockAxiosGet.mockResolvedValue({
      data: { today_intake: 0, weekly_intake: [0, 0, 0, 0, 0, 0, 0], hit_rate: 0, negative_feedback_rate: 0, rollback_warnings: [] },
    })
    const monitor = useKbMonitor()

    // 显式调 startPolling (测试环境 onMounted 不触发)
    monitor.startPolling()
    // 等立即拉的 promise resolve
    await vi.advanceTimersByTimeAsync(0)
    await nextTick()
    expect(mockAxiosGet).toHaveBeenCalledTimes(1)

    // 推进 5min tick → 第 2 次 fetch
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000)
    expect(mockAxiosGet).toHaveBeenCalledTimes(2)

    // stopPolling 清理 → 后续不再触发
    monitor.stopPolling()
    await vi.advanceTimersByTimeAsync(10 * 60 * 1000)
    expect(mockAxiosGet).toHaveBeenCalledTimes(2)
  })
})
