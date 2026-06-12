/**
 * IndexedDB 存储封装 — 会议录音 chunk 持久化
 *
 * 解决 2026-06-12 会议 #84 问题：录音 Blob 全部存内存，刷新/断网即丢失。
 * 本模块把每个 5s 的 WebM chunk 写 IndexedDB，断网/刷新/重启浏览器后仍可恢复。
 *
 * 表结构（v1）：
 *   - chunks       主键 autoIncrement，存 chunk blob + meeting_id + index + uploaded 标志
 *                  索引：by_meeting (meeting_id)，by_meeting_uploaded ([meeting_id, uploaded])
 *   - uploadQueue  待上传队列（chunks 表的子集，但便于扫描）
 *   - meta         会议级元数据（meeting_id → {title, startedAt, lastChunkIndex}）
 *
 * 兼容性：Chrome / Edge / Firefox / Safari 14+ 全支持，无第三方依赖。
 */

const DB_NAME = 'microbubble_recorder'
const DB_VERSION = 1
const STORE_CHUNKS = 'chunks'
const STORE_META = 'meta'

let dbPromise = null

/**
 * 打开（惰性单例）
 * @returns {Promise<IDBDatabase>}
 */
export function openDB() {
  if (dbPromise) return dbPromise

  dbPromise = new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB not supported in this environment'))
      return
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = (event) => {
      const db = event.target.result
      if (!db.objectStoreNames.contains(STORE_CHUNKS)) {
        const store = db.createObjectStore(STORE_CHUNKS, {
          keyPath: 'id',
          autoIncrement: true,
        })
        store.createIndex('by_meeting', 'meeting_id', { unique: false })
      }
      if (!db.objectStoreNames.contains(STORE_META)) {
        db.createObjectStore(STORE_META, { keyPath: 'meeting_id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
    req.onblocked = () => reject(new Error('IndexedDB open blocked'))
  })

  return dbPromise
}

/**
 * 包装 IndexedDB 请求为 Promise
 * @param {IDBRequest} req
 * @returns {Promise<any>}
 */
function reqToPromise(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

/**
 * 写入一个 chunk
 * @param {number} meetingId
 * @param {number} index  顺序号（0-based）
 * @param {Blob} blob
 * @param {{ uploaded?: boolean }} [opts]
 * @returns {Promise<number>}  写入的 id
 */
export async function putChunk(meetingId, index, blob, opts = {}) {
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readwrite')
  const store = tx.objectStore(STORE_CHUNKS)
  // 如果 blob 不是真正的 Blob（如 fake-indexeddb 在 jsdom 中反序列化的对象），
  // 重新包装为 Blob 以便后续 FormData.append 不会抛错
  const safeBlob = blob instanceof Blob ? blob : new Blob([blob], { type: 'audio/webm' })
  const record = {
    meeting_id: meetingId,
    chunk_index: index,
    blob: safeBlob,
    uploaded: !!opts.uploaded,
    created_at: Date.now(),
    size: safeBlob.size,
  }
  const id = await reqToPromise(store.add(record))
  await txDone(tx)
  return id
}

/**
 * 把一个 chunk 标记为已上传（用 chunk_index 查 + 改字段）
 * 找到该 meeting_id 下 chunk_index 匹配的那条记录，更新 uploaded=true
 */
export async function markChunkUploaded(meetingId, chunkIndex) {
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readwrite')
  const store = tx.objectStore(STORE_CHUNKS)
  const idx = store.index('by_meeting')
  const records = await reqToPromise(idx.getAll(IDBKeyRange.only(meetingId)))
  const target = records.find(r => r.chunk_index === chunkIndex && !r.uploaded)
  if (target) {
    target.uploaded = true
    target.uploaded_at = Date.now()
    await reqToPromise(store.put(target))
  }
  await txDone(tx)
  return !!target
}

/**
 * 取出记录时把 blob 重新包装为真正的 Blob（fake-indexeddb 在 jsdom 中会反序列化为普通对象）
 */
function _ensureBlob(record) {
  if (record && record.blob && !(record.blob instanceof Blob)) {
    record.blob = new Blob([record.blob], { type: 'audio/webm' })
  }
  return record
}

/**
 * 获取某会议的所有 chunk（按 index 升序）
 * @returns {Promise<Array<{id, meeting_id, chunk_index, blob, uploaded, created_at, size}>>}
 */
export async function getAllChunks(meetingId) {
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readonly')
  const store = tx.objectStore(STORE_CHUNKS)
  const idx = store.index('by_meeting')
  const records = await reqToPromise(idx.getAll(IDBKeyRange.only(meetingId)))
  await txDone(tx)
  return records.map(_ensureBlob).sort((a, b) => a.chunk_index - b.chunk_index)
}

/**
 * 获取待上传的 chunk（uploaded=false），按 index 升序
 */
export async function getPendingChunks(meetingId) {
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readonly')
  const store = tx.objectStore(STORE_CHUNKS)
  const idx = store.index('by_meeting')
  const records = await reqToPromise(idx.getAll(IDBKeyRange.only(meetingId)))
  await txDone(tx)
  return records
    .map(_ensureBlob)
    .filter(r => !r.uploaded)
    .sort((a, b) => a.chunk_index - b.chunk_index)
}

/**
 * 获取已上传的 chunk 数
 */
export async function countUploaded(meetingId) {
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readonly')
  const store = tx.objectStore(STORE_CHUNKS)
  const idx = store.index('by_meeting')
  const records = await reqToPromise(idx.getAll(IDBKeyRange.only(meetingId)))
  await txDone(tx)
  return records.filter(r => r.uploaded).length
}

/**
 * 获取最大已收到的 chunk_index（-1 表示没有）
 */
export async function getLastChunkIndex(meetingId) {
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readonly')
  const store = tx.objectStore(STORE_CHUNKS)
  const idx = store.index('by_meeting')
  const records = await reqToPromise(idx.getAll(IDBKeyRange.only(meetingId)))
  await txDone(tx)
  if (records.length === 0) return -1
  return Math.max(...records.map(r => r.chunk_index))
}

/**
 * 删除单个 chunk
 */
export async function deleteChunk(id) {
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readwrite')
  await reqToPromise(tx.objectStore(STORE_CHUNKS).delete(id))
  await txDone(tx)
}

/**
 * 删除某会议的所有 chunk
 */
export async function deleteAllChunks(meetingId) {
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readwrite')
  const store = tx.objectStore(STORE_CHUNKS)
  const idx = store.index('by_meeting')
  const records = await reqToPromise(idx.getAllKeys(IDBKeyRange.only(meetingId)))
  for (const key of records) {
    await reqToPromise(store.delete(key))
  }
  await txDone(tx)
  return records.length
}

/**
 * 写入会议元数据
 */
export async function putMeta(meetingId, meta) {
  const db = await openDB()
  const tx = db.transaction(STORE_META, 'readwrite')
  const record = { meeting_id: meetingId, ...meta, updated_at: Date.now() }
  await reqToPromise(tx.objectStore(STORE_META).put(record))
  await txDone(tx)
  return record
}

/**
 * 读取会议元数据
 */
export async function getMeta(meetingId) {
  const db = await openDB()
  const tx = db.transaction(STORE_META, 'readonly')
  const record = await reqToPromise(tx.objectStore(STORE_META).get(meetingId))
  await txDone(tx)
  return record || null
}

/**
 * 估算已用配额（navigator.storage.estimate，浏览器支持时）
 * @returns {Promise<{usage: number, quota: number} | null>}
 */
export async function estimateStorage() {
  if (typeof navigator === 'undefined' || !navigator.storage?.estimate) return null
  try {
    return await navigator.storage.estimate()
  } catch {
    return null
  }
}

/**
 * 申请持久化存储（弹一次性权限，请求浏览器不主动驱逐）
 */
export async function requestPersistence() {
  if (typeof navigator === 'undefined' || !navigator.storage?.persist) return false
  try {
    return await navigator.storage.persist()
  } catch {
    return false
  }
}

/**
 * 等待事务完成
 */
function txDone(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error || new Error('Transaction aborted'))
  })
}

/**
 * 重置整个数据库（仅测试用）
 */
export async function _resetAll() {
  const db = await openDB()
  await Promise.all([
    new Promise((resolve, reject) => {
      const tx = db.transaction([STORE_CHUNKS, STORE_META], 'readwrite')
      tx.objectStore(STORE_CHUNKS).clear()
      tx.objectStore(STORE_META).clear()
      tx.oncomplete = resolve
      tx.onerror = () => reject(tx.error)
    }),
  ])
}
