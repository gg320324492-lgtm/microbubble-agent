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
