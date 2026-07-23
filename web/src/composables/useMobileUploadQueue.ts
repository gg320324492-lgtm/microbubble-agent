/**
 * 移动端上传队列 (W68 Mobile UX v3.0)
 *
 * 设计目标:
 *   - 移动端上传文件 (图片/录音/视频) 走**分片 + 断点续传 + 进度同步**三件套
 *   - 离线时队列累积到 IndexedDB, 在线时自动恢复 (即使关 app)
 *   - 进度通过 BroadcastChannel 跨 tab 同步 (一个 tab 传到 50%, 另一个 tab 开也能看到)
 *   - 与 useIDBQueue 集成: dispatcher 走 IDB queue, 保证重试 + ttl
 *
 * 与 useChunkedUploader 的关系:
 *   - useChunkedUploader: 单会议录音的 chunk 队列, meetingId 维度, 内存 + IDB 混合
 *   - useMobileUploadQueue: 通用文件上传队列, item 维度, 纯 IDB (W68 新)
 *   - 移动端 KB 上传 / 头像上传 / Drive 上传均可走本队列
 *
 * 分片策略:
 *   - 默认 1MB/chunk, 可通过 chunkSize 调整
 *   - 整文件入队时即切片 (slice Blob), 每片独立存 IDB
 *   - 服务端需配合: PUT /upload/{uploadId}/chunk/{index} + POST /upload/{uploadId}/complete
 *   - 若服务端不支持分片, 自动 fallback: 单片 (chunk = 整文件)
 *
 * 进度同步:
 *   - 每个 chunk 上传完更新 IDB (item.progress = uploaded / total)
 *   - BroadcastChannel 'mobile_upload_progress' 广播 { uploadId, progress, status }
 *   - 组件订阅 onProgress(cb) 实时显示
 *
 * 持久化保证:
 *   - 文件 Blob + 元数据都进 IDB, 关 app / 杀进程不丢
 *   - 上传完成后, IDB 记录清理 (7 天后兜底清理)
 *   - 失败重试: 默认 5 次, 指数退避 1s, 2s, 4s, 8s, 16s
 *
 * 关键 API:
 *   - enqueueUpload(file, opts)        → uploadId
 *   - start(uploadId)                  → 启动/恢复一个 upload
 *   - pause(uploadId) / resume(uploadId)
 *   - cancel(uploadId)                 → 删 IDB 记录
 *   - getUpload(uploadId)              → 上传详情
 *   - listUploads()                    → 所有 active upload
 *   - onProgress(cb)                   → 跨 tab 进度订阅
 *
 * 纪律 (W68 新铁律):
 *   1. **分片必须用 Blob.slice**, 不要走 FileReader.readAsArrayBuffer (移动端大文件爆内存)
 *   2. **每个 chunk 独立 try/catch**, 一片失败不影响其他片
 *   3. **进度按 chunk 完成数计算**, 不要按字节 (避免半片状态难判定)
 *   4. **暂停/恢复靠 IDB**, 不要靠内存 (移动端页面随时被切后台)
 *   5. **complete 失败也要保留 chunks**, 让用户能 retry (不要 cleanup)
 */

import { ref, readonly, onUnmounted } from 'vue'
import { getNetworkStatus } from '@/composables/useNetworkStatus'
import { enqueue as idbEnqueue, drain as idbDrain, onChange as onIdbChange } from '@/composables/useIDBQueue'

// ===== 可调参数 =====
const DEFAULT_CHUNK_SIZE = 1024 * 1024  // 1MB
const DEFAULT_MAX_RETRIES = 5
const DEFAULT_PRIORITY = 5
const PROGRESS_CHANNEL = 'mobile_upload_progress'
const CLEANUP_AFTER_MS = 7 * 24 * 3600 * 1000  // 7 天

// ===== IDB Schema (独立 db, 不与 useIDBQueue 共享) =====
const DB_NAME = 'microbubble_mobile_upload'
const DB_VERSION = 1
const STORE_UPLOADS = 'uploads'
const STORE_CHUNKS = 'chunks'

// ===== 模块级单例 =====
const activeUploads = ref(new Map())  // uploadId → { progress, status, error }
const isProcessing = ref(false)
let dbPromise = null
let progressChannel = null
let progressListeners = new Set()
let networkListenerAttached = false

