import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useMemberStore = defineStore('member', () => {
  const members = ref([])
  const loading = ref(false)

  async function fetchMembers() {
    if (members.value.length > 0) return
    loading.value = true
    try {
      const res = await axios.get('/api/v1/members', { params: { page_size: 100 } })
      members.value = res.data.items || []
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

  function getMemberById(id) {
    return members.value.find(m => m.id === id) || null
  }

  return { members, loading, fetchMembers, getMemberName, getMemberById }
})
