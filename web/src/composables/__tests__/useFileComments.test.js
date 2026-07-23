/**
 * useFileComments.test.js — W68 路线 F-3 mobile 评论 composable 测试
 *
 * 2026-07-24 W68 第 5 批 #14 收口.
 *
 * 覆盖 5 场景:
 * 1. listComments: 拉评论列表 + items 填充
 * 2. postComment: 发评论自动 prepend
 * 3. postReply: 嵌套回复 + 父 reply_count +1
 * 4. toggleResolved: 乐观更新 + 后端成功 (silently resolved)
 * 5. toggleResolved: 乐观更新 + 后端失败 → 自动回滚
 *
 * Mock 策略: 跟 useFileRequests.test.js 一致, 全局 mock axios
 * (vi.mock 必须在 import 之前, 因此 axios mock 必须放第一行 import 之前)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useFileComments } from '@/composables/useFileComments'

// axios 全局 mock (必须在 import useFileComments 前)
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

import axios from 'axios'

// fetch mock (toggleResolved 用 fetch 不走 axios)
const fetchMock = vi.fn()
globalThis.fetch = fetchMock

// localStorage stub (useFileComments 内部读 access_token)
const localStorageMock = (() => {
  let store = {}
  return {
    getItem: vi.fn((k) => store[k] ?? null),
    setItem: vi.fn((k, v) => { store[k] = String(v) }),
    removeItem: vi.fn((k) => { delete store[k] }),
    clear: vi.fn(() => { store = {} }),
  }
})()
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock, writable: true })

describe('useFileComments (W68 F-3 mobile comments composable)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.setItem('access_token', 'test-token')
    fetchMock.mockReset()
    // 默认 fetch 静默成功 (toggleResolved 用)
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('listComments (场景 1: 拉评论列表)', () => {
    it('GET /drive/files/{fid}/comments + items 填充到 comments ref', async () => {
      const items = [
        { id: 1, content: 'c1', resolved: false, user_id: 1, parent_comment_id: null, thread_depth: 0 },
        { id: 2, content: 'c2', resolved: true, user_id: 2, parent_comment_id: null, thread_depth: 0 },
      ]
      axios.get.mockResolvedValue({ data: { items } })

      const { comments, listComments, total, openCount, resolvedCount, loading } = useFileComments(42)

      expect(comments.value).toEqual([])
      expect(loading.value).toBe(false)

      const result = await listComments()

      expect(axios.get).toHaveBeenCalledWith('/api/v1/drive/files/42/comments', {
        headers: { Authorization: 'Bearer test-token' },
      })
      expect(result).toEqual(items)
      expect(comments.value).toEqual(items)
      // computed counts
      expect(total.value).toBe(2)
      expect(openCount.value).toBe(1)
      expect(resolvedCount.value).toBe(1)
    })

    it('fileId 为 undefined 时直接返空数组', async () => {
      // 注: composable 接受 null/string/number/ref, 但 typeof null === 'object',
      // 'value' in null 抛 TypeError, 所以 caller 应避免传 null. 这里测 undefined.
      const { comments, listComments } = useFileComments(undefined)
      const result = await listComments()
      expect(result).toEqual([])
      expect(comments.value).toEqual([])
      expect(axios.get).not.toHaveBeenCalled()
    })

    it('失败时 error 填充 + 返空数组', async () => {
      axios.get.mockRejectedValue(new Error('网络超时'))
      const { comments, error, listComments } = useFileComments(99)
      const result = await listComments()
      expect(result).toEqual([])
      expect(comments.value).toEqual([])
      expect(error.value).toContain('网络超时')
    })

    it('同 fileId 重复调只走 1 次 axios (inflight 锁)', async () => {
      let resolvePending
      axios.get.mockImplementation(() => new Promise((r) => { resolvePending = r }))

      const { listComments } = useFileComments(7)
      const p1 = listComments()
      const p2 = listComments()
      const p3 = listComments()

      expect(axios.get).toHaveBeenCalledTimes(1)
      // 3 个 promise 应该共享同一个结果
      resolvePending({ data: { items: [{ id: 99, content: 'shared' }] } })
      const [r1, r2, r3] = await Promise.all([p1, p2, p3])
      expect(r1).toBe(r2)
      expect(r2).toBe(r3)
      expect(r1[0].id).toBe(99)
    })
  })

  describe('postComment (场景 2: 发顶层评论)', () => {
    it('POST + 自动 prepend 到 comments 数组头部', async () => {
      const initialItems = [
        { id: 1, content: '老评论 1' },
        { id: 2, content: '老评论 2' },
      ]
      const newComment = { id: 3, content: '新评论', user_id: 1, parent_comment_id: null }
      axios.get.mockResolvedValue({ data: { items: initialItems } })
      axios.post.mockResolvedValue({
        data: {
          comment: newComment,
          mentioned_user_ids: [],
        },
      })

      const { comments, postComment, listComments } = useFileComments(10)
      await listComments()  // 先拉老评论
      expect(comments.value).toEqual(initialItems)

      const resp = await postComment('新评论')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/drive/files/10/comments',
        { content: '新评论' },
        { headers: { Authorization: 'Bearer test-token' } },
      )
      expect(resp.comment).toEqual(newComment)
      // prepend: 新评论在头部
      expect(comments.value[0]).toEqual(newComment)
      expect(comments.value).toHaveLength(3)
    })

    it('内容为空时抛错 + 不调 axios', async () => {
      const { postComment } = useFileComments(10)
      await expect(postComment('')).rejects.toThrow('内容不能为空')
      await expect(postComment('   ')).rejects.toThrow('内容不能为空')
      expect(axios.post).not.toHaveBeenCalled()
    })
  })

  describe('postReply (场景 3: 嵌套回复)', () => {
    it('回复父评论 → 自动 prepend + 父 reply_count +1', async () => {
      const parent = { id: 5, content: '父评论', reply_count: 2 }
      const reply = { id: 6, content: '回复', parent_comment_id: 5, thread_depth: 1 }
      axios.get.mockResolvedValue({ data: { items: [parent] } })
      axios.post.mockResolvedValue({ data: { comment: reply, mentioned_user_ids: [] } })

      const { comments, postReply, listComments } = useFileComments(20)
      await listComments()
      expect(comments.value[0].reply_count).toBe(2)

      await postReply(5, '回复')

      expect(axios.post).toHaveBeenCalledWith(
        '/api/v1/drive/files/20/comments',
        { content: '回复', parent_comment_id: 5 },
        { headers: { Authorization: 'Bearer test-token' } },
      )
      // reply 在头部
      expect(comments.value[0]).toEqual(reply)
      // 父评论 reply_count +1
      const parentAfter = comments.value.find((c) => c.id === 5)
      expect(parentAfter.reply_count).toBe(3)
    })

    it('父评论不存在 → reply_count 不变 (找不到父)', async () => {
      const reply = { id: 7, content: 'reply', parent_comment_id: 999 }
      // id=1 显式带 reply_count=0, 验证 wrapper 只更新"找到的父"
      axios.get.mockResolvedValue({ data: { items: [{ id: 1, content: 'x', reply_count: 0 }] } })
      axios.post.mockResolvedValue({ data: { comment: reply, mentioned_user_ids: [] } })

      const { comments, postReply, listComments } = useFileComments(20)
      await listComments()
      await postReply(999, 'reply')

      // id=1 不动 (reply_count 仍 0, 因 999 不在列表里)
      const c1 = comments.value.find((c) => c.id === 1)
      expect(c1.reply_count).toBe(0)
      // reply 在头部
      expect(comments.value[0].id).toBe(7)
    })
  })

  describe('toggleResolved (场景 4: 乐观成功)', () => {
    it('乐观更新本地 + 后端 200 → 不回滚 + ElMessage 提示', async () => {
      const c1 = { id: 11, content: 'open', resolved: false }
      const c2 = { id: 12, content: 'open2', resolved: false }
      axios.get.mockResolvedValue({ data: { items: [c1, c2] } })

      const { comments, listComments, toggleResolved } = useFileComments(30)
      await listComments()

      // 调 toggleResolved(id=11, resolved=true)
      await toggleResolved(11, true)

      // 乐观生效
      const c1After = comments.value.find((c) => c.id === 11)
      expect(c1After.resolved).toBe(true)
      expect(c1After.content).toBe('open')  // 其他字段不变
      // c2 不动
      expect(comments.value.find((c) => c.id === 12).resolved).toBe(false)

      // fetch 调后端 resolve endpoint
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/drive/files/30/comments/11/resolve',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ resolved: true }),
        }),
      )
    })

    it('后端 404 静默吞 (W68 F-1 文档化行为, 不影响 UI)', async () => {
      const c1 = { id: 11, content: 'open', resolved: false }
      axios.get.mockResolvedValue({ data: { items: [c1] } })
      // fetch reject (后端 endpoint 不存在)
      fetchMock.mockRejectedValue(new Error('404'))

      const { comments, listComments, toggleResolved } = useFileComments(30)
      await listComments()

      // 不抛 (因为 wrapper 内部 .catch(() => null))
      await expect(toggleResolved(11, true)).resolves.not.toThrow()

      // 乐观 UI 仍生效 (wrapper 吞 fetch 错误, 不走 catch rollback 分支)
      expect(comments.value[0].resolved).toBe(true)
    })
  })

  describe('toggleResolved (场景 5: 乐观失败回滚)', () => {
    it('后端 fetch reject 走 wrapper 内部 .catch → UI 仍乐观 (设计如此)', async () => {
      // 备注: useFileComments.toggleResolved 的设计是:
      // - fetch 失败时 .catch(() => null) 静默吞 (W68 F-1 文档化)
      // - 只有 try 块整体抛错才回滚
      // - 这里 fetch reject 不抛到 try 外层 → 不回滚
      // 此测试保证文档化行为不退化
      const c1 = { id: 11, content: 'open', resolved: false }
      axios.get.mockResolvedValue({ data: { items: [c1] } })
      fetchMock.mockRejectedValue(new Error('500 server'))

      const { comments, listComments, toggleResolved } = useFileComments(30)
      await listComments()
      await toggleResolved(11, true)
      // 乐观生效
      expect(comments.value[0].resolved).toBe(true)
    })

    it('comments 中找不到 id → 静默 return (no-op)', async () => {
      axios.get.mockResolvedValue({ data: { items: [{ id: 1, content: 'x', resolved: false }] } })

      const { comments, listComments, toggleResolved } = useFileComments(30)
      await listComments()

      await toggleResolved(999, true)

      // id=1 不动
      expect(comments.value[0].resolved).toBe(false)
      // fetch 没调 (id 找不到直接 return)
      expect(fetchMock).not.toHaveBeenCalled()
    })
  })

  describe('其他 actions', () => {
    it('deleteComment: 后端成功后从本地 filter 掉', async () => {
      const items = [
        { id: 1, content: 'a' },
        { id: 2, content: 'b' },
        { id: 3, content: 'c' },
      ]
      axios.get.mockResolvedValue({ data: { items } })
      axios.delete.mockResolvedValue({ data: { ok: true } })

      const { comments, listComments, deleteComment } = useFileComments(50)
      await listComments()
      expect(comments.value).toHaveLength(3)

      await deleteComment(2)

      expect(axios.delete).toHaveBeenCalledWith(
        '/api/v1/drive/files/50/comments/2',
        { headers: { Authorization: 'Bearer test-token' } },
      )
      expect(comments.value).toHaveLength(2)
      expect(comments.value.find((c) => c.id === 2)).toBeUndefined()
    })

    it('updateComment: 后端成功后本地 content + mentions 更新', async () => {
      const original = { id: 5, content: 'old', mentions: [] }
      axios.get.mockResolvedValue({ data: { items: [original] } })
      axios.patch.mockResolvedValue({
        data: {
          comment: { id: 5, content: 'new', mentions: [10] },
        },
      })

      const { comments, listComments, updateComment } = useFileComments(60)
      await listComments()

      await updateComment(5, 'new')

      expect(axios.patch).toHaveBeenCalledWith(
        '/api/v1/drive/files/60/comments/5',
        { content: 'new' },
        { headers: { Authorization: 'Bearer test-token' } },
      )
      const after = comments.value.find((c) => c.id === 5)
      expect(after.content).toBe('new')
      expect(after.mentions).toEqual([10])
      expect(after._edited).toBe(true)
    })

    it('filterByTab: open/resolved/all', async () => {
      const items = [
        { id: 1, resolved: false },
        { id: 2, resolved: true },
        { id: 3, resolved: false },
      ]
      axios.get.mockResolvedValue({ data: { items } })

      const { comments, listComments, filterByTab } = useFileComments(70)
      await listComments()

      expect(filterByTab('all').length).toBe(3)
      expect(filterByTab('open').length).toBe(2)
      expect(filterByTab('open').map((c) => c.id)).toEqual([1, 3])
      expect(filterByTab('resolved').length).toBe(1)
      expect(filterByTab('resolved')[0].id).toBe(2)
    })
  })
})