import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useUserStore = defineStore('user', () => {
  // 状态
  const user = ref(null)
  const token = ref(localStorage.getItem('access_token') || '')
  const loading = ref(false)

  // 计算属性
  const isLoggedIn = computed(() => !!token.value)
  const username = computed(() => user.value?.username || '')
  const userInitial = computed(() => username.value.charAt(0) || '用')

  // 设置 token
  const setToken = (newToken) => {
    token.value = newToken
    localStorage.setItem('access_token', newToken)
  }

  // 清除 token
  const clearToken = () => {
    token.value = ''
    localStorage.removeItem('access_token')
  }

  // 登录
  const login = async (credentials) => {
    loading.value = true
    try {
      const response = await axios.post('/api/v1/auth/login', credentials)
      const { access_token, user: userData } = response.data
      setToken(access_token)
      user.value = userData
      return { success: true }
    } catch (error) {
      return {
        success: false,
        message: error.response?.data?.detail || '登录失败'
      }
    } finally {
      loading.value = false
    }
  }

  // 登出
  const logout = () => {
    clearToken()
    user.value = null
  }

  // 获取用户信息
  const fetchUser = async () => {
    if (!token.value) return

    try {
      const response = await axios.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      user.value = response.data
    } catch (error) {
      if (error.response?.status === 401) {
        clearToken()
      }
    }
  }

  // 更新用户信息
  const updateUser = async (userData) => {
    try {
      const response = await axios.put('/api/v1/auth/profile', userData, {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      user.value = response.data
      return { success: true }
    } catch (error) {
      return {
        success: false,
        message: error.response?.data?.detail || '更新失败'
      }
    }
  }

  // 初始化时获取用户信息
  if (token.value) {
    fetchUser()
  }

  return {
    user,
    token,
    loading,
    isLoggedIn,
    username,
    userInitial,
    setToken,
    clearToken,
    login,
    logout,
    fetchUser,
    updateUser
  }
})
