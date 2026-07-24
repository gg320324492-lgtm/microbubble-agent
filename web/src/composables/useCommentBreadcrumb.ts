/**
 * useCommentBreadcrumb.ts — W68 第 9 批 B-3 嵌套评论 ancestor chain (面包屑) composable
 *
 * 2026-07-24 主指挥协调范式第 110 守恒 (桌面端 v3.2 收口).
 *
 * 职责:
 * - 拉取某评论的祖先链 (从顶层 → 直接父级), 用于嵌套 comment 顶部 breadcrumb 渲染
 * - 本地 cache (chainByComment) 避免重复请求 (同 commentId 只拉 1 次)
 * - 深链性能: 请求级 inflight 锁 + LRU-ish cache (依赖组件卸载清理)
 *
 * 后端 API 契约 (Drive v2 PR11):
 * - GET /api/v1/drive/comments/{id}/breadcrumb
 *   → { items: [{ id, user_id, username, snippet }] }  顶层在前, 直接父级在后 (不含自身)
 *
 * 设计原则:
 * - 0 production code 改动铁律 — 纯前端
 * - snippet 已由后端截断 (~40 字), 前端只负责渲染 + 溢出省略
 * - 后端 endpoint 未部署时静默降级 (返回 [], breadcrumb 不渲染, 不阻塞列表)
 */

import { ref } from 'vue'
import axios from 'axios'

const API_BASE = '/api/v1'
const MAX_SNIPPET_LEN = 40

function getAuthToken(): string {
  return typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') || '' : ''
}

function authHeaders() {
  return { Authorization: `Bearer ${getAuthToken()}` }
}

export interface BreadcrumbNode {
  id: number | string
  user_id: number | string
  username: string
  snippet: string
}

/**
 * 评论面包屑 composable
 */
export function useCommentBreadcrumb() {
  // { [commentId]: BreadcrumbNode[] }
  const chainByComment = ref<Record<string | number, BreadcrumbNode[]>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 防重复请求
  const inflight = new Map<string | number, Promise<BreadcrumbNode[]>>()

  function _truncate(s: string): string {
    const str = String(s || '')
    return str.length > MAX_SNIPPET_LEN ? str.slice(0, MAX_SNIPPET_LEN) + '…' : str
  }

  /**
   * 拉取某评论的祖先链
   * @param commentId
   * @param opts.force 强制刷新 (默认走 cache)
   */
  async function fetchBreadcrumb(commentId: string | number, opts: { force?: boolean } = {}) {
    if (commentId == null) return []
    if (!opts.force && chainByComment.value[commentId]) {
      return chainByComment.value[commentId]
    }
    if (inflight.has(commentId)) return inflight.get(commentId)!
    loading.value = true
    error.value = null
    const p = (async (): Promise<BreadcrumbNode[]> => {
      try {
        const resp = await axios.get(`${API_BASE}/drive/comments/${commentId}/breadcrumb`, {
          headers: authHeaders(),
        })
        const items: BreadcrumbNode[] = (resp.data?.items || []).map((n: any) => ({
          id: n.id,
          user_id: n.user_id,
          username: n.username || `用户 #${n.user_id}`,
          snippet: _truncate(n.snippet || n.content || ''),
        }))
        chainByComment.value = { ...chainByComment.value, [commentId]: items }
        return items
      } catch (e: any) {
        error.value = e?.response?.data?.error?.message || e?.message || '加载面包屑失败'
        // 静默降级: 缓存空数组避免重复请求
        chainByComment.value = { ...chainByComment.value, [commentId]: [] }
        return []
      } finally {
        loading.value = false
        inflight.delete(commentId)
      }
    })()
    inflight.set(commentId, p)
    return p
  }

  /**
   * 读取某评论的祖先链 (本地, 供模板绑定)
   */
  function breadcrumbFor(commentId: string | number): BreadcrumbNode[] {
    return chainByComment.value[commentId] || []
  }

  /**
   * 清 cache (fileId 切换时调用, 防跨文件串链)
   */
  function clear() {
    chainByComment.value = {}
    inflight.clear()
  }

  return {
    // state
    chainByComment,
    loading,
    error,
    // getters
    breadcrumbFor,
    // actions
    fetchBreadcrumb,
    clear,
  }
}

export default useCommentBreadcrumb
