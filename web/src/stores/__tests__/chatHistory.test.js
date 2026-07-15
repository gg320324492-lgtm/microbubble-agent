import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

/**
 * #043 Phase 8 — useChatHistoryStore Pinia 单元测试
 *
 * 关键铁律（CLAUDE.md 2026-06-15 持久化必须 best-effort）：
 * - 失败不抛，返回 null/默认值
 * - search/share/export 3 actions 写入对应 state
 * - reset 清空所有 state
 */

const mockChatHistoryApi = {
  listSessions: vi.fn(),
  appendMessage: vi.fn(),
  createSession: vi.fn(),
  listMessages: vi.fn(),
  deleteSession: vi.fn(),
  updateSession: vi.fn(),
  searchSessions: vi.fn(),
  createShare: vi.fn(),
  exportSession: vi.fn(),
  syncFromLocal: vi.fn(),
  getPublicShare: vi.fn(),
}

vi.mock('@/api/chatHistory', () => ({ chatHistoryApi: mockChatHistoryApi }))

describe('useChatHistoryStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('loadFromServer', () => {
    it('成功 → 写入 serverSessions + syncStatus=success', async () => {
      const fakeSessions = [
        { id: 's1', title: '会话1', user_id: 1 },
        { id: 's2', title: '会话2', user_id: 1 },
      ]
      mockChatHistoryApi.listSessions.mockResolvedValue({
        items: fakeSessions,
        total: 2,
        page: 1,
        page_size: 50,
      })

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.loadFromServer()

      expect(result).toEqual(fakeSessions)
      expect(store.serverSessions).toEqual(fakeSessions)
      expect(store.syncStatus).toBe('success')
    })

    it('失败 → syncStatus=error + syncError 有值 + throw', async () => {
      mockChatHistoryApi.listSessions.mockRejectedValue(new Error('网络错误'))

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()

      await expect(store.loadFromServer()).rejects.toThrow('网络错误')
      expect(store.syncStatus).toBe('error')
      expect(store.syncError).toContain('网络错误')
    })
  })

  describe('appendMessageAsync', () => {
    it('成功 → 返回 { id }', async () => {
      mockChatHistoryApi.appendMessage.mockResolvedValue({ id: 42, content: 'test' })

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.appendMessageAsync('s1', { role: 'user', content: 'test' })

      expect(result).toEqual({ id: 42, content: 'test' })
    })

    it('失败 → 返回 null（best-effort 兜底）', async () => {
      mockChatHistoryApi.appendMessage.mockRejectedValue(new Error('网络错误'))

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.appendMessageAsync('s1', { role: 'user', content: 'test' })

      expect(result).toBeNull()
    })

    // 2026-07-15 P2-#chatHistory-appendMessage-404 修复回归保护
    it('404 时自动 createServerSession + 重试一次 (本地新 session race 兜底)', async () => {
      const err404 = Object.assign(new Error('Request failed with status code 404'), {
        response: { status: 404, data: { detail: '会话不存在或已删除' } },
      })
      // 第一次 appendMessage → 404
      // 第二次 appendMessage (重试) → 成功
      mockChatHistoryApi.appendMessage
        .mockRejectedValueOnce(err404)
        .mockResolvedValueOnce({ id: 99, content: 'recovered' })
      mockChatHistoryApi.createSession.mockResolvedValue({ id: 'user_1782916607641_ddzr', user_id: 1 })

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.appendMessageAsync('user_1782916607641_ddzr', {
        role: 'user',
        content: 'first user msg',
      })

      // 验证: 第一次 404 → 自动 createServerSession 用 clientSessionId 复用 → 第二次重试成功
      expect(mockChatHistoryApi.createSession).toHaveBeenCalledWith({
        client_session_id: 'user_1782916607641_ddzr',
        first_message: 'first user msg',
      })
      expect(mockChatHistoryApi.appendMessage).toHaveBeenCalledTimes(2)
      expect(result).toEqual({ id: 99, content: 'recovered' })
    })

    it('404 + createSession 也失败 → 返回 null 不死循环', async () => {
      const err404 = Object.assign(new Error('404'), { response: { status: 404 } })
      mockChatHistoryApi.appendMessage.mockRejectedValue(err404)  // 永远 404
      mockChatHistoryApi.createSession.mockRejectedValue(new Error('session create failed'))

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.appendMessageAsync('sid_x', { role: 'user', content: 'x' })

      // createSession 失败 → 不再 appendMessage 重试 (避免死循环) → 返回 null
      expect(mockChatHistoryApi.appendMessage).toHaveBeenCalledTimes(1)
      expect(result).toBeNull()
    })

    it('timeout (无 response.status) 不触发 404 重试 (避免不确定状态重复写)', async () => {
      // axios timeout 错误: e.response === undefined
      const errTimeout = new Error('timeout of 10000ms exceeded')
      mockChatHistoryApi.appendMessage.mockRejectedValue(errTimeout)

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.appendMessageAsync('sid_timeout', { role: 'user', content: 'x' })

      // timeout 不是 404, 不重试, 直接返回 null (best-effort)
      expect(mockChatHistoryApi.createSession).not.toHaveBeenCalled()
      expect(mockChatHistoryApi.appendMessage).toHaveBeenCalledTimes(1)
      expect(result).toBeNull()
    })

    it('500 server error 不触发 404 重试', async () => {
      const err500 = Object.assign(new Error('500'), { response: { status: 500 } })
      mockChatHistoryApi.appendMessage.mockRejectedValue(err500)

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.appendMessageAsync('sid_500', { role: 'user', content: 'x' })

      expect(mockChatHistoryApi.createSession).not.toHaveBeenCalled()
      expect(result).toBeNull()
    })
  })

  describe('createShareLink', () => {
    it('成功 → 写入 shareToken', async () => {
      mockChatHistoryApi.createShare.mockResolvedValue({
        id: 'share_abc',
        share_url: 'https://agent.mnb-lab.cn/chat/shares/share_abc',
        permission: 'read',
        expires_at: '2026-07-30T00:00:00Z',
      })

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.createShareLink('s1', { permission: 'read', expiresHours: 720 })

      expect(result.share_url).toContain('share_abc')
      expect(store.shareToken).toBe('https://agent.mnb-lab.cn/chat/shares/share_abc')
    })

    it('失败 → 返回 null', async () => {
      mockChatHistoryApi.createShare.mockRejectedValue(new Error('创建失败'))

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.createShareLink('s1')

      expect(result).toBeNull()
    })
  })

  describe('exportToFile', () => {
    it('成功 → 写入 exportBlob', async () => {
      const fakeBlob = new Blob(['# Title\n'], { type: 'text/markdown' })
      mockChatHistoryApi.exportSession.mockResolvedValue(fakeBlob)

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.exportToFile('s1', { format: 'md' })

      expect(result).toBe(fakeBlob)
      expect(store.exportBlob).toBe(fakeBlob)
    })

    it('失败 → 返回 null', async () => {
      mockChatHistoryApi.exportSession.mockRejectedValue(new Error('导出失败'))

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.exportToFile('s1')

      expect(result).toBeNull()
    })
  })

  describe('searchSessions', () => {
    it('成功 → 写入 searchResults', async () => {
      const fakeResult = {
        items: [
          { session_id: 's1', message_id: 1, snippet: 'zeta 电位...', session_title: 'S1', role: 'user' },
        ],
        total: 1,
        page: 1,
      }
      mockChatHistoryApi.searchSessions.mockResolvedValue(fakeResult)

      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.searchSessions('zeta')

      expect(result).toEqual(fakeResult)
      expect(store.searchResults.items).toHaveLength(1)
      expect(store.searchResults.items[0].session_id).toBe('s1')
    })

    it('查询 < 2 字符 → 返回空结果不调 API', async () => {
      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()
      const result = await store.searchSessions('z')

      expect(result).toEqual({ items: [], total: 0, page: 1 })
      expect(mockChatHistoryApi.searchSessions).not.toHaveBeenCalled()
    })
  })

  describe('reset', () => {
    it('清空所有 state', async () => {
      const { useChatHistoryStore } = await import('../chatHistory')
      const store = useChatHistoryStore()

      // 先填值
      store.serverSessions = [{ id: 's1' }]
      store.searchResults = { items: [{ x: 1 }], total: 1, page: 1 }
      store.shareToken = 'token_x'
      store.exportBlob = new Blob(['x'])

      store.reset()

      expect(store.serverSessions).toEqual([])
      expect(store.searchResults).toEqual({ items: [], total: 0, page: 1 })
      expect(store.shareToken).toBeNull()
      expect(store.exportBlob).toBeNull()
    })
  })
})
