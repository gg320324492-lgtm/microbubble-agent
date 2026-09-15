/**
 * useMeetingAudioUpload.js — 听会录音的"收尾上传"统一入口（2026-09-15 P0）
 *
 * 事故背景（2026-09-14 群组会，会议 250 / 杜同贺 / iPhone）
 * ------------------------------------------------------------------
 * 1. 19:38:34 用户点"开始听会"，会议 250 创建，录音持续 1h40m。
 * 2. 录音期间 **零分片上传** —— iOS Safari 不遵守
 *    `MediaRecorder.start(timeslice)`，`ondataavailable` 只在 stop 时触发一次，
 *    所以 useChunkedRecorder 的"边录边传"在 iOS 上完全退化成"停止时一次性上传"。
 * 3. 20:14:58 后端 orphan_meeting_cleanup 因"录音超 30min 未 stop"把会议 250
 *    标记为 error（已修：加录音心跳守卫）。
 * 4. 21:18:28 用户点停止 → 前端 POST /upload-audio，请求体
 *    **162,317,126 bytes**，被云端 nginx 的 `client_max_body_size 50m` 拒绝：
 *    error.log: "client intended to send too large body: 162317126 bytes"。
 *    nginx 直接 RST 掉 HTTP/2 流，浏览器拿不到 413 正文 → axios 只抛
 *    **"Network Error"**，用户完全不知道发生了什么。
 * 5. 结果：整场录音丢失，用户只能用手机自带录音机补录（桌面上那个 137MB m4a）。
 *
 * 本模块的职责
 * ------------------------------------------------------------------
 * 提供一个**不依赖 MediaRecorder 分片能力**的上传路径：
 *
 *   - 实时分片已完整落库（桌面 Chrome 正常路径）→ 只调 merge-chunks（ffmpeg 拼接）
 *   - 大文件但实时分片不完整（iOS Safari）→ 把整段 blob 按固定字节切片重传，
 *     再调 merge-chunks?mode=raw（字节级拼接，精确还原原始容器字节）
 *   - 小文件 → 一次性 upload-audio（保持老路径，省往返）
 *   - 收到 413 → 自动降级到切片路径重试（双保险）
 *
 * 这样无论浏览器是否支持 timeslice，单个 HTTP 请求体都远低于 nginx 上限，
 * 且断点可重试、失败有明确中文提示。
 */

import axios from 'axios'

/** 单次一次性上传的体积安全线：超过就走分片（40MB，给 nginx 上限留足余量） */
export const ONESHOT_SAFE_BYTES = 40 * 1024 * 1024

/** 分片大小：4MB。移动端弱网下单片 10~40s 可传完，失败只重传这一片 */
export const SLICE_SIZE = 4 * 1024 * 1024

/** 单片上传超时（含重试前的单次尝试） */
const SLICE_TIMEOUT_MS = 180000
/** 一次性上传超时 */
const ONESHOT_TIMEOUT_MS = 600000
/** merge 超时（服务端要下载+拼接+回传几十~几百 MB） */
const MERGE_TIMEOUT_MS = 600000
/** 停止后等待实时分片收敛的最长时间（桌面 Chrome 每 1s 一片，通常 1~2s 内传完） */
const SETTLE_TIMEOUT_MS = 15000

