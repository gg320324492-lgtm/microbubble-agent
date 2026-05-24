import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useMemberStore = defineStore('member', () => {
  const members = ref([])
  const loading = ref(false)
  let lastFetchTime = 0
  const CACHE_DURATION = 60000 // 缓存1分钟

  async function fetchMembers(params = {}) {
    // 如果没有搜索参数且已有数据且缓存未过期，直接返回
    const now = Date.now()
    const hasSearchParams = params.name || params.grade
    if (!hasSearchParams && members.value.length > 0 && (now - lastFetchTime) < CACHE_DURATION) {
      return
    }

    loading.value = true
    try {
      const res = await axios.get('/api/v1/members', {
        params: { page_size: 100, ...params }
      })
      members.value = res.data.items || []
      lastFetchTime = now
    } catch (e) {
      console.error('获取成员列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  function getMemberName(id) {
    const m = members.value.find(m => m.id === id)
    return m ? m.name : '未分配'
  }

  function getMemberAvatar(id) {
    const m = members.value.find(m => m.id === id)
    return m?.avatar || null
  }

  return { members, loading, fetchMembers, getMemberName, getMemberAvatar }
})
