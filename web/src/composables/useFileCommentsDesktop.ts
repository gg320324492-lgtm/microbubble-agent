/**
 * useFileCommentsDesktop.ts — 桌面端评论 composable (W85 B-2 P1-1 Step 1 thin-shell 兼容层)
 *
 * 历史: W68 路线 F-4 桌面端评论 composable (2026-07-24 主指挥协调范式第 45 守恒).
 * W85 第 1 批 B-2 P1 冗余重构 batch 3 (2026-07-29):
 * - Step 1 (本批): 收敛为 thin-shell — 核心 CRUD 100% 委派 useFileComments (F-3),
 *   UI 反馈适配 (ElMessage wrapper: onEditComment / onToggleResolved / onDeleteComment /
 *   onReplyPrefix) 已提取到 view 层 `web/src/views/desktop/DesktopFileCommentsView.vue`.
 *   本文件仅保留 desktop 数据层差异:
 *   - fetchFileMeta (文件元信息 header + isFileOwner 判断)
 *   - batchResolveMembers (@mention autocomplete + username 解析)
 *   - inline edit 状态 (editingCommentId + editDraft) + activeTab 过滤
 *   老 UI wrapper 以 @deprecated 兼容导出保留 (W82/W83/W84 B-2 拦截铁律: 分步走不删老).
 * - Step 2 (W86 后续 batch): 删 @deprecated wrapper + 评估整文件收敛.
 *
 * 设计原则:
 * - 0 production code 改动铁律例外已批 (W85 B-2 P1 重构 batch 3 派工批文)
 * - 不重新实现 API, 核心 list / post / postReply / delete / update / toggleResolved
 *   全部来自 useFileComments
 */

