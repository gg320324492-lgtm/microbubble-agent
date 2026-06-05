import { ref, computed } from 'vue'
import axios from 'axios'

export function useMeeting() {
  // 状态
  const meetings = ref([])
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const keyword = ref('')
  const dateFrom = ref('')
  const dateTo = ref('')

  // 当前会议
  const currentMeeting = ref(null)

  // API 调用
  const fetchMeetings = async (params = {}) => {
    loading.value = true
    try {
      const queryParams = {
        page: currentPage.value,
        page_size: pageSize.value,
        ...params
      }
      if (keyword.value) queryParams.keyword = keyword.value
      if (dateFrom.value) queryParams.date_from = dateFrom.value
      if (dateTo.value) queryParams.date_to = dateTo.value

      const res = await axios.get('/api/v1/meetings', { params: queryParams })
      meetings.value = res.data.items || []
      total.value = res.data.pagination?.total || res.data.total || 0
    } finally {
      loading.value = false
    }
  }

  const fetchMeeting = async (id) => {
    const res = await axios.get(`/api/v1/meetings/${id}`)
    currentMeeting.value = res.data
    return res.data
  }

  const createMeeting = async (meetingData) => {
    const res = await axios.post('/api/v1/meetings', meetingData)
    await fetchMeetings()
    return res.data
  }

  const updateMeeting = async (id, meetingData) => {
    const res = await axios.put(`/api/v1/meetings/${id}`, meetingData)
    await fetchMeetings()
    return res.data
  }

  const deleteMeeting = async (id) => {
    await axios.delete(`/api/v1/meetings/${id}`)
    await fetchMeetings()
  }

  const updateAgenda = async (id, agenda) => {
    const res = await axios.patch(`/api/v1/meetings/${id}/agenda`, { agenda })
    return res.data
  }

  return {
    // 状态
    meetings, total, currentPage, pageSize, loading,
    keyword, dateFrom, dateTo, currentMeeting,
    // 方法
    fetchMeetings, fetchMeeting, createMeeting,
    updateMeeting, deleteMeeting, updateAgenda
  }
}
