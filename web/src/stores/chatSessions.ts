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

const STORAGE_KEY = 'chat_sessions_v3'
const CURRENT_KEY = 'chat_current_session_v3'

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
    const raw = localStorage.getItem(STORAGE_KEY)
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
    const clean = sessions.map(serializeSession)
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ sessions: clean, currentId }))
    if (currentId) localStorage.setItem(CURRENT_KEY, currentId)
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

  function deleteSession(id: string) {
    const idx = sessions.value.findIndex(s => s.id === id)
    if (idx < 0) return
    sessions.value.splice(idx, 1)
    if (currentId.value === id) {
      currentId.value = sessions.value[0]?.id || null
    }
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
   */
  function mergeServerList(serverSessions: any[]) {
    if (!Array.isArray(serverSessions)) return

    // 建立本地 id → index 索引
    const localById = new Map<string, number>()
    sessions.value.forEach((s, i) => localById.set(s.id, i))

    const mergedLocal: ChatSession[] = []
    const seenServerIds = new Set<string>()

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
  }
})
