/**
 * useFileCommentsDesktop.ts — W68 路线 F-4 桌面端评论 composable
 *
 * 2026-07-24 主指挥协调范式第 45 守恒.
 *
 * 职责:
 * - 复用 useFileComments (W68 F-3) 的核心 API 调用
 * - 桌面端适配: RightClick 触发的 inline editor / resolved toggle / delete
 *   都通过 desktop-only adjust 包装 — 不污染 mobile store
 * - 文件元信息 fetch + members 批查 (用于 @mention autocomplete)
 *
 * 设计原则:
 * - 0 production code 改动铁律 — 复用 useFileComments + useNotifications store
 * - desktop-only adjust: 同 API 调用, 不同 UI binding (右键菜单触发)
 * - 不重新实现 API, 仅在 F-3 useFileComments 上加 desktop 适配
 *
 * 与 F-3 useFileComments 差异:
 * - F-3 是 mobile-only (long-press + 触觉反馈), 桌面走右键 + 无 vibrate
 * - F-4 加 fetchFileMeta + batchResolveMembers (desktop UI 完整化)
 * - F-4 加 onEditComment (5 分钟内 owner 可编辑, 桌面 inline edit)
 * - F-4 加 onMoveToTab (desktop 切换 resolved 过滤)
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
 * Desktop 文件评论 composable
 * @param {string|number|Ref<number|string>} fileId
 */
export function useFileCommentsDesktop(fileId) {
  // 内部 reactive fileId
  const _fileIdRef = typeof fileId === 'object' && 'value' in fileId ? fileId : ref(fileId)

  // 复用 F-3 核心逻辑 (list / post / postReply / delete / update / toggleResolved)
  const base = useFileComments(_fileIdRef)

  // === Desktop-only state ===
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
   * 桌面端编辑评论 — 复用 base.updateComment + 状态管理
   * @param {number} commentId
   * @param {string} newContent
   */
  async function onEditComment(commentId, newContent) {
    try {
      await base.updateComment(commentId, newContent)
      ElMessage.success('评论已更新')
      editingCommentId.value = null
      editDraft.value = ''
    } catch (e) {
      ElMessage.error(e?.response?.data?.error?.message || e?.message || '编辑失败')
    }
  }

  /**
   * 右键菜单触发的 resolved toggle — 走 base.toggleResolved
   * @param {object} comment - 评论对象
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
   * 右键菜单触发的删除评论 — 走 base.deleteComment
   * @param {object} comment
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
   * 右键菜单触发的回复评论 (跳到输入栏 + @ 该用户)
   * @param {object} comment
   * @returns {string} mention prefix to prepend
   */
  function onReplyPrefix(comment) {
    const userName = comment?.user_name || `用户 #${comment?.user_id}`
    return `@${userName} `
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

  // 计算属性: 按 activeTab 过滤
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
    // state
    fileMeta,
    membersList,
    usernameMap,
    editingCommentId,
    editDraft,
    activeTab,
    loadingMeta,
    currentUserId,
    isFileOwner,
    // base API
    comments: base.comments,
    loading: base.loading,
    posting: base.posting,
    error: base.error,
    total: base.total,
    openCount: base.openCount,
    resolvedCount: base.resolvedCount,
    filteredComments,
    // actions
    fetchFileMeta,
    batchResolveMembers,
    listComments: base.listComments,
    postComment: base.postComment,
    postReply: base.postReply,
    updateComment: base.updateComment,
    deleteComment: base.deleteComment,
    toggleResolved: base.toggleResolved,
    onEditComment,
    onToggleResolved,
    onDeleteComment,
    onReplyPrefix,
    startEditComment,
    cancelEditComment,
    switchTab,
  }
}

export default useFileCommentsDesktop