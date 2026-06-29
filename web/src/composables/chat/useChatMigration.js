/**
 * useChatMigration.js — #043 Phase 5 旧数据自动迁移（localStorage → server）
 *
 * 触发时机：用户**首次登录**新版（前端用 localStorage `chat_migrated_v1` 标记判断）
 *
 * 设计要点：
 * - **幂等**：chat_migrated_v1 标志 + server `client_msg_id` 唯一约束双重保证
 * - **失败回退**：迁移失败时**不**设标志，下次启动重试（不卡死用户）
 * - **不阻塞登录**：useChatStream.onMounted 异步 setTimeout 1s 后跑，UI 立即可用
 * - **数据收集**：复用 chatSessionsStore.sessions + 直接读 chat_msgs_<sid> localStorage
 *
 * 关键纪律（CLAUDE.md 2026-06-19 教训）：
 * - 老 localStorage 消息没有 client_msg_id → 服务端 sync_from_local 自动用 hash 生成
 * - 网络失败 / 401 → 抛异常但**不**写标志，下次重试
 * - 不要把 localStorage 标记设到 chatHistoryStore.syncStatus（那是同步状态，不是迁移状态）
 */

import { useChatSessionsStore } from '@/stores/chatSessions'
import { useChatHistoryStore } from '@/stores/chatHistory'
import { chatHistoryApi } from '@/api/chatHistory'

const MIGRATION_FLAG_KEY = 'chat_migrated_v1'

export function useChatMigration() {
  const chatSessionsStore = useChatSessionsStore()
  const chatHistoryStore = useChatHistoryStore()

  /** 检查是否需要迁移（前端标志位） */
  function needsMigration() {
    return !localStorage.getItem(MIGRATION_FLAG_KEY)
  }

  /** 主入口：迁移 localStorage → server（幂等，可重复调用） */
  async function migrateLocalToServer() {
    // 已迁移过 → 跳过（CLAUDE.md 2026-06-12 幂等性铁律）
    if (!needsMigration()) {
      return { skipped: true, reason: 'already_migrated' }
    }

    // 没登录态 → 跳过（等登录态再跑，useChatStream.onMounted 已 check access_token）
    const token = localStorage.getItem('access_token')
    if (!token) {
      return { skipped: true, reason: 'not_logged_in' }
    }

    const localSessions = chatSessionsStore.sessions || []

    // 没有 localStorage 数据 → 直接标记已迁移（不用调 API）
    if (localSessions.length === 0) {
      localStorage.setItem(MIGRATION_FLAG_KEY, new Date().toISOString())
      return { skipped: false, migrated: 0, reason: 'no_local_data' }
    }

    // 收集所有 localStorage 消息（每个 session 一个 chat_msgs_<sid> key）
    const localSessionsWithMessages = localSessions.map(s => {
      let messages = []
      try {
        const raw = localStorage.getItem(`chat_msgs_${s.id}`)
        if (raw) messages = JSON.parse(raw)
      } catch (e) {
        // corrupt JSON 不阻断其他 session 的迁移
        console.warn(`[useChatMigration] chat_msgs_${s.id} JSON 损坏，跳过`, e)
      }

      return {
        id: s.id,
        title: s.title,
        preview: s.preview,
        is_pinned: !!s.is_pinned,
        is_archived: !!s.is_archived,
        tags: s.tags || [],
        created_at: s.createdAt,
        updated_at: s.updatedAt,
        messages: messages.map((m) => ({
          role: m.role || 'user',
          content: m.content || '',
          rich_blocks: m.richBlocks || [],
          tool_trace: m.toolTrace || {},
          message_metadata: { source: 'local_migration' },
          created_at: m.timestamp || new Date().toISOString(),
        })),
      }
    })

    try {
      // 调用 /chat/sync 端点（dedup by client_msg_id，幂等）
      const result = await chatHistoryApi.syncFromLocal({
        localSessions: localSessionsWithMessages.map(s => ({
          id: s.id,
          title: s.title,
          preview: s.preview,
          is_pinned: s.is_pinned,
          is_archived: s.is_archived,
          tags: s.tags,
          created_at: s.created_at,
          updated_at: s.updated_at,
        })),
        localMessages: localSessionsWithMessages.map(s => ({
          session_id: s.id,
          messages: s.messages,
        })),
      })

      if (result?.ok) {
        // 标记已迁移（写入前端标志）
        localStorage.setItem(MIGRATION_FLAG_KEY, new Date().toISOString())
        // refresh store（让侧栏显示 server 状态）
        try {
          await chatHistoryStore.loadFromServer()
          chatSessionsStore.mergeServerList(chatHistoryStore.serverSessions)
        } catch (e) {
          // refresh 失败不影响迁移已成功的状态
          console.warn('[useChatMigration] 迁移后 refresh server 列表失败:', e)
        }
        return {
          skipped: false,
          migrated: result.migrated_count || 0,
          conflicts: result.conflicts || [],
        }
      }
      return { skipped: false, error: 'sync_not_ok' }
    } catch (e) {
      // 失败时不设标志，下次启动重试（CLAUDE.md 2026-06-19 失败回退铁律）
      const detail = e?.response?.data?.detail || e?.message || 'unknown'
      console.warn('[useChatMigration] 迁移失败，保留 localStorage 兜底:', detail)
      return { skipped: false, error: detail }
    }
  }

  return { needsMigration, migrateLocalToServer }
}

export default useChatMigration