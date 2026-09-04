/**
 * useDriveFiles.f4-batchstar.test.js — 批次② F4 + ②-5 配套
 *
 * 覆盖:
 * 1. F4: fetchFiles 非 2xx → 解析后端统一异常 envelope {"error":{"message"}},
 *    loadError 含后端 message 而非裸 HTTP 状态码
 * 2. F4 兜底: body 非 JSON → 'HTTP <status>'
 * 3. ②-5: fetchFiles search 参数透传 URL (前端先行, params 展开)
 * 4. batchStar: 一次 POST /files/batch-star {file_ids, starred} (mock 断言一次请求)
 *    + 局部更新 is_starred
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockAxiosPost = vi.fn()

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: (...args) => mockAxiosPost(...args),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

function stubFetch(response) {
  globalThis.fetch = vi.fn(async () => response)
}

describe('useDriveFiles 批次② (F4 错误 envelope + search 透传 + batchStar)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockAxiosPost.mockReset()
  })
  afterEach(() => { delete globalThis.fetch })

  it('F4: 500 + error envelope → loadError 含后端 message', async () => {
    stubFetch({
      ok: false,
      status: 500,
      json: async () => ({ error: { code: 'INTERNAL', message: '数据库连接池耗尽' } }),
    })
    const { useDriveFiles } = await import('@/composables/useDriveFiles')
    const { fetchFiles, loadError } = useDriveFiles()
    await fetchFiles()
    expect(loadError.value).toContain('数据库连接池耗尽')
  })

  it('F4: 403 + FastAPI detail → loadError 含 detail', async () => {
    stubFetch({
      ok: false,
      status: 403,
      json: async () => ({ detail: '无权访问该文件夹' }),
    })
    const { useDriveFiles } = await import('@/composables/useDriveFiles')
    const { fetchFiles, loadError } = useDriveFiles()
    await fetchFiles()
    expect(loadError.value).toContain('无权访问该文件夹')
  })

  it('F4 兜底: 非 JSON body → HTTP <status>', async () => {
    stubFetch({
      ok: false,
      status: 502,
      json: async () => { throw new SyntaxError('not json') },
    })
    const { useDriveFiles } = await import('@/composables/useDriveFiles')
    const { fetchFiles, loadError } = useDriveFiles()
    await fetchFiles()
    expect(loadError.value).toContain('HTTP 502')
  })

  it('②-5: fetchFiles({search}) 透传 search 到 URL; 空串被剔除', async () => {
    const calls = []
    globalThis.fetch = vi.fn(async (url) => {
      calls.push(url)
      return { ok: true, status: 200, json: async () => ({ items: [], total: 0 }) }
    })
    const { useDriveFiles } = await import('@/composables/useDriveFiles')
    const { fetchFiles } = useDriveFiles()

    await fetchFiles({ search: '组会' })
    expect(new URL(calls[0], 'http://localhost').searchParams.get('search')).toBe('组会')

    await fetchFiles({ search: '' })
    expect(new URL(calls[1], 'http://localhost').searchParams.has('search')).toBe(false)
  })

  it('batchStar: 一次 POST batch-star {file_ids, starred:true} + 局部 is_starred 更新', async () => {
    stubFetch({ ok: true, status: 200, json: async () => ({ items: [
      { id: 1, is_starred: false }, { id: 2, is_starred: true }, { id: 3, is_starred: false },
    ], total: 3 }) })
    mockAxiosPost.mockResolvedValue({ data: { updated: 3 } })

    const { useDriveFiles } = await import('@/composables/useDriveFiles')
    const { fetchFiles, batchStar, driveFiles } = useDriveFiles()
    await fetchFiles()

    await batchStar([1, 2, 3], true)
    expect(mockAxiosPost).toHaveBeenCalledTimes(1)
    const [url, body] = mockAxiosPost.mock.calls[0]
    expect(url).toBe('/api/v1/drive/files/batch-star')
    expect(body).toEqual({ file_ids: [1, 2, 3], starred: true })
    expect(driveFiles.value.every(f => f.is_starred)).toBe(true)
  })
})
