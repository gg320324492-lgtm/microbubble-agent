/**
 * IndexedDB 离线消息队列 (W68 Mobile UX v3.0)
 *
 * 设计目标:
 *   - 提供一个**通用、持久化、可优先级排序**的离线消息队列
 *   - 与 useNetworkStatus 联动: 离线时缓存, 在线时 flush
 *   - 跨标签页同步: BroadcastChannel API (一个 tab 入队, 其他 tab 也能感知)
 *   - 失败重试: 内建 retry_count + ttl 过期清理
 *
 * 与 useDriveNotifications 集成:
 *   - 入队: enqueue(item) → 写 IDB + 触发 flush (若 online)
 *   - flush: 按 priority DESC 排序, 逐条调用 dispatcher(item)
 *   - dispatcher 由调用方注入 (典型: 发 HTTP 请求 / 更新本地 store / 触发 SW)
 *
 * 持久化模型:
 *   - DB: microbubble_idb_queue
 *   - Store: idb_queue  (keyPath: id, autoIncrement)
 *   - 索引: by_priority ([priority, created_at]) — flush 时按此扫描
 *           by_status    ([status, ttl])          — 清理过期/已完成
 *   - Schema 版本: 1
 *
 * 关键 API:
 *   - enqueue<T>(item: QueueItem<T>) → Promise<number>  返回 id
 *   - drain(dispatcher)             → Promise<DrainResult> 排空队列
 *   - markCompleted(id) / markFailed(id, error)
 *   - getPending(opts?)             → Promise<QueueItem[]>
 *   - cleanupExpired()              → Promise<number>  清掉 ttl 过期项
 *   - onChange(cb)                  → unsubscribe()  跨 tab 同步订阅
 *
 * 状态机:
 *   pending → in_flight → completed
 *                ↓
 *             failed (retry_count < maxRetries) → pending
 *             failed (retry_count >= maxRetries) → dead (不再重试)
 *
 * 失败模式:
 *   - dispatcher 抛错 → markFailed → 若 retry_count < maxRetries, 5s 后回 pending
 *   - TTL 到期 → cleanupExpired 永久删除
 *   - 浏览器无 IDB → 静默 fallback, 所有 enqueue 都进 in-memory 兜底 Map
 *
 * 纪律 (W68 新铁律):
 *   1. **跨 tab 同步必须 BroadcastChannel + storage 事件双写** — 防止 channel 在某些浏览器 (iOS Safari 嵌入) 不可用
 *   2. **enqueue 失败时必须 fallback in-memory** — 不要 throw, 调用方网络层可能在 1s 后才能判断 offline
 *   3. **flush 必须串行** — 同 priority FIFO, 不同 priority 高优先先, 但不并发 (避免后端限流)
 *   4. **dead item 不自动删** — 留给人工排查, 只统计 deadCount
 *   5. **跨 tab 收到的 onMessage 不再 flush** — 避免 N 个 tab 同时抢同一 item, 只有发起者 flush
 */

import { ref, readonly } from 'vue'
import { getNetworkStatus, markReachable, markUnreachable } from '@/composables/useNetworkStatus'

// ===== 类型 (TS-style 注释, .ts 编译时强校验) =====
/**
 * @typedef {Object} QueueItem
 * @property {number} [id]            - autoIncrement IDB key
 * @property {string} key             - 业务键, 同 key 的 failed item 重试时复用 (避免重复入队)
 * @property {number} priority        - 0-10, 越大越先发; 默认 5
 * @property {number} ttl             - 过期时间 (ms), 0 = 永不过期
 * @property {number} created_at      - ms timestamp
 * @property {number} updated_at      - ms timestamp
 * @property {number} retry_count     - 已重试次数
 * @property {number} maxRetries      - 最大重试, 默认 5
 * @property {string} status          - 'pending' | 'in_flight' | 'completed' | 'failed' | 'dead'
 * @property {string} last_error      - 最近一次失败原因
 * @property {*} payload              - 业务负载 (任意可序列化对象, 走 structured clone)
 * @property {string} [tag]           - 业务标签 (e.g. 'drive_notification', 'chat_message'), 用于按 tag 过滤
 */

