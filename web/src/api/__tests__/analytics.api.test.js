import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockPost = vi.fn()
vi.mock('axios', () => ({
  default: { post: (...args) => mockPost(...args) },
}))

import { recordSearchEvent } from '../analytics'

describe('recordSearchEvent', () => {
  beforeEach(() => vi.clearAllMocks())

  it('422 埋点失败静默返回 null', async () => {
    mockPost.mockRejectedValueOnce({ response: { status: 422 } })

    await expect(recordSearchEvent({ query: '气泡', top_ids: [1] })).resolves.toBeNull()
  })

  it('空 query 在前端拦截且不发送请求', async () => {
    await expect(recordSearchEvent({ query: '  ', top_ids: [1] })).resolves.toBeNull()
    expect(mockPost).not.toHaveBeenCalled()
  })
})
