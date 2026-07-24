/**
 * useCommentReactions.ts — W68 第 9 批 B-3 桌面/移动 评论 emoji 表情反应 composable
 *
 * 2026-07-24 主指挥协调范式第 110 守恒 (桌面端 v3.2 收口).
 *
 * 职责:
 * - emoji 表情反应 CRUD: fetchReactions / addReaction / removeReaction / toggleReaction
 * - 本地 store: reactionsByComment (Map<commentId, EmojiSummary[]>)
 * - 乐观更新 + 失败 rollback (与 useFileComments.toggleResolved 模式对齐)
 * - 12 emoji 白名单 (前端强校验, 后端二次校验)
 *
 * 后端 API 契约 (Drive v2 PR12):
 * - GET    /api/v1/drive/reactions?comment_ids=1,2,3
 *          → { items: { [commentId]: [{ emoji, count, reacted_by_me, user_ids }] } }
 * - POST   /api/v1/drive/reactions  { comment_id, emoji }
 *          → { comment_id, emoji, count, reacted_by_me }
 * - DELETE /api/v1/drive/reactions  { comment_id, emoji }
 *          → { comment_id, emoji, count, reacted_by_me }
 *
 * 设计原则:
 * - 0 production code 改动铁律 — 纯前端, 复用 axios + localStorage token
 * - 桌面 (DesktopCommentThread) + 移动 (MobileCommentThread) parity: 一次实现两处用
 * - 白名单集中管理 — 桌面/移动/e2e 都 import EMOJI_WHITELIST 单一真源
 * - 后端 endpoint 未部署时静默降级 (乐观值保留, 不阻塞 UI, 与 F-1 resolve 模式一致)
 */

import { ref, computed } from 'vue'
import axios from 'axios'

const API_BASE = '/api/v1'

/**
 * 12 emoji 白名单 (单一真源, 桌面/移动/e2e 共享)
 * 顺序即工具栏渲染顺序. 修改必须同步后端白名单 (PR12 REACTION_EMOJI_WHITELIST).
 */
export const EMOJI_WHITELIST = [
  '👍', '❤️', '🎉', '😂', '😮', '😢',
  '🔥', '💯', '✨', '🙏', '🤔', '👀',
]

function isValidEmoji(emoji: string): boolean {
  return EMOJI_WHITELIST.includes(emoji)
}

function getAuthToken(): string {
  return typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') || '' : ''
}

function authHeaders() {
  return { Authorization: `Bearer ${getAuthToken()}` }
}

/**
 * emoji 反应 composable
 */
