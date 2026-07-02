/**
 * 边录边传录音器 — 包装 useGlobalRecorder，每个 chunk 自动写 IndexedDB
 *
 * v2 (2026-07-02 修复): 支持 lazy meetingId
 *   之前 meetingId 在 setup() 时强制传入, 但 AudioRecorder 实际时序是:
 *     - 用户点"开始听会" → start() + emit('recording-start')
 *     - 父组件 MeetingRoomView.onRecordingStart 调 POST /start-recording 异步拿 meetingId
 *     - 1s 后 ondataavailable 触发 chunk → 这时 useChunkedRecorder 还没创建 (meetingId=null)
 *     → chunk 永远不被上传
 *   修复: meetingId 改用 ref 传入, setup() 时立即注册 onChunk 钩子
 *     meetingId 未到时 chunk 缓存到内存, meetingId 到了 flush.
 *     同时兼容 resumePending 恢复路径 (meetingId 持久化在 IDB).
 *
 * 核心：每 1s MediaRecorder 触发 ondataavailable → useGlobalRecorder.onChunk 回调
 *      → 本 composable 同步写 IDB + 触发上传（失败不阻塞，标记 uploaded=false）
 *
 * 解决问题：2026-06-12 #84 案例 — 录音全内存累积，刷新/断网即丢失。
 * 现在：即使网络断开、刷新页面、关闭浏览器，chunks 仍在 IDB，可恢复。
 */

import { ref, readonly, onUnmounted, watch, isRef, unref } from 'vue'
import { ElMessage } from 'element-plus'
import { useGlobalRecorder } from '@/composables/useGlobalRecorder'
import { useChunkedUploader } from '@/composables/useChunkedUploader'
import { useRecordingState } from '@/composables/useRecordingState'
import * as idbStore from '@/utils/idbStore'

