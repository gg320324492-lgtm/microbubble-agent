/**
 * 分片上传器 — 负责把 IndexedDB 里的 chunk 推到后端
 *
 * 关键能力：
 *   - uploadOne: 单片上传（带指数退避）
 *   - uploadAll: 顺序批量上传（保持 chunk_index 顺序）
 *   - enqueue: 入队（网络恢复时自动触发）
 *   - online 事件监听：浏览器从 offline 恢复时自动重传
 *
 * 失败模式：
 *   - 上传失败：抛 error，调用方决定（IDB 标记不更新，保留 pending）
 *   - 网络断开：online 事件不触发，pending 累积；恢复时一次性补传
 */

import { ref, readonly } from 'vue'
import axios from 'axios'
import * as idbStore from '@/utils/idbStore'
import { markReachable, markUnreachable } from '@/composables/useNetworkStatus'  // v2: 网络状态联动

// ===== 模块级状态（单例模式，多个组件共享） =====
const isUploading = ref(false)
const uploadQueue = new Map()  // meetingId → Array<{index, blob}>
const onlineListenersAttached = new Set()

/**
 * 单片上传（带指数退避）
 * @param {number} meetingId
 * @param {number} index
 * @param {Blob} blob
 * @param {object} [opts]
 * @param {number} [opts.maxRetries=5]
 * @returns {Promise<void>}
 */
export async function uploadOne(meetingId, index, blob, opts = {}) {
  const maxRetries = opts.maxRetries ?? 5
  let lastErr = null
  let sawNetworkError = false  // v2: 追踪是否所有重试都是网络类错误

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const fd = new FormData()
      fd.append('file', blob, `chunk_${index}.webm`)
      await axios.put(
        `/api/v1/meetings/${meetingId}/audio-chunk?chunk_index=${index}`,
        fd,
        { timeout: 30000 }
      )
      markReachable()  // v2: 任何一片成功 → 立刻告诉网络层"通的"
      return  // 成功
    } catch (err) {
      lastErr = err
      const status = err.response?.status
      // 4xx 客户端错（除 408/429）不重试
      if (status && status >= 400 && status < 500 && status !== 408 && status !== 429) {
        throw err
      }
      // 网络类错误（无 status 字段 = ECONNABORTED/ETIMEDOUT/ENETUNREACH 等）
      if (!status) sawNetworkError = true
      // 指数退避：1s, 2s, 4s, 8s, 16s, max 30s
      const wait = Math.min(30000, 1000 * Math.pow(2, attempt))
      await sleep(wait)
    }
  }
  // v2: 5 次重试耗尽且全是网络类错误 → 标记网络不可达
  // 4xx 业务错走 throw err 早退不会到这里
  if (sawNetworkError) markUnreachable()
  throw lastErr || new Error(`chunk ${index} 上传失败（重试 ${maxRetries} 次）`)
}

/**
 * 顺序批量上传（保持 chunk_index 顺序）
 * @param {number} meetingId
 * @param {Array<{chunk_index: number, blob: Blob}>} chunks
 * @returns {Promise<{uploaded: number, failed: number}>}
 */
export async function uploadAll(meetingId, chunks) {
  if (chunks.length === 0) return { uploaded: 0, failed: 0 }
  isUploading.value = true
  let uploaded = 0
  let failed = 0
  try {
    for (const chunk of chunks) {
      try {
        await uploadOne(meetingId, chunk.chunk_index, chunk.blob)
        await idbStore.markChunkUploaded(meetingId, chunk.chunk_index)
        uploaded++
      } catch (err) {
        console.warn(`[uploader] chunk ${chunk.chunk_index} 失败:`, err?.message)
        failed++
        break  // 严格顺序：失败就停，避免乱序
      }
    }
  } finally {
    isUploading.value = false
  }
  return { uploaded, failed }
}

/**
 * 入队 + 立即尝试上传
 * @param {number} meetingId
 * @param {Array<{chunk_index: number, blob: Blob}>} chunks
 */
export function enqueue(meetingId, chunks) {
  if (!uploadQueue.has(meetingId)) {
    uploadQueue.set(meetingId, [])
  }
  const queue = uploadQueue.get(meetingId)
  for (const c of chunks) {
    if (!queue.find(x => x.chunk_index === c.chunk_index)) {
      queue.push(c)
    }
  }
  // 异步触发（不阻塞调用方）
  drainQueue(meetingId).catch(err => {
    console.warn('[uploader] drainQueue 失败:', err)
  })
}

/**
 * 排空某会议的队列
 */
async function drainQueue(meetingId) {
  if (isUploading.value) return
  const queue = uploadQueue.get(meetingId) || []
  if (queue.length === 0) return
  // 转 IDB pending（保证即使进程退出也能恢复）
  const result = await uploadAll(meetingId, queue)
  // 清掉已成功的
  uploadQueue.set(meetingId, queue.slice(result.uploaded))
  return result
}

/**
 * 监听 online 事件（仅一次，模块级单例）
 */
function ensureOnlineListener() {
  if (onlineListenersAttached.has('global')) return
  onlineListenersAttached.add('global')

  const onOnline = async () => {
    console.log('[uploader] 检测到 online 事件，扫描所有待传 chunks')
    // v2.2 修复 (2026-07-03): 双层扫描
    //   1. 优先 uploadQueue Map (in-memory, 快) — catch 主动 enqueue 的 chunk 在这里
    //   2. 兜底 IDB 全表扫 — 录音失败但 enqueue 漏了 / 刷新打断 / 新代码路径绕过
    // 合并去重 meetings → 各自 drainQueue
    const meetings = new Set()
    for (const [meetingId] of uploadQueue) meetings.add(meetingId)
    try {
      const idbMeetings = await idbStore.getAllMeetingsWithPending()
      for (const m of idbMeetings) meetings.add(m.meeting_id)
    } catch (err) {
      console.warn('[uploader] 扫 IDB pending meetings 失败, 继续内存队列:', err)
    }
    for (const meetingId of meetings) {
      try {
        const pending = await idbStore.getPendingChunks(meetingId)
        if (pending.length > 0) {
          console.log(`[uploader] 会议 ${meetingId} 有 ${pending.length} 片待传`)
          // 把 IDB 找到但 uploadQueue 没的 chunk 入队, 让 drainQueue 处理
          if (!uploadQueue.has(meetingId) || uploadQueue.get(meetingId).length === 0) {
            uploader.enqueue(meetingId, pending)
          } else {
            await drainQueue(meetingId)
          }
        }
      } catch (err) {
        console.warn(`[uploader] 会议 ${meetingId} 恢复失败:`, err)
      }
    }
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('online', onOnline)
  }
}

ensureOnlineListener()

/**
 * Composable 形式（供组件内 reactive 使用）
 */
export function useChunkedUploader() {
  return {
    isUploading: readonly(isUploading),
    uploadOne,
    uploadAll,
    enqueue,
    drainQueue,
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
