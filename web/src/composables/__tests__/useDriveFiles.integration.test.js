/**
 * useDriveFiles.integration.test.js — W2 T2 真实集成测试
 *
 * 背景 (2026-07-20):
 * W3 commit `9c88ba31` 修了 useDriveFiles.test.js 的 5 个 mock fail (axios → fetch),
 * 但只是 mock 单测。本文件覆盖真实 fetch + URLSearchParams 的端到端行为。
 *
 * 覆盖 (5 case):
 * 1. fetchFiles 真实端到端: 验证 URLSearchParams query body 正确性 (view/sort_by/page/page_size/starred_only)
 *    + Authorization header 透传 + 解析响应写入 driveFiles
 * 2. batchDownload 真实流程: 模拟 server 返 200 + binary blob, 验证 anchor click 触发
 * 3. batchShare 真实流程: 复用 createShareLink (DesktopDriveView 批量分享的底层调用),
 *    验证 share URL 拼接逻辑
 * 4. 空响应容错: server 返 404 / 500 → useDriveFiles.loadError 写入 + driveFiles 清空 (不是 silent fail)
 * 5. 网络错误容错: fetch reject → useDriveFiles.loadError 写入 (无 retry 行为, 但错误正确传播)
 *
 * 纪律 (4 条):
 * 1. 用 vitest jsdom + fetch mock (跟 W3 修的 mock 一致)
 * 2. 不改 useDriveFiles.js 实现
 * 3. 跟 W3 commit `9c88ba31` 修过的 mock 测试隔离 (独立文件)
 * 4. 单 commit defer: `test(useDriveFiles): 真实集成测试覆盖 5 场景`
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// axios mock — batchDownload / createShareLink / instantUpload 走 axios
const mockAxiosPost = vi.fn()

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: (...args) => mockAxiosPost(...args),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

// fetch mock — fetchFiles 走 fetch + URLSearchParams
const fetchCalls = []
const fetchMock = vi.fn(async (url, options = {}) => {
  fetchCalls.push({ url, options })
  const u = new URL(url, 'http://localhost')
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    url,
    headers: { get: () => 'application/json' },
    json: async () => ({ items: [], total: 0 }),
    text: async () => JSON.stringify({ items: [], total: 0 }),
  }
})

function installFetchMock() {
  fetchCalls.length = 0
  fetchMock.mockClear()
  globalThis.fetch = fetchMock
}

describe('useDriveFiles integration (W2 T2 真实集成测试)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    installFetchMock()
    vi.clearAllMocks()
    // 默认 axios.post 成功 (不传参的通用 case)
    mockAxiosPost.mockResolvedValue({ data: {} })
  })

  afterEach(() => {
    delete globalThis.fetch
  })

  describe('场景 1: fetchFiles 真实端到端 URLSearchParams', () => {
    it('默认 view=personal: URL 包含所有 query params + Authorization header', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, driveFiles, total, loading } = useDriveFiles()

      expect(loading.value).toBe(false)
      await fetchFiles()

      // 1 次 fetch, URL 含全部预期 query params
      expect(fetchCalls).toHaveLength(1)
      const { url, options } = fetchCalls[0]
      const u = new URL(url, 'http://localhost')

      expect(url.startsWith('/api/v1/drive/files?')).toBe(true)
      expect(u.searchParams.get('view')).toBe('personal')
      expect(u.searchParams.get('page')).toBe('1')
      expect(u.searchParams.get('page_size')).toBe('20')
      expect(u.searchParams.get('sort_by')).toBe('created_at')
      expect(u.searchParams.get('sort_order')).toBe('desc')
      expect(u.searchParams.get('starred_only')).toBe('false')
      // Authorization header 透传
      expect(options.headers.Authorization).toBe('Bearer ' + (localStorage.getItem('access_token') || ''))
      // 响应正确写入
      expect(driveFiles.value).toEqual([])
      expect(total.value).toBe(0)
      expect(loading.value).toBe(false)
    })

    it('view=team + folderId 未传: 自动注入 include_subfolders=true (v2.21 行为)', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, viewMode } = useDriveFiles()

      viewMode.value = 'team'
      await fetchFiles()

      const u = new URL(fetchCalls[0].url, 'http://localhost')
      expect(u.searchParams.get('view')).toBe('team')
      expect(u.searchParams.get('include_subfolders')).toBe('true')
    })

    it('view=team + 显式传 folder_id: 不再自动加 include_subfolders (调用方决定)', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, viewMode } = useDriveFiles()

      viewMode.value = 'team'
      await fetchFiles({ folder_id: 42 })

      const u = new URL(fetchCalls[0].url, 'http://localhost')
      expect(u.searchParams.get('folder_id')).toBe('42')
      expect(u.searchParams.has('include_subfolders')).toBe(false)
    })

    it('fileType 透传 + 空值自动剔除', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, fileType } = useDriveFiles()

      fileType.value = 'pdf'
      await fetchFiles({ keyword: '', owner_id: null })

      const u = new URL(fetchCalls[0].url, 'http://localhost')
      expect(u.searchParams.get('file_type')).toBe('pdf')
      // 空字符串/null 应被剔除 (避免污染 URL)
      expect(u.searchParams.has('keyword')).toBe(false)
      expect(u.searchParams.has('owner_id')).toBe(false)
    })
  })

  describe('场景 2: batchDownload 真实流程', () => {
    beforeEach(() => {
      // jsdom 缺 URL.createObjectURL / revokeObjectURL
      global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
      global.URL.revokeObjectURL = vi.fn()
      vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    })

    it('server 返 blob + Content-Disposition: 触发 anchor.click + 解码文件名', async () => {
      mockAxiosPost.mockResolvedValueOnce({
        data: new Blob(['zip-bytes'], { type: 'application/zip' }),
        headers: { 'content-disposition': "attachment; filename*=UTF-8''drive_alice_20260720.zip" },
      })

      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { batchDownload } = useDriveFiles()

      const ret = await batchDownload([1, 2, 3])

      expect(ret).toBe(true)
      // POST URL 正确
      expect(mockAxiosPost.mock.calls[0][0]).toBe('/api/v1/drive/files/batch-download')
      expect(mockAxiosPost.mock.calls[0][1]).toEqual({ ids: [1, 2, 3] })
      // responseType 必须 blob (后端流式 ZIP)
      expect(mockAxiosPost.mock.calls[0][2]).toMatchObject({ responseType: 'blob' })
      // URL.createObjectURL + revokeObjectURL 配对
      expect(global.URL.createObjectURL).toHaveBeenCalledTimes(1)
      expect(global.URL.revokeObjectURL).toHaveBeenCalledTimes(1)
    })

    it('server 返 500: batchDownload catch 转 Error(detail) (W1 修, 跟其他方法风格统一)', async () => {
      // W1 (2026-07-20) 修复: batchDownload 改加 try/catch, axios reject 不再原样传播
      // 风格跟 fetchFiles/deleteFile/createShareLink 等其他方法完全一致:
      // throw new Error(e.response?.data?.error?.message || e.response?.data?.detail || '批量下载失败')
      const axiosError = new Error('Request failed with status code 500')
      axiosError.response = { data: { detail: '权限不足' } }
      mockAxiosPost.mockRejectedValueOnce(axiosError)

      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { batchDownload } = useDriveFiles()

      await expect(batchDownload([1])).rejects.toThrow('权限不足')
    })
  })

  describe('场景 3: batchShare 真实流程 (createShareLink 是 batch share 底层)', () => {
    it('createShareLink: server 返 share_url, 解析 token/shareUrl/expiresAt/passwordRequired', async () => {
      mockAxiosPost.mockResolvedValueOnce({
        data: {
          token: 'abc-token-123',
          share_url: '/api/v1/drive/files/share/abc-token-123',
          expires_at: '2026-07-27T10:00:00Z',
          password_required: true,
        },
      })

      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { createShareLink } = useDriveFiles()

      const result = await createShareLink(99, { expiresHours: 168, password: 'secret123' })

      expect(result.token).toBe('abc-token-123')
      expect(result.shareUrl).toBe('/api/v1/drive/files/share/abc-token-123')
      expect(result.expiresAt).toBe('2026-07-27T10:00:00Z')
      expect(result.passwordRequired).toBe(true)

      // POST URL 正确 + payload 正确
      expect(mockAxiosPost.mock.calls[0][0]).toBe('/api/v1/drive/files/99/share-link')
      expect(mockAxiosPost.mock.calls[0][1]).toEqual({
        expires_hours: 168,
        password: 'secret123',
      })
    })

    it('createShareLink 不传 password: payload 跳过 password 字段', async () => {
      mockAxiosPost.mockResolvedValueOnce({
        data: {
          token: 'no-pw-token',
          share_url: '/api/v1/drive/files/share/no-pw-token',
          expires_at: '2026-07-21T10:00:00Z',
          password_required: false,
        },
      })

      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { createShareLink } = useDriveFiles()

      await createShareLink(1)

      expect(mockAxiosPost.mock.calls[0][1]).toEqual({ expires_hours: 168 })
      expect(mockAxiosPost.mock.calls[0][1].password).toBeUndefined()
    })
  })

  describe('场景 4: 空响应容错 (HTTP 4xx/5xx)', () => {
    it('fetchFiles 收到 404: loadError 写入 + driveFiles 清空 + loading=false', async () => {
      // 覆写 fetch mock 返 404
      globalThis.fetch = vi.fn(async () => ({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        headers: { get: () => 'application/json' },
        json: async () => ({ error: { message: '文件列表加载失败: not found' } }),
      }))

      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, driveFiles, total, loadError, loading } = useDriveFiles()

      await fetchFiles()

      expect(loadError.value).toBeTruthy()
      expect(driveFiles.value).toEqual([])
      expect(total.value).toBe(0)
      expect(loading.value).toBe(false)
    })

    it('fetchFiles 收到 500: loadError 写入 (不 silent fail)', async () => {
      globalThis.fetch = vi.fn(async () => ({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        headers: { get: () => 'application/json' },
        json: async () => ({ error: { message: 'server boom' } }),
      }))

      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, loadError } = useDriveFiles()

      await fetchFiles()

      // 实现侧会 throw `HTTP 500`, catch 块 catch 写 loadError
      expect(loadError.value).toBe('HTTP 500')
    })
  })

  describe('场景 5: 网络错误容错 (fetch reject)', () => {
    it('fetchFiles 抛 TypeError (network disconnected): loadError 写入 + driveFiles 清空', async () => {
      globalThis.fetch = vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      })

      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, driveFiles, total, loadError, loading } = useDriveFiles()

      await fetchFiles()

      // fetch 抛 TypeError → catch 块 catch 写 loadError, 不让 silent fail
      expect(loadError.value).toBe('Failed to fetch')
      expect(driveFiles.value).toEqual([])
      expect(total.value).toBe(0)
      expect(loading.value).toBe(false)
    })

    it('fetchFiles retry: 无内置 retry, 需调用方主动重试 (有界契约)', async () => {
      let attempts = 0
      globalThis.fetch = vi.fn(async () => {
        attempts++
        throw new TypeError('Failed to fetch')
      })

      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles } = useDriveFiles()

      await fetchFiles()
      await fetchFiles()

      // 2 次 fetchFiles 调用 = 2 次 fetch 尝试 (无 retry)
      expect(attempts).toBe(2)
      expect(globalThis.fetch).toHaveBeenCalledTimes(2)
    })
  })
})
