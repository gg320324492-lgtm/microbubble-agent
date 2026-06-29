import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref(null)
  const notificationCount = ref(0)
  const notifications = ref([])

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

  async function fetchNotificationCount() {
    try {
      const res = await axios.get('/api/v1/reminders/pending-count')
      notificationCount.value = res.data.count || 0
    } catch {
      notificationCount.value = 0
    }
  }

  async function fetchNotifications() {
    try {
      const res = await axios.get('/api/v1/reminders')
      notifications.value = res.data.reminders || []
    } catch {
      notifications.value = []
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
  }

  return { userInfo, notificationCount, notifications, username, userRole, loadFromStorage, fetchNotificationCount, fetchNotifications, logout }
})
