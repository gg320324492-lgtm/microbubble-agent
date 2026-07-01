/**
 * chatSessions store — 多会话管理（Pinia）
 *
 * 状态：sessions: ChatSession[]、currentId: string
 * 持久化：localStorage（避免 IndexedDB 依赖）
 *
 * 每个 ChatSession:
 *  - id: 唯一 ID（user_<timestamp> 格式）
 *  - title: 会话标题（取首条 user 消息前 30 字）
 *  - createdAt: 创建时间 ISO
 *  - updatedAt: 最后活动时间
 *  - messageCount: 消息数
 *  - preview: 最后一条消息预览
 *  - is_pinned / is_archived / tags / last_message_at: #043 服务端同步字段（可选）
 *  - _isLocalOnly / _syncStatus: #043 内部标记（不序列化到 localStorage）
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

// === 2026-07-01: per-user localStorage key（防御 1c 跨用户污染） ===
// 旧 key (chat_sessions_v3) 不带 userId 后缀，logout 切换用户后本地的
// sessionId/currentId 会被新用户继承，导致后端 ensure_session_for_stream
// 看到不属于本用户的 session_id 静默创建新行 ("新对话" 重复 bug 根因 1d)。
// 修复: 用 per-user 后缀 (chat_sessions_v3__u<id>)，并在 logout 时整体清空。
const STORAGE_KEY_BASE = 'chat_sessions_v3'
const CURRENT_KEY_BASE = 'chat_current_session_v3'

function readUserId(): string | null {
  try {
    const raw = localStorage.getItem('user_info')
    if (!raw) return null
    const id = String(JSON.parse(raw)?.id ?? '')
    return id || null
  } catch {
    return null
  }
}

function userKey(base: string, userId: string | null): string {
  return userId ? `${base}__u${userId}` : `${base}__anon`
}

// 内部标记字段（不写入 localStorage，避免污染用户数据）
const INTERNAL_FIELDS = new Set(['_isLocalOnly', '_syncStatus'])

function serializeSession(s: ChatSession): any {
  const out: any = {}
  for (const k of Object.keys(s)) {
    if (!INTERNAL_FIELDS.has(k)) out[k] = (s as any)[k]
  }
  return out
}

function deserializeSession(obj: any): ChatSession {
  return {
    ...obj,
    _isLocalOnly: true,        // 默认标记为本地（mergeServerList 后会改）
    _syncStatus: 'pending',
  }
}

function loadFromStorage() {
  try {
    const userId = readUserId()
    const newKey = userKey(STORAGE_KEY_BASE, userId)
    // 优先新 key，fallback 旧 key（向后兼容一次，老用户迁移后下次 save 写新 key）
    const raw = localStorage.getItem(newKey) || localStorage.getItem(STORAGE_KEY_BASE)
    if (!raw) return { sessions: [], currentId: null }
    const parsed = JSON.parse(raw)
    const sessions = Array.isArray(parsed.sessions)
      ? parsed.sessions.map((s: any) => deserializeSession(s))
      : []
    return { sessions, currentId: parsed.currentId }
  } catch {
    return { sessions: [], currentId: null }
  }
}

function saveToStorage(sessions: ChatSession[], currentId: string | null) {
  try {
    const userId = readUserId()
    const newKey = userKey(STORAGE_KEY_BASE, userId)
    const clean = sessions.map(serializeSession)
    localStorage.setItem(newKey, JSON.stringify({ sessions: clean, currentId }))
    if (currentId) localStorage.setItem(userKey(CURRENT_KEY_BASE, userId), currentId)
    // 清理老非 namespace key（一次）
    localStorage.removeItem(STORAGE_KEY_BASE)
    localStorage.removeItem(CURRENT_KEY_BASE)
  } catch (e) {
    console.warn('会话持久化失败', e)
  }
}

export interface ChatSession {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messageCount: number
  preview: string
  // === #043 新增字段（与 server 同步用） ===
  is_pinned?: boolean
  is_archived?: boolean
  tags?: string[]
  last_message_at?: string
  // === 内部标记（不序列化） ===
  _isLocalOnly?: boolean
  _syncStatus?: 'synced' | 'pending' | 'error'
}

export const useChatSessionsStore = defineStore('chatSessions', () => {
  const initial = loadFromStorage()
  const sessions = ref<ChatSession[]>(initial.sessions || [])
  const currentId = ref<string | null>(initial.currentId)

  // 排序：v78 UI-redesign — 置顶冒泡到顶，同优先级内按 updatedAt 倒序
  const sortedSessions = computed(() =>
    [...sessions.value].sort((a, b) => {
      const ap = a.is_pinned ? 1 : 0
      const bp = b.is_pinned ? 1 : 0
      if (ap !== bp) return bp - ap
      return (b.updatedAt || '').localeCompare(a.updatedAt || '')
    })
  )

  // 自动持久化
  watch([sessions, currentId], () => {
    saveToStorage(sessions.value, currentId.value)
  }, { deep: true })

  function createSession(firstUserMsg?: string): ChatSession {
    const now = new Date().toISOString()
    const title = (firstUserMsg || '新对话').slice(0, 30) || '新对话'
    const session: ChatSession = {
      id: `user_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      title,
      createdAt: now,
      updatedAt: now,
      messageCount: 1,
      preview: (firstUserMsg || '').slice(0, 50),
      _isLocalOnly: true,
      _syncStatus: 'pending',
    }
    sessions.value.push(session)
    currentId.value = session.id
    return session
  }

  function switchSession(id: string) {
    if (sessions.value.find(s => s.id === id)) {
      currentId.value = id
      return true
    }
    return false
  }

  /**
   * 删除会话(本地 + 服务端)
   * - 本地立即 splice,UI 立刻响应
   * - 异步调服务端 hard delete(参考 setTags/setPinned best-effort 模式)
   * - 失败 best-effort:console.warn(不阻塞 UI,不回滚本地)
   * - 2026-07-01 修复:之前只动本地,导致 refresh 后 mergeServerList 复活
   */
  function deleteSession(id: string) {
    const idx = sessions.value.findIndex(s => s.id === id)
    if (idx < 0) return
    sessions.value.splice(idx, 1)
    if (currentId.value === id) {
      currentId.value = sessions.value[0]?.id || null
    }
    // ★ 2026-07-01:同步服务端(用户决策 hard delete,UI 文案"不可撤销")
    ;(async () => {
      try {
        const { useChatHistoryStore } = await import('@/stores/chatHistory')
        await useChatHistoryStore().deleteServerSession(id, { hard: true })
      } catch (e) {
        // best-effort:失败时刷新页面会让会话复活(虽然不理想,但比"用户看到已删除又出现"更糟的是"操作被撤销")
        console.warn('[chatSessions] deleteServerSession failed:', e)
      }
    })()
  }

  function renameSession(id: string, newTitle: string) {
    const s = sessions.value.find(s => s.id === id)
    if (s) s.title = newTitle.slice(0, 50)
  }

  function updateActivity(id: string, messageCount: number, lastMessage: string) {
    const s = sessions.value.find(s => s.id === id)
    if (s) {
      s.updatedAt = new Date().toISOString()
      s.messageCount = messageCount
      s.preview = lastMessage.slice(0, 50)
      // 首条 user 消息时自动用其作为标题
      // 2026-06-25: 限制 10 字（与 MobileHeader currentTitle 一致）
      // 之前 30 字在移动端 header 太长，会显示完整聊天消息内容
      if (s.messageCount === 1 && lastMessage) {
        s.title = lastMessage.slice(0, 10) || '新对话'
      }
    }
  }

  function currentSession() {
    return sessions.value.find(s => s.id === currentId.value) || null
  }

  // 兼容 v1 localStorage 单会话（chat_session_id 旧 key）
  function migrateFromV1() {
    const oldId = localStorage.getItem('chat_session_id')
    if (oldId && sessions.value.length === 0) {
      const session: ChatSession = {
        id: oldId,
        title: '旧对话（已迁移）',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        messageCount: 0,
        preview: '',
        _isLocalOnly: true,
        _syncStatus: 'pending',
      }
      sessions.value.push(session)
      currentId.value = oldId
    }
  }

  // ============================================================================
  // #043 新增方法 — 与 chatHistory store 同步
  // ============================================================================

  /**
   * 从服务端会话列表合并到本地（保留本地标记，覆盖服务端元数据）
   * - 已存在的本地 session：更新 title/preview/updatedAt/is_pinned/is_archived/tags，标记 _isLocalOnly=false
   * - 仅 server 有 / 仅本地有：保留两侧
   * - ★ 2026-07-01 修复 bug 1b: merge 完成后 repair currentId
   *   旧实现: currentId 保留指向已删除的本地 id → currentSession() 返回 null
   *   → useChatStream 触发 createSession() 重新 mint 新 id → 重复 "新对话"
   */
  function mergeServerList(serverSessions: any[]) {
    if (!Array.isArray(serverSessions)) return

    // 建立本地 id → index 索引
    const localById = new Map<string, number>()
    sessions.value.forEach((s, i) => localById.set(s.id, i))

    const mergedLocal: ChatSession[] = []
    const seenServerIds = new Set<string>()
    const previousCurrentId = currentId.value  // ★ 修复 1b: merge 之前先快照

    // 1. 先处理 server 列表（服务端为权威）
    for (const server of serverSessions) {
      seenServerIds.add(server.id)
      const localIdx = localById.get(server.id)
      if (localIdx !== undefined) {
        // 合并：保留本地 _isLocalOnly/_syncStatus（迁移后才会变 synced）
        mergedLocal.push({
          ...sessions.value[localIdx],
          title: server.title || sessions.value[localIdx].title,
          preview: server.preview || sessions.value[localIdx].preview,
          updatedAt: server.updated_at || sessions.value[localIdx].updatedAt,
          messageCount: server.message_count ?? sessions.value[localIdx].messageCount,
          is_pinned: server.is_pinned ?? sessions.value[localIdx].is_pinned,
          is_archived: server.is_archived ?? sessions.value[localIdx].is_archived,
          tags: server.tags ?? sessions.value[localIdx].tags,
          last_message_at: server.last_message_at ?? sessions.value[localIdx].last_message_at,
          _isLocalOnly: false,
          _syncStatus: 'synced',
        })
      } else {
        // server 独有 → 加入本地（仅服务端有）
        mergedLocal.push({
          id: server.id,
          title: server.title || '新对话',
          createdAt: server.created_at || new Date().toISOString(),
          updatedAt: server.updated_at || new Date().toISOString(),
          messageCount: server.message_count ?? 0,
          preview: server.preview || '',
          is_pinned: server.is_pinned ?? false,
          is_archived: server.is_archived ?? false,
          tags: server.tags ?? [],
          last_message_at: server.last_message_at,
          _isLocalOnly: false,
          _syncStatus: 'synced',
        })
      }
    }

    // 2. 本地有 + server 没有 → 保留（标记为本地 only，待 Phase 5 迁移）
    for (const local of sessions.value) {
      if (!seenServerIds.has(local.id)) {
        mergedLocal.push({
          ...local,
          _isLocalOnly: true,
          _syncStatus: 'pending',
        })
      }
    }

    sessions.value = mergedLocal

    // ★ 关键修复 1b: repair currentId
    // 1) local currentId 仍是 server-confirmed session → 保留
    if (previousCurrentId && mergedLocal.some(s => s.id === previousCurrentId && !s._isLocalOnly)) {
      currentId.value = previousCurrentId
      return
    }
    // 2) 选最近活动(非 archived)服务端会话（用户决策 2026-07-01: 自动恢复最近）
    const activeServer = mergedLocal
      .filter(s => !s._isLocalOnly && !s.is_archived)
      .sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''))[0]
    if (activeServer) { currentId.value = activeServer.id; return }
    // 3) 选最近 local-only 会话（待迁移,用户曾经在这会话里写过消息）
    const localOnly = mergedLocal
      .filter(s => s._isLocalOnly)
      .sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''))[0]
    if (localOnly) { currentId.value = localOnly.id; return }
    // 4) 都没有 → null（不 mint，UI 显示空状态）
    currentId.value = null
  }

  /**
   * ★ 2026-07-01: pickInitialSessionId 纯函数（供 useChatStream 调）
   * 给定 server list / local currentId / local session ids，选出初始 sessionId。
   * 用户决策: 登录后服务端有会话时自动恢复最近（ChatGPT/豆包模式）。
   * 返回 null = 让 UI 显示空状态 + "新对话" 按钮，**不**自动 mint。
   */
  function pickInitialSessionId(input: {
    serverSessions: Array<{ id: string; updated_at?: string; is_archived?: boolean }>
    localCurrentId: string | null
    localSessionIds: string[]
  }): string | null {
    const { serverSessions, localCurrentId, localSessionIds } = input
    const localIdSet = new Set(localSessionIds)
    // 1) local currentId 在服务端存在 → 保留
    if (localCurrentId && serverSessions.some(s => s.id === localCurrentId)) return localCurrentId
    // 2) local currentId 只在本地(待迁移) → 保留
    if (localCurrentId && localIdSet.has(localCurrentId)) return localCurrentId
    // 3) 选最近活动服务端会话
    const active = serverSessions
      .filter(s => !s.is_archived)
      .sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''))[0]
    if (active) return active.id
    return null
  }

  /**
   * 标记 session 同步状态（chatHistoryStore 调用）
   */
  function markSyncStatus(id: string, status: 'synced' | 'pending' | 'error') {
    const s = sessions.value.find(s => s.id === id)
    if (s) s._syncStatus = status
  }

  /**
   * 标记 session 已同步到 server（清空 _isLocalOnly 标记）
   */
  function markSynced(id: string) {
    const s = sessions.value.find(s => s.id === id)
    if (s) {
      s._isLocalOnly = false
      s._syncStatus = 'synced'
    }
  }

  // ============================================================================
  // #043 Phase 6 新增 — 本地 mutation helpers（双向同步 server）
  // ============================================================================

  /**
   * 设置标签（本地立即更新 + 异步 PATCH server）
   * CLAUDE.md 2026-06-15 "持久化失败必须 best-effort" 铁律：失败不阻塞 UI
   */
  async function setTags(id: string, tags: string[]) {
    const s = sessions.value.find(s => s.id === id)
    if (s) {
      s.tags = [...tags]
      s._syncStatus = 'pending'
    }
    try {
      const { useChatHistoryStore } = await import('@/stores/chatHistory')
      const updated = await useChatHistoryStore().updateServerSession(id, { tags: [...tags] })
      if (s) s._syncStatus = updated ? 'synced' : 'error'
    } catch (e) {
      if (s) s._syncStatus = 'error'
      console.warn('[chatSessions] setTags server sync failed:', e)
    }
  }

  /**
   * 设置收藏（本地立即更新 + 异步 PATCH server）
   */
  async function setPinned(id: string, isPinned: boolean) {
    const s = sessions.value.find(s => s.id === id)
    if (s) {
      s.is_pinned = isPinned
      s._syncStatus = 'pending'
    }
    try {
      const { useChatHistoryStore } = await import('@/stores/chatHistory')
      const updated = await useChatHistoryStore().updateServerSession(id, { is_pinned: isPinned })
      if (s) s._syncStatus = updated ? 'synced' : 'error'
    } catch (e) {
      if (s) s._syncStatus = 'error'
      console.warn('[chatSessions] setPinned server sync failed:', e)
    }
  }

  /**
   * 设置归档（本地立即更新 + 异步 PATCH server）
   */
  async function setArchived(id: string, isArchived: boolean) {
    const s = sessions.value.find(s => s.id === id)
    if (s) {
      s.is_archived = isArchived
      s._syncStatus = 'pending'
    }
    try {
      const { useChatHistoryStore } = await import('@/stores/chatHistory')
      const updated = await useChatHistoryStore().updateServerSession(id, { is_archived: isArchived })
      if (s) s._syncStatus = updated ? 'synced' : 'error'
    } catch (e) {
      if (s) s._syncStatus = 'error'
      console.warn('[chatSessions] setArchived server sync failed:', e)
    }
  }

  return {
    sessions,
    currentId,
    sortedSessions,
    currentSession,
    createSession,
    switchSession,
    deleteSession,
    renameSession,
    updateActivity,
    migrateFromV1,
    // #043 新增
    mergeServerList,
    markSyncStatus,
    markSynced,
    // #043 Phase 6 新增 — 本地 mutation helpers
    setTags,
    setPinned,
    setArchived,
    // 2026-07-01 修复 bug 1a/1b：登录/同步后纯函数选 session
    pickInitialSessionId,
  }
})
