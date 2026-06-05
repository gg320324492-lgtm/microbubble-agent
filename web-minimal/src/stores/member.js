import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useMemberStore = defineStore('member', () => {
  // 状态
  const members = ref([])
  const loading = ref(false)

  // 计算属性
  const memberMap = computed(() => {
    const map = {}
    members.value.forEach(m => {
      map[m.id] = m
    })
    return map
  })

  // 获取成员姓名
  const getMemberName = (memberId) => {
    return memberMap.value[memberId]?.name || '未知成员'
  }

  // 获取成员头像
  const getMemberAvatar = (memberId) => {
    return memberMap.value[memberId]?.avatar || ''
  }

  // 获取成员首字母
  const getMemberInitial = (memberId) => {
    const name = getMemberName(memberId)
    return name.charAt(0)
  }

  // 获取所有成员
  const fetchMembers = async () => {
    loading.value = true
    try {
      const response = await axios.get('/api/v1/members')
      members.value = response.data
    } catch (error) {
      console.error('获取成员列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  // 获取单个成员
  const fetchMember = async (memberId) => {
    try {
      const response = await axios.get(`/api/v1/members/${memberId}`)
      const index = members.value.findIndex(m => m.id === memberId)
      if (index !== -1) {
        members.value[index] = response.data
      } else {
        members.value.push(response.data)
      }
      return response.data
    } catch (error) {
      console.error('获取成员详情失败:', error)
      return null
    }
  }

  // 创建成员
  const createMember = async (memberData) => {
    try {
      const response = await axios.post('/api/v1/members', memberData)
      members.value.push(response.data)
      return { success: true, data: response.data }
    } catch (error) {
      return {
        success: false,
        message: error.response?.data?.detail || '创建失败'
      }
    }
  }

  // 更新成员
  const updateMember = async (memberId, memberData) => {
    try {
      const response = await axios.put(`/api/v1/members/${memberId}`, memberData)
      const index = members.value.findIndex(m => m.id === memberId)
      if (index !== -1) {
        members.value[index] = response.data
      }
      return { success: true, data: response.data }
    } catch (error) {
      return {
        success: false,
        message: error.response?.data?.detail || '更新失败'
      }
    }
  }

  // 删除成员
  const deleteMember = async (memberId) => {
    try {
      await axios.delete(`/api/v1/members/${memberId}`)
      members.value = members.value.filter(m => m.id !== memberId)
      return { success: true }
    } catch (error) {
      return {
        success: false,
        message: error.response?.data?.detail || '删除失败'
      }
    }
  }

  return {
    members,
    loading,
    memberMap,
    getMemberName,
    getMemberAvatar,
    getMemberInitial,
    fetchMembers,
    fetchMember,
    createMember,
    updateMember,
    deleteMember
  }
})
