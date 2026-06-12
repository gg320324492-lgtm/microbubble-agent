import { describe, it, expect, beforeEach } from 'vitest'
import * as idbStore from '../idbStore'

describe('idbStore', () => {
  beforeEach(async () => {
    // 每个测试前清空数据库
    await idbStore._resetAll()
  })

  it('putChunk 写入后可通过 getAllChunks 读取', async () => {
    const blob = new Blob(['chunk0'], { type: 'audio/webm' })
    const id = await idbStore.putChunk(100, 0, blob)
    expect(id).toBeGreaterThan(0)

    const all = await idbStore.getAllChunks(100)
    expect(all).toHaveLength(1)
    expect(all[0].meeting_id).toBe(100)
    expect(all[0].chunk_index).toBe(0)
    expect(all[0].uploaded).toBe(false)
    expect(all[0].size).toBe(blob.size)
  })

  it('getAllChunks 按 chunk_index 升序返回', async () => {
    await idbStore.putChunk(100, 2, new Blob(['c2']))
    await idbStore.putChunk(100, 0, new Blob(['c0']))
    await idbStore.putChunk(100, 1, new Blob(['c1']))

    const all = await idbStore.getAllChunks(100)
    expect(all.map(r => r.chunk_index)).toEqual([0, 1, 2])
  })

  it('markChunkUploaded 把指定 chunk 标记为已上传', async () => {
    await idbStore.putChunk(100, 0, new Blob(['c0']))
    const ok = await idbStore.markChunkUploaded(100, 0)
    expect(ok).toBe(true)

    const all = await idbStore.getAllChunks(100)
    expect(all[0].uploaded).toBe(true)
    expect(all[0].uploaded_at).toBeGreaterThan(0)
  })

  it('getPendingChunks 只返回 uploaded=false', async () => {
    await idbStore.putChunk(100, 0, new Blob(['c0']))
    await idbStore.putChunk(100, 1, new Blob(['c1']))
    await idbStore.markChunkUploaded(100, 0)

    const pending = await idbStore.getPendingChunks(100)
    expect(pending).toHaveLength(1)
    expect(pending[0].chunk_index).toBe(1)
  })

  it('countUploaded 返回已上传 chunk 数', async () => {
    await idbStore.putChunk(100, 0, new Blob(['c0']))
    await idbStore.putChunk(100, 1, new Blob(['c1']))
    await idbStore.putChunk(100, 2, new Blob(['c2']))
    await idbStore.markChunkUploaded(100, 0)
    await idbStore.markChunkUploaded(100, 2)

    const count = await idbStore.countUploaded(100)
    expect(count).toBe(2)
  })

  it('getLastChunkIndex 返回 -1 当无 chunk', async () => {
    const idx = await idbStore.getLastChunkIndex(999)
    expect(idx).toBe(-1)
  })

  it('getLastChunkIndex 返回最大 index', async () => {
    await idbStore.putChunk(100, 0, new Blob(['c0']))
    await idbStore.putChunk(100, 5, new Blob(['c5']))
    await idbStore.putChunk(100, 3, new Blob(['c3']))

    const idx = await idbStore.getLastChunkIndex(100)
    expect(idx).toBe(5)
  })

  it('不同 meetingId 的 chunks 互不干扰', async () => {
    await idbStore.putChunk(100, 0, new Blob(['100-0']))
    await idbStore.putChunk(200, 0, new Blob(['200-0']))

    const c100 = await idbStore.getAllChunks(100)
    const c200 = await idbStore.getAllChunks(200)
    expect(c100).toHaveLength(1)
    expect(c200).toHaveLength(1)
    expect(c100[0].meeting_id).toBe(100)
    expect(c200[0].meeting_id).toBe(200)
  })

  it('deleteAllChunks 删除某会议所有 chunk', async () => {
    await idbStore.putChunk(100, 0, new Blob(['c0']))
    await idbStore.putChunk(100, 1, new Blob(['c1']))
    await idbStore.putChunk(200, 0, new Blob(['d0']))

    const deleted = await idbStore.deleteAllChunks(100)
    expect(deleted).toBe(2)

    const c100 = await idbStore.getAllChunks(100)
    const c200 = await idbStore.getAllChunks(200)
    expect(c100).toHaveLength(0)
    expect(c200).toHaveLength(1)  // 200 的不受影响
  })

  it('meta 读写', async () => {
    await idbStore.putMeta(100, { title: '测试会议', started_at: 1234567890 })
    const meta = await idbStore.getMeta(100)
    expect(meta).not.toBeNull()
    expect(meta.meeting_id).toBe(100)
    expect(meta.title).toBe('测试会议')
    expect(meta.started_at).toBe(1234567890)
  })

  it('getMeta 不存在的 meeting 返回 null', async () => {
    const meta = await idbStore.getMeta(999)
    expect(meta).toBeNull()
  })
})