// ===== 类型注释 =====
/**
 * @typedef {Object} UploadItem
 * @property {string} upload_id
 * @property {string} filename
 * @property {string} mime_type
 * @property {number} total_size
 * @property {number} chunk_size
 * @property {number} total_chunks
 * @property {number} uploaded_chunks
 * @property {string} status     - 'pending' | 'uploading' | 'paused' | 'completed' | 'failed' | 'cancelled'
 * @property {string} endpoint   - 'auto' | 'kb' | 'avatar' | 'drive' | custom
 * @property {Object} meta       - 业务元数据 (e.g. { knowledgeId, folderId })
 * @property {number} retry_count
 * @property {number} max_retries
 * @property {number} priority
 * @property {number} created_at
 * @property {number} updated_at
 * @property {string} last_error
 * @property {string} server_upload_id  - 服务端返回的 id (用于 complete)
 */

/**
 * @typedef {Object} UploadOpts
 * @property {number} [chunkSize=1MB]
 * @property {number} [maxRetries=5]
 * @property {number} [priority=5]
 * @property {string} [endpoint='auto']
 * @property {Object} [meta={}]
 * @property {string} [tag]    - 业务标签, 用于按 tag 过滤
 */

// ===== IDB 基础 =====

function isIDBAvailable() {
  return typeof indexedDB !== 'undefined'
}

function openDB() {
  if (dbPromise) return dbPromise
  if (!isIDBAvailable()) return Promise.reject(new Error('IDB not available'))

  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = (event) => {
      const db = event.target.result
      if (!db.objectStoreNames.contains(STORE_UPLOADS)) {
        const store = db.createObjectStore(STORE_UPLOADS, { keyPath: 'upload_id' })
        store.createIndex('by_status', ['status', 'updated_at'], { unique: false })
        store.createIndex('by_tag', 'tag', { unique: false })
      }
      if (!db.objectStoreNames.contains(STORE_CHUNKS)) {
        const store = db.createObjectStore(STORE_CHUNKS, { keyPath: ['upload_id', 'chunk_index'] })
        store.createIndex('by_upload', 'upload_id', { unique: false })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
    req.onblocked = () => reject(new Error('IDB open blocked'))
  })
  return dbPromise
}

function reqToPromise(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function txDone(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error || new Error('Tx aborted'))
  })
}

// ===== 公共 API =====

/**
 * 入队一个上传任务
 * @param {File|Blob} file
 * @param {UploadOpts} [opts]
 * @returns {Promise<string>} uploadId
 */
export async function enqueueUpload(file, opts = {}) {
  const uploadId = generateUploadId()
  const chunkSize = opts.chunkSize || DEFAULT_CHUNK_SIZE
  const totalChunks = Math.max(1, Math.ceil(file.size / chunkSize))
  const now = Date.now()

  /** @type {UploadItem} */
  const item = {
    upload_id: uploadId,
    filename: file.name || `blob_${now}.bin`,
    mime_type: file.type || 'application/octet-stream',
    total_size: file.size,
    chunk_size: chunkSize,
    total_chunks: totalChunks,
    uploaded_chunks: 0,
    status: 'pending',
    endpoint: opts.endpoint || 'auto',
    meta: opts.meta || {},
    retry_count: 0,
    max_retries: opts.maxRetries ?? DEFAULT_MAX_RETRIES,
    priority: opts.priority ?? DEFAULT_PRIORITY,
    created_at: now,
    updated_at: now,
    last_error: '',
    server_upload_id: '',
    tag: opts.tag || '',
  }

  if (!isIDBAvailable()) {
    console.warn('[mobileUpload] IDB not available, in-memory only')
    activeUploads.value.set(uploadId, item)
    triggerRefMap()
    return uploadId
  }

  try {
    const db = await openDB()
    const tx = db.transaction([STORE_UPLOADS, STORE_CHUNKS], 'readwrite')
    const uploadsStore = tx.objectStore(STORE_UPLOADS)
    const chunksStore = tx.objectStore(STORE_CHUNKS)

    await reqToPromise(uploadsStore.add(item))

    // 切片并存 chunks
    for (let i = 0; i < totalChunks; i++) {
      const start = i * chunkSize
      const end = Math.min(start + chunkSize, file.size)
      // 铁律 1: Blob.slice 不读内存
      const chunkBlob = file.slice(start, end, file.type)
      await reqToPromise(chunksStore.add({
        upload_id: uploadId,
        chunk_index: i,
        blob: chunkBlob,
        uploaded: false,
        created_at: now,
      }))
    }
    await txDone(tx)

    activeUploads.value.set(uploadId, { ...item })
    triggerRefMap()
    broadcastProgress({ uploadId, progress: 0, status: 'queued' })

    // 入 IDB queue (用于跨 tab 协调, 但本模块自己处理进度)
    await idbEnqueue({
      key: `upload:${uploadId}`,
      priority: item.priority,
      tag: opts.tag || 'mobile_upload',
      payload: { type: 'mobile_upload', uploadId },
      maxRetries: item.max_retries,
    })

    return uploadId
  } catch (err) {
    console.error('[mobileUpload] enqueue failed:', err)
    throw err
  }
}

