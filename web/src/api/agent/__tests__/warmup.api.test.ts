/**
 * warmup.api.test.ts — 聊天模型预热调用 (2026-09-18 冷加载防御)
 *
 * 覆盖:
 * - 必须发 POST /api/v1/chat/warmup 且带 Bearer token
 * - 每次页面加载只发一次 (模块级去重)
 * - fetch 失败静默 (永不 throw)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

import { warmupChatModel, resetWarmupForTest } from '../warmup'

describe('warmupChatModel (冷加载防御)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetWarmupForTest()
    localStorage.setItem('access_token', 'tok-123')
    mockFetch.mockResolvedValue({ ok: true, status: 200 })
  })

  it('发 POST /api/v1/chat/warmup 并带 Authorization', async () => {
    await warmupChatModel()

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const [url, init] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/v1/chat/warmup')
    expect(init.method).toBe('POST')
    expect(init.headers.Authorization).toBe('Bearer tok-123')
  })

  it('同一次页面加载去重: 第二次调用不再发请求', async () => {
    await warmupChatModel()
    await warmupChatModel()
    await warmupChatModel()

    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it('未登录 (无 token) 也照发, 只是不带 Authorization', async () => {
    localStorage.removeItem('access_token')
    await warmupChatModel()

    const [, init] = mockFetch.mock.calls[0]
    expect(init.headers.Authorization).toBeUndefined()
  })

  it('fetch 网络失败静默, 永不 throw', async () => {
    mockFetch.mockRejectedValue(new TypeError('network error'))

    await expect(warmupChatModel()).resolves.toBeUndefined()

    // 失败同样消耗去重标记: 本次页面加载不再重试 (下个测试复位后可再发)
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })
})
