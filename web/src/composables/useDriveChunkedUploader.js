// useDriveChunkedUploader.js — v2 网盘 PR5 分片上传 + 断点续传 composable
// 2026-07-01

import { ref, computed } from 'vue'
import axios from 'axios'
import { useResumableUpload } from './useResumableUpload'

/**
 * 分片上传管理器 (PR5)
 *
 * 适用场景:
 * - 文件 > 50MB 走分片 (避开 nginx 单请求 max_body 限制)
 * - 网络不稳时, 断点续传避免重新上传整个文件
 *
 * 流程:
 * 1. initSession() -> POST /files/upload/init -> uploadId + chunkSize
 * 2. uploadChunks() 循环 PUT chunks, 跳过已传 (断点续传核心)
 * 3. completeSession() -> POST /files/upload/{id}/complete -> Knowledge row
 * 4. 任何失败可 abortSession() 清 staging
 *
 * 进度回调:
 * - onProgress({ uploadedChunks, totalChunks, percent, speed })
 *   speed = bytes/sec (最近 1s 滑动平均)
 */
export function useDriveChunkedUploader(options = {}) {
  const {
    chunkSize = 5 * 1024 * 1024,           // 5MB / chunk
    concurrency = 3,                         // 同时上传 chunk 数 (防 MinIO 限流)
    maxRetries = 3,                          // 单 chunk 失败重试
    retryDelay = 1000,                       // 重试退避 (指数 1s, 2s, 4s)
  } = options

  // === 状态 ===
  const uploadId = ref(null)
  const fileName = ref(null)
  const fileSize = ref(0)
  const fileHash = ref(null)
  const totalChunks = ref(0)
  const uploadedChunks = ref([])  // 已上传的 chunk indices
  const status = ref('idle')      // idle | initializing | uploading | completing | done | aborted | error
  const percent = computed(() => {
    if (totalChunks.value === 0) return 0
    return Math.round((uploadedChunks.value.length / totalChunks.value) * 100)
  })
  const error = ref(null)
  const resultFile = ref(null)  // complete 后存 DriveFileItem

  // 速度计算 (1s 滑动平均)
  const bytesUploaded = ref(0)
  const speedBps = ref(0)  // bytes per second
  let lastTick = null

  // 持久化 (localStorage)
  const resumable = useResumableUpload()

  /**
   * 初始化分片 session
   */
  async function initSession({ file, folderId = null, visibility = 'team' }) {
    status.value = 'initializing'
    error.value = null
    fileName.value = file.name
    fileSize.value = file.size
    fileHash.value = null  // 可选: 上传前算 hash

    const total = Math.ceil(file.size / chunkSize)
    totalChunks.value = total

    try {
      const resp = await axios.post('/api/v1/drive/files/upload/init', {
        file_name: file.name,
        file_size: file.size,
        total_chunks: total,
        folder_id: folderId,
        visibility,
      })
      uploadId.value = resp.data.upload_id
      // 服务端返回已传 chunks (可能为 [] 因为新 session)
      uploadedChunks.value = resp.data.uploaded_chunks || []

      // 持久化 (断点续传用)
      resumable.saveSession({
        upload_id: uploadId.value,
        file_name: file.name,
        file_size: file.size,
        total_chunks: total,
        folder_id: folderId,
        visibility,
        created_at: Date.now(),
      })

      return uploadId.value
    } catch (e) {
      status.value = 'error'
      error.value = e.response?.data?.detail || e.message || '分片初始化失败'
      throw e
    }
  }

  /**
   * 续传: 从已存在的 session 恢复 (前端 reload / 切换网络场景)
   */
  async function resumeSession(savedSession) {
    status.value = 'initializing'
    uploadId.value = savedSession.upload_id
    fileName.value = savedSession.file_name
    fileSize.value = savedSession.file_size
    totalChunks.value = savedSession.total_chunks
    fileHash.value = null

    try {
      const resp = await axios.get(`/api/v1/drive/files/upload/${uploadId.value}`)
      uploadedChunks.value = resp.data.uploaded_chunks || []
      status.value = 'idle'  // 已就绪, 等调 uploadChunks
      return uploadId.value
    } catch (e) {
      status.value = 'error'
      error.value = e.response?.data?.detail || e.message || '续传失败'
      resumable.removeSession(uploadId.value)
      throw e
    }
  }

  /**
   * 上传所有 chunks (跳过已传)
   * @param {File} file - 待上传文件
   * @param {Function} onProgress - 进度回调 (可选)
   */
  async function uploadChunks(file, onProgress = null) {
    if (!uploadId.value) {
      throw new Error('uploadId 未初始化, 先调 initSession()')
    }
    status.value = 'uploading'
    bytesUploaded.value = 0
    lastTick = { time: Date.now(), bytes: 0 }

    const uploadedSet = new Set(uploadedChunks.value)
    const pending = []  // [{ idx, start, end }]
    for (let i = 0; i < totalChunks.value; i++) {
      if (!uploadedSet.has(i)) {
        pending.push({
          idx: i,
          start: i * chunkSize,
          end: Math.min((i + 1) * chunkSize, file.size),
        })
      }
    }

    // 并发上传 (concurrency 个一组)
    for (let i = 0; i < pending.length; i += concurrency) {
      const batch = pending.slice(i, i + concurrency)
      await Promise.all(batch.map((p) => uploadOneChunk(file, p, onProgress)))
      if (status.value === 'aborted') return
    }

    // 速度稳定在 0 (上传完)
    speedBps.value = 0
  }

  /**
   * 单 chunk 上传 (含重试)
   */
  async function uploadOneChunk(file, { idx, start, end }, onProgress) {
    const blob = file.slice(start, end)
    const arrayBuf = await blob.arrayBuffer()

    let attempt = 0
    while (attempt <= maxRetries) {
      try {
        await axios.put(
          `/api/v1/drive/files/upload/${uploadId.value}/chunk/${idx}`,
          arrayBuf,
          headers: { 'Content-Type': 'application/octet-stream' },
        )
        // 成功 → 标记
        if (!uploadedChunks.value.includes(idx)) {
          uploadedChunks.value = [...uploadedChunks.value, idx].sort((a, b) => a - b)
        }
        bytesUploaded.value += (end - start)
        updateSpeed(end - start)
        if (onProgress) {
          onProgress({
            uploadedChunks: uploadedChunks.value.length,
            totalChunks: totalChunks.value,
            percent: percent.value,
            speedBps: speedBps.value,
          })
        }
        return
      } catch (e) {
        attempt++
        if (attempt > maxRetries) {
          status.value = 'error'
          error.value = `chunk ${idx} 上传失败 ${maxRetries} 次: ${e.message}`
          throw e
        }
        // 指数退避
        await new Promise(r => setTimeout(r, retryDelay * Math.pow(2, attempt - 1)))
      }
    }
  }

  /**
   * 滑动平均计算上传速度
   */
  function updateSpeed(chunkBytes) {
    const now = Date.now()
    const dt = (now - lastTick.time) / 1000
    if (dt >= 1.0) {
      const bytesSinceLastTick = bytesUploaded.value - lastTick.bytes
      speedBps.value = Math.round(bytesSinceLastTick / dt)
      lastTick = { time: now, bytes: bytesUploaded.value }
    }
  }

  /**
   * 完成上传 (拼接 chunks → Knowledge)
   */
  async function completeSession(changeNote = null) {
    if (!uploadId.value) throw new Error('uploadId 未初始化')
    status.value = 'completing'
    try {
      const resp = await axios.post(
        `/api/v1/drive/files/upload/${uploadId.value}/complete`,
        changeNote ? { change_note: changeNote } : {},
      )
      resultFile.value = resp.data
      status.value = 'done'
      // 清持久化
      resumable.removeSession(uploadId.value)
      return resp.data
    } catch (e) {
      status.value = 'error'
      error.value = e.response?.data?.detail || e.message || '完成上传失败'
      throw e
    }
  }

  /**
   * 中止上传 + 清 staging
   */
  async function abortSession() {
    if (!uploadId.value) return
    try {
      await axios.post(`/api/v1/drive/files/upload/${uploadId.value}/abort`)
    } catch (e) {
      // 中止失败不抛, 至少清本地状态
      console.warn('[Uploader] abort 失败:', e.message)
    }
    status.value = 'aborted'
    resumable.removeSession(uploadId.value)
  }

  /**
   * 重置 composable 状态 (供下一个文件复用)
   */
  function reset() {
    uploadId.value = null
    fileName.value = null
    fileSize.value = 0
    totalChunks.value = 0
    uploadedChunks.value = []
    status.value = 'idle'
    percent.value = 0
    bytesUploaded.value = 0
    speedBps.value = 0
    error.value = null
    resultFile.value = null
  }

  return {
    // 状态
    uploadId,
    fileName,
    fileSize,
    totalChunks,
    uploadedChunks,
    status,
    percent,
    bytesUploaded,
    speedBps,
    error,
    resultFile,
    // 方法
    initSession,
    resumeSession,
    uploadChunks,
    completeSession,
    abortSession,
    reset,
  }
}