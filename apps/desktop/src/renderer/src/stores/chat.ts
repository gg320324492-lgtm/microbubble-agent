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

  async function send(content: string): Promise<{ userMessage: ChatMessage; assistantMessage: ChatMessage }> {
    if (!activeId.value) throw new Error('未选择会话')
    const sessionId = activeId.value
    // DL-6 乐观上屏：真实模型时代 CHAT_SEND 悬置数秒~分钟，用户消息必须即时可见。
    // temp- 前缀与主进程 m- 前缀不冲突：成功被真实结果原位替换，失败即移除，无残留。
    const optimistic: ChatMessage = {
      id: `temp-${Date.now()}`,
      sessionId,
      role: 'user',
      content,
      meta: null,
      createdAt: Date.now()
    }
    messages.value.push(optimistic)
    let result: { userMessage: ChatMessage; assistantMessage: ChatMessage }
    try {
      result = await window.api.chat.send(sessionId, content)
    } catch (e) {
      // 失败路径：按引用定位移除临时条目再抛错（ChatPanel 会回填草稿）
      const idx = messages.value.indexOf(optimistic)
      if (idx !== -1) messages.value.splice(idx, 1)
      throw e
    }
    // 原位替换临时条目（引用定位，不受并发插入影响），再追加 assistant 回复
    const idx = messages.value.indexOf(optimistic)
    if (idx !== -1) messages.value.splice(idx, 1, result.userMessage)
    else messages.value.push(result.userMessage)
    messages.value.push(result.assistantMessage)
    // 标题可能因首条消息自动生成，刷新列表
    await refreshSessions()
    return result
  }

  return { sessions, activeId, messages, loadingList, refreshSessions, select, create, rename, remove, send }
})
