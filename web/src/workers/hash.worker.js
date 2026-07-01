// hash.worker.js — 文件 hash 计算 Web Worker (PR4 秒传核心)
// 2026-07-01

// Module Worker 模式 (type: 'module') — Vite 自动解析 npm 包路径
// 由 useFileHash.js 通过 `new Worker(new URL('./hash.worker.js', import.meta.url), { type: 'module' })` 加载

import SparkMD5 from 'spark-md5'

self.onmessage = async function (e) {
  const { file, chunkSize = 4 * 1024 * 1024 } = e.data
  if (!file) {
    self.postMessage({ type: 'error', message: 'no file' })
    return
  }
  try {
    const total = file.size
    const md5 = new SparkMD5.ArrayBuffer()
    let offset = 0
    while (offset < total) {
      const end = Math.min(offset + chunkSize, total)
      const slice = file.slice(offset, end)
      const buf = await slice.arrayBuffer()
      md5.append(buf)
      offset = end
      self.postMessage({
        type: 'progress',
        pct: Math.floor(offset * 100 / total),
      })
    }
    self.postMessage({ type: 'done', hash: md5.end() })
  } catch (err) {
    self.postMessage({ type: 'error', message: String(err && err.message || err) })
  }
}