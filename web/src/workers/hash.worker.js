// hash.worker.js — 文件 hash 计算 Web Worker (PR4 秒传核心)
// 2026-07-01; 2026-10-10 统一算法为 SHA-256 (与分片路径 sha256.worker.js 一致)
//
// 算法一致性铁律: 秒传查询 (InstantUploadRequest.file_hash) 在后端是**严格字符串
// 相等**比对 (DriveService.hash_lookup → Knowledge.file_hash == file_hash)。因此
// "存进去的 hash" 与 "查询时算的 hash" 必须是同一算法。分片上传路径
// (useDriveChunkedUpload.js → sha256.worker.js) 用的是整文件 SHA-256 hex (64 chars)，
// 本 worker 必须同样产 SHA-256 hex，否则同一文件走小文件/分片两条路永远 miss。
// (旧实现用 spark-md5 产 32 字符 MD5，与分片路径 64 字符 SHA256 不同 → 秒传跨路径失效)

// Module Worker 模式 (type: 'module') — Vite 自动解析 npm 包路径
// 由 useFileHash.js 通过 `new Worker(new URL('./hash.worker.js', import.meta.url), { type: 'module' })` 加载

self.onmessage = async function (e) {
  const { file } = e.data
  if (!file) {
    self.postMessage({ type: 'error', message: 'no file' })
    return
  }
  try {
    // 分片读取整文件后一次性摘要 (SHA-256 hex, 64 chars)，进度按已读字节上报。
    // 与 sha256.worker.js 的 `crypto.subtle.digest('SHA-256', await blob.arrayBuffer())`
    // 对同一文件产出一致结果（SHA-256 是整文件哈希，分片拼接结果相同）。
    const total = file.size
    const chunkSize = 4 * 1024 * 1024
    const parts = []
    let offset = 0
    while (offset < total) {
      const end = Math.min(offset + chunkSize, total)
      parts.push(await file.slice(offset, end).arrayBuffer())
      offset = end
      self.postMessage({
        type: 'progress',
        pct: total === 0 ? 100 : Math.floor(offset * 100 / total),
      })
    }
    // 拼成单个 ArrayBuffer 交给 SubtleCrypto (整文件 SHA-256)
    const merged = new Uint8Array(total)
    let cursor = 0
    for (const part of parts) {
      merged.set(new Uint8Array(part), cursor)
      cursor += part.byteLength
    }
    const digest = await crypto.subtle.digest('SHA-256', merged)
    const hash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
    self.postMessage({ type: 'done', hash })
  } catch (err) {
    self.postMessage({ type: 'error', message: String(err && err.message || err) })
  }
}