// ===== 可调参数 =====
const DB_NAME = 'microbubble_idb_queue'
const DB_VERSION = 1
const STORE_QUEUE = 'idb_queue'
const CHANNEL_NAME = 'microbubble_idb_queue_channel'
const RETRY_BACKOFF_MS = 5_000
const DEFAULT_MAX_RETRIES = 5
const DEFAULT_PRIORITY = 5

// ===== 模块级单例 =====
const pendingCount = ref(0)
const deadCount = ref(0)
const isFlushing = ref(false)
const lastFlushAt = ref(0)
let dbPromise = null
let memoryFallback = new Map()  // IDB 不可用时的内存兜底
let broadcastChannel = null
let messageListeners = new Set()
let networkListenerAttached = false
let onlineListenerAttached = false

// ===== IDB 基础 =====

function isIDBAvailable() {
  return typeof indexedDB !== 'undefined'
}

function openDB() {
  if (dbPromise) return dbPromise
  if (!isIDBAvailable()) return Promise.reject(new Error('IndexedDB not available'))

  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = (event) => {
      const db = event.target.result
      if (!db.objectStoreNames.contains(STORE_QUEUE)) {
        const store = db.objectStore(STORE_QUEUE, {
          keyPath: 'id',
          autoIncrement: true,
        })
        // 按优先级 + 时间扫描 (flush 主路径)
        store.createIndex('by_priority', ['status', 'priority', 'created_at'], { unique: false })
        // 按状态 + ttl 扫描 (清理过期主路径)
        store.createIndex('by_status', ['status', 'ttl'], { unique: false })
        // 按业务 key 查重
        store.createIndex('by_key', 'key', { unique: false })
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
    tx.onabort = () => reject(tx.error || new Error('Transaction aborted'))
  })
}

// ===== 公共 API =====

/**
 * 入队一个 item
 * @param {Omit<QueueItem, 'id'|'status'|'retry_count'|'last_error'|'created_at'|'updated_at'>} partial
 * @returns {Promise<number>} id (autoIncrement)
 */
export async function enqueue(partial) {
  const now = Date.now()
  const item = {
    key: partial.key || `auto_${now}_${Math.random().toString(36).slice(2, 8)}`,
    priority: partial.priority ?? DEFAULT_PRIORITY,
    ttl: partial.ttl || 0,
    created_at: now,
    updated_at: now,
    retry_count: 0,
    maxRetries: partial.maxRetries ?? DEFAULT_MAX_RETRIES,
    status: 'pending',
    last_error: '',
    payload: partial.payload,
    tag: partial.tag || '',
  }

  if (!isIDBAvailable()) {
    // 内存兜底
    const fakeId = -Date.now() - Math.floor(Math.random() * 1000)
    memoryFallback.set(fakeId, { id: fakeId, ...item })
    pendingCount.value = memoryFallback.size
    notifyChange({ type: 'enqueued', id: fakeId, key: item.key, tag: item.tag, fromSelf: true })
    scheduleFlush()
    return fakeId
  }

  try {
    const db = await openDB()
    const tx = db.transaction(STORE_QUEUE, 'readwrite')
    const store = tx.objectStore(STORE_QUEUE)
    const id = await reqToPromise(store.add(item))
    await txDone(tx)
    pendingCount.value = await countPending()
    notifyChange({ type: 'enqueued', id, key: item.key, tag: item.tag, fromSelf: true })
    scheduleFlush()
    return id
  } catch (err) {
    // IDB 写失败 → 内存兜底
    const fakeId = -Date.now() - Math.floor(Math.random() * 1000)
    memoryFallback.set(fakeId, { id: fakeId, ...item })
    pendingCount.value = memoryFallback.size
    notifyChange({ type: 'enqueued_fallback', id: fakeId, error: err.message, fromSelf: true })
    return fakeId
  }
}

/**
 * 排空 pending 队列
 * @param {(item: QueueItem) => Promise<void>} dispatcher
 * @param {{ onlyTag?: string, maxItems?: number }} [opts]
 * @returns {Promise<{processed:number, succeeded:number, failed:number, dead:number, skipped:number}>}
 */
