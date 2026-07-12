import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref(null)

  const username = computed(() => userInfo.value?.name || '用户')
  const userRole = computed(() => {
    const roleMap = { admin: '管理员', leader: '组长', member: '成员' }
    return roleMap[userInfo.value?.role] || '成员'
  })

  function loadFromStorage() {
    const info = localStorage.getItem('user_info')
    if (info) {
      userInfo.value = JSON.parse(info)
    }
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_info')
    delete axios.defaults.headers.common['Authorization']
    userInfo.value = null

    // #043: 退出登录清空 chatHistory store（防止下一用户看到上一用户数据 = 越权）
    // CLAUDE.md 2026-06-15 "退出登录清空" 铁律
    import('@/stores/chatHistory').then(({ useChatHistoryStore }) => {
      try {
        useChatHistoryStore().reset()
      } catch (e) { /* store 没初始化也无害 */ }
    })

    // ★ 2026-07-01 修复 bug 1c: 退出登录时清空所有 chat 相关 localStorage
    // 防御跨用户污染：用户 A 的 sessionId 留在 localStorage → 用户 B 登录后
    // 用 A 的 sessionId 发请求 → 后端 ensure_session_for_stream 看到
    // session_id 不属于 B → 静默创建新行(标题"新对话") → 重复 bug
    const CHAT_KEYS = [
      'chat_sessions_v3',
      'chat_current_session_v3',
      'chat_migrated_v1',
      'mnb:search_analytics:session_id',
    ]
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i)
      if (!k) continue
      if (
        k.startsWith('chat_sessions_v3__u') ||
        k.startsWith('chat_current_session_v3__u') ||
        k.startsWith('chat_msgs_') ||
        k === 'chat_messages_v2' || k === 'chat_session_id' || k === 'chat_messages_v1'
      ) {
        localStorage.removeItem(k)
      }
    }
    CHAT_KEYS.forEach(k => localStorage.removeItem(k))

    // 同步重置 chatSessions store（in-memory）— 防止下次登录沿用旧 sessions 数组
    import('@/stores/chatSessions').then(({ useChatSessionsStore }) => {
      try {
        useChatSessionsStore().$reset()
      } catch (e) { /* store 没初始化也无害 */ }
    })
  }

  return { userInfo, username, userRole, loadFromStorage, logout }
})
