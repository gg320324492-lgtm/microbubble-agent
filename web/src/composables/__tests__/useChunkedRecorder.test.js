/**
 * useChunkedRecorder.test.js - P1-5 修复端到端单测
 *
 * 覆盖:
 * - 接受 titleRef 参数 (与 meetingIdRef 镜像的 reactive 模式)
 * - setup 时用 titleRef.value 写 IDB meta.title (不再是 props 一次性值)
 * - titleRef 后续变化 → watch 触发 putMeta 更新 IDB meta.title (保留 started_at)
 * - 兼容旧调用 (传 opts.title 字符串, 不传 titleRef) 不报错
 *
 * 注意: useChunkedRecorder 严重依赖 Vue + IDB + 其他 composables.
 * 这里用 vi.mock 拦截所有依赖, 只测核心 reactive title 写入逻辑.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref, nextTick } from 'vue'

// === mock 依赖 ===
const mockPutMeta = vi.fn().mockResolvedValue(undefined)
const mockGetMeta = vi.fn().mockResolvedValue(null)
const mockUnsubscribe = vi.fn()

vi.mock('@/utils/idbStore', () => ({
  putMeta: (...args) => mockPutMeta(...args),
  getMeta: (...args) => mockGetMeta(...args),
  // 其他 idbStore 方法不 mock, 使用空 stub (useChunkedRecorder setup 不调用)
  putChunk: vi.fn().mockResolvedValue(undefined),
  markChunkUploaded: vi.fn().mockResolvedValue(undefined),
  countUploaded: vi.fn().mockResolvedValue(0),
  getLastChunkIndex: vi.fn().mockResolvedValue(-1),
  getPendingChunks: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/composables/useGlobalRecorder', () => ({
  useGlobalRecorder: () => ({
    onChunk: vi.fn(() => mockUnsubscribe),
  }),
}))

vi.mock('@/composables/useChunkedUploader', () => ({
  useChunkedUploader: () => ({
    enqueue: vi.fn(),
    uploadOne: vi.fn().mockResolvedValue(undefined),
    uploadAll: vi.fn().mockResolvedValue(undefined),
    drainQueue: vi.fn(),
  }),
}))

vi.mock('@/composables/useRecordingState', () => ({
  useRecordingState: () => ({
    stopRecording: vi.fn(),
  }),
}))

vi.mock('element-plus', () => ({
  ElMessage: { warning: vi.fn() },
}))

// 必须在 mock 后再 import
import { useChunkedRecorder } from '../useChunkedRecorder.js'

describe('useChunkedRecorder - P1-5 title reactive', () => {
  beforeEach(() => {
    // 重置 mock 状态: clear 调用历史 + reset mock impl (包括 mockResolvedValue)
    mockPutMeta.mockReset()
    mockGetMeta.mockReset()
    // 重新设置默认值
    mockPutMeta.mockResolvedValue(undefined)
    mockGetMeta.mockResolvedValue(null)
  })

  it('uses titleRef.value for initial meta (not opts.title string)', async () => {
    const meetingIdRef = ref(123)
    const titleRef = ref('正在录音 #123')

    useChunkedRecorder(meetingIdRef, { titleRef })

    // setup 时立即调 putMeta (initialMid 已就绪)
    expect(mockPutMeta).toHaveBeenCalledTimes(1)
    const [mid, meta] = mockPutMeta.mock.calls[0]
    expect(mid).toBe(123)
    expect(meta.title).toBe('正在录音 #123')
    expect(meta.started_at).toBeGreaterThan(0)
  })

  it('watch titleRef change → real-time patch IDB meta.title', async () => {
    const meetingIdRef = ref(123)
    const titleRef = ref('正在录音 #123')

    useChunkedRecorder(meetingIdRef, { titleRef })

    // 第一次 putMeta (setup)
    expect(mockPutMeta).toHaveBeenCalledTimes(1)
    const firstStartedAt = mockPutMeta.mock.calls[0][1].started_at
    expect(mockPutMeta.mock.calls[0][1].title).toBe('正在录音 #123')

    // 用户录音中, 父组件 pageTitle 变化
    titleRef.value = 'bar'
    await nextTick()

    // watch 应触发第二次 putMeta, 用新 title + 复用同一 started_at
    expect(mockPutMeta).toHaveBeenCalledTimes(2)
    const [, meta2] = mockPutMeta.mock.calls[1]
    expect(meta2.title).toBe('bar')  // 新 title
    expect(meta2.started_at).toBe(firstStartedAt)  // started_at 保留 (P1-5 fix)

    // 继续变化
    titleRef.value = 'baz'
    await nextTick()
    expect(mockPutMeta).toHaveBeenCalledTimes(3)
    expect(mockPutMeta.mock.calls[2][1].title).toBe('baz')
    expect(mockPutMeta.mock.calls[2][1].started_at).toBe(firstStartedAt)
  })

  it('creates new meta when titleRef changes from initial', async () => {
    const meetingIdRef = ref(123)
    const titleRef = ref('init')
    useChunkedRecorder(meetingIdRef, { titleRef })

    // 第一次 setup putMeta
    expect(mockPutMeta).toHaveBeenCalledTimes(1)
    const initialStartedAt = mockPutMeta.mock.calls[0][1].started_at

    // 改 title → 走 watch putMeta (复用同一 started_at)
    titleRef.value = 'new title'
    await nextTick()

    expect(mockPutMeta).toHaveBeenCalledTimes(2)
    const meta2 = mockPutMeta.mock.calls[1][1]
    expect(meta2.title).toBe('new title')
    expect(meta2.started_at).toBe(initialStartedAt)
  })

  it('fallback to opts.title string when titleRef not provided (compat)', async () => {
    const meetingIdRef = ref(456)

    // 旧调用: opts.title 字符串 (无 titleRef)
    useChunkedRecorder(meetingIdRef, { title: 'legacy title' })

    expect(mockPutMeta).toHaveBeenCalledTimes(1)
    expect(mockPutMeta.mock.calls[0][1].title).toBe('legacy title')
  })

  it('no putMeta call when meetingId is null (lazy mode setup)', async () => {
    const meetingIdRef = ref(null)  // 还没拿到 meetingId
    const titleRef = ref('pending title')

    useChunkedRecorder(meetingIdRef, { titleRef })

    // initialMid = null → 跳过 setup putMeta (lazy 模式, 等 meetingId 到位)
    expect(mockPutMeta).not.toHaveBeenCalled()
  })

  it('does not watch titleRef if meetingId is null (no point updating meta)', async () => {
    mockGetMeta.mockResolvedValue({
      meeting_id: 999, title: 'old', started_at: 1, updated_at: 1,
    })

    const meetingIdRef = ref(null)
    const titleRef = ref('init')

    useChunkedRecorder(meetingIdRef, { titleRef })
    expect(mockPutMeta).not.toHaveBeenCalled()

    // 改 title 不应触发任何 watch (因为没有 fixedMid 锁定)
    titleRef.value = 'changed'
    await nextTick()

    expect(mockPutMeta).not.toHaveBeenCalled()
    expect(mockGetMeta).not.toHaveBeenCalled()
  })

  it('locks meetingId at setup time (mid 后续变化不影响 watch 目标)', async () => {
    const meetingIdRef = ref(123)
    const titleRef = ref('init')
    useChunkedRecorder(meetingIdRef, { titleRef })

    // meetingId 后续变化 (虽然实际不会发生) → 不应影响 watch 锁定的 mid=123
    meetingIdRef.value = 999
    titleRef.value = 'new'

    await nextTick()
    expect(mockPutMeta).toHaveBeenCalledTimes(2)  // setup + watch
    // 第二次 watch 仍写 mid=123 (closure 锁定)
    expect(mockPutMeta.mock.calls[1][0]).toBe(123)
  })
})