export function useCommentReactions() {
  // reactionsByComment: { [commentId]: [{ emoji, count, reacted_by_me }] }
  const reactionsByComment = ref<Record<string | number, Array<{ emoji: string; count: number; reacted_by_me: boolean }>>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  /**
   * 拉取一批评论的反应汇总
   * @param commentIds 评论 id 数组
   */
  async function fetchReactions(commentIds: Array<string | number>) {
    const ids = (commentIds || []).filter((x) => x != null)
    if (ids.length === 0) return {}
    loading.value = true
    error.value = null
    try {
      const resp = await axios.get(`${API_BASE}/drive/reactions`, {
        headers: authHeaders(),
        params: { comment_ids: ids.join(',') },
      })
      const items = resp.data?.items || {}
      // merge (不覆盖其他已存在评论的反应)
      reactionsByComment.value = { ...reactionsByComment.value, ...items }
      return items
    } catch (e: any) {
      error.value = e?.response?.data?.error?.message || e?.message || '加载表情反应失败'
      return {}
    } finally {
      loading.value = false
    }
  }

  /**
   * 读取某评论某 emoji 的当前汇总 (本地)
   */
  function _summaryFor(commentId: string | number, emoji: string) {
    const list = reactionsByComment.value[commentId] || []
    return list.find((r) => r.emoji === emoji) || null
  }

  /**
   * 本地乐观写入 (delta = +1 添加 / -1 移除)
   */
  function _applyLocal(commentId: string | number, emoji: string, reacted: boolean) {
    const list = (reactionsByComment.value[commentId] || []).slice()
    const idx = list.findIndex((r) => r.emoji === emoji)
    if (idx >= 0) {
      const cur = list[idx]
      const nextCount = Math.max(0, cur.count + (reacted ? 1 : -1))
      if (nextCount === 0) {
        list.splice(idx, 1)  // count 归零 → 移除该 emoji 条目
      } else {
        list[idx] = { ...cur, count: nextCount, reacted_by_me: reacted }
      }
    } else if (reacted) {
      list.push({ emoji, count: 1, reacted_by_me: true })
    }
    reactionsByComment.value = { ...reactionsByComment.value, [commentId]: list }
  }

  /**
   * 添加反应 (乐观 + rollback)
   */
  async function addReaction(commentId: string | number, emoji: string) {
    if (!isValidEmoji(emoji)) throw new Error(`不支持的 emoji: ${emoji}`)
    const before = _summaryFor(commentId, emoji)
    if (before?.reacted_by_me) return  // 已 react 幂等
    _applyLocal(commentId, emoji, true)
    try {
      const resp = await axios.post(
        `${API_BASE}/drive/reactions`,
        { comment_id: commentId, emoji },
        { headers: authHeaders() },
      )
      // 用服务端权威 count 校准
      _reconcile(commentId, resp.data)
      return resp.data
    } catch (e: any) {
      _applyLocal(commentId, emoji, false)  // rollback
      error.value = e?.response?.data?.error?.message || e?.message || '添加表情失败'
      throw e
    }
  }

  /**
   * 移除反应 (乐观 + rollback)
   */
  async function removeReaction(commentId: string | number, emoji: string) {
    if (!isValidEmoji(emoji)) throw new Error(`不支持的 emoji: ${emoji}`)
    const before = _summaryFor(commentId, emoji)
    if (!before?.reacted_by_me) return  // 未 react 幂等
    _applyLocal(commentId, emoji, false)
    try {
      const resp = await axios.delete(`${API_BASE}/drive/reactions`, {
        headers: authHeaders(),
        data: { comment_id: commentId, emoji },
      })
      _reconcile(commentId, resp.data)
      return resp.data
    } catch (e: any) {
      _applyLocal(commentId, emoji, true)  // rollback
      error.value = e?.response?.data?.error?.message || e?.message || '移除表情失败'
      throw e
    }
  }

  /**
   * 切换反应 — 已 react 则移除, 否则添加
   */
  async function toggleReaction(commentId: string | number, emoji: string) {
    const cur = _summaryFor(commentId, emoji)
    if (cur?.reacted_by_me) return removeReaction(commentId, emoji)
    return addReaction(commentId, emoji)
  }

  /**
   * 用服务端权威值校准某评论某 emoji (count + reacted_by_me)
   */
  function _reconcile(commentId: string | number, payload: any) {
    if (!payload || !payload.emoji) return
    const list = (reactionsByComment.value[commentId] || []).slice()
    const idx = list.findIndex((r) => r.emoji === payload.emoji)
    const count = typeof payload.count === 'number' ? payload.count : 0
    if (count <= 0) {
      if (idx >= 0) list.splice(idx, 1)
    } else if (idx >= 0) {
      list[idx] = { emoji: payload.emoji, count, reacted_by_me: !!payload.reacted_by_me }
    } else {
      list.push({ emoji: payload.emoji, count, reacted_by_me: !!payload.reacted_by_me })
    }
    reactionsByComment.value = { ...reactionsByComment.value, [commentId]: list }
  }

  /**
   * 某评论的反应汇总 (供模板绑定)
   */
  function reactionsFor(commentId: string | number) {
    return reactionsByComment.value[commentId] || []
  }

  /**
   * 某评论的反应总数 (跨 emoji 求和)
   */
  const totalReactions = computed(() => {
    let sum = 0
    for (const list of Object.values(reactionsByComment.value)) {
      for (const r of list) sum += r.count
    }
    return sum
  })

  return {
    // state
    reactionsByComment,
    loading,
    error,
    // computed / getters
    totalReactions,
    reactionsFor,
    // actions
    fetchReactions,
    addReaction,
    removeReaction,
    toggleReaction,
    // constants / helpers
    EMOJI_WHITELIST,
    isValidEmoji,
  }
}

export default useCommentReactions
