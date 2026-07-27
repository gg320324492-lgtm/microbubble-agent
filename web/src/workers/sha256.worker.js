// sha256.worker.js — W72 B-3 Drive 分片上传 SHA256 Web Worker
// 每个 chunk 独立 SHA256；主线程只负责 Blob.slice 与调度，不做摘要计算。

self.onmessage = async (event) => {
  const { id, blob } = event.data || {}
  try {
    if (!(blob instanceof Blob)) throw new Error('blob required')
    const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())
    const hash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
    self.postMessage({ id, type: 'done', hash })
  } catch (error) {
    self.postMessage({ id, type: 'error', message: error?.message || String(error) })
  }
}
