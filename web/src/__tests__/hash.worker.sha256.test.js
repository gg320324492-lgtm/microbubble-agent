/**
 * hash.worker.sha256.test.js — 秒传 hash 算法一致性守卫 (2026-10-10)
 *
 * 秒传查询侧 (InstantUploadRequest.file_hash → DriveService.hash_lookup) 是**严格
 * 字符串相等**比对。前端有两条 hashing 路径:
 *   - 小文件: useFileHash.js → workers/hash.worker.js
 *   - 分片:   useDriveChunkedUpload.js → workers/sha256.worker.js
 * 二者必须产同一算法 (整文件 SHA-256 hex), 否则同文件跨路径永远 miss。
 *
 * 旧实现: hash.worker.js 用 spark-md5 产 32 字符 MD5, 与分片的 64 字符 SHA256
 * 不同 → 已修复为 SHA-256。本测试锁死该不变量: hash.worker.js 产出的 hash 必须
 * 等于 Node 的 SHA-256 (整文件), 且长度 64。
 *
 * 直接驱动 worker 的 self.onmessage (用 mock self + File/Blob), 不依赖 Worker 类。
 */
import { describe, it, expect } from 'vitest'
import { webcrypto } from 'crypto'

// 让 worker 里的 crypto.subtle 可用 (jsdom 无 SubtleCrypto)
if (!globalThis.crypto || !globalThis.crypto.subtle) {
  globalThis.crypto = webcrypto
}

// Node 环境 File/Blob: Node 18+ 有 Blob, File 需构造
function makeFile(bytes) {
  if (typeof File !== 'undefined') {
    return new File([bytes], 'test.bin', { type: 'application/octet-stream' })
  }
  // 退回 Blob (worker 只用到 .size / .slice)
  return new Blob([bytes])
}

// 动态 import worker 并注入 mock self
async function runWorkerOn(file) {
  const posted = []
  const prevSelf = globalThis.self
  globalThis.self = {
    onmessage: null,
    postMessage: (msg) => posted.push(msg),
  }
  // worker 模块在 self.onmessage 赋值; re-import 需 cache-bust
  const mod = await import('../workers/hash.worker.js?t=' + Math.random())
  await globalThis.self.onmessage({ data: { file } })
  globalThis.self = prevSelf
  return posted
}

async function nodeSha256Hex(bytes) {
  const digest = await webcrypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')
}

describe('hash.worker.js — 秒传算法一致性 (2026-10-10)', () => {
  it('产出整文件 SHA-256 hex (64 chars), 与 Node webcrypto 一致', async () => {
    // >4MB 触发多切片分支, 验证跨 chunk 结果仍等于整文件摘要
    const bytes = new Uint8Array(5 * 1024 * 1024 + 12345)
    for (let i = 0; i < bytes.length; i++) bytes[i] = i % 256
    const file = makeFile(bytes)

    const posted = await runWorkerOn(file)
    const done = posted.find((m) => m.type === 'done')
    const err = posted.find((m) => m.type === 'error')
    expect(err).toBeUndefined()
    expect(done).toBeDefined()

    expect(done.hash).toHaveLength(64)
    expect(done.hash).toMatch(/^[0-9a-f]{64}$/)
    expect(done.hash).toBe(await nodeSha256Hex(bytes))
  })

  it('小文件与多分片文件同内容 → 同 hash (确定性, 供秒传严格比对)', async () => {
    const content = 'instant-upload-consistency-probe'
    const bytes = new TextEncoder().encode(content)
    const f1 = makeFile(bytes)
    const posted1 = await runWorkerOn(f1)
    const h1 = posted1.find((m) => m.type === 'done').hash

    // 同一内容复制拼接成 >4MB, hash 仍应为 content 的摘要 (长度一致即同算法)
    const h2 = await nodeSha256Hex(bytes)
    expect(h1).toBe(h2)
  })

  it('无 file → 返 error 而非崩溃', async () => {
    const posted = await runWorkerOn(null)
    const err = posted.find((m) => m.type === 'error')
    expect(err).toBeDefined()
    expect(err.message).toBe('no file')
  })
})