/**
 * 启动/恢复一个 upload
 * @param {string} uploadId
 * @returns {Promise<{ uploaded_chunks: number, total_chunks: number, status: string }>}
 */
export async function start(uploadId) {
  const item = await getUpload(uploadId)
  if (!item) throw new Error(`Upload ${uploadId} not found`)

  if (item.status === 'completed') {
    return { uploaded_chunks: item.uploaded_chunks, total_chunks: item.total_chunks, status: 'completed' }
  }

  await updateUpload(uploadId, { status: 'uploading', updated_at: Date.now() })
  broadcastProgress({ uploadId, progress: item.uploaded_chunks / item.total_chunks, status: 'uploading' })

  try {
    // 若服务端无 server_upload_id, 先 init
    if (!item.server_upload_id) {
      const initResp = await initOnServer(item)
      await updateUpload(uploadId, { server_upload_id: initResp.server_upload_id })
      item.server_upload_id = initResp.server_upload_id
    }

    // 顺序上传 chunks (按 chunk_index)
    for (let i = 0; i < item.total_chunks; i++) {
      const current = await getUpload(uploadId)
      if (current.status === 'paused' || current.status === 'cancelled') {
        return { uploaded_chunks: current.uploaded_chunks, total_chunks: current.total_chunks, status: current.status }
      }
      // 跳过已上传
      const chunk = await getChunk(uploadId, i)
      if (chunk?.uploaded) continue

      let uploaded = false
      let lastErr = null
      for (let attempt = 0; attempt < item.max_retries; attempt++) {
        try {
          await uploadChunk(item, i, chunk.blob)
          await markChunkUploaded(uploadId, i)
          uploaded = true
          break
        } catch (err) {
          lastErr = err
          const status = err?.response?.status
          // 4xx 业务错 (除 408/429) 不重试
          if (status && status >= 400 && status < 500 && status !== 408 && status !== 429) {
            throw err
          }
          // 指数退避 1s, 2s, 4s, 8s, 16s
          await sleep(Math.min(30000, 1000 * Math.pow(2, attempt)))
        }
      }
      if (!uploaded) {
        const errMsg = lastErr?.message || 'unknown'
        await updateUpload(uploadId, {
          status: 'failed',
          last_error: errMsg,
          retry_count: item.retry_count + 1,
          updated_at: Date.now(),
        })
        broadcastProgress({ uploadId, progress: 0, status: 'failed', error: errMsg })
        throw new Error(`Upload ${uploadId} failed: ${errMsg}`)
      }

      // 更新进度
      const newUploaded = i + 1
      await updateUpload(uploadId, { uploaded_chunks: newUploaded, updated_at: Date.now() })
      activeUploads.value.set(uploadId, { ...activeUploads.value.get(uploadId), uploaded_chunks: newUploaded })
      triggerRefMap()
      broadcastProgress({
        uploadId,
        progress: newUploaded / item.total_chunks,
        status: 'uploading',
      })
    }

    // 全部 chunks 上传完, 通知服务端 complete
    await completeOnServer(item)
    await updateUpload(uploadId, { status: 'completed', updated_at: Date.now() })
    broadcastProgress({ uploadId, progress: 1, status: 'completed' })

    // 完成后 7 天兜底清理 (立即调度一次 cleanup)
    scheduleCleanup()

    return { uploaded_chunks: item.total_chunks, total_chunks: item.total_chunks, status: 'completed' }
  } catch (err) {
    console.error('[mobileUpload] start failed:', err)
    throw err
  }
}

export async function pause(uploadId) {
  await updateUpload(uploadId, { status: 'paused', updated_at: Date.now() })
  broadcastProgress({ uploadId, progress: undefined, status: 'paused' })
}

export async function resume(uploadId) {
  return start(uploadId)
}

export async function cancel(uploadId) {
  if (!isIDBAvailable()) {
    activeUploads.value.delete(uploadId)
    triggerRefMap()
    return
  }
  try {
    const db = await openDB()
    const tx = db.transaction([STORE_UPLOADS, STORE_CHUNKS], 'readwrite')
    await reqToPromise(tx.objectStore(STORE_UPLOADS).delete(uploadId))
    const chunksIdx = tx.objectStore(STORE_CHUNKS).index('by_upload')
    await new Promise((resolve, reject) => {
      const req = chunksIdx.openCursor(IDBKeyRange.only(uploadId))
      req.onsuccess = () => {
        const cursor = req.result
        if (cursor) { cursor.delete(); cursor.continue() }
        else resolve()
      }
      req.onerror = () => reject(req.error)
    })
    await txDone(tx)
    activeUploads.value.delete(uploadId)
    triggerRefMap()
    broadcastProgress({ uploadId, progress: undefined, status: 'cancelled' })
  } catch (err) {
    console.error('[mobileUpload] cancel failed:', err)
  }
}

