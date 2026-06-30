import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

/**
 * #043 Phase 8 — useChatMigration 单元测试
 *
 * 关键铁律（CLAUDE.md 2026-06-19 教训）：
 * - 幂等：chat_migrated_v1 标志 + server client_msg_id 双重保证
 * - 失败回退：迁移失败不设标志 → 下次启动重试
 * - 不阻塞：syncFromLocal 失败抛异常时返回 error 字段，不 throw
 */

// 在文件顶部 vi.mock 才能拦截模块顶层 import
const mockChatHistoryApi = {
  syncFromLocal: vi.fn(),
}

const mockChatSessionsStore = {
  sessions: [],
  mergeServerList: vi.fn(),
}

const mockChatHistoryStore = {
  serverSessions: [],
  loadFromServer: vi.fn(),
}

vi.mock('@/api/chatHistory', () => ({ chatHistoryApi: mockChatHistoryApi }))
vi.mock('@/stores/chatSessions', () => ({ useChatSessionsStore: () => mockChatSessionsStore }))
vi.mock('@/stores/chatHistory', () => ({ useChatHistoryStore: () => mockChatHistoryStore }))

const MIGRATION_FLAG_KEY = 'chat_migrated_v1'

describe('useChatMigration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    // 重置 mock 状态
    mockChatSessionsStore.sessions = []
    mockChatSessionsStore.mergeServerList.mockClear()
    mockChatHistoryStore.loadFromServer.mockClear()
    mockChatHistoryApi.syncFromLocal.mockReset()
    // 必须有 access_token 才能跑迁移
    localStorage.setItem('access_token', 'mock-jwt-token')
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('needsMigration 首次登录返回 true', async () => {
    const { useChatMigration } = await import('../useChatMigration')
    const { needsMigration } = useChatMigration()
    expect(needsMigration()).toBe(true)
  })

  it('needsMigration 已迁移后返回 false', async () => {
    localStorage.setItem(MIGRATION_FLAG_KEY, new Date().toISOString())
    const { useChatMigration } = await import('../useChatMigration')
    const { needsMigration } = useChatMigration()
    expect(needsMigration()).toBe(false)
  })

  it('migrateLocalToServer 0 个会话 → 标记已迁移', async () => {
    mockChatSessionsStore.sessions = []
    const { useChatMigration } = await import('../useChatMigration')
    const { migrateLocalToServer } = useChatMigration()

    const result = await migrateLocalToServer()

    expect(result).toEqual({ skipped: false, migrated: 0, reason: 'no_local_data' })
    expect(localStorage.getItem(MIGRATION_FLAG_KEY)).toBeTruthy()
    expect(mockChatHistoryApi.syncFromLocal).not.toHaveBeenCalled()
  })

  it('migrateLocalToServer 成功 → 标记已迁移 + refresh store', async () => {
    mockChatSessionsStore.sessions = [
      { id: 's1', title: '会话1', preview: '', is_pinned: false, is_archived: false, tags: [], createdAt: '2026-06-30T00:00:00Z', updatedAt: '2026-06-30T00:00:00Z' },
    ]
    localStorage.setItem('chat_msgs_s1', JSON.stringify([
      { role: 'user', content: 'hello', timestamp: '2026-06-30T00:00:00Z' },
    ]))
    mockChatHistoryApi.syncFromLocal.mockResolvedValue({
      ok: true,
      migrated_count: 1,
      conflicts: [],
    })

    const { useChatMigration } = await import('../useChatMigration')
    const { migrateLocalToServer } = useChatMigration()

    const result = await migrateLocalToServer()

    expect(result.skipped).toBe(false)
    expect(result.migrated).toBe(1)
    expect(localStorage.getItem(MIGRATION_FLAG_KEY)).toBeTruthy()
    expect(mockChatHistoryStore.loadFromServer).toHaveBeenCalled()
    expect(mockChatSessionsStore.mergeServerList).toHaveBeenCalled()
  })

  it('migrateLocalToServer 失败 → 不设标志（下次重试）', async () => {
    mockChatSessionsStore.sessions = [
      { id: 's1', title: '会话1', preview: '', is_pinned: false, is_archived: false, tags: [], createdAt: '2026-06-30T00:00:00Z', updatedAt: '2026-06-30T00:00:00Z' },
    ]
    mockChatHistoryApi.syncFromLocal.mockRejectedValue(new Error('网络错误'))

    const { useChatMigration } = await import('../useChatMigration')
    const { migrateLocalToServer } = useChatMigration()

    const result = await migrateLocalToServer()

    expect(result.skipped).toBe(false)
    expect(result.error).toContain('网络错误')
    // 关键：失败时不设标志
    expect(localStorage.getItem(MIGRATION_FLAG_KEY)).toBeFalsy()
  })

  it('migrateLocalToServer 幂等：调两次不重复迁移', async () => {
    mockChatSessionsStore.sessions = []
    const { useChatMigration } = await import('../useChatMigration')
    const { migrateLocalToServer } = useChatMigration()

    const result1 = await migrateLocalToServer()
    // 第二次应跳过（标志已设）
    const result2 = await migrateLocalToServer()

    expect(result1.skipped).toBe(false)
    expect(result2.skipped).toBe(true)
    expect(result2.reason).toBe('already_migrated')
  })

  it('migrateLocalToServer 失败后下次启动重试', async () => {
    mockChatSessionsStore.sessions = [
      { id: 's1', title: '会话1', preview: '', is_pinned: false, is_archived: false, tags: [], createdAt: '2026-06-30T00:00:00Z', updatedAt: '2026-06-30T00:00:00Z' },
    ]
    // 第一次失败
    mockChatHistoryApi.syncFromLocal.mockRejectedValueOnce(new Error('网络错误'))

    const { useChatMigration } = await import('../useChatMigration')
    const { migrateLocalToServer } = useChatMigration()

    await migrateLocalToServer()
    expect(localStorage.getItem(MIGRATION_FLAG_KEY)).toBeFalsy()

    // 第二次成功（网络恢复）
    mockChatHistoryApi.syncFromLocal.mockResolvedValueOnce({
      ok: true,
      migrated_count: 1,
      conflicts: [],
    })

    const result = await migrateLocalToServer()
    expect(result.migrated).toBe(1)
    expect(localStorage.getItem(MIGRATION_FLAG_KEY)).toBeTruthy()
  })

  it('migrateLocalToServer 无 access_token → 跳过', async () => {
    localStorage.removeItem('access_token')
    mockChatSessionsStore.sessions = [
      { id: 's1', title: '会话1', preview: '', is_pinned: false, is_archived: false, tags: [], createdAt: '2026-06-30T00:00:00Z', updatedAt: '2026-06-30T00:00:00Z' },
    ]
    const { useChatMigration } = await import('../useChatMigration')
    const { migrateLocalToServer } = useChatMigration()

    const result = await migrateLocalToServer()

    expect(result.skipped).toBe(true)
    expect(result.reason).toBe('not_logged_in')
    expect(mockChatHistoryApi.syncFromLocal).not.toHaveBeenCalled()
  })

  it('corrupt chat_msgs JSON 不阻断其他 session 迁移', async () => {
    mockChatSessionsStore.sessions = [
      { id: 'good', title: 'OK', preview: '', is_pinned: false, is_archived: false, tags: [], createdAt: '2026-06-30T00:00:00Z', updatedAt: '2026-06-30T00:00:00Z' },
      { id: 'corrupt', title: 'Bad', preview: '', is_pinned: false, is_archived: false, tags: [], createdAt: '2026-06-30T00:00:00Z', updatedAt: '2026-06-30T00:00:00Z' },
    ]
    localStorage.setItem('chat_msgs_good', JSON.stringify([{ role: 'user', content: 'ok' }]))
    localStorage.setItem('chat_msgs_corrupt', '{not valid json}')
    mockChatHistoryApi.syncFromLocal.mockResolvedValue({
      ok: true,
      migrated_count: 2,
      conflicts: [],
    })

    const { useChatMigration } = await import('../useChatMigration')
    const { migrateLocalToServer } = useChatMigration()

    const result = await migrateLocalToServer()

    // 仍能成功迁移（corrupt session 用空消息数组）
    expect(result.migrated).toBe(2)
    expect(mockChatHistoryApi.syncFromLocal).toHaveBeenCalledWith(
      expect.objectContaining({
        localMessages: expect.arrayContaining([
          expect.objectContaining({ session_id: 'good', messages: expect.any(Array) }),
          expect.objectContaining({ session_id: 'corrupt', messages: [] }),
        ]),
      })
    )
  })
})
