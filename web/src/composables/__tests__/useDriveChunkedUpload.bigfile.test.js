// useDriveChunkedUpload.bigfile.test.js — 大文件不再整文件哈希 (2026-11-11)
//
// 事故: 12.5GB COMSOL zip 在「计算 SHA256」阶段失败 —— 旧实现把整文件
// `blob.arrayBuffer()` 读进 worker 内存, 浏览器直接报
// "The requested file could not be read"。
//
// 判据 (结构 + 行为):
//   ① 源码里不再引用 sha256.worker.js / hashChunk(file)
//   ② init 不再带 checksum; complete 不再带 final_checksum (整文件哈希由服务端算)
//   ③ 每片单独算 SHA256 并带 X-Chunk-SHA256
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const SOURCE = fs.readFileSync(
  path.resolve(__dirname, '../useDriveChunkedUpload.js'),
  'utf8',
)

describe('结构守卫: 大文件不整文件哈希', () => {
  it('不再引用 sha256.worker.js 或 hashChunk(file)', () => {
    expect(SOURCE).not.toContain('sha256.worker.js')
    expect(SOURCE).not.toContain('hashChunk(file)')
    expect(SOURCE).not.toContain("status.value = 'hashing'")
  })

  it('init 传 checksum: null, complete 传 final_checksum: null', () => {
    expect(SOURCE).toContain('checksum: null')
    expect(SOURCE).toContain('final_checksum: null')
  })

  it('逐片 SHA256 仍在 (内存峰值 = 一片)', () => {
    expect(SOURCE).toContain("crypto.subtle.digest('SHA-256', buffer)")
    expect(SOURCE).toContain("'X-Chunk-SHA256': chunkSha")
  })
})
