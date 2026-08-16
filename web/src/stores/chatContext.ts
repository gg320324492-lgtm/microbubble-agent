// chatContext.ts — 跨页 Pinia store: 聊天 ↔ 知识库 附加文档
//
// 2026-08-15 #P5: 升级为**服务端权威**模式 (之前是进程内内存态, 刷新即失)
// - 用户全局附加文档 (跨 session 复用, 像 ChatGPT Project Memory)
// - 启动调 /api/v1/chat/attached-documents 加载
// - add/remove/clear 都调后端 API
// - 乐观更新 + 失败回滚
//
// 旧字段 (selectingForChat, sourceSessionId) 保留兼容 KnowledgeView 选择模式

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export interface AttachedDocument {
  id: number
  title: string
  category?: string | null
  snippet?: string | null
  attached_at: string
  // 内部标记 (不写到后端, 仅前端 transient state)
  _pending?: boolean
}

export const useChatContextStore = defineStore('chatContext', () => {
  /** 用户全局附加文档 (从 server 加载) */
  const attachedDocuments = ref<AttachedDocument[]>([])

  /** 加载状态 */
  const loading = ref(false)

  /** 选择模式标记 (KnowledgeView banner 控制) */
  const selectingForChat = ref(false)
  const sourceSessionId = ref<string | null>(null)

  /** 硬上限 (与后端 MAX_ATTACHED_PER_USER 一致) */
  const MAX_ATTACHED = 8

  // ============================================================================
  // 服务端交互
  // ============================================================================

  /** 启动时加载 (ChatViewSSE.onMounted 调用) */
  async function loadFromServer() {
    loading.value = true
    try {
      const res = await axios.get('/api/v1/chat/attached-documents')
      const data = Array.isArray(res.data) ? res.data : []
      attachedDocuments.value = data.map(d => ({
        id: d.id,
        title: d.title,
        category: d.category ?? null,
        snippet: d.snippet ?? null,
        attached_at: d.attached_at,
      }))
    } catch (e) {
      // best-effort: 加载失败保持空列表, 用户可手动刷新
      console.warn('[chatContext] loadFromServer failed', e)
      attachedDocuments.value = []
    } finally {
      loading.value = false
    }
  }

  /** 附加文档 (乐观更新 + 后端落库) */
  async function add(item: { id: number; title: string; category?: string | null; snippet?: string | null }) {
    if (!item || item.id == null) return
    if (attachedDocuments.value.find(x => x.id === item.id)) return  // 幂等
    if (attachedDocuments.value.length >= MAX_ATTACHED) {
      throw new Error(`最多附加 ${MAX_ATTACHED} 个文档`)
    }

    // 乐观更新
    const tempDoc: AttachedDocument = {
      id: item.id,
      title: item.title,
      category: item.category ?? null,
      snippet: item.snippet ?? null,
      attached_at: new Date().toISOString(),
      _pending: true,
    }
    attachedDocuments.value.push(tempDoc)

    try {
      await axios.post(`/api/v1/chat/attached-documents/${item.id}`)
      tempDoc._pending = false
    } catch (e: any) {
      // 回滚
      attachedDocuments.value = attachedDocuments.value.filter(x => x.id !== item.id)
      const msg = e?.response?.data?.detail || e?.message || '附加失败'
      throw new Error(msg)
    }
  }

  /** 移除文档 (乐观更新 + 后端删除) */
  async function remove(id: number) {
    const before = [...attachedDocuments.value]
    attachedDocuments.value = attachedDocuments.value.filter(x => x.id !== id)

    try {
      await axios.delete(`/api/v1/chat/attached-documents/${id}`)
    } catch (e: any) {
      // 回滚
      attachedDocuments.value = before
      const msg = e?.response?.data?.detail || e?.message || '移除失败'
      throw new Error(msg)
    }
  }

  /** 清空所有 (乐观更新 + 后端清空) */
  async function clear() {
    const before = [...attachedDocuments.value]
    attachedDocuments.value = []

    try {
      await axios.delete('/api/v1/chat/attached-documents')
    } catch (e: any) {
      attachedDocuments.value = before
      const msg = e?.response?.data?.detail || e?.message || '清空失败'
      throw new Error(msg)
    }
  }

  // ============================================================================
  // 选择模式 (KnowledgeView banner 控制)
  // ============================================================================

  function startSelecting(sessionId: string) {
    selectingForChat.value = true
    sourceSessionId.value = sessionId
  }

  function finishSelecting() {
    selectingForChat.value = false
  }

  const count = computed(() => attachedDocuments.value.length)
  const isAttached = computed(() => attachedDocuments.value.length > 0)
  // #P5+: 消息气泡显示附加文档列表 (按 ID 查 store)
  function getDocsByIds(ids: number[]) {
    if (!ids || ids.length === 0) return []
    return attachedDocuments.value.filter(d => ids.includes(d.id))
  }

  return {
    attachedDocuments,
    loading,
    selectingForChat,
    sourceSessionId,
    count,
    isAttached,
    loadFromServer,
    add,
    remove,
    clear,
    startSelecting,
    finishSelecting,
    getDocsByIds,
  }
})