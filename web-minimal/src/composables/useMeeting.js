import { ref, computed } from 'vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { useMemberStore } from '@/stores/member'

export function useMeeting() {
  const meetings = ref([])
  const loading = ref(false)
  const error = ref(null)
  const filters = ref({
    status: 'all',
    date: null,
    keyword: ''
  })

  const memberStore = useMemberStore()

  // 计算属性
  const filteredMeetings = computed(() => {
    let result = [...meetings.value]

    // 按状态筛选
    if (filters.value.status && filters.value.status !== 'all') {
      result = result.filter(m => m.status === filters.value.status)
    }

    // 按日期筛选
    if (filters.value.date) {
      result = result.filter(m => dayjs(m.start_time).isSame(filters.value.date, 'day'))
    }

    // 按关键词搜索
    if (filters.value.keyword) {
      const keyword = filters.value.keyword.toLowerCase()
      result = result.filter(m =>
        m.title.toLowerCase().includes(keyword) ||
        (m.description && m.description.toLowerCase().includes(keyword))
      )
    }

    return result
  })

  const sortedMeetings = computed(() => {
    return [...filteredMeetings.value].sort((a, b) => {
      return dayjs(a.start_time).diff(dayjs(b.start_time))
    })
  })

  const groupedByDate = computed(() => {
    const groups = {}
    sortedMeetings.value.forEach(meeting => {
      const date = dayjs(meeting.start_time).format('YYYY-MM-DD')
      if (!groups[date]) {
        groups[date] = {
          date,
          meetings: []
        }
      }
      groups[date].meetings.push(meeting)
    })
    return Object.values(groups)
  })

  const todayMeetings = computed(() => {
    return meetings.value.filter(m => dayjs(m.start_time).isSame(dayjs(), 'day'))
  })

  const upcomingMeetings = computed(() => {
    return meetings.value.filter(m => dayjs(m.start_time).isAfter(dayjs(), 'day'))
  })

  const pastMeetings = computed(() => {
    return meetings.value.filter(m => dayjs(m.start_time).isBefore(dayjs(), 'day'))
  })

  const liveMeetings = computed(() => {
    return meetings.value.filter(m => m.status === 'live')
  })

  const stats = computed(() => ({
    total: meetings.value.length,
    today: todayMeetings.value.length,
    upcoming: upcomingMeetings.value.length,
    past: pastMeetings.value.length,
    live: liveMeetings.value.length
  }))

  // 获取会议列表
  const fetchMeetings = async (params = {}) => {
    loading.value = true
    error.value = null
    try {
      const response = await axios.get('/api/v1/meetings', { params })
      meetings.value = response.data
    } catch (err) {
      error.value = err.response?.data?.detail || '获取会议列表失败'
      console.error('获取会议列表失败:', err)
    } finally {
      loading.value = false
    }
  }

  // 获取单个会议
  const fetchMeeting = async (meetingId) => {
    try {
      const response = await axios.get(`/api/v1/meetings/${meetingId}`)
      const index = meetings.value.findIndex(m => m.id === meetingId)
      if (index !== -1) {
        meetings.value[index] = response.data
      } else {
        meetings.value.push(response.data)
      }
      return response.data
    } catch (err) {
      console.error('获取会议详情失败:', err)
      return null
    }
  }

  // 创建会议
  const createMeeting = async (meetingData) => {
    try {
      const response = await axios.post('/api/v1/meetings', meetingData)
      meetings.value.push(response.data)
      return { success: true, data: response.data }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '创建会议失败'
      }
    }
  }

  // 更新会议
  const updateMeeting = async (meetingId, meetingData) => {
    try {
      const response = await axios.put(`/api/v1/meetings/${meetingId}`, meetingData)
      const index = meetings.value.findIndex(m => m.id === meetingId)
      if (index !== -1) {
        meetings.value[index] = response.data
      }
      return { success: true, data: response.data }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '更新会议失败'
      }
    }
  }

  // 删除会议
  const deleteMeeting = async (meetingId) => {
    try {
      await axios.delete(`/api/v1/meetings/${meetingId}`)
      meetings.value = meetings.value.filter(m => m.id !== meetingId)
      return { success: true }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '删除会议失败'
      }
    }
  }

  // 开始会议
  const startMeeting = async (meetingId) => {
    try {
      const response = await axios.post(`/api/v1/meetings/${meetingId}/start`)
      const index = meetings.value.findIndex(m => m.id === meetingId)
      if (index !== -1) {
        meetings.value[index] = response.data
      }
      return { success: true, data: response.data }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '开始会议失败'
      }
    }
  }

  // 结束会议
  const endMeeting = async (meetingId) => {
    try {
      const response = await axios.post(`/api/v1/meetings/${meetingId}/end`)
      const index = meetings.value.findIndex(m => m.id === meetingId)
      if (index !== -1) {
        meetings.value[index] = response.data
      }
      return { success: true, data: response.data }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '结束会议失败'
      }
    }
  }

  // 设置筛选条件
  const setFilters = (newFilters) => {
    filters.value = { ...filters.value, ...newFilters }
  }

  // 重置筛选条件
  const resetFilters = () => {
    filters.value = {
      status: 'all',
      date: null,
      keyword: ''
    }
  }

  // 获取参与者姓名
  const getParticipantName = (participantId) => {
    return memberStore.getMemberName(participantId)
  }

  // 获取参与者头像
  const getParticipantAvatar = (participantId) => {
    return memberStore.getMemberAvatar(participantId)
  }

  // 获取参与者首字母
  const getParticipantInitial = (participantId) => {
    return memberStore.getMemberInitial(participantId)
  }

  // 格式化会议时间
  const formatMeetingTime = (startTime) => {
    return dayjs(startTime).format('HH:mm')
  }

  // 格式化会议日期
  const formatMeetingDate = (startTime) => {
    const d = dayjs(startTime)
    const now = dayjs()

    if (d.isSame(now, 'day')) {
      return '今天'
    } else if (d.isSame(now.add(1, 'day'), 'day')) {
      return '明天'
    } else if (d.isSame(now.subtract(1, 'day'), 'day')) {
      return '昨天'
    } else {
      return d.format('MM月DD日')
    }
  }

  // 获取会议状态
  const getMeetingStatus = (meeting) => {
    if (meeting.status === 'live') return '进行中'
    if (meeting.status === 'ended') return '已结束'
    if (dayjs(meeting.start_time).isBefore(dayjs())) return '已过期'
    return '即将开始'
  }

  // 获取会议状态颜色
  const getMeetingStatusColor = (meeting) => {
    if (meeting.status === 'live') return '#ef4444'
    if (meeting.status === 'ended') return '#10b981'
    if (dayjs(meeting.start_time).isBefore(dayjs())) return '#666666'
    return '#3b82f6'
  }

  return {
    meetings,
    loading,
    error,
    filters,
    filteredMeetings,
    sortedMeetings,
    groupedByDate,
    todayMeetings,
    upcomingMeetings,
    pastMeetings,
    liveMeetings,
    stats,
    fetchMeetings,
    fetchMeeting,
    createMeeting,
    updateMeeting,
    deleteMeeting,
    startMeeting,
    endMeeting,
    setFilters,
    resetFilters,
    getParticipantName,
    getParticipantAvatar,
    getParticipantInitial,
    formatMeetingTime,
    formatMeetingDate,
    getMeetingStatus,
    getMeetingStatusColor
  }
}