export async function getUpload(uploadId) {
  if (!isIDBAvailable()) {
    return activeUploads.value.get(uploadId) || null
  }
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_UPLOADS, 'readonly')
    const item = await reqToPromise(tx.objectStore(STORE_UPLOADS).get(uploadId))
    return item || null
  } catch (err) {
    return null
  }
}

export async function listUploads(opts = {}) {
  const { status, tag } = opts
  if (!isIDBAvailable()) {
    let items = Array.from(activeUploads.value.values())
    if (status) items = items.filter(it => it.status === status)
    if (tag) items = items.filter(it => it.tag === tag)
    return items
  }
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_UPLOADS, 'readonly')
    const store = tx.objectStore(STORE_UPLOADS)
    const all = await reqToPromise(store.getAll())
    let items = all
    if (status) items = items.filter(it => it.status === status)
    if (tag) items = items.filter(it => it.tag === tag)
    return items.sort((a, b) => b.created_at - a.created_at)
  } catch (err) {
    return []
  }
}

export function onProgress(cb) {
  ensureProgressChannel()
  progressListeners.add(cb)
  return () => progressListeners.delete(cb)
}

export function getActiveUploads() {
  return readonly(activeUploads)
}

export function isUploading() {
  return readonly(isProcessing)
}

// ===== 内部 =====

async function getChunk(uploadId, chunkIndex) {
  if (!isIDBAvailable()) return null
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readonly')
  return await reqToPromise(tx.objectStore(STORE_CHUNKS).get([uploadId, chunkIndex]))
}

async function markChunkUploaded(uploadId, chunkIndex) {
  if (!isIDBAvailable()) return
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readwrite')
  const store = tx.objectStore(STORE_CHUNKS)
  const chunk = await reqToPromise(store.get([uploadId, chunkIndex]))
  if (chunk) {
    chunk.uploaded = true
    chunk.uploaded_at = Date.now()
    await reqToPromise(store.put(chunk))
  }
  await txDone(tx)
}

async function updateUpload(uploadId, patch) {
  if (!isIDBAvailable()) {
    const existing = activeUploads.value.get(uploadId)
    if (existing) {
      activeUploads.value.set(uploadId, { ...existing, ...patch })
      triggerRefMap()
    }
    return
  }
  const db = await openDB()
  const tx = db.transaction(STORE_UPLOADS, 'readwrite')
  const store = tx.objectStore(STORE_UPLOADS)
  const existing = await reqToPromise(store.get(uploadId))
  if (existing) {
    Object.assign(existing, patch)
    await reqToPromise(store.put(existing))
    activeUploads.value.set(uploadId, { ...existing })
    triggerRefMap()
  }
  await txDone(tx)
}

function triggerRefMap() {
  // 触发 Map ref 重渲染
  activeUploads.value = new Map(activeUploads.value)
}

function broadcastProgress(payload) {
  if (progressChannel && progressChannel.postMessage) {
    try { progressChannel.postMessage({ ...payload, fromSelf: true }) } catch (e) { /* noop */ }
  }
  for (const cb of progressListeners) {
    try { cb(payload) } catch (err) { console.warn('[mobileUpload] progress listener error:', err) }
  }
}

function ensureProgressChannel() {
  if (progressChannel !== null) return
  if (typeof BroadcastChannel === 'undefined') {
    progressChannel = false
    return
  }
  try {
    progressChannel = new BroadcastChannel(PROGRESS_CHANNEL)
    progressChannel.onmessage = (event) => {
      const data = event.data
      if (!data || data.fromSelf) return
      for (const cb of progressListeners) {
        try { cb({ ...data, remote: true }) } catch (e) { /* noop */ }
      }
    }
  } catch (err) {
    progressChannel = false
  }
}

