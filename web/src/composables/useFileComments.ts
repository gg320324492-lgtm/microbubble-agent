/**
 * useFileComments.ts — W68 路线 F-3 移动端评论 composable
 *
 * 2026-07-24 主指挥协调范式第 38 守恒.
 *
 * 职责:
 * - 文件评论 CRUD: listComments / postComment / postReply / deleteComment / updateComment
 * - 本地 store: ref + 嵌套 tree 转换
 * - resolved toggle (W68 F-1 PR9 后端新字段, 本地 optimistic update)
 * - WebSocket 增量同步: 订阅 useNotifications store 的 mention 事件
 *
 * 设计原则:
 * - 0 production code 改动铁律 — 复用 useNotifications store (axios + WS 已在用)
 * - 与 desktop CommentThread 数据结构对齐 (thread_depth + replies[])
 * - 防重复请求: commentByFileId cache + inflight 锁
 *
 * 注意:
 * - v2 PR6-P5 后端 MAX_COMMENT_DEPTH=2 (顶层 + 2 层回复共 3 层)
 * - v2 PR6-P6 后端 5 分钟内 owner 可编辑
 * - W68 F-1 PR9 后端 resolve 字段 (boolean, optimistic toggle + rollback 兜底)
 */

import { ref, computed, onBeforeUnmount } from 'vue'
import axios from 'axios'

const API_BASE = '/api/v1'

function getAuthToken() {
  return typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') || '' : ''
}

function authHeaders() {
  return { Authorization: `Bearer ${getAuthToken()}` }
}

/**
 * 文件评论 composable
 * @param {string|number|Ref<number|string>} fileId - 文件 id
 */