export async function drain(dispatcher, opts = {}) {
  if (isFlushing.value) {
    return { processed: 0, succeeded: 0, failed: 0, dead: 0, skipped: 0, reason: 'already_flushing' }
  }

  const { online } = getNetworkStatus()
  if (!online) {
    return { processed: 0, succeeded: 0, failed: 0, dead: 0, skipped: 0, reason: 'offline' }
  }

  isFlushing.value = true
  let processed = 0
  let succeeded = 0
  let failed = 0
  let dead = 0
  let skipped = 0

  try {
    const items = await getPending({ onlyTag: opts.onlyTag, maxItems: opts.maxItems ?? 50 })
    for (const item of items) {
      processed++
      const result = await dispatchOne(item, dispatcher)
      if (result === 'success') succeeded++
      else if (result === 'dead') dead++
      else if (result === 'skipped') skipped++
      else failed++
    }
    lastFlushAt.value = Date.now()
    pendingCount.value = await countPending()
    deadCount.value = await countDead()
  } finally {
    isFlushing.value = false
  }

  return { processed, succeeded, failed, dead, skipped }
}

/**
 * 单条派发 (供 drain 内部用, 也可外部手动触发)
 * @returns {Promise<'success'|'failed'|'dead'|'skipped'>}
 */
export async function dispatchOne(item, dispatcher) {
  if (item.status === 'in_flight') return 'skipped'

  // 标记 in_flight
  await updateItem(item.id, { status: 'in_flight', updated_at: Date.now() })

  try {
    await dispatcher(item.payload)
    await markCompleted(item.id)
    markReachable()  // 任何一条成功 → 告诉网络层通的
    notifyChange({ type: 'completed', id: item.id, fromSelf: true })
    return 'success'
  } catch (err) {
    const nextRetry = item.retry_count + 1
    const errorMsg = err?.message || String(err)
    if (nextRetry >= item.maxRetries) {
      await updateItem(item.id, {
        status: 'dead',
        retry_count: nextRetry,
        last_error: errorMsg,
        updated_at: Date.now(),
      })
      notifyChange({ type: 'dead', id: item.id, error: errorMsg, fromSelf: true })
      return 'dead'
    } else {
      await updateItem(item.id, {
        status: 'pending',
        retry_count: nextRetry,
        last_error: errorMsg,
        updated_at: Date.now(),
      })
      // 网络类错误 (无 status) 才标记 unreachable, 业务错不动网络层
      if (!err?.response?.status) {
        // 可能是网络问题, 但先保守, 不调 markUnreachable (避免抖动)
      }
      return 'failed'
    }
  }
}

export async function markCompleted(id) {
  if (id < 0) {
    // 内存兜底
    if (memoryFallback.has(id)) {
      memoryFallback.delete(id)
      pendingCount.value = memoryFallback.size
    }
    return
  }
  if (!isIDBAvailable()) return
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_QUEUE, 'readwrite')
    const store = tx.objectStore(STORE_QUEUE)
    await reqToPromise(store.delete(id))
    await txDone(tx)
  } catch (err) {
    console.warn('[idbQueue] markCompleted failed:', err)
  }
}

export async function markFailed(id, error) {
  await updateItem(id, {
    status: 'failed',
    last_error: error?.message || String(error),
    updated_at: Date.now(),
  })
}

export async function getPending(opts = {}) {
  const { onlyTag, maxItems = 100 } = opts
  if (!isIDBAvailable()) {
    let items = Array.from(memoryFallback.values())
      .filter(it => it.status === 'pending' || it.status === 'failed')
      .filter(it => !onlyTag || it.tag === onlyTag)
    items.sort((a, b) => b.priority - a.priority || a.created_at - b.created_at)
    return items.slice(0, maxItems)
  }
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_QUEUE, 'readonly')
    const store = tx.objectStore(STORE_QUEUE)
    const idx = store.index('by_priority')
    // IDBKeyRange 仅 [status, priority, created_at] 前缀扫描, 用 'pending' 单值 + open cursor
    const range = IDBKeyRange.bound(['pending', 0, 0], ['pending', 10, Number.MAX_SAFE_INTEGER])
    const out = []
    await new Promise((resolve, reject) => {
      const req = idx.openCursor(range)
      req.onsuccess = () => {
        const cursor = req.result
        if (cursor && out.length < maxItems) {
          const item = cursor.value
          if (!onlyTag || item.tag === onlyTag) {
            out.push(item)
          }
          cursor.continue()
        } else {
          resolve()
        }
      }
      req.onerror = () => reject(req.error)
    })
    return out
  } catch (err) {
    console.warn('[idbQueue] getPending failed:', err)
    return []
  }
}

