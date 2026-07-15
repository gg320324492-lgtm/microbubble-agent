/**
 * chatHistory store — #043 账号持久化聊天历史（Pinia）
 *
 * 与 chatSessions.ts 平行，但**专门负责与服务端通信**：
 * - 登录后从 server 拉会话列表（替代/补充 localStorage）
 * - 流式 chat 时 fire-and-forget 写消息到 server
 * - 流式中断时 refreshSession reload 当前会话消息
 * - 退出登录时 reset() 清空 store（防止下一用户看到上一用户数据）
 *
 * 与 chatSessions.ts 关系：
 * - chatSessions 持有**本地 + 缓存**会话列表（侧栏渲染）
 * - chatHistory 持有**服务端**会话列表（用于跨设备同步）
 * - 两者通过 useChatStream.mergeServerList() 同步（后端元信息 → 侧栏）
 *
 * 关键纪律（CLAUDE.md 2026-06-15 "退出登录清空 store" 铁律）：
 * - logout() 必须调 reset()，否则下一用户看到上一用户数据 = 越权
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatHistoryApi } from '@/api/chatHistory'

export type SyncStatus = 'idle' | 'syncing' | 'success' | 'error' | 'offline'

export const useChatHistoryStore = defineStore('chatHistory', () => {
  // ============================================================================
  // State
  // ============================================================================

  /** 服务端会话列表（按 user_id 隔离，登录后从 server 拉） */
  const serverSessions = ref<any[]>([])

  /** 已同步到 server 的本地 session id 集合（用于增量同步判断） */
  const syncedSessionIds = ref<Set<string>>(new Set())

  /** 最后一次同步时间戳（ISO 字符串） */
  const lastSyncedAt = ref<string | null>(null)

  /** 当前同步状态（UI 显示用） */
  const syncStatus = ref<SyncStatus>('idle')

  /** 同步错误信息（侧栏徽章显示用） */
  const syncError = ref<string | null>(null)

  // ===== #043 Phase 6 新增 state =====

  /** 搜索结果（Cmd/Ctrl+K 跨会话搜索） */
  const searchResults = ref<{ items: any[]; total: number; page: number }>({
    items: [],
    total: 0,
    page: 1,
  })

  /** 当前分享链接 token（ShareDialog 显示用） */
  const shareToken = ref<string | null>(null)

  /** 当前导出 blob（ExportDialog 触发浏览器下载用） */
  const exportBlob = ref<Blob | null>(null)

  // ============================================================================
  // Computed
  // ============================================================================

  /** 未同步（仅本地）的会话数（侧栏徽章"⚠️ N 条未同步"） */
  const pendingSyncCount = computed(() =>
    serverSessions.value.filter(s => s._isLocalOnly).length,
  )

  /** 已登录且有服务端会话（侧栏"切换到云端"提示用） */
  const hasServerSessions = computed(() =>
    serverSessions.value.filter(s => !s._isLocalOnly).length > 0,
  )

  // ============================================================================
  // Actions
  // ============================================================================

  /**
   * 登录后首次拉服务端列表
   * 失败抛异常（让 caller 决定 fallback 策略）
   */
  async function loadFromServer() {
    syncStatus.value = 'syncing'
    syncError.value = null
    try {
      const data = await chatHistoryApi.listSessions({ pageSize: 100 })
      serverSessions.value = data.items || []
      syncStatus.value = 'success'
      return serverSessions.value
    } catch (e: any) {
      syncStatus.value = 'error'
      syncError.value = e?.response?.data?.detail || e?.message || '加载失败'
      throw e
    }
  }

  /**
   * 异步追加消息到 server（fire-and-forget，不阻塞流式）
   * @returns {Promise<ServerChatMessage|null>} 成功返回 message，失败返回 null
   */
  async function appendMessageAsync(sid: string, msg: any) {
    try {
      const result = await chatHistoryApi.appendMessage(sid, msg)
      return result
    } catch (e: any) {
      // best-effort: 失败不阻塞流式，仅 console 记录
      // CLAUDE.md 2026-06-12 "持久化失败必须 best-effort" 铁律
      console.error(`[chatHistory] appendMessage 失败: sid=${sid}`, e?.response?.data?.detail || e?.message)
      return null
    }
  }

  /**
   * 创建服务端 session（client_session_id = localStorage sessionId 兼容）
   * @returns {Promise<ServerChatSession|null>}
   */
  async function createServerSession({
    title,
    firstMessage,
    clientSessionId,
  }: {
    title?: string
    firstMessage?: string
    clientSessionId?: string
  }) {
    try {
      const session = await chatHistoryApi.createSession({
        ...(title ? { title } : {}),
        ...(firstMessage ? { first_message: firstMessage } : {}),
        ...(clientSessionId ? { client_session_id: clientSessionId } : {}),
      })
      // 头部插入（最新会话在前）
      serverSessions.value.unshift(session)
      syncedSessionIds.value.add(session.id)
      return session
    } catch (e: any) {
      console.error('[chatHistory] createServerSession 失败', e?.response?.data?.detail || e?.message)
      return null
    }
  }

  /**
   * 拉取会话消息（首次进会话 / 流式中断后 reload 用）
   * @returns {Promise<{items: ServerChatMessage[], has_more: boolean}>}
   */
  async function fetchMessages(sid: string, opts: { afterId?: number; pageSize?: number } = {}) {
    // ★ 2026-07-15 #P2 修复: 空 sid 早返 (避免 /chat/sessions//messages 双斜杠 404)
    // 触发场景: useChatStream.ensureSessionLoaded('') 走 onMounted 冷启动路径
    if (!sid) {
      console.warn('[chatHistory] fetchMessages skipped: empty sid')
      return { items: [], has_more: false }
    }
    try {
      return await chatHistoryApi.listMessages(sid, {
        afterId: opts.afterId ?? 0,
        pageSize: opts.pageSize ?? 200,
      })
    } catch (e: any) {
      console.error(`[chatHistory] fetchMessages 失败: sid=${sid}`, e?.response?.data?.detail || e?.message)
      throw e
    }
  }

  /**
   * 流式中断 / 异常时 refresh session（前端 store 全量 reload）
   * @returns {Promise<ServerChatMessage[]|null>}
   */
  async function refreshSession(sid: string) {
    // ★ 2026-07-15 #P2 修复: 空 sid 早返 (与 fetchMessages 镜像, 防止 sync_required reload 误调)
    if (!sid) {
      console.warn('[chatHistory] refreshSession skipped: empty sid')
      return null
    }
    try {
      const data = await chatHistoryApi.listMessages(sid, { pageSize: 200 })
      return data.items || []
    } catch (e: any) {
      console.error(`[chatHistory] refreshSession 失败: sid=${sid}`, e?.response?.data?.detail || e?.message)
      return null
    }
  }

  /**
   * 删除服务端 session（默认软删除）
   * @returns {Promise<boolean>}
   */
  async function deleteServerSession(sid: string, opts: { hard?: boolean } = {}) {
    try {
      await chatHistoryApi.deleteSession(sid, { hard: opts.hard ?? false })
      serverSessions.value = serverSessions.value.filter(s => s.id !== sid)
      syncedSessionIds.value.delete(sid)
      return true
    } catch (e: any) {
      console.error(`[chatHistory] deleteServerSession 失败: sid=${sid}`, e?.response?.data?.detail || e?.message)
      return false
    }
  }

  /**
   * 更新服务端 session（title / is_pinned / is_archived / tags）
   * @returns {Promise<ServerChatSession|null>}
   */
  async function updateServerSession(sid: string, patch: Record<string, any>) {
    try {
      const updated = await chatHistoryApi.updateSession(sid, patch)
      const idx = serverSessions.value.findIndex(s => s.id === sid)
      if (idx >= 0) {
        serverSessions.value[idx] = { ...serverSessions.value[idx], ...updated }
      }
      return updated
    } catch (e: any) {
      console.error(`[chatHistory] updateServerSession 失败: sid=${sid}`, e?.response?.data?.detail || e?.message)
      return null
    }
  }

  /**
   * 退出登录时清空 store（CLAUDE.md 2026-06-15 退出登录清空铁律）
   */
  function reset() {
    serverSessions.value = []
    syncedSessionIds.value.clear()
    lastSyncedAt.value = null
    syncStatus.value = 'idle'
    syncError.value = null
    // Phase 6 新增 state 也要清空
    searchResults.value = { items: [], total: 0, page: 1 }
    shareToken.value = null
    exportBlob.value = null
  }

  // ============================================================================
  // #043 Phase 6 新增 actions — 搜索 / 分享 / 导出
  // ============================================================================

  /**
   * 跨会话搜索（按消息内容 ILIKE 匹配，最少 2 字符）
   * @returns {Promise<{items, total, page}>} 失败返空结果
   */
  async function searchSessions(query: string, opts: { page?: number; pageSize?: number } = {}) {
    if (!query || query.trim().length < 2) {
      searchResults.value = { items: [], total: 0, page: 1 }
      return searchResults.value
    }
    try {
      const data = await chatHistoryApi.searchSessions(query, {
        page: opts.page ?? 1,
        pageSize: opts.pageSize ?? 20,
      })
      searchResults.value = data
      return data
    } catch (e: any) {
      console.error(`[chatHistory] searchSessions 失败: q=${query}`, e?.response?.data?.detail || e?.message)
      return { items: [], total: 0, page: 1 }
    }
  }

  /**
   * 生成分享链接
   * @returns {Promise<{id, share_url, permission, expires_at} | null>}
   */
  async function createShareLink(sid: string, opts: { permission?: 'read' | 'write'; expiresHours?: number } = {}) {
    try {
      const result = await chatHistoryApi.createShare(sid, {
        permission: opts.permission ?? 'read',
        ...(opts.expiresHours ? { expiresHours: opts.expiresHours } : {}),
      })
      shareToken.value = result?.share_url || null
      return result
    } catch (e: any) {
      console.error(`[chatHistory] createShareLink 失败: sid=${sid}`, e?.response?.data?.detail || e?.message)
      return null
    }
  }

  /**
   * 导出为 Markdown / JSON blob
   * @returns {Promise<Blob | null>}
   */
  async function exportToFile(sid: string, opts: { format?: 'md' | 'json' } = {}) {
    try {
      const blob = await chatHistoryApi.exportSession(sid, { format: opts.format ?? 'md' })
      exportBlob.value = blob
      return blob
    } catch (e: any) {
      console.error(`[chatHistory] exportToFile 失败: sid=${sid}`, e?.response?.data?.detail || e?.message)
      return null
    }
  }

  // ============================================================================
  // Return
  // ============================================================================

  return {
    // state
    serverSessions,
    syncedSessionIds,
    lastSyncedAt,
    syncStatus,
    syncError,
    // Phase 6 新增 state
    searchResults,
    shareToken,
    exportBlob,
    // computed
    pendingSyncCount,
    hasServerSessions,
    // actions
    loadFromServer,
    appendMessageAsync,
    createServerSession,
    fetchMessages,
    refreshSession,
    deleteServerSession,
    updateServerSession,
    reset,
    // Phase 6 新增 actions
    searchSessions,
    createShareLink,
    exportToFile,
  }
})