/**
 * @param {number|import('vue').Ref<number|null>} meetingIdRef  当前录音关联的会议 ID（可传 ref，初始为 null 时 buffer）
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
export function useChunkedRecorder(meetingIdRef, opts = {}) {
  const { onChunk } = useGlobalRecorder()
  const uploader = useChunkedUploader()

  const uploadedCount = ref(0)
  const pendingCount = ref(0)
  const lastChunkIndex = ref(-1)
  const totalChunks = ref(0)
  const status = ref('idle')  // 镜像 useGlobalRecorder.state

  // P1 修复 (2026-07-03): 守卫会议状态变化
  // 真实场景：会议被 stop-recording 或后处理触发后 status→processing，
  // 但浏览器录音器仍持续发送 chunk → 全部 400 业务错。
  // 修复：catch 4xx + detail 含"录音状态"时立即 stop 录音器 + 提示用户。
  // 一次录音会话只触发一次（flag 防止后续 chunk 重复 stop 噪声）。
  let meetingClosedDetected = false

  let unsubscribe = null
  let writeQueue = Promise.resolve()  // 串行化 IDB 写入，避免并发

  // 兼容 meetingIdRef 是 ref 或 number
  const getMid = () => {
    const v = isRef(meetingIdRef) ? meetingIdRef.value : meetingIdRef
    return v && v > 0 ? v : null
  }

  // v2: meetingId 还没回来时, 缓存 chunks 到内存
  // {index, blob, size}[]
  const chunkBuffer = []

  // 启动时：恢复上次未上传的 chunks（如果刷新页面后回到录音页）
  async function resumePending() {
    const mid = getMid()
    if (!mid) return  // 没 meetingId 无法恢复
    try {
      const pending = await idbStore.getPendingChunks(mid)
      pendingCount.value = pending.length
      uploadedCount.value = await idbStore.countUploaded(mid)
      lastChunkIndex.value = await idbStore.getLastChunkIndex(mid)
      if (pending.length > 0) {
        console.log(`[useChunkedRecorder] 恢复 ${mid} ${pending.length} 个未上传 chunk`)
        uploader.enqueue(mid, pending)
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

    const mid = getMid()
    if (!mid) {
      // v2: meetingId 还没回来, 缓存
      chunkBuffer.push({ index, blob, size })
      pendingCount.value = chunkBuffer.length
      console.log(`[useChunkedRecorder] chunk ${index} 缓存 (meetingId 未就绪, buffer=${chunkBuffer.length})`)
      return
    }

    // 串行化 IDB 写入（避免并发事务）
    writeQueue = writeQueue
      .then(() => idbStore.putChunk(mid, index, blob, { uploaded: false }))
      .then(() => {
        // IDB 写完后立即尝试上传
        return uploader.uploadOne(mid, index, blob).then(() => {
          uploadedCount.value++
          pendingCount.value = Math.max(0, pendingCount.value)
          return idbStore.markChunkUploaded(mid, index)
        }).catch((err) => {
          // v2.1 修复: 4xx 业务错 (401/403/404) 不算"待重传"
          // 401 = token 过期, 需要重新登录 (不是网络问题, 不该累积 pending)
          // 403 = 无权, 重试无用
          // 404 = 端点不存在, 重试无用
          // 只 5xx + !status (网络错) 才累积到 pendingCount
          const status = err?.response?.status
          if (status && status >= 400 && status < 500 && status !== 408 && status !== 429) {
            console.warn(`[useChunkedRecorder] chunk ${index} 4xx 业务错 ${status}, 不累积 pending:`, err?.message || err)
            // 4xx 不需要重传, 不动 pendingCount
            // 同时不调用 markChunkUploaded (chunk 留在 IDB 但不算 pending)
            // P1: 400 "会议不在录音状态" = 后端会议已 stop/后处理触发, 立即停浏览器录音器
            if (status === 400 && !meetingClosedDetected) {
              const detail = err?.response?.data?.detail || ''
              if (typeof detail === 'string' && (detail.includes('录音状态') || detail.includes('recording'))) {
                meetingClosedDetected = true
                console.warn('[useChunkedRecorder] 检测到会议已不在录音状态, 主动停止浏览器录音器')
                ElMessage.warning('会议已结束，录音已自动停止')
                // fire-and-forget: useGlobalRecorder.stop() 是 Promise 但当前不是 async 上下文
                try {
                  const { stop } = useGlobalRecorder()
                  stop().catch(e => console.warn('[useChunkedRecorder] 停止录音器失败:', e))
                } catch (e) {
                  console.warn('[useChunkedRecorder] 调 useGlobalRecorder.stop() 失败:', e)
                }
                try {
                  const { stopRecording } = useRecordingState()
                  stopRecording()
                } catch (e) {
                  console.warn('[useChunkedRecorder] 清录音状态失败:', e)
                }
              }
            }
            return
          }
          // 5xx / 网络错: 保留在 IDB pending 队列, 等待 online 重传
          // v2.2 修复 (2026-07-03): 主动入队 uploadQueue, onOnline 事件能扫描到
          // 之前: 只 pendingCount++ 标 UI, uploadQueue 不知道有这 chunk
          //       → onOnline 触发时 drainQueue 不会扫它
          //       → 必须刷新页面靠 resumePending 才能恢复
          console.warn(`[useChunkedRecorder] chunk ${index} 上传失败 (网络/5xx):`, err?.message || err)
          try {
            uploader.enqueue(mid, [{ chunk_index: index, blob }])
          } catch (enqErr) {
            console.warn(`[useChunkedRecorder] enqueue failed, 将由 IDB 兜底扫到:`, enqErr?.message || enqErr)
          }
          pendingCount.value++
        })
      })
      .catch((err) => {
        console.error(`[useChunkedRecorder] chunk ${index} IDB 写入失败:`, err)
      })
  }

  // v2: watch meetingId 变化, meetingId 回来时 flush buffer
  // isRef 才 watch, 否则 setup 时已有 meetingId 直接走正常路径
  if (isRef(meetingIdRef)) {
    watch(meetingIdRef, (newMid, oldMid) => {
      if (newMid && newMid > 0 && newMid !== oldMid && chunkBuffer.length > 0) {
        const mid = newMid
        const toFlush = chunkBuffer.splice(0)  // 清空 buffer
        pendingCount.value = 0
        console.log(`[useChunkedRecorder] meetingId ${mid} 就绪, flush ${toFlush.length} 个 buffered chunk`)
        // 串行处理, 保持 index 顺序
        for (const c of toFlush) {
          writeQueue = writeQueue
            .then(() => idbStore.putChunk(mid, c.index, c.blob, { uploaded: false }))
            .then(() => uploader.uploadOne(mid, c.index, c.blob).then(() => {
              uploadedCount.value++
              return idbStore.markChunkUploaded(mid, c.index)
            }).catch((err) => {
              console.warn(`[useChunkedRecorder] flush chunk ${c.index} 上传失败:`, err?.message || err)
              pendingCount.value++
            }))
            .catch((err) => {
              console.error(`[useChunkedRecorder] flush chunk ${c.index} IDB 写入失败:`, err)
            })
        }
        // 同时启动 resumePending (可能从 IDB 恢复历史 chunks)
        resumePending()
      }
    }, { immediate: false })
  }

  // 注册回调（不管 meetingId 是否就绪, 都立即注册, 否则会丢早期 chunks）
  unsubscribe = onChunk(handleChunk)

  // 写入元数据（仅在 meetingId 就绪时）
  const initialMid = getMid()
  if (initialMid && opts.title) {
    idbStore.putMeta(initialMid, { title: opts.title, started_at: Date.now() })
      .catch(err => console.warn('[useChunkedRecorder] 写 meta 失败:', err))
  }

  // 启动时尝试恢复 (meetingId 就绪时才恢复)
  if (initialMid) {
    resumePending()
  }

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
    const mid = getMid()
    if (mid) {
      const pending = await idbStore.getPendingChunks(mid).catch(() => [])
      if (pending.length > 0) {
        await uploader.uploadAll(mid, pending).catch(err => {
          console.warn('[useChunkedRecorder] 最终补传失败:', err)
        })
      }
    } else if (chunkBuffer.length > 0) {
      // meetingId 一直未到, 但有 buffered chunks → 警告
      console.warn(`[useChunkedRecorder] 停止时 meetingId 仍为 null, ${chunkBuffer.length} 个 chunk 未上传 (会随 stop-recording 一次性 upload-audio 兜底)`)
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