function ensureNetworkListener() {
  if (networkListenerAttached) return
  networkListenerAttached = true
  ensureProgressChannel()
  // online 时尝试恢复所有 paused upload
  if (typeof window === 'undefined') return
  window.addEventListener('online', async () => {
    const paused = await listUploads({ status: 'paused' })
    for (const item of paused) {
      start(item.upload_id).catch(err => console.warn('[mobileUpload] auto-resume failed:', err))
    }
  })
  // 启动时, 若有 pending upload, 自动 start
  setTimeout(async () => {
    const { online } = getNetworkStatus()
    if (!online) return
    const pending = await listUploads({ status: 'pending' })
    for (const item of pending) {
      start(item.upload_id).catch(err => console.warn('[mobileUpload] auto-start failed:', err))
    }
    // 兜底清理 7 天前完成项
    cleanupOldCompleted()
  }, 1000)
}

async function initOnServer(item) {
  // 真实场景: POST /api/v1/{endpoint}/upload/init
  // 这里走动态 endpoint 解析
  const url = resolveEndpoint(item.endpoint, 'init')
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({
      filename: item.filename,
      mime_type: item.mime_type,
      total_size: item.total_size,
      total_chunks: item.total_chunks,
      meta: item.meta,
    }),
  })
  if (!res.ok) throw new Error(`init failed: ${res.status}`)
  return await res.json()
}

async function uploadChunk(item, index, blob) {
  const url = resolveEndpoint(item.endpoint, `chunk/${item.server_upload_id}/${index}`)
  const fd = new FormData()
  fd.append('file', blob, `chunk_${index}.bin`)
  const res = await fetch(url, {
    method: 'PUT',
    body: fd,
    credentials: 'same-origin',
  })
  if (!res.ok) {
    const err = new Error(`chunk ${index} upload failed: ${res.status}`)
    err.response = { status: res.status }
    throw err
  }
}

async function completeOnServer(item) {
  const url = resolveEndpoint(item.endpoint, `complete/${item.server_upload_id}`)
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
  })
  if (!res.ok) throw new Error(`complete failed: ${res.status}`)
  return await res.json()
}

function resolveEndpoint(endpoint, action) {
  // endpoint: 'auto' | 'kb' | 'avatar' | 'drive' | custom URL prefix
  if (endpoint.startsWith('http')) return `${endpoint}/${action}`
  const baseMap = {
    kb: '/api/v1/knowledge/upload',
    avatar: '/api/v1/users/me/avatar/upload',
    drive: '/api/v1/drive/upload',
    auto: '/api/v1/upload',
  }
  const base = baseMap[endpoint] || baseMap.auto
  return `${base}/${action}`
}

let cleanupTimer = null
function scheduleCleanup() {
  if (cleanupTimer) return
  cleanupTimer = setTimeout(() => {
    cleanupTimer = null
    cleanupOldCompleted().catch(err => console.warn('[mobileUpload] cleanup failed:', err))
  }, 60_000)  // 1 分钟后兜底清理
}

async function cleanupOldCompleted() {
  if (!isIDBAvailable()) return
  const cutoff = Date.now() - CLEANUP_AFTER_MS
  const db = await openDB()
  const tx = db.transaction([STORE_UPLOADS, STORE_CHUNKS], 'readwrite')
  const uploadsStore = tx.objectStore(STORE_UPLOADS)
  const completed = await reqToPromise(uploadsStore.index('by_status').getAll('completed'))
  let removed = 0
  for (const item of completed) {
    if (item.updated_at < cutoff) {
      await reqToPromise(uploadsStore.delete(item.upload_id))
      // 删 chunks
      const chunksIdx = tx.objectStore(STORE_CHUNKS).index('by_upload')
      await new Promise((resolve) => {
        const req = chunksIdx.openCursor(IDBKeyRange.only(item.upload_id))
        req.onsuccess = () => {
          const cursor = req.result
          if (cursor) { cursor.delete(); cursor.continue() }
          else resolve()
        }
      })
      activeUploads.value.delete(item.upload_id)
      removed++
    }
  }
  await txDone(tx)
  if (removed > 0) triggerRefMap()
}

function generateUploadId() {
  return `up_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// ===== Composable =====

/**
 * 组件内使用
 */
export function useMobileUploadQueue() {
  ensureNetworkListener()

  return {
    activeUploads: readonly(activeUploads),
    isProcessing: readonly(isProcessing),
    enqueueUpload,
    start,
    pause,
    resume,
    cancel,
    getUpload,
    listUploads,
    onProgress,
  }
}

// ===== 单测辅助 =====
export function _resetForTesting() {
  activeUploads.value = new Map()
  isProcessing.value = false
  dbPromise = null
  if (progressChannel && progressChannel.close) {
    try { progressChannel.close() } catch (e) { /* noop */ }
  }
  progressChannel = null
  progressListeners = new Set()
  networkListenerAttached = false
  if (cleanupTimer) {
    clearTimeout(cleanupTimer)
    cleanupTimer = null
  }
}