function humanSize(bytes) {
  if (!bytes && bytes !== 0) return '?'
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

/** 把 axios 错误翻译成人能看懂的中文文案 */
export function describeUploadError(err) {
  const status = err?.response?.status
  const detail = err?.response?.data?.detail
  if (status === 413) {
    return detail || '录音文件过大，服务器拒绝接收。系统已尝试改用分片上传，请重试。'
  }
  if (status === 400) return detail || '上传参数有误，请重试。'
  if (status === 401) return '登录已过期，请重新登录后再试。'
  if (status === 403) return detail || '没有权限上传该录音。'
  if (status === 404) return detail || '会议不存在，可能已被清理，请重新录制。'
  if (status >= 500) return `服务器处理失败 (${status})：${detail || '请稍后重试'}`
  if (err?.code === 'ECONNABORTED' || /timeout/i.test(err?.message || '')) {
    return '网络超时。录音体积较大时上传耗时较长，请保持页面在前台后重试。'
  }
  if (!status) {
    return '网络连接中断（Network Error）。常见原因：录音体积超过服务器单次上传上限、'
      + '手机切到后台导致上传被系统挂起、或隧道/网络抖动。请保持页面在前台重试。'
  }
  return detail || err?.message || '上传失败'
}

/**
 * 上报一次录音心跳（防止后端孤儿清理误杀仍在录音的会议）
 * @param {number} meetingId
 */
export async function sendRecordingHeartbeat(meetingId) {
  if (!meetingId) return false
  try {
    await axios.post(`/api/v1/meetings/${meetingId}/recording-heartbeat`, {}, { timeout: 15000 })
    return true
  } catch (err) {
    console.warn('[audioUpload] 录音心跳上报失败:', err?.message)
    return false
  }
}

/**
 * 分片上传整段 blob（字节切片）+ 字节级合并。
 * 调用前会先 reset 服务端已有分片，避免索引撞号导致合并出交错的垃圾音频。
 *
 * @param {number} meetingId
 * @param {Blob} blob
 * @param {(done:number,total:number)=>void} [onProgress]
 * @returns {Promise<{mode:string, chunks:number, bytes:number, mergeMode?:string}>}
 */
export async function uploadBlobInSlices(meetingId, blob, onProgress) {
  if (!blob || blob.size === 0) throw new Error('录音内容为空，无法上传')

  const total = Math.ceil(blob.size / SLICE_SIZE)

  // 1) 复位服务端分片（可能有早先零散上传的实时分片）
  await axios.post(`/api/v1/meetings/${meetingId}/chunks/reset`, {}, { timeout: 60000 })

  // 2) 顺序切片上传（顺序保证合并时字节顺序正确）
  for (let i = 0; i < total; i++) {
    const start = i * SLICE_SIZE
    const part = blob.slice(start, Math.min(blob.size, start + SLICE_SIZE))
    const fd = new FormData()
    fd.append('file', part, `slice_${String(i).padStart(5, '0')}.bin`)
    await axios.put(
      `/api/v1/meetings/${meetingId}/audio-chunk?chunk_index=${i}`,
      fd,
      { timeout: SLICE_TIMEOUT_MS }
    )
    if (typeof onProgress === 'function') onProgress(i + 1, total)
  }

  // 3) 字节级拼接（不能用 ffmpeg concat —— 这些切片不是独立可解析的媒体文件）
  const res = await axios.post(
    `/api/v1/meetings/${meetingId}/merge-chunks?mode=raw`,
    {},
    { timeout: MERGE_TIMEOUT_MS }
  )
  return {
    mode: 'sliced',
    chunks: total,
    bytes: blob.size,
    mergeMode: res?.data?.merge_mode || 'raw',
  }
}

/**
 * 收尾上传统一入口。
 *
 * @param {object} opts
 * @param {number} opts.meetingId
 * @param {Blob} opts.blob                       完整录音
 * @param {object|Function} [opts.liveStats]     useChunkedRecorder 的实时分片统计
 *        {uploadedCount, totalChunks, pendingCount}；也可传函数（推荐），
 *        因为停止瞬间可能仍有分片在飞行中，需要重新采样。
 * @param {(msg:string)=>void} [opts.onNotice]   给用户的提示（用于切换策略时告知）
 * @param {(done:number,total:number)=>void} [opts.onProgress]
 * @returns {Promise<{mode:string, chunks?:number, bytes?:number, mergeMode?:string}>}
 */
export async function finalizeMeetingAudioUpload({
  meetingId,
  blob,
  liveStats = {},
  onNotice,
  onProgress,
} = {}) {
  if (!meetingId) throw new Error('会议未创建，无法上传')

  const notify = (m) => {
    if (typeof onNotice === 'function') onNotice(m)
    else console.warn('[audioUpload]', m)
  }

  const readStats = () => {
    const s = typeof liveStats === 'function' ? liveStats() : liveStats
    return {
      uploadedCount: Number(s?.uploadedCount || 0),
      totalChunks: Number(s?.totalChunks || 0),
      pendingCount: Number(s?.pendingCount || 0),
    }
  }
  const isComplete = (s) => s.totalChunks > 0 && s.uploadedCount >= s.totalChunks && s.pendingCount === 0

  let stats = readStats()

  // 停止瞬间可能仍有分片在飞行中（桌面 Chrome 每 1s 一片）。
  // 给它最多 SETTLE_TIMEOUT_MS 收敛，避免因为"差几片没传完"就白白重传整段录音。
  if (stats.totalChunks > 0 && stats.uploadedCount < stats.totalChunks) {
    const deadline = Date.now() + SETTLE_TIMEOUT_MS
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 1000))
      const next = readStats()
      const done = next.uploadedCount >= next.totalChunks || next.pendingCount > 0
      stats = next
      if (done) break
    }
  }

  // ---- 路径 A：实时分片完整（桌面 Chrome 的正常情况）----
  if (isComplete(stats)) {
    const res = await axios.post(
      `/api/v1/meetings/${meetingId}/merge-chunks?mode=auto`,
      {},
      { timeout: MERGE_TIMEOUT_MS }
    )
    return { mode: 'live-chunks', chunks: stats.totalChunks, mergeMode: res?.data?.merge_mode }
  }

  const size = blob?.size || 0
  console.warn(
    `[audioUpload] 实时分片不完整 (uploaded=${stats.uploadedCount}, total=${stats.totalChunks}, `
      + `pending=${stats.pendingCount}, blob=${humanSize(size)})，改用切片路径`
  )

  // ---- 路径 B：大文件 → 字节切片上传 ----
  if (size > ONESHOT_SAFE_BYTES) {
    notify(`录音 ${humanSize(size)}，正在分片上传，请保持页面在前台…`)
    return await uploadBlobInSlices(meetingId, blob, onProgress)
  }

  // ---- 路径 C：小文件 → 一次性上传（老路径）----
  const fd = new FormData()
  fd.append('file', blob, `recording_${meetingId}.webm`)
  try {
    await axios.post(`/api/v1/meetings/${meetingId}/upload-audio`, fd, {
      timeout: ONESHOT_TIMEOUT_MS,
      onUploadProgress: (e) => {
        if (typeof onProgress === 'function' && e?.total) onProgress(e.loaded, e.total)
      },
    })
    return { mode: 'oneshot', bytes: size }
  } catch (err) {
    // 双保险：即便走了小文件路径也被拒（例如反向代理上限又被动过），
    // 自动降级到切片路径再试一次，而不是把 "Network Error" 甩给用户。
    const status = err?.response?.status
    if (status === 413 || !status) {
      console.warn('[audioUpload] 一次性上传失败，降级为分片上传重试:', err?.message)
      notify('一次性上传被拒，正在改用分片上传重试…')
      return await uploadBlobInSlices(meetingId, blob, onProgress)
    }
    throw err
  }
}

export function useMeetingAudioUpload() {
  return {
    finalizeMeetingAudioUpload,
    uploadBlobInSlices,
    sendRecordingHeartbeat,
    describeUploadError,
    ONESHOT_SAFE_BYTES,
    SLICE_SIZE,
  }
}

export default useMeetingAudioUpload
