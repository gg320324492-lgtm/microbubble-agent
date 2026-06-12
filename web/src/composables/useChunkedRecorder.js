/**
 * 边录边传录音器 — 包装 useGlobalRecorder，每个 chunk 自动写 IndexedDB
 *
 * 核心：每 1s MediaRecorder 触发 ondataavailable → useGlobalRecorder.onChunk 回调
 *      → 本 composable 同步写 IDB + 触发上传（失败不阻塞，标记 uploaded=false）
 *
 * 解决问题：2026-06-12 #84 案例 — 录音全内存累积，刷新/断网即丢失。
 * 现在：即使网络断开、刷新页面、关闭浏览器，chunks 仍在 IDB，可恢复。
 */

import { ref, readonly, onUnmounted } from 'vue'
import { useGlobalRecorder } from '@/composables/useGlobalRecorder'
import { useChunkedUploader } from '@/composables/useChunkedUploader'
import * as idbStore from '@/utils/idbStore'

/**
 * @param {number} meetingId  当前录音关联的会议 ID（由 start-recording 端点返回）
 * @param {object} [opts]
 * @param {string} [opts.title]  会议标题（写入 IDB meta）
 * @returns {{
 *   uploadedCount: import('vue').Ref<number>,
 *   pendingCount: import('vue').Ref<number>,
 *   lastChunkIndex: import('vue').Ref<number>,
 *   totalChunks: import('vue').Ref<number>,
 *   status: import('vue').Ref<'idle'|'recording'|'paused'|'stopped'>,
 *   stop: () => Promise<void>,
 * }}
 */
export function useChunkedRecorder(meetingId, opts = {}) {
  const { onChunk } = useGlobalRecorder()
  const uploader = useChunkedUploader()

  const uploadedCount = ref(0)
  const pendingCount = ref(0)
  const lastChunkIndex = ref(-1)
  const totalChunks = ref(0)
  const status = ref('idle')  // 镜像 useGlobalRecorder.state

  let unsubscribe = null
  let writeQueue = Promise.resolve()  // 串行化 IDB 写入，避免并发

  // 启动时：恢复上次未上传的 chunks（如果刷新页面后回到录音页）
  async function resumePending() {
    try {
      const pending = await idbStore.getPendingChunks(meetingId)
      pendingCount.value = pending.length
      uploadedCount.value = await idbStore.countUploaded(meetingId)
      lastChunkIndex.value = await idbStore.getLastChunkIndex(meetingId)
      if (pending.length > 0) {
        console.log(`[useChunkedRecorder] 恢复 ${pending.length} 个未上传 chunk`)
        // 入队补传
        uploader.enqueue(meetingId, pending)
      }
    } catch (err) {
      console.error('[useChunkedRecorder] 恢复 pending 失败:', err)
    }
  }

  // 处理单个 chunk：写 IDB + 触发上传
  function handleChunk({ index, blob, size }) {
    status.value = 'recording'
    lastChunkIndex.value = index
    totalChunks.value = index + 1

    // 串行化 IDB 写入（避免并发事务）
    writeQueue = writeQueue
      .then(() => idbStore.putChunk(meetingId, index, blob, { uploaded: false }))
      .then(() => {
        // IDB 写完后立即尝试上传
        return uploader.uploadOne(meetingId, index, blob).then(() => {
          uploadedCount.value++
          pendingCount.value = Math.max(0, pendingCount.value)
          return idbStore.markChunkUploaded(meetingId, index)
        }).catch((err) => {
          // 上传失败：保留在 IDB pending 队列，等待 online 重传
          console.warn(`[useChunkedRecorder] chunk ${index} 上传失败:`, err?.message || err)
          pendingCount.value++
        })
      })
      .catch((err) => {
        console.error(`[useChunkedRecorder] chunk ${index} IDB 写入失败:`, err)
      })
  }

  // 注册回调
  unsubscribe = onChunk(handleChunk)

  // 写入元数据
  if (opts.title) {
    idbStore.putMeta(meetingId, { title: opts.title, started_at: Date.now() })
      .catch(err => console.warn('[useChunkedRecorder] 写 meta 失败:', err))
  }

  // 启动时尝试恢复
  resumePending()

  onUnmounted(() => {
    if (unsubscribe) {
      unsubscribe()
      unsubscribe = null
    }
  })

  /**
   * 主动停止：等待所有 in-flight 写入/上传完成，返回最终状态
   * @returns {Promise<void>}
   */
  async function stop() {
    status.value = 'stopped'
    // 等待队列排空
    await writeQueue.catch(() => {})
    // 触发最后一次补传
    const pending = await idbStore.getPendingChunks(meetingId).catch(() => [])
    if (pending.length > 0) {
      await uploader.uploadAll(meetingId, pending).catch(err => {
        console.warn('[useChunkedRecorder] 最终补传失败:', err)
      })
    }
    if (unsubscribe) {
      unsubscribe()
      unsubscribe = null
    }
  }

  return {
    uploadedCount: readonly(uploadedCount),
    pendingCount: readonly(pendingCount),
    lastChunkIndex: readonly(lastChunkIndex),
    totalChunks: readonly(totalChunks),
    status: readonly(status),
    stop,
  }
}
