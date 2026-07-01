// useFileRequests — v2 PR7 文件请求 Pinia composable
import { ref, computed } from 'vue'
import axios from 'axios'

const requests = ref([])
const loading = ref(false)
const error = ref(null)

async function fetchMy(includeInactive = false) {
  loading.value = true
  error.value = null
  try {
    const resp = await axios.get('/api/v1/file-requests/my', {
      params: { include_inactive: includeInactive ? 'true' : 'false' }
    })
    requests.value = resp.data.items || []
    return requests.value
  } catch (e) {
    error.value = e?.response?.data?.error?.message || e?.message || '加载失败'
    requests.value = []
    return []
  } finally {
    loading.value = false
  }
}

async function createRequest(payload) {
  try {
    const resp = await axios.post('/api/v1/file-requests', payload)
    // 重新拉列表
    await fetchMy()
    return resp.data
  } catch (e) {
    const detail = e?.response?.data?.detail
    throw new Error(detail || e?.message || '创建失败')
  }
}

async function deactivate(requestId) {
  try {
    await axios.post(`/api/v1/file-requests/${requestId}/deactivate`)
    await fetchMy()
    return true
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '关闭失败'
    return false
  }
}

async function fetchPublicInfo(token) {
  // 公开端点, 不用 token
  const resp = await axios.get(`/api/v1/file-requests/${token}/info`)
  return resp.data
}

async function submitPublic(token, formData) {
  // 公开端点, 不用 token; formData 含 file + uploader_name
  const resp = await axios.post(`/api/v1/file-requests/${token}/submit`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return resp.data
}

const hasRequests = computed(() => requests.value.length > 0)

export function useFileRequests() {
  return {
    requests,
    loading,
    error,
    hasRequests,
    fetchMy,
    createRequest,
    deactivate,
    fetchPublicInfo,
    submitPublic,
  }
}
