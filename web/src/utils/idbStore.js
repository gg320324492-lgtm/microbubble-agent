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
// v2 (2026-11-16 会议录音深度加固): chunks 增加 [meeting_id, chunk_index] 唯一复合索引。
// 老库可能有重复 index；升级时去重保留最新一条，再建唯一索引，避免刷新恢复重复写导致重复上传。
const DB_VERSION = 2
const INDEX_MEETING_CHUNK = 'by_meeting_chunk'
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
      const oldVersion = event.oldVersion || 0
      let chunksStore
      if (!db.objectStoreNames.contains(STORE_CHUNKS)) {
        chunksStore = db.createObjectStore(STORE_CHUNKS, {
          keyPath: 'id',
          autoIncrement: true,
        })
        chunksStore.createIndex('by_meeting', 'meeting_id', { unique: false })
      } else {
        chunksStore = req.transaction.objectStore(STORE_CHUNKS)
      }
      if (!db.objectStoreNames.contains(STORE_META)) {
        db.createObjectStore(STORE_META, { keyPath: 'meeting_id' })
      }
      // v2: 去重历史重复 chunk_index，再建唯一复合索引。
      // 老库里 add(record) 可能写入同会议同 index 多行（刷新恢复/重复回调），
      // 唯一索引前必须只保留每个 (meeting_id, chunk_index) 最新一条，否则 upgrade 失败。
      if (oldVersion < 2 && !chunksStore.indexNames.contains(INDEX_MEETING_CHUNK)) {
        const allReq = chunksStore.getAll()
        allReq.onsuccess = () => {
          const records = allReq.result || []
          const latest = new Map()
          for (const record of records) {
            const key = `${record.meeting_id}:${record.chunk_index}`
            const prev = latest.get(key)
            if (!prev || (record.created_at || 0) >= (prev.created_at || 0)) {
              latest.set(key, record)
            }
          }
          const keepIds = new Set([...latest.values()].map(r => r.id))
          if (keepIds.size === records.length) {
            chunksStore.createIndex(INDEX_MEETING_CHUNK, ['meeting_id', 'chunk_index'], { unique: true })
            return
          }
          // 用游标逐个删除重复项；每个 delete 都落在同一 upgrade 事务里，
          // 游标完成后再 createIndex，避免唯一索引撞到尚未删除的旧记录。
          const cursorReq = chunksStore.openCursor()
          cursorReq.onsuccess = (ev) => {
            const cursor = ev.target.result
            if (!cursor) {
              chunksStore.createIndex(INDEX_MEETING_CHUNK, ['meeting_id', 'chunk_index'], { unique: true })
              return
            }
            if (!keepIds.has(cursor.value.id)) cursor.delete()
            cursor.continue()
          }
          cursorReq.onerror = () => {
            console.error('[idbStore] v2 去重游标失败:', cursorReq.error)
          }
        }
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
  // 2026-11-16 加固：同会议同 index 是逻辑唯一键。先查复合唯一索引复用主键再 put，
  // 否则重复回调 / 刷新恢复会用新自增主键 add 撞 ConstraintError 并丢失后续上传链。
  const existing = store.indexNames.contains(INDEX_MEETING_CHUNK)
    ? await reqToPromise(store.index(INDEX_MEETING_CHUNK).get(IDBKeyRange.only([meetingId, index])))
    : null
  if (existing) record.id = existing.id
  const id = await reqToPromise(store.put(record))
  await txDone(tx)
  return id
}

/** putChunk 的语义化别名：upsert 同会议同序号的 chunk */
export const upsertChunk = putChunk

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
 * 列出有未上传 chunk 的所有 meeting_id（去重 + 含每个 meeting 的 pending count）
 * 用于 online 重传 / 启动恢复时不依赖 uploadQueue 全局 Map,
 * 也能从 IDB 找到所有"孤儿" pending chunk（录音中失败的 chunk 只在 IDB 标 uploaded=false）。
 *
 * 实现: 全表扫 chunks, 过滤 uploaded=false, 按 meeting_id 聚合 → 去重 Map。
 * 性能: O(N) 单次 ≤ 10ms (单会议 720 chunks/h, 数小时录音仍 < 5000 条)。
 *       如未来 N 巨大 (单浏览器万级), 再加 [meeting_id, uploaded] 复合索引 (需 DB_VERSION 升级)。
 * @returns {Promise<Array<{meeting_id: number, count: number}>>}
 */
export async function getAllMeetingsWithPending() {
  const db = await openDB()
  const tx = db.transaction(STORE_CHUNKS, 'readonly')
  const store = tx.objectStore(STORE_CHUNKS)
  const all = await reqToPromise(store.getAll())
  await txDone(tx)
  const map = new Map()
  for (const r of all) {
    if (r.uploaded) continue
    map.set(r.meeting_id, (map.get(r.meeting_id) || 0) + 1)
  }
  return Array.from(map, ([meeting_id, count]) => ({ meeting_id, count }))
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