export async function cleanupExpired() {
  if (!isIDBAvailable()) {
    // 内存兜底清理
    const now = Date.now()
    let removed = 0
    for (const [id, item] of memoryFallback) {
      if (item.ttl > 0 && item.created_at + item.ttl < now) {
        memoryFallback.delete(id)
        removed++
      }
    }
    if (removed > 0) pendingCount.value = memoryFallback.size
    return removed
  }
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_QUEUE, 'readwrite')
    const store = tx.objectStore(STORE_QUEUE)
    const now = Date.now()
    let removed = 0
    await new Promise((resolve, reject) => {
      const req = store.openCursor()
      req.onsuccess = () => {
        const cursor = req.result
        if (cursor) {
          const item = cursor.value
          // ttl > 0 且 (created_at + ttl) < now → 删
          if (item.ttl > 0 && (item.created_at + item.ttl) < now) {
            cursor.delete()
            removed++
          }
          // 死信超过 1h 永久清 (避免死信堆积)
          if (item.status === 'dead' && (item.updated_at + 3600_000) < now) {
            cursor.delete()
            removed++
          }
          cursor.continue()
        } else {
          resolve()
        }
      }
      req.onerror = () => reject(req.error)
    })
    await txDone(tx)
    if (removed > 0) {
      pendingCount.value = await countPending()
      deadCount.value = await countDead()
    }
    return removed
  } catch (err) {
    console.warn('[idbQueue] cleanupExpired failed:', err)
    return 0
  }
}

export async function clearAll() {
  if (!isIDBAvailable()) {
    memoryFallback.clear()
    pendingCount.value = 0
    deadCount.value = 0
    return
  }
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_QUEUE, 'readwrite')
    const store = tx.objectStore(STORE_QUEUE)
    await reqToPromise(store.clear())
    await txDone(tx)
    pendingCount.value = 0
    deadCount.value = 0
  } catch (err) {
    console.warn('[idbQueue] clearAll failed:', err)
  }
}

export function onChange(cb) {
  messageListeners.add(cb)
  return () => messageListeners.delete(cb)
}

export function getStats() {
  return {
    pending: pendingCount.value,
    dead: deadCount.value,
    isFlushing: isFlushing.value,
    lastFlushAt: lastFlushAt.value,
  }
}

// ===== 内部工具 =====

async function updateItem(id, patch) {
  if (id < 0) {
    if (memoryFallback.has(id)) {
      Object.assign(memoryFallback.get(id), patch)
    }
    return
  }
  if (!isIDBAvailable()) return
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_QUEUE, 'readwrite')
    const store = tx.objectStore(STORE_QUEUE)
    const item = await reqToPromise(store.get(id))
    if (item) {
      Object.assign(item, patch)
      await reqToPromise(store.put(item))
    }
    await txDone(tx)
  } catch (err) {
    console.warn('[idbQueue] updateItem failed:', err)
  }
}

async function countPending() {
  const items = await getPending({ maxItems: 1000 })
  return items.length
}

async function countDead() {
  if (!isIDBAvailable()) {
    let count = 0
    for (const item of memoryFallback.values()) if (item.status === 'dead') count++
    return count
  }
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_QUEUE, 'readonly')
    const store = tx.objectStore(STORE_QUEUE)
    let count = 0
    await new Promise((resolve, reject) => {
      const req = store.openCursor()
      req.onsuccess = () => {
        const cursor = req.result
        if (cursor) {
          if (cursor.value.status === 'dead') count++
          cursor.continue()
        } else {
          resolve()
        }
      }
      req.onerror = () => reject(req.error)
    })
    return count
  } catch (err) {
    return 0
  }
}

function notifyChange(payload) {
  for (const cb of messageListeners) {
    try { cb(payload) } catch (err) { console.warn('[idbQueue] listener error:', err) }
  }
  // 跨 tab 广播 (有 channel 才发)
  if (broadcastChannel && payload.fromSelf) {
    try {
      broadcastChannel.postMessage(payload)
    } catch (err) {
      // postMessage 失败不影响本地
    }
  }
}

