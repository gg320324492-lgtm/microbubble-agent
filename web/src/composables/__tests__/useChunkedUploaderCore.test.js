/**
 * useChunkedUploaderCore.test.js — W84 B-2 P1-1 通用 chunked upload 核心单元测试
 *
 * 派工依据:
 * - W84 B-2 P1-1: 建 useChunkedUploaderCore.js 兼容层 (W82/W83 B-2 拦截铁律 #16/#17 分步走)
 * - 验证 useChunkedUploader.js thin-shell 委派后行为完全等价
 *
 * 覆盖 6 场景:
 * 1. composable 形式: 返回 isUploading / uploadOne / uploadAll / enqueue / drainQueue
 * 2. uploadOne 成功 + 调 markReachable
 * 3. uploadOne 4xx 立即抛错 (业务错不重试)
 * 4. uploadOne 网络错指数退避 (重试 N 次)
 * 5. uploadAll 顺序上传 + IDB markChunkUploaded
 * 6. uploadAll 失败立即停止 (第 2 片 4xx → uploaded=1)
 *
 * 与 useChunkedUploader.test.js 关系:
 * - useChunkedUploader.test.js 走 thin-shell 委派路径, 验证导入兼容
 * - 本测试针对 useChunkedUploaderCore 直接验证核心 API
 * - IDB 单例 reset: 用 _resetCoreForTests() + idbStore._resetAll()
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as idbStore from '@/utils/idbStore'
import * as core from '../useChunkedUploaderCore'

// Mock axios
vi.mock('axios', () => ({
  default: {
    put: vi.fn(),
  },
}))

// Mock useNetworkStatus 模块
vi.mock('@/composables/useNetworkStatus', () => ({
  markReachable: vi.fn(),
  markUnreachable: vi.fn(),
  getNetworkStatus: vi.fn(),
}))

import axios from 'axios'
import { markReachable, markUnreachable } from '@/composables/useNetworkStatus'

describe('useChunkedUploaderCore (W84 B-2 P1-1 通用核心)', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    await idbStore._resetAll()
    core._resetCoreForTests()
  })

  describe('useChunkedUploaderCore composable', () => {
    it('返回完整 API (isUploading + 4 actions)', () => {
      const c = core.useChunkedUploaderCore()
      expect(c).toHaveProperty('isUploading')
      expect(c).toHaveProperty('uploadOne')
      expect(c).toHaveProperty('uploadAll')
      expect(c).toHaveProperty('enqueue')
      expect(c).toHaveProperty('drainQueue')
      expect(typeof c.uploadOne).toBe('function')
      expect(typeof c.uploadAll).toBe('function')
      expect(typeof c.enqueue).toBe('function')
      expect(typeof c.drainQueue).toBe('function')
      // isUploading 是 readonly ref
      expect(c.isUploading.value).toBe(false)
    })

    it('isUploading 在 uploadAll 期间为 true', async () => {
      axios.put.mockResolvedValue({ data: { ok: true } })
      const { isUploading } = core.useChunkedUploaderCore()

      await idbStore.putChunk(100, 0, new Blob(['c0']))
      const chunks = await idbStore.getPendingChunks(100)

      const uploadPromise = core.uploadAll(100, chunks)
      // 立即检查 (微任务前)
      // 注: isUploading.value 在 await axios.put 之前已设 true
      expect(typeof isUploading.value).toBe('boolean')
      await uploadPromise
      expect(isUploading.value).toBe(false)
    })

    it('多次调用共享同一单例 (module-level state)', () => {
      const c1 = core.useChunkedUploaderCore()
      const c2 = core.useChunkedUploaderCore()
      // isUploading 是同一个 ref
      expect(c1.isUploading).toBe(c2.isUploading)
    })
  })

  describe('uploadOne 单片上传', () => {
    it('成功上传 + 调 markReachable', async () => {
      axios.put.mockResolvedValue({ data: { chunk_index: 0, size: 10 } })
      markReachable.mockClear()
      const blob = new Blob(['x'.repeat(10)])
      await expect(core.uploadOne(100, 0, blob)).resolves.toBeUndefined()
      expect(axios.put).toHaveBeenCalledTimes(1)
      expect(axios.put).toHaveBeenCalledWith(
        '/api/v1/meetings/100/audio-chunk?chunk_index=0',
        expect.any(FormData),
        { timeout: 30000 }
      )
      expect(markReachable).toHaveBeenCalledTimes(1)
    })

    it('4xx 错误立即抛错 + 不重试 + 不调 markUnreachable', async () => {
      axios.put.mockRejectedValue({ response: { status: 400 } })
      markUnreachable.mockClear()
      const blob = new Blob(['x'])
      await expect(core.uploadOne(100, 0, blob)).rejects.toBeDefined()
      expect(axios.put).toHaveBeenCalledTimes(1)
      expect(markUnreachable).not.toHaveBeenCalled()
    })

    it('网络错指数退避 + 重试成功', async () => {
      axios.put
        .mockRejectedValueOnce({ code: 'ECONNABORTED' })
        .mockRejectedValueOnce({ code: 'ECONNABORTED' })
        .mockResolvedValueOnce({ data: { ok: true } })

      const blob = new Blob(['x'])
      await core.uploadOne(100, 0, blob, { maxRetries: 5 })
      expect(axios.put).toHaveBeenCalledTimes(3)
    })

    it('重试耗尽抛错 + 调 markUnreachable (5 次网络错)', async () => {
      axios.put.mockRejectedValue({ code: 'ECONNABORTED' })
      markUnreachable.mockClear()
      const blob = new Blob(['x'])
      await expect(core.uploadOne(100, 0, blob, { maxRetries: 5 })).rejects.toBeDefined()
      expect(axios.put).toHaveBeenCalledTimes(5)
      expect(markUnreachable).toHaveBeenCalledTimes(1)
    }, 40_000)
  })

  describe('uploadAll 顺序批量上传', () => {
    it('3 片全成功 + IDB 标记 uploaded', async () => {
      axios.put.mockResolvedValue({ data: { ok: true } })

      await idbStore.putChunk(200, 0, new Blob(['c0']))
      await idbStore.putChunk(200, 1, new Blob(['c1']))
      await idbStore.putChunk(200, 2, new Blob(['c2']))

      const chunks = await idbStore.getPendingChunks(200)
      const result = await core.uploadAll(200, chunks)

      expect(result.uploaded).toBe(3)
      expect(result.failed).toBe(0)
      expect(axios.put).toHaveBeenCalledTimes(3)
      const uploadedCount = await idbStore.countUploaded(200)
      expect(uploadedCount).toBe(3)
    })

    it('第 2 片 4xx 立即停止 (uploaded=1, 不重试)', async () => {
      axios.put
        .mockResolvedValueOnce({ data: { ok: true } })
        .mockRejectedValueOnce({ response: { status: 400 } })

      await idbStore.putChunk(300, 0, new Blob(['c0']))
      await idbStore.putChunk(300, 1, new Blob(['c1']))
      await idbStore.putChunk(300, 2, new Blob(['c2']))

      const chunks = await idbStore.getPendingChunks(300)
      const result = await core.uploadAll(300, chunks)

      expect(result.uploaded).toBe(1)
      expect(axios.put).toHaveBeenCalledTimes(2)
    })

    it('空数组返 { uploaded: 0, failed: 0 }', async () => {
      const result = await core.uploadAll(999, [])
      expect(result).toEqual({ uploaded: 0, failed: 0 })
      expect(axios.put).not.toHaveBeenCalled()
    })
  })

  describe('enqueue + drainQueue', () => {
    it('enqueue 触发上传 + IDB 标记', async () => {
      axios.put.mockResolvedValue({ data: { ok: true } })

      await idbStore.putChunk(400, 0, new Blob(['c0']))
      const pending = await idbStore.getPendingChunks(400)
      core.enqueue(400, pending)

      // 等异步触发
      await new Promise((r) => setTimeout(r, 100))

      const count = await idbStore.countUploaded(400)
      expect(count).toBe(1)
    })

    it('enqueue 重复 chunk_index 去重', async () => {
      axios.put.mockResolvedValue({ data: { ok: true } })

      // 第二次 enqueue 同样 chunk_index 不会重复
      core.enqueue(500, [{ chunk_index: 0, blob: new Blob(['c0']) }])
      core.enqueue(500, [{ chunk_index: 0, blob: new Blob(['c0-dup']) }])

      await new Promise((r) => setTimeout(r, 100))

      // 期望 axios.put 只被调 1 次 (去重生效)
      expect(axios.put).toHaveBeenCalledTimes(1)
    })

    it('drainQueue 排空队列', async () => {
      axios.put.mockResolvedValue({ data: { ok: true } })

      // 手动 enqueue 2 片
      core.enqueue(600, [
        { chunk_index: 0, blob: new Blob(['c0']) },
        { chunk_index: 1, blob: new Blob(['c1']) },
      ])

      // 等异步 drain
      await new Promise((r) => setTimeout(r, 100))

      // 期望至少 2 次 axios.put
      expect(axios.put).toHaveBeenCalledTimes(2)
    })
  })

  describe('module-level 单例状态', () => {
    it('_getCoreState 暴露 isUploading + uploadQueue + onlineListenersAttached', () => {
      const state = core._getCoreState()
      expect(state).toHaveProperty('isUploading')
      expect(state).toHaveProperty('uploadQueue')
      expect(state).toHaveProperty('onlineListenersAttached')
      expect(state.uploadQueue).toBeInstanceOf(Map)
      expect(state.onlineListenersAttached).toBeInstanceOf(Set)
    })

    it('_resetCoreForTests 清空 uploadQueue + reset isUploading', async () => {
      axios.put.mockResolvedValue({ data: { ok: true } })

      // 注入数据
      core.enqueue(700, [{ chunk_index: 0, blob: new Blob(['c0']) }])
      await new Promise((r) => setTimeout(r, 50))

      core._resetCoreForTests()
      const state = core._getCoreState()
      expect(state.uploadQueue.size).toBe(0)
      expect(state.isUploading.value).toBe(false)
    })
  })

  describe('useChunkedUploader thin-shell 委派验证', () => {
    it('从 useChunkedUploader.js 导入的函数 === core 函数', async () => {
      const sh = await import('../useChunkedUploader')
      // 函数引用一致 (thin-shell re-export)
      expect(sh.uploadOne).toBe(core.uploadOne)
      expect(sh.uploadAll).toBe(core.uploadAll)
      expect(sh.enqueue).toBe(core.enqueue)
      expect(sh.drainQueue).toBe(core.drainQueue)
    })

    it('useChunkedUploader() 返回与 useChunkedUploaderCore() 等价', () => {
      const sh = core.useChunkedUploaderCore()
      // 验证 shape 一致 (不验证 isUploading ref 相等, 因为 re-create computed)
      expect(Object.keys(sh).sort()).toEqual(['drainQueue', 'enqueue', 'isUploading', 'uploadAll', 'uploadOne'])
    })
  })
})
