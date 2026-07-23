/**
 * useNotifications.js — v2 PR6 通知 + 活动 + 评论 composable
 *
 * 提供:
 * - notifications[]: 当前用户 mentions (倒序)
 * - unreadCount: 未读数 (红点数字)
 * - commentsByFileId: { file_id: [comments] }
 *
 * 操作:
 * - fetchNotifications / fetchUnreadCount / markRead / markAllRead
 * - fetchComments / postComment / deleteComment
 *
 * 自动:
 * - WS 收到 'mention' 事件 → 增量 prepend notifications + 重新拉 unreadCount
 * - 30s polling unreadCount (兜底, WS 断时仍能显示)
 * - W68 PR8d: 客户端订阅 priority filter (?priority=high|medium|low)
 * - W68 PR8d: 离线消息 replay (reconnect 时 server 端自动 replayed, 前端监听 hello)
 * - W68 PR8d: heartbeat client (5s 自动响应 server ping)
 *
 * 注: 2026-07-03 用户决策"活动动态彻底删除" — activities state + fetchActivities +
 *     WS 'activity' handler 已删除. activity_service 后端仍保留 (驱动 audit log).
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import getWsClient from '@/utils/wsClient'

const API_BASE = '/api/v1'

// W68 PR8d: client-side heartbeat (响应 server 5s ping)
const HEARTBEAT_RESPONSE_TIMEOUT_MS = 8000  // 8s 没收到 server ping → 主动断

function getAuthToken() {
  return localStorage.getItem('access_token') || ''
}

export const useNotificationsStore = defineStore('notifications', () => {
  const notifications = ref([])
  const unreadCount = ref(0)
  const commentsByFileId = ref({})  // { file_id: [{ id, ... }] }
  const loadingNotifications = ref(false)
  const wsConnected = ref(false)
  // W68 PR8d: priority filter (UI 可调)
  const priorityFilter = ref(null)  // null = 全部, 或 'high' | 'medium' | 'low'
  const lastReplayed = ref(0)  // 最近一次 reconnect 补推条数
  let pollTimer = null
  let wsHandlersBound = false
  let heartbeatMonitorTimer = null
  let lastServerPingTs = 0  // 上次收到 server ping 的时间戳

  async function fetchNotifications(unreadOnly = false, limit = 50) {
    loadingNotifications.value = true
    try {
      const resp = await axios.get(`${API_BASE}/notifications`, {
        params: { unread_only: unreadOnly, limit },
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      })
      notifications.value = resp.data.items || []
      unreadCount.value = resp.data.unread_count || 0
      return resp.data
    } catch (e) {
      console.error('[Notify] fetchNotifications failed:', e)
      throw e
    } finally {
      loadingNotifications.value = false
    }
  }

  async function fetchUnreadCount() {
    try {
      const resp = await axios.get(`${API_BASE}/notifications/unread-count`, {
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      })
      unreadCount.value = resp.data.unread_count || 0
      return resp.data.unread_count
    } catch (e) {
      console.debug('[Notify] fetchUnreadCount failed:', e)
      return 0
    }
  }

  async function markRead(mentionId) {
    try {
      await axios.post(
        `${API_BASE}/notifications/${mentionId}/read`,
        {},
        { headers: { Authorization: `Bearer ${getAuthToken()}` } }
      )
      const item = notifications.value.find((n) => n.id === mentionId)
      if (item && !item.is_read) {
        item.is_read = true
        item.read_at = new Date().toISOString()
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
    } catch (e) {
      console.error('[Notify] markRead failed:', e)
    }
  }

  async function markAllRead() {
    try {
      const resp = await axios.post(
        `${API_BASE}/notifications/read-all`,
        {},
        { headers: { Authorization: `Bearer ${getAuthToken()}` } }
      )
      notifications.value.forEach((n) => {
        n.is_read = true
        n.read_at = new Date().toISOString()
      })
      unreadCount.value = 0
      return resp.data.marked_count
    } catch (e) {
      console.error('[Notify] markAllRead failed:', e)
    }
  }

  async function fetchComments(fileId) {
    try {
      const resp = await axios.get(`${API_BASE}/drive/files/${fileId}/comments`, {
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      })
      commentsByFileId.value = { ...commentsByFileId.value, [fileId]: resp.data.items || [] }
      return resp.data.items
    } catch (e) {
      console.error('[Notify] fetchComments failed:', e)
      return []
    }
  }

  async function postComment(fileId, content) {
    try {
      const resp = await axios.post(
        `${API_BASE}/drive/files/${fileId}/comments`,
        { content },
        { headers: { Authorization: `Bearer ${getAuthToken()}` } }
      )
      // prepend to local cache
      const existing = commentsByFileId.value[fileId] || []
      commentsByFileId.value = {
        ...commentsByFileId.value,
        [fileId]: [resp.data.comment, ...existing],
      }
      return resp.data
    } catch (e) {
      console.error('[Notify] postComment failed:', e)
      throw e
    }
  }

  /**
   * v2 PR6-P5: 回复评论 (threading)
   * @param fileId - 文件 id
   * @param parentCommentId - 父评论 id
   * @param content - 回复内容
   * 422 错误 (parent 不存在 / 跨文件 / 深度超限) 抛 error 让 caller 处理
   */
  async function postReply(fileId, parentCommentId, content) {
    try {
      const resp = await axios.post(
        `${API_BASE}/drive/files/${fileId}/comments`,
        { content, parent_comment_id: parentCommentId },
        { headers: { Authorization: `Bearer ${getAuthToken()}` } }
      )
      const existing = commentsByFileId.value[fileId] || []
      const updated = existing.map((c) => {
        if (c.id === parentCommentId) {
          return { ...c, reply_count: (c.reply_count || 0) + 1 }
        }
        return c
      })
      commentsByFileId.value = {
        ...commentsByFileId.value,
        [fileId]: [resp.data.comment, ...updated],
      }
      return resp.data
    } catch (e) {
      console.error('[Notify] postReply failed:', e)
      throw e
    }
  }

  async function deleteComment(fileId, commentId) {
    try {
      await axios.delete(`${API_BASE}/drive/files/${fileId}/comments/${commentId}`, {
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      })
      const existing = commentsByFileId.value[fileId] || []
      commentsByFileId.value = {
        ...commentsByFileId.value,
        [fileId]: existing.filter((c) => c.id !== commentId),
      }
    } catch (e) {
      console.error('[Notify] deleteComment failed:', e)
    }
  }

  /**
   * v2 PR6-P6: 编辑评论 (owner only, 5 分钟窗口)
   * @param fileId - 文件 id
   * @param commentId - 评论 id
   * @param newContent - 新内容
   * @returns {Promise<{ comment, mentioned_user_ids }>}
   *
   * 422 错误 (评论不存在 / 无权编辑 / 编辑窗口已过 / 内容空/超长)
   * 全部抛 error, caller 用 try/catch + ElMessage 处理
   */
  async function updateComment(fileId, commentId, newContent) {
    try {
      const resp = await axios.patch(
        `${API_BASE}/drive/files/${fileId}/comments/${commentId}`,
        { content: newContent },
        { headers: { Authorization: `Bearer ${getAuthToken()}` } }
      )
      // 本地替换原 comment 的 content + mentions (其他字段不动)
      const existing = commentsByFileId.value[fileId] || []
      const updated = existing.map((c) => {
        if (c.id === commentId) {
          return {
            ...c,
            content: resp.data.comment.content,
            mentions: resp.data.comment.mentions,
          }
        }
        return c
      })
      commentsByFileId.value = {
        ...commentsByFileId.value,
        [fileId]: updated,
      }
      return resp.data
    } catch (e) {
      console.error('[Notify] updateComment failed:', e)
      throw e
    }
  }

  function bindWsHandlers() {
    if (wsHandlersBound) return
    const ws = getWsClient()
    ws.on('open', () => {
      wsConnected.value = true
      // W68 PR8d: 启动 heartbeat monitor (8s 没收到 server ping → 主动断)
      startHeartbeatMonitor()
    })
    ws.on('close', () => {
      wsConnected.value = false
      stopHeartbeatMonitor()
    })
    // W68 PR8d: 监听 hello 事件 (含 priority_filter + replayed 离线条数)
    ws.on('hello', (data) => {
      if (typeof data?.replayed === 'number') {
        lastReplayed.value = data.replayed
        if (data.replayed > 0) {
          console.info(`[Notify] W68 reconnect: ${data.replayed} 条离线消息已补推`)
          // 主动拉一次 unreadCount 同步
          fetchUnreadCount()
        }
      }
    })
    // W68 PR8d: 监听 server 主动 ping (5s 一次), 用于 client-side heartbeat
    ws.on('ping', (_data) => {
      lastServerPingTs = Date.now()
    })
    // W68 PR8d: 监听 batch 事件 (3s 内合并的多条通知)
    ws.on('batch', (data) => {
      const count = data?.count || 0
      const key = data?.batch_key || 'unknown'
      import('element-plus').then(({ ElMessage }) => {
        ElMessage.info({
          message: `${key} 有 ${count} 条新通知 (批量)`,
          duration: 2500,
          grouping: true,
        })
      }).catch(() => {})
    })
    ws.on('mention', async (data) => {
      // v2 PR6-P7: merged=true 表示这是 5s dedup 命中, 重复已合并到现有 row
      if (data.merged) {
        // 找到已存在的同 id row, 替换 updated (含新 repeated_count + 新 created_at + 新 title/body)
        const existingIdx = notifications.value.findIndex((n) => n.id === data.id)
        if (existingIdx !== -1) {
          notifications.value = [
            {
              ...notifications.value[existingIdx],
              repeated_count: data.repeated_count || 1,
              created_at: data.created_at || new Date().toISOString(),
              mentioned_by: data.mentioned_by,
              // v2 PR6-P8: rich metadata 更新 (重复最新 preview/file_type)
              title: data.title ?? notifications.value[existingIdx].title,
              body: data.body ?? notifications.value[existingIdx].body,
              file_name: data.file_name ?? notifications.value[existingIdx].file_name,
              file_type: data.file_type ?? notifications.value[existingIdx].file_type,
            },
            ...notifications.value.slice(0, existingIdx),
            ...notifications.value.slice(existingIdx + 1),
          ]
        }
        // dedup 命中: 红点**不增** (代表同一逻辑通知), 弹 toast 提示
        // ElMessage 是动态 import 避免 SSR 报错
        import('element-plus').then(({ ElMessage }) => {
          ElMessage.info({
            message: `已合并 ${data.repeated_count} 条类似通知 (5 秒内)`,
            duration: 2500,
            grouping: true,
          })
        }).catch(() => {})
        return
      }
      // 首次创建: 增量 prepend (避免重拉)
      notifications.value = [
        {
          id: data.id,
          file_id: data.file_id,
          file_name: data.file_name,  // v2 PR6-P8: rich
          file_type: data.file_type,  // v2 PR6-P8: rich
          mentioned_by: data.mentioned_by,
          context: data.context,
          is_read: false,
          repeated_count: data.repeated_count || 1,
          created_at: data.created_at || new Date().toISOString(),
          title: data.title,  // v2 PR6-P8: rich
          body: data.body,    // v2 PR6-P8: rich
          // W68 PR8d: priority 字段 (UI 可按 priority 区分样式)
          priority: data.priority || 'medium',
        },
        ...notifications.value,
      ]
      unreadCount.value = unreadCount.value + 1
    })
    wsHandlersBound = true
  }

  /**
   * W68 PR8d: client-side heartbeat monitor
   * - 监听 server 5s 一次 ping (data.ts 更新)
   * - 8s 没收到 server ping → 主动 disconnect 让 reconnect 逻辑兜底
   * - 不主动发 ping (server 主动 ping 我们, 我们只被动响应)
   */
  function startHeartbeatMonitor() {
    stopHeartbeatMonitor()
    lastServerPingTs = Date.now()
    heartbeatMonitorTimer = setInterval(() => {
      if (Date.now() - lastServerPingTs > HEARTBEAT_RESPONSE_TIMEOUT_MS) {
        console.warn('[Notify] W68 heartbeat timeout, forcing reconnect')
        const ws = getWsClient()
        ws.disconnect()
        // 触发 reconnect (3s 后)
        setTimeout(() => {
          startWs()
        }, 3000)
      }
    }, 3000)  // 每 3s 检查一次
  }

  function stopHeartbeatMonitor() {
    if (heartbeatMonitorTimer) {
      clearInterval(heartbeatMonitorTimer)
      heartbeatMonitorTimer = null
    }
  }

  /**
   * W68 PR8d: 设置 priority filter (UI 开关)
   * 改变后会自动重连 WS 走新的 ?priority=...
   * @param {string|null} priority - 'high' | 'medium' | 'low' | null (全部)
   */
  function setPriorityFilter(priority) {
    const validPriorities = ['high', 'medium', 'low', null]
    if (!validPriorities.includes(priority)) {
      console.warn(`[Notify] invalid priority: ${priority}, use one of`, validPriorities)
      return
    }
    if (priorityFilter.value === priority) return
    priorityFilter.value = priority
    // 重连 WS 走新 priority
    stopWs()
    setTimeout(() => startWs(), 100)
  }

  function startWs() {
    const token = getAuthToken()
    if (!token) return
    const ws = getWsClient()
    bindWsHandlers()
    // W68 PR8d: 传入 priority filter (?priority=high|medium|low)
    ws.connect(token, { priority: priorityFilter.value })
  }

  function stopWs() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    stopHeartbeatMonitor()  // W68 PR8d
    const ws = getWsClient()
    ws.disconnect()
    wsConnected.value = false
  }

  function startPolling(intervalMs = 30000) {
    if (pollTimer) return
    pollTimer = setInterval(() => {
      fetchUnreadCount()
    }, intervalMs)
  }

  return {
    notifications,
    unreadCount,
    commentsByFileId,
    loadingNotifications,
    wsConnected,
    priorityFilter,       // W68 PR8d
    lastReplayed,         // W68 PR8d
    fetchNotifications,
    fetchUnreadCount,
    markRead,
    markAllRead,
    fetchComments,
    postComment,
    postReply,
    updateComment,
    deleteComment,
    startWs,
    stopWs,
    startPolling,
    setPriorityFilter,    // W68 PR8d
  }
})

export function useNotifications() {
  const store = useNotificationsStore()
  return {
    store,
    ...store,
  }
}

export default useNotifications