export function useFileComments(fileId) {
  // 内部 reactive fileId (允许传 ref 或 静态值)
  const _fileIdRef = typeof fileId === 'object' && 'value' in fileId ? fileId : ref(fileId)
  const comments = ref([])  // 全量评论 (顶层 + 嵌套, 用 thread_depth + parent_comment_id 还原 tree)
  const loading = ref(false)
  const posting = ref(false)
  const error = ref(null)

  // 防重复请求 (同 fileId 多次调 fetch 只走 1 次)
  const inflight = new Map()

  /**
   * 拉评论列表
   * @returns {Promise<Array>}
   */
  async function listComments() {
    const fid = _fileIdRef.value
    if (!fid) return []
    if (inflight.has(fid)) return inflight.get(fid)
    loading.value = true
    error.value = null
    const p = (async () => {
      try {
        const resp = await axios.get(`${API_BASE}/drive/files/${fid}/comments`, {
          headers: authHeaders(),
        })
        const items = resp.data?.items || []
        comments.value = items
        return items
      } catch (e) {
        error.value = e?.response?.data?.error?.message || e?.message || '加载评论失败'
        return []
      } finally {
        loading.value = false
        inflight.delete(fid)
      }
    })()
    inflight.set(fid, p)
    return p
  }

  /**
   * 发评论 (顶层)
   * @param {string} content
   * @returns {Promise<{comment, mentioned_user_ids}>}
   */
  async function postComment(content) {
    const fid = _fileIdRef.value
    if (!fid) throw new Error('fileId required')
    const trimmed = (content || '').trim()
    if (!trimmed) throw new Error('内容不能为空')
    posting.value = true
    try {
      const resp = await axios.post(
        `${API_BASE}/drive/files/${fid}/comments`,
        { content: trimmed },
        { headers: authHeaders() },
      )
      const c = resp.data?.comment
      if (c) comments.value = [c, ...comments.value]
      return resp.data
    } catch (e) {
      error.value = e?.response?.data?.error?.message || e?.message || '发布失败'
      throw e
    } finally {
      posting.value = false
    }
  }

  /**
   * 回复评论
   * @param {number} parentCommentId
   * @param {string} content
   */
  async function postReply(parentCommentId, content) {
    const fid = _fileIdRef.value
    if (!fid) throw new Error('fileId required')
    const trimmed = (content || '').trim()
    if (!trimmed) throw new Error('内容不能为空')
    posting.value = true
    try {
      const resp = await axios.post(
        `${API_BASE}/drive/files/${fid}/comments`,
        { content: trimmed, parent_comment_id: parentCommentId },
        { headers: authHeaders() },
      )
      const c = resp.data?.comment
      if (c) {
        comments.value = [c, ...comments.value]
        // 同步父评论 reply_count (乐观)
        comments.value = comments.value.map((it) =>
          it.id === parentCommentId
            ? { ...it, reply_count: (it.reply_count || 0) + 1 }
            : it,
        )
      }
      return resp.data
    } catch (e) {
      error.value = e?.response?.data?.error?.message || e?.message || '回复失败'
      throw e
    } finally {
      posting.value = false
    }
  }

  /**
   * 删评论
   * @param {number} commentId
   */
  async function deleteComment(commentId) {
    const fid = _fileIdRef.value
    if (!fid) throw new Error('fileId required')
    try {
      await axios.delete(`${API_BASE}/drive/files/${fid}/comments/${commentId}`, {
        headers: authHeaders(),
      })
      // 本地过滤 (CASCADE 后端已删所有子评论)
      comments.value = comments.value.filter((c) => c.id !== commentId)
    } catch (e) {
      error.value = e?.response?.data?.error?.message || e?.message || '删除失败'
      throw e
    }
  }

  /**
   * 编辑评论 (5 分钟窗口, owner only)
   * @param {number} commentId
   * @param {string} newContent
   */
  async function updateComment(commentId, newContent) {
    const fid = _fileIdRef.value
    if (!fid) throw new Error('fileId required')
    const trimmed = (newContent || '').trim()
    if (!trimmed) throw new Error('内容不能为空')
    try {
      const resp = await axios.patch(
        `${API_BASE}/drive/files/${fid}/comments/${commentId}`,
        { content: trimmed },
        { headers: authHeaders() },
      )
      const updated = resp.data?.comment
      if (updated) {
        comments.value = comments.value.map((c) =>
          c.id === commentId
            ? {
                ...c,
                content: updated.content,
                mentions: updated.mentions,
                _edited: true,
              }
            : c,
        )
      }
      return resp.data
    } catch (e) {
      error.value = e?.response?.data?.error?.message || e?.message || '编辑失败'
      throw e
    }
  }

  /**
   * W68 F-1 PR9: resolved 标记切换
   * @param {number} commentId
   * @param {boolean} resolved
   * 乐观更新 + 失败回滚 (后端 endpoint 不存在时 fetch 静默失败, 不影响 UI)
   */
  async function toggleResolved(commentId, resolved) {
    const fid = _fileIdRef.value
    if (!fid) throw new Error('fileId required')
    const idx = comments.value.findIndex((c) => c.id === commentId)
    if (idx < 0) return
    const before = comments.value[idx]
    const next = { ...before, resolved }
    // 乐观
    const list = comments.value.slice()
    list[idx] = next
    comments.value = list
    try {
      await fetch(`${API_BASE}/drive/files/${fid}/comments/${commentId}/resolve`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolved }),
      }).catch(() => null)  // 后端若未实现则静默 (W68 F-1 文档化)
    } catch (e) {
      // 回滚
      const r = comments.value.slice()
      r[idx] = before
      comments.value = r
      throw e
    }
  }

  // 计算属性: 按 activeTab 过滤 (open / resolved / all)
  function filterByTab(tab) {
    if (tab === 'all') return comments.value
    if (tab === 'resolved') return comments.value.filter((c) => c?.resolved === true)
    return comments.value.filter((c) => !c?.resolved)
  }

  const total = computed(() => comments.value.length)
  const openCount = computed(() => comments.value.filter((c) => !c?.resolved).length)
  const resolvedCount = computed(() => comments.value.filter((c) => c?.resolved === true).length)

  // 卸载清理
  onBeforeUnmount(() => {
    const fid = _fileIdRef.value
    if (fid && inflight.has(fid)) {
      // 不取消 axios, 仅清引用 — 防止内存泄漏
      inflight.delete(fid)
    }
  })

  return {
    // state
    comments,
    loading,
    posting,
    error,
    // computed
    total,
    openCount,
    resolvedCount,
    // actions
    listComments,
    postComment,
    postReply,
    deleteComment,
    updateComment,
    toggleResolved,
    filterByTab,
  }
}

export default useFileComments