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

// ── 匿名分片上传 (2026-11-09, 10GB 级外部收件) ───────────────────────────────
// 五个端点全部**无 JWT**, 只靠 URL 里的 token 鉴权 —— 与 info/submit 同一口径。
// 契约要点 (改前端前先核 app/api/v1/file_requests.py):
//   · chunk_size 由**服务端**定, 前端必须用返回的那个 (非末片长度要逐字节相等)
//   · 分片 PUT 走 chunked_upload 限流档 (120/min/IP), 其余四个走 write 档 (30/min)
//     ⇒ 所以「发起/查询/合并/放弃」一场上传各只调一次, 不能进重试循环
//   · 失败一律是 HTTPException(detail=中文), 取 e.response.data.detail
//   · 状态码语义与文案翻译收在 utils/fileRequestFailure.js, 这里只管发请求

/** 1. 发起分片会话 → {upload_id, chunk_size, total_chunks, missing_chunks, ...} */
async function initPublicUpload(token, { filename, fileSize, chunkSize, uploaderName }) {
  const fd = new FormData()
  fd.append('filename', filename)
  fd.append('file_size', String(fileSize))
  // 只在调用方显式给了值时才传, 否则让服务端自己按文件大小选
  if (chunkSize) fd.append('chunk_size', String(chunkSize))
  if (uploaderName) fd.append('uploader_name', uploaderName)
  const resp = await axios.post(`/api/v1/file-requests/${token}/uploads`, fd)
  return resp.data
}

/** 2. 查询会话进度 → 断点续传靠它的 missing_chunks */
async function getPublicUploadStatus(token, uploadId) {
  const resp = await axios.get(`/api/v1/file-requests/${token}/uploads/${uploadId}`)
  return resp.data
}

/**
 * 3. 传第 index 片
 * @param {string} sha256Hex 本片字节的 sha256; 传 null/undefined 就不带校验头
 *        (非 secure context 下 crypto.subtle 不可用, 必须能降级)
 * ⚠️ 超时单独放宽: 32 MiB 的上行在弱网下会超过全局默认, 默认无超时会让
 *    「其实已传成功」被当成失败重传。10 分钟够 1 Mbps 传完 32 MiB。
 */
async function putPublicChunk(token, uploadId, index, blob, sha256Hex, signal) {
  const fd = new FormData()
  fd.append('chunk', blob, String(index))
  const headers = {}
  if (sha256Hex) headers['X-Chunk-SHA256'] = sha256Hex
  const resp = await axios.put(
    `/api/v1/file-requests/${token}/uploads/${uploadId}/chunks/${index}`,
    fd,
    { headers, timeout: 600000, signal }
  )
  return resp.data
}

/** 4. 让服务端合并 + 实算校验 → {success, file_id, size, sha256, request_closed, ...} */
async function completePublicUpload(token, uploadId, checksum) {
  const fd = new FormData()
  // 整文件 sha256 可选; 前端**默认不传** (浏览器 crypto.subtle 没有流式 API,
  // 算 10GB 的整文件哈希要把整份读进内存)。服务端合并时会自己实算并核对。
  if (checksum) fd.append('checksum', checksum)
  const resp = await axios.post(
    `/api/v1/file-requests/${token}/uploads/${uploadId}/complete`,
    fd,
    // 合并是服务端逐片 compose + 流式哈希, 10GB 会明显慢于普通请求
    { timeout: 0 }
  )
  return resp.data
}

/** 5. 放弃会话 (服务端会删掉已上传的临时分片) */
async function abortPublicUpload(token, uploadId) {
  const resp = await axios.post(`/api/v1/file-requests/${token}/uploads/${uploadId}/abort`)
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
    // 匿名分片上传 (2026-11-09)
    initPublicUpload,
    getPublicUploadStatus,
    putPublicChunk,
    completePublicUpload,
    abortPublicUpload,
  }
}
