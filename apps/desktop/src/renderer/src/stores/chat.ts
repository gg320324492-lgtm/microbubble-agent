// 会话状态 — 列表/当前会话/消息，经 window.api 落 SQLite
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage, ChatSession } from '@shared/types'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const activeId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const loadingList = ref(false)

  async function refreshSessions(): Promise<void> {
    loadingList.value = true
    try {
      sessions.value = await window.api.chat.sessionsList()
    } finally {
      loadingList.value = false
    }
  }

  async function select(id: string | null): Promise<void> {
    activeId.value = id
    messages.value = id ? await window.api.chat.messagesList(id) : []
  }

  async function create(title?: string): Promise<void> {
    const s = await window.api.chat.sessionCreate(title)
    await refreshSessions()
    await select(s.id)
  }

  async function rename(id: string, title: string): Promise<void> {
    await window.api.chat.sessionRename(id, title)
    await refreshSessions()
  }

  async function remove(id: string): Promise<void> {
    await window.api.chat.sessionDelete(id)
    if (activeId.value === id) await select(null)
    await refreshSessions()
  }

  async function send(content: string): Promise<void> {
    if (!activeId.value) throw new Error('未选择会话')
    const { userMessage, assistantMessage } = await window.api.chat.send(activeId.value, content)
    messages.value.push(userMessage, assistantMessage)
    // 标题可能因首条消息自动生成，刷新列表
    await refreshSessions()
  }

  return { sessions, activeId, messages, loadingList, refreshSessions, select, create, rename, remove, send }
})
