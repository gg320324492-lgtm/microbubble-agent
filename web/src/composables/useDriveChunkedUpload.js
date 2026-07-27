// useDriveChunkedUpload.js — W72 B-3 Drive chunk/resume uploader
import { computed, ref } from 'vue'
import axios from 'axios'
import { useResumableUpload } from './useResumableUpload'

const DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024
const MAX_CONCURRENT_CHUNKS = 3
const MAX_CHUNK_RETRIES = 3

let workerInstance = null
let nextHashId = 1
const hashWaiters = new Map()

function getHashWorker() {
  if (workerInstance) return workerInstance
  workerInstance = new Worker(
    new URL('../workers/sha256.worker.js', import.meta.url),
    { type: 'module' }
  )
  workerInstance.onmessage = (event) => {
    const msg = event.data || {}
    const waiters = hashWaiters.get(msg.id)
    if (!waiters) return
    hashWaiters.delete(msg.id)
    if (msg.type === 'done') waiters.resolve(msg.hash)
    else waiters.reject(new Error(msg.message || 'hash failed'))
  }
  workerInstance.onerror = (err) => {
    hashWaiters.forEach((w) => w.reject(err))
    hashWaiters.clear()
  }
  return workerInstance
}

function hashChunk(blob) {
  if (typeof Worker === 'undefined' && typeof crypto !== 'undefined' && crypto.subtle) {
    return crypto.subtle.digest('SHA-256', blob).then((buf) =>
      Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('')
    )
  }
  const id = nextHashId++
  const worker = getHashWorker()
  return new Promise((resolve, reject) => {
    hashWaiters.set(id, { resolve, reject })
    worker.postMessage({ id, blob })
  })
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function authHeaders() {
  const token = localStorage.getItem('access_token') || ''
  return token ? { Authorization: 'Bearer ' + token } : {}
}

export function useDriveChunkedUpload() {
  const resumable = useResumableUpload()

  const uploadId = ref(null)
  const totalChunks = ref(0)
  const chunkSize = ref(DEFAULT_CHUNK_SIZE)
  const fileSize = ref(0)
  const filename = ref('')
  const parentId = ref(null)
  const uploadedChunks = ref(new Set())
  const status = ref('idle')
  const errorMessage = ref('')
  const checksum = ref('')

  const progress = computed(() => {
    if (totalChunks.value === 0) return 0
    return Math.round((uploadedChunks.value.size / totalChunks.value) * 100)
  })

  const remainingChunks = computed(() => {
    const remaining = []
    for (let i = 0; i < totalChunks.value; i += 1) {
      if (!uploadedChunks.value.has(i)) remaining.push(i)
    }
    return remaining
  })

  function reset() {
    uploadId.value = null
    totalChunks.value = 0
    chunkSize.value = DEFAULT_CHUNK_SIZE
    fileSize.value = 0
    filename.value = ''
    parentId.value = null
    uploadedChunks.value = new Set()
    status.value = 'idle'
    errorMessage.value = ''
    checksum.value = ''
  }

  async function runChunkUploads(file) {
    let cursor = 0
    const workers = []
    for (let i = 0; i < MAX_CONCURRENT_CHUNKS; i += 1) {
      const worker = (async () => {
        while (true) {
          const index = cursor
          cursor += 1
          if (index >= totalChunks.value) return
          if (uploadedChunks.value.has(index)) continue
          await uploadChunkWithRetry(file, index)
          const next = new Set(uploadedChunks.value)
          next.add(index)
          uploadedChunks.value = next
        }
      })()
      workers.push(worker)
    }
    await Promise.all(workers)
  }

  async function uploadChunkWithRetry(file, index) {
    const start = index * chunkSize.value
    const end = Math.min(start + chunkSize.value, file.size)
    const blob = file.slice(start, end)
    const buffer = await blob.arrayBuffer()
    let attempt = 0
    let lastError
    while (attempt < MAX_CHUNK_RETRIES) {
      try {
        await axios.put(
          '/api/v1/drive/chunked-uploads/' + uploadId.value + '/chunks/' + index,
          buffer,
          {
            headers: Object.assign(
              { 'Content-Type': 'application/octet-stream' },
              authHeaders()
            ),
            transformRequest: (data) => data,
          }
        )
        return
      } catch (error) {
        lastError = error
        attempt += 1
        if (attempt < MAX_CHUNK_RETRIES) await sleep(400 * attempt)
      }
    }
    throw lastError
  }

  async function startUpload({ file, parent_id = null, visibility = 'team', is_team_shared = false }) {
    if (!file) throw new Error('file is required')
    reset()
    filename.value = file.name
    fileSize.value = file.size
    parentId.value = parent_id
    chunkSize.value = DEFAULT_CHUNK_SIZE
    status.value = 'hashing'
    try {
      checksum.value = await hashChunk(file)
    } catch (error) {
      status.value = 'error'
      errorMessage.value = '计算 SHA256 失败'
      throw error
    }
    status.value = 'initializing'
    const initResp = await axios.post(
      '/api/v1/drive/chunked-uploads/init',
      {
        filename: file.name,
        file_size: file.size,
        chunk_size: DEFAULT_CHUNK_SIZE,
        parent_id,
        checksum: checksum.value,
      },
      { headers: authHeaders() }
    )
    uploadId.value = initResp.data.upload_id
    totalChunks.value = initResp.data.total_chunks
    chunkSize.value = initResp.data.chunk_size
    uploadedChunks.value = new Set(initResp.data.uploaded_chunks || [])
    status.value = 'uploading'
    resumable.saveSession({
      upload_id: uploadId.value,
      file_name: file.name,
      file_size: file.size,
      total_chunks: totalChunks.value,
      chunk_size: chunkSize.value,
      folder_id: parent_id,
      visibility,
      created_at: Date.now(),
    })
    try {
      await runChunkUploads(file)
      status.value = 'finalizing'
      await axios.post(
        '/api/v1/drive/chunked-uploads/' + uploadId.value + '/complete',
        { final_checksum: checksum.value, visibility, is_team_shared },
        { headers: authHeaders() }
      )
      status.value = 'done'
      resumable.removeSession(uploadId.value)
    } catch (error) {
      status.value = 'error'
      errorMessage.value = errorMessageFromAxios(error) || '上传失败'
      throw error
    }
    return { upload_id: uploadId.value, file_name: file.name }
  }

  async function abort() {
    if (!uploadId.value) return
    status.value = 'aborted'
    try {
      await axios.delete('/api/v1/drive/chunked-uploads/' + uploadId.value, { headers: authHeaders() })
    } finally {
      resumable.removeSession(uploadId.value)
      reset()
    }
  }

  async function resume({ file }) {
    if (!file) throw new Error('file is required')
    const sessions = resumable
      .listSessions()
      .filter((s) => s.file_name === file.name && s.file_size === file.size)
    if (sessions.length === 0) return null
    const session = sessions[0]
    uploadId.value = session.upload_id
    totalChunks.value = session.total_chunks
    chunkSize.value = session.chunk_size || DEFAULT_CHUNK_SIZE
    fileSize.value = session.file_size
    filename.value = session.file_name
    parentId.value = session.folder_id || null
    const resumeResp = await axios.get(
      '/api/v1/drive/chunked-uploads/' + uploadId.value,
      { headers: authHeaders() }
    )
    uploadedChunks.value = new Set(resumeResp.data.uploaded_chunks || [])
    status.value = 'uploading'
    try {
      await runChunkUploads(file)
      status.value = 'finalizing'
      await axios.post(
        '/api/v1/drive/chunked-uploads/' + uploadId.value + '/complete',
        { final_checksum: checksum.value || null, visibility: session.visibility || 'team' },
        { headers: authHeaders() }
      )
      status.value = 'done'
      resumable.removeSession(uploadId.value)
    } catch (error) {
      status.value = 'error'
      errorMessage.value = errorMessageFromAxios(error) || '续传失败'
      throw error
    }
    return { upload_id: uploadId.value }
  }

  function errorMessageFromAxios(error) {
    if (!error) return ''
    if (error.response && error.response.data) {
      return error.response.data.detail || error.response.data.message || ''
    }
    return error.message || ''
  }

  return {
    uploadId,
    filename,
    fileSize,
    chunkSize,
    totalChunks,
    uploadedChunks,
    remainingChunks,
    status,
    errorMessage,
    progress,
    checksum,
    startUpload,
    resume,
    abort,
    reset,
  }
}