import { ref, computed, watch, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { useFileComments } from '@/composables/useFileComments'
import { ElMessage } from 'element-plus'

const API_BASE = '/api/v1'

function getAuthToken() {
  return typeof localStorage !== 'undefined' ? localStorage.getItem('access_token') || '' : ''
}

function authHeaders() {
  return { Authorization: `Bearer ${getAuthToken()}` }
}

/**
 * Desktop 文件评论 composable (thin-shell 委派 useFileComments 核心)
 * @param {string|number|Ref<number|string>} fileId
 */
export function useFileCommentsDesktop(fileId) {
  // 内部 reactive fileId
  const _fileIdRef = typeof fileId === 'object' && 'value' in fileId ? fileId : ref(fileId)

  // === 核心委派: F-3 useFileComments (list / post / postReply / delete / update / toggleResolved) ===
  const base = useFileComments(_fileIdRef)

  // === Desktop-only 数据层 state ===
  const fileMeta = ref({ id: null, title: '', file_name: '', owner_id: null })
  const membersList = ref([])
  const usernameMap = ref({})
  const editingCommentId = ref(null)
  const editDraft = ref('')
  const activeTab = ref('open')  // 'all' | 'open' | 'resolved'
  const loadingMeta = ref(false)

  /**
   * 拉文件元信息 (用于 header + isFileOwner 判断)
   */
  async function fetchFileMeta() {
    const fid = _fileIdRef.value
    if (!fid) return null
    loadingMeta.value = true
    try {
      const resp = await axios.get(`${API_BASE}/drive/files/${fid}`, {
        headers: authHeaders(),
      })
      fileMeta.value = resp.data || {}
      return fileMeta.value
    } catch (e) {
      console.error('[DesktopComments] fetchFileMeta failed:', e)
      return null
    } finally {
      loadingMeta.value = false
    }
  }

  /**
   * 批查 members (用于 @mention autocomplete + username 解析)
   */
  async function batchResolveMembers() {
    try {
      const resp = await axios.get(`${API_BASE}/members`, {
        headers: authHeaders(),
      })
      const items = resp.data?.items || []
      const map = {}
      for (const m of items) {
        map[m.id] = m.username || m.name
      }
      usernameMap.value = map
      if (membersList.value.length === 0) {
        membersList.value = items.map((m) => ({
          id: m.id,
          username: m.username,
          wechat_id: m.wechat_id,
          name: m.name,
          avatar: m.avatar,
          role: m.role,
        }))
      }
    } catch (e) {
      console.error('[DesktopComments] batchResolveMembers failed:', e)
    }
  }

  /**
   * 触发编辑评论 — 设置 editingCommentId + editDraft
   * @param {object} comment
   */
  function startEditComment(comment) {
    if (!comment || !comment.id) return
    editingCommentId.value = comment.id
    editDraft.value = comment.content || ''
  }

  function cancelEditComment() {
    editingCommentId.value = null
    editDraft.value = ''
  }

  /**
   * 切换 tab — 重新过滤
   */
  function switchTab(name) {
    activeTab.value = name
  }

  // 计算属性: 按 activeTab 过滤 (委派 base.filterByTab)
  const filteredComments = computed(() => base.filterByTab(activeTab.value))

  // 计算属性: 当前文件 owner
  const currentUserId = ref(null)
  // 尝试从 localStorage 读 user_id (兼容 userStore)
  try {
    const userInfo = JSON.parse(localStorage.getItem('user_info') || '{}')
    if (userInfo?.id) currentUserId.value = userInfo.id
  } catch {
    // ignore
  }
  const isFileOwner = computed(() => {
    if (!currentUserId.value || !fileMeta.value?.owner_id) return false
    return fileMeta.value.owner_id === currentUserId.value
  })

  // === W85 B-2 P1-1 Step 1: @deprecated UI wrapper 兼容层 ===
  // UI 反馈 (ElMessage) 适配已提取到 DesktopFileCommentsView.vue view 层.
  // 以下 wrapper 仅为老消费方兼容保留, W86 后续 batch Step 2 删除.

  /**
   * @deprecated W85 B-2 P1-1 — UI 适配已迁移到 view 层, 请在 view 内包装 base.updateComment
   */
  async function onEditComment(commentId, newContent) {
    try {
      await base.updateComment(commentId, newContent)
      ElMessage.success('评论已更新')
      cancelEditComment()
    } catch (e) {
      ElMessage.error(e?.response?.data?.error?.message || e?.message || '编辑失败')
    }
  }

  /**
   * @deprecated W85 B-2 P1-1 — UI 适配已迁移到 view 层, 请在 view 内包装 base.toggleResolved
   */
  async function onToggleResolved(comment) {
    if (!comment || !comment.id) return
    try {
      await base.toggleResolved(comment.id, !comment.resolved)
      ElMessage.success(comment.resolved ? '已标记为未解决' : '已标记为已解决')
    } catch (e) {
      ElMessage.error('操作失败: ' + (e?.message || '未知错误'))
    }
  }

  /**
   * @deprecated W85 B-2 P1-1 — UI 适配已迁移到 view 层, 请在 view 内包装 base.deleteComment
   */
  async function onDeleteComment(comment) {
    if (!comment || !comment.id) return
    try {
      await base.deleteComment(comment.id)
      ElMessage.success('评论已删除')
    } catch (e) {
      ElMessage.error(e?.response?.data?.error?.message || e?.message || '删除失败')
    }
  }

  /**
   * @deprecated W85 B-2 P1-1 — 纯 UI 逻辑已迁移到 view 层
   */
  function onReplyPrefix(comment) {
    const userName = comment?.user_name || `用户 #${comment?.user_id}`
    return `@${userName} `
  }

  // === 监听 fileId 切换 → 自动 reset state ===
  watch(_fileIdRef, (newId, oldId) => {
    if (newId !== oldId) {
      editingCommentId.value = null
      editDraft.value = ''
      activeTab.value = 'open'
    }
  })

  onBeforeUnmount(() => {
    editingCommentId.value = null
    editDraft.value = ''
  })

  return {
    // desktop state
    fileMeta,
    membersList,
    usernameMap,
    editingCommentId,
    editDraft,
    activeTab,
    loadingMeta,
    currentUserId,
    isFileOwner,
    // base API (thin-shell 委派)
    comments: base.comments,
    loading: base.loading,
    posting: base.posting,
    error: base.error,
    total: base.total,
    openCount: base.openCount,
    resolvedCount: base.resolvedCount,
    filteredComments,
    // desktop actions
    fetchFileMeta,
    batchResolveMembers,
    startEditComment,
    cancelEditComment,
    switchTab,
    // base actions (thin-shell 委派)
    listComments: base.listComments,
    postComment: base.postComment,
    postReply: base.postReply,
    updateComment: base.updateComment,
    deleteComment: base.deleteComment,
    toggleResolved: base.toggleResolved,
    // @deprecated 兼容层 (W86 Step 2 删)
    onEditComment,
    onToggleResolved,
    onDeleteComment,
    onReplyPrefix,
  }
}

export default useFileCommentsDesktop
