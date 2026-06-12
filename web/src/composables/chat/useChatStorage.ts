/**
 * useChatStorage.ts — Chat 消息 localStorage 持久化
 *
 * 从 ChatViewSSE.vue 抽取（PR #1 基建）。
 * 与 useChatStream 解耦：纯 localStorage 读写，可独立单测。
 *
 * 存储结构：
 *   chat_current_session_v3       当前显示的 sessionId
 *   chat_msgs_<sessionId>         每个 session 的消息数组 JSON（最多保留 200 条）
 *   chat_messages_v2              旧单会话兼容键（仅写不读）
 */

import type { ChatMessage } from './useChatStream'

const MESSAGES_KEY_PREFIX = 'chat_msgs_'
const LEGACY_MESSAGES_KEY = 'chat_messages_v2'

const PERSIST_DEBOUNCE_MS = 100
const MESSAGES_SLICE_KEEP = 200

export function useChatStorage() {
  // --------------------------------------------------------------------------
  // 同步写入（不 debounce）— 用于切会话/卸载/发送完成等关键节点
  // --------------------------------------------------------------------------
  function persistSessionSync(
    id: string,
    messagesBySession: Record<string, ChatMessage[]>,
    currentSessionId: string
  ) {
    const msgs = messagesBySession[id] || []
    const slice = msgs.slice(-MESSAGES_SLICE_KEEP)
    try {
      localStorage.setItem(`${MESSAGES_KEY_PREFIX}${id}`, JSON.stringify(slice))
    } catch (e) {
      console.warn('[useChatStorage] persist failed', e)
    }
    if (id === currentSessionId) {
      try {
        localStorage.setItem(LEGACY_MESSAGES_KEY, JSON.stringify(slice))
      } catch { /* ignore */ }
    }
    return msgs
  }

  // --------------------------------------------------------------------------
  // debounce 持久化 — SSE 流式 yield 时调用，避免 localStorage 写入风暴
  // --------------------------------------------------------------------------
  function persistSessionDebounced(
    id: string,
    messagesBySession: Record<string, ChatMessage[]>,
    currentSessionId: string,
    timers: Record<string, ReturnType<typeof setTimeout>>
  ) {
    if (timers[id]) clearTimeout(timers[id])
    timers[id] = setTimeout(() => {
      persistSessionSync(id, messagesBySession, currentSessionId)
    }, PERSIST_DEBOUNCE_MS)
  }

  // --------------------------------------------------------------------------
  // 加载 session 历史（loadedSessions 防重复覆盖后台 SSE 增量）
  // --------------------------------------------------------------------------
  function loadSession(
    id: string,
    loadedSessions: Set<string>,
    messagesBySession: Record<string, ChatMessage[]>
  ) {
    if (loadedSessions.has(id)) return false
    loadedSessions.add(id)
    const saved = localStorage.getItem(`${MESSAGES_KEY_PREFIX}${id}`)
    if (saved) {
      try {
        messagesBySession[id] = JSON.parse(saved)
      } catch {
        messagesBySession[id] = []
      }
    } else {
      messagesBySession[id] = []
    }
    return true
  }

  // --------------------------------------------------------------------------
  // 持久化所有 session（卸载时用）
  // --------------------------------------------------------------------------
  function persistAll(
    messagesBySession: Record<string, ChatMessage[]>,
    currentSessionId: string
  ) {
    for (const id of Object.keys(messagesBySession)) {
      persistSessionSync(id, messagesBySession, currentSessionId)
    }
  }

  // --------------------------------------------------------------------------
  // 清除单 session 持久化
  // --------------------------------------------------------------------------
  function clearSession(id: string) {
    try {
      localStorage.removeItem(`${MESSAGES_KEY_PREFIX}${id}`)
    } catch { /* ignore */ }
  }

  return {
    persistSessionSync,
    persistSessionDebounced,
    loadSession,
    persistAll,
    clearSession,
  }
}

export default useChatStorage