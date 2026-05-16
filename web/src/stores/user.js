import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref(null)
  const notificationCount = ref(0)

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

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_info')
    delete axios.defaults.headers.common['Authorization']
    userInfo.value = null
  }

  return { userInfo, notificationCount, username, userRole, loadFromStorage, fetchNotificationCount, logout }
})