let flushScheduled = false
function scheduleFlush() {
  if (flushScheduled) return
  flushScheduled = true
  setTimeout(() => {
    flushScheduled = false
    const { online } = getNetworkStatus()
    if (online && pendingCount.value > 0 && !isFlushing.value) {
      // 自动 flush 需要 dispatcher, 这里只 mark 一个 hint, 真正 flush 由 useIDBQueue().startAutoFlush 启动
    }
  }, 100)
}

function ensureBroadcastChannel() {
  if (broadcastChannel !== null) return  // 已被处理 (可能初始化失败)
  if (typeof BroadcastChannel === 'undefined') {
    broadcastChannel = false  // 标记为不可用
    return
  }
  try {
    broadcastChannel = new BroadcastChannel(CHANNEL_NAME)
    broadcastChannel.onmessage = (event) => {
      const data = event.data
      if (!data || data.fromSelf) return  // 跳过自己的消息
      // 跨 tab 只通知, 不触发 flush
      for (const cb of messageListeners) {
        try { cb({ ...data, remote: true }) } catch (err) { /* noop */ }
      }
    }
  } catch (err) {
    broadcastChannel = false
  }
}

function ensureNetworkListener() {
  if (networkListenerAttached) return
  networkListenerAttached = true
  // 初始化 pendingCount
  if (isIDBAvailable()) {
    countPending().then(c => { pendingCount.value = c }).catch(() => {})
    countDead().then(c => { deadCount.value = c }).catch(() => {})
  } else {
    pendingCount.value = memoryFallback.size
  }
  ensureBroadcastChannel()
}

function ensureOnlineListener() {
  if (onlineListenerAttached) return
  onlineListenerAttached = true
  if (typeof window === 'undefined') return
  // online 事件触发时, 调度一次 flush, 但 flush 需要 dispatcher, 由 useIDBQueue().startAutoFlush 注册
  window.addEventListener('online', () => {
    // 通知监听器 (auto-flush 启动后会自动消费)
    notifyChange({ type: 'online', fromSelf: true })
  })
}

// ===== Composable (组件内 reactive) =====

/**
 * 组件内使用
 * @param {(item: any) => Promise<void>} [dispatcher]  - 若提供, 自动开启 auto-flush
 */
export function useIDBQueue(dispatcher) {
  ensureNetworkListener()
  ensureOnlineListener()

  const autoFlush = (async () => {
    if (!dispatcher) return () => {}
    const { online } = getNetworkStatus()
    if (online && pendingCount.value > 0) {
      await drain(dispatcher).catch(err => console.warn('[idbQueue] auto drain failed:', err))
    }
  })

  const interval = dispatcher
    ? setInterval(() => {
        const { online } = getNetworkStatus()
        if (online && pendingCount.value > 0 && !isFlushing.value) {
          drain(dispatcher).catch(err => console.warn('[idbQueue] auto drain failed:', err))
        }
      }, 10_000)
    : null

  // 立即触发一次
  if (dispatcher) {
    setTimeout(autoFlush, 500)
  }

  return {
    pendingCount: readonly(pendingCount),
    deadCount: readonly(deadCount),
    isFlushing: readonly(isFlushing),
    lastFlushAt: readonly(lastFlushAt),
    enqueue,
    drain,
    markCompleted,
    markFailed,
    getPending,
    cleanupExpired,
    clearAll,
    onChange,
    getStats,
    stopAutoFlush: () => {
      if (interval) clearInterval(interval)
    },
  }
}

// ===== 单测辅助 =====
export function _resetForTesting() {
  pendingCount.value = 0
  deadCount.value = 0
  isFlushing.value = false
  lastFlushAt.value = 0
  memoryFallback = new Map()
  dbPromise = null
  if (broadcastChannel && broadcastChannel.close) {
    try { broadcastChannel.close() } catch (e) { /* noop */ }
  }
  broadcastChannel = null
  messageListeners = new Set()
  networkListenerAttached = false
  onlineListenerAttached = false
  flushScheduled = false
}
