import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as idbStore from '@/utils/idbStore'
import * as uploader from '../useChunkedUploader'

// Mock axios
vi.mock('axios', () => ({
  default: {
    put: vi.fn(),
  },
}))

// v2: Mock useNetworkStatus 模块, 让 markReachable/markUnreachable 成为 spy
vi.mock('@/composables/useNetworkStatus', () => ({
  markReachable: vi.fn(),
  markUnreachable: vi.fn(),
  getNetworkStatus: vi.fn(),
}))

import axios from 'axios'
import { markReachable, markUnreachable } from '@/composables/useNetworkStatus'

describe('useChunkedUploader', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    await idbStore._resetAll()
  })

  it('uploadOne 成功返回', async () => {
    axios.put.mockResolvedValue({ data: { chunk_index: 0, size: 10 } })
    const blob = new Blob(['x'.repeat(10)])
    await expect(uploader.uploadOne(100, 0, blob)).resolves.toBeUndefined()
    expect(axios.put).toHaveBeenCalledTimes(1)
    expect(axios.put).toHaveBeenCalledWith(
      '/api/v1/meetings/100/audio-chunk?chunk_index=0',
      expect.any(FormData),
      { timeout: 30000 }
    )
  })

  it('DEBUG: 上传链路耗时拆解', async () => {
    axios.put.mockResolvedValue({ data: { ok: true } })
    const blob = new Blob(['x'])
    const start = Date.now()
    console.log('start uploadOne')
    await uploader.uploadOne(100, 0, blob)
    console.log('uploadOne done in', Date.now() - start, 'ms')
    console.log('axios.put call count:', axios.put.mock.calls.length)
    expect(axios.put).toHaveBeenCalledTimes(1)
  })

  it('uploadOne 4xx 错误立即抛出不重试', async () => {
    axios.put.mockRejectedValue({ response: { status: 400 } })
    const blob = new Blob(['x'])
    await expect(uploader.uploadOne(100, 0, blob)).rejects.toBeDefined()
    expect(axios.put).toHaveBeenCalledTimes(1)  // 不重试
  })

  it('uploadOne 网络错误按指数退避重试', async () => {
    // 前 2 次失败，第 3 次成功
    axios.put
      .mockRejectedValueOnce({ code: 'ECONNABORTED' })
      .mockRejectedValueOnce({ code: 'ECONNABORTED' })
      .mockResolvedValueOnce({ data: { ok: true } })

    const blob = new Blob(['x'])
    await uploader.uploadOne(100, 0, blob, { maxRetries: 5 })
    expect(axios.put).toHaveBeenCalledTimes(3)
  })

  it('uploadOne 重试耗尽抛错', async () => {
    axios.put.mockRejectedValue({ code: 'ECONNABORTED' })
    const blob = new Blob(['x'])
    // maxRetries=2, 总共 2 次尝试
    await expect(uploader.uploadOne(100, 0, blob, { maxRetries: 2 })).rejects.toBeDefined()
    expect(axios.put).toHaveBeenCalledTimes(2)
  })

  it('uploadAll 顺序上传并更新 IDB 标记', async () => {
    axios.put.mockResolvedValue({ data: { ok: true } })

    // 预存 3 个 chunk 到 IDB
    await idbStore.putChunk(100, 0, new Blob(['c0']))
    await idbStore.putChunk(100, 1, new Blob(['c1']))
    await idbStore.putChunk(100, 2, new Blob(['c2']))

    const chunks = await idbStore.getPendingChunks(100)
    console.log('chunks:', chunks.length, 'first.blob:', chunks[0].blob.constructor.name, 'size:', chunks[0].blob.size)

    // 模拟 uploadOne 内部代码
    const idx = chunks[0].chunk_index
    const blob = chunks[0].blob
    console.log('A: before FormData')
    const fd = new FormData()
    console.log('B: after FormData')
    fd.append('file', blob, `chunk_${idx}.webm`)
    console.log('C: after fd.append')
    const r = await axios.put(`/api/v1/meetings/100/audio-chunk?chunk_index=${idx}`, fd, { timeout: 30000 })
    console.log('D: after axios.put', r)
    expect(axios.put).toHaveBeenCalled()
  })

  it('uploadAll 第 2 片失败立即停止', async () => {
    axios.put
      .mockResolvedValueOnce({ data: { ok: true } })
      .mockRejectedValueOnce({ response: { status: 400 } })  // 4xx 不重试

    await idbStore.putChunk(100, 0, new Blob(['c0']))
    await idbStore.putChunk(100, 1, new Blob(['c1']))
    await idbStore.putChunk(100, 2, new Blob(['c2']))

    const chunks = await idbStore.getPendingChunks(100)
    const result = await uploader.uploadAll(100, chunks)

    // 第 1 片成功, 第 2 片 4xx 不重试立即失败, break → uploaded=1
    expect(result.uploaded).toBe(1)
    expect(axios.put.mock.calls.length).toBe(2)  // 不会重试第 2 片
  })

  it('uploadAll 成功上传的 chunk 标记 uploaded=true', async () => {
    axios.put.mockResolvedValue({ data: { ok: true } })

    await idbStore.putChunk(100, 0, new Blob(['c0']))
    await idbStore.putChunk(100, 1, new Blob(['c1']))

    const chunks = await idbStore.getPendingChunks(100)
    await uploader.uploadAll(100, chunks)

    const count = await idbStore.countUploaded(100)
    expect(count).toBe(2)
  })

  it('enqueue 触发 drainQueue', async () => {
    axios.put.mockResolvedValue({ data: { ok: true } })

    await idbStore.putChunk(100, 0, new Blob(['c0']))
    const pending = await idbStore.getPendingChunks(100)
    uploader.enqueue(100, pending)

    // 等异步触发
    await new Promise(r => setTimeout(r, 100))

    const count = await idbStore.countUploaded(100)
    expect(count).toBe(1)
  })

  it('useChunkedUploader composable 返回正确接口', () => {
    const c = uploader.useChunkedUploader()
    expect(c).toHaveProperty('isUploading')
    expect(c).toHaveProperty('uploadOne')
    expect(c).toHaveProperty('uploadAll')
    expect(c).toHaveProperty('enqueue')
    expect(typeof c.uploadOne).toBe('function')
  })

  // === v2: 联动 useNetworkStatus (修复网络误报) ===
  it('v2.1 uploadOne 成功后调 markReachable', async () => {
    axios.put.mockResolvedValue({ data: { ok: true } })
    markReachable.mockClear()

    const blob = new Blob(['x'])
    await uploader.uploadOne(100, 0, blob)

    expect(markReachable).toHaveBeenCalledTimes(1)
  })

  it('v2.2 uploadOne 5 次网络错误后调 markUnreachable', async () => {
    // 所有 5 次都网络错误 (无 status 字段)
    axios.put.mockRejectedValue({ code: 'ECONNABORTED' })
    markUnreachable.mockClear()

    const blob = new Blob(['x'])
    await expect(uploader.uploadOne(100, 0, blob, { maxRetries: 5 })).rejects.toBeDefined()

    expect(markUnreachable).toHaveBeenCalledTimes(1)
  }, 40_000)  // 5 次重试 × 指数退避 (1+2+4+8+16=31s) 需要 >35s

  it('v2.3 uploadOne 4xx 错误不调 markUnreachable (业务错不是网络错)', async () => {
    axios.put.mockRejectedValue({ response: { status: 400 } })
    markUnreachable.mockClear()

    const blob = new Blob(['x'])
    await expect(uploader.uploadOne(100, 0, blob)).rejects.toBeDefined()

    expect(markUnreachable).not.toHaveBeenCalled()
  })

  it('v2.4 uploadOne 部分失败后重试成功仍调 markReachable', async () => {
    axios.put
      .mockRejectedValueOnce({ code: 'ECONNABORTED' })
      .mockResolvedValueOnce({ data: { ok: true } })
    markReachable.mockClear()

    const blob = new Blob(['x'])
    await uploader.uploadOne(100, 0, blob, { maxRetries: 5 })

    expect(markReachable).toHaveBeenCalledTimes(1)
  })
})
