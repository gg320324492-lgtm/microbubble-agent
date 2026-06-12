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
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const STORAGE_KEY = 'chat_sessions_v3'
const CURRENT_KEY = 'chat_current_session_v3'

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { sessions: [], currentId: null }
    return JSON.parse(raw)
  } catch {
    return { sessions: [], currentId: null }
  }
}

function saveToStorage(sessions: ChatSession[], currentId: string | null) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
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
}

export const useChatSessionsStore = defineStore('chatSessions', () => {
  const initial = loadFromStorage()
  const sessions = ref<ChatSession[]>(initial.sessions || [])
  const currentId = ref<string | null>(initial.currentId)

  // 排序：按 updatedAt 倒序
  const sortedSessions = computed(() =>
    [...sessions.value].sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''))
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
      if (s.messageCount === 1 && lastMessage) {
        s.title = lastMessage.slice(0, 30)
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
      }
      sessions.value.push(session)
      currentId.value = oldId
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
  }
})
