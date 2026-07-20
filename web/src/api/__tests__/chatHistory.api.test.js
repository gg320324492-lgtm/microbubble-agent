/**
 * chatHistory.api.test.js — W2 T4 P2-C (2026-07-20) chatHistory api listMessages 30s timeout
 *
 * 覆盖 (1 case):
 * - listMessages axios.get 必须传 timeout: 30000 (跟 syncFromLocal { timeout: 30000 } 一致)
 *
 * 跟 W2 T2 useDriveFiles.integration.test.js 风格对齐 (jsdom + axios mock),
 * 不改 chatHistory.js 实现。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockAxiosGet = vi.fn()
const mockAxiosPost = vi.fn()

vi.mock('axios', () => ({
  default: {
    get: (...args) => mockAxiosGet(...args),
    post: (...args) => mockAxiosPost(...args),
  },
}))

import { listMessages } from '../chatHistory'

describe('chatHistory api (W2 T4 P2-C listMessages 30s timeout)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAxiosGet.mockResolvedValue({ data: { items: [], has_more: false } })
  })

  it('listMessages 必须传 timeout: 30000 (后端慢响应防御)', async () => {
    await listMessages('test-sid', { page: 1, pageSize: 100, afterId: 0 })

    expect(mockAxiosGet).toHaveBeenCalledTimes(1)
    const [url, config] = mockAxiosGet.mock.calls[0]
    expect(url).toContain('/api/v1/chat/sessions/test-sid/messages')
    expect(config).toMatchObject({
      params: { page: 1, page_size: 100, after_id: 0 },
      timeout: 30000,
    })
  })
})
