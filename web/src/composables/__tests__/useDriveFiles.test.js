/**
 * useDriveFiles.test.js — v2 PR6-P19 团队共享盘隔离 (is_team_shared)
 *
 * 覆盖 (5 case):
 * 1. fetchFiles 默认 view=personal (后端参数正确)
 * 2. fetchFiles 切到 view=team (后端参数 + viewMode ref 同步)
 * 3. fetchFiles 切到 view=all (不过滤)
 * 4. fetchFiles params 覆盖: DesktopDriveView 切到 team 时传 view=team 覆盖默认
 * 5. fetchFiles 切到 team 再切回 personal, 下次 fetchFiles 透传 personal
 *
 * 实现侧 fetchFiles 已改用 `fetch + URLSearchParams` (v2.26 BUG E 修复),
 * 因此测试用 `globalThis.fetch` mock 拦截, 直接断言 URL 中的 query 参数。
 * instantUpload 仍走 axios.post, 所以 axios mock 保留。
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

// fetch mock: 解析 URL 返回标准化结果, 测试断言 view 等 query 参数
const fetchCalls = []
const fetchMock = vi.fn(async (url, options = {}) => {
  fetchCalls.push({ url, options })
  const u = new URL(url, 'http://localhost')
  const items = []
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    url,
    headers: { get: () => 'application/json' },
    json: async () => ({ items, total: 0, page: Number(u.searchParams.get('page') || 1), page_size: Number(u.searchParams.get('page_size') || 50) }),
    text: async () => JSON.stringify({ items, total: 0 }),
  }
})

function installFetchMock() {
  fetchCalls.length = 0
  fetchMock.mockClear()
  globalThis.fetch = fetchMock
}

function viewFromUrl(url) {
  const u = new URL(url, 'http://localhost')
  return u.searchParams.get('view')
}

describe('useDriveFiles v2 PR6-P19 (团队共享盘隔离)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    installFetchMock()
    mockAxiosPost.mockResolvedValue({ data: { instant: false, upload_url: '/api/v1/drive/files/upload' } })
  })

  afterEach(() => {
    delete globalThis.fetch
  })

  describe('fetchFiles view 参数', () => {
    it('默认 viewMode=personal, fetchFiles 透传 view=personal 到后端', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, viewMode } = useDriveFiles()
      expect(viewMode.value).toBe('personal')

      await fetchFiles()

      expect(fetchCalls).toHaveLength(1)
      const url = fetchCalls[0].url
      expect(url.startsWith('/api/v1/drive/files?')).toBe(true)
      expect(viewFromUrl(url)).toBe('personal')
    })

    it('viewMode 切到 team 后, 下次 fetchFiles 透传 view=team', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, viewMode } = useDriveFiles()

      viewMode.value = 'team'
      await fetchFiles()

      expect(fetchCalls).toHaveLength(1)
      expect(viewFromUrl(fetchCalls[0].url)).toBe('team')
    })

    it('viewMode 切到 all 后, fetchFiles 透传 view=all (不过滤)', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, viewMode } = useDriveFiles()

      viewMode.value = 'all'
      await fetchFiles()

      expect(fetchCalls).toHaveLength(1)
      expect(viewFromUrl(fetchCalls[0].url)).toBe('all')
    })

    it('params 覆盖: DesktopDriveView 切到 team 时传 view=team 覆盖默认', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles } = useDriveFiles()

      // 模拟 DesktopDriveView: fetchFiles({ view: 'team' })
      await fetchFiles({ view: 'team' })

      expect(fetchCalls).toHaveLength(1)
      expect(viewFromUrl(fetchCalls[0].url)).toBe('team')
    })
  })

  describe('instantUpload isTeamShared 透传', () => {
    it('默认 isTeamShared=false, 透传 false', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { instantUpload } = useDriveFiles()

      await instantUpload({
        fileHash: 'abc123def456',
        fileName: 'test.txt',
        fileSize: 1024,
        folderId: null,
        visibility: 'team',
      })

      const callArgs = mockAxiosPost.mock.calls[0]
      expect(callArgs[0]).toBe('/api/v1/drive/files/instant-upload')
      expect(callArgs[1].is_team_shared).toBe(false)
    })

    it('isTeamShared=true 透传到后端 (DesktopDriveView team 视图上传)', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { instantUpload } = useDriveFiles()

      mockAxiosPost.mockClear()
      await instantUpload({
        fileHash: 'abc123def456',
        fileName: 'shared-doc.pdf',
        fileSize: 1024 * 100,
        folderId: null,
        visibility: 'team',
        isTeamShared: true,
      })

      const callArgs = mockAxiosPost.mock.calls[0]
      expect(callArgs[1].is_team_shared).toBe(true)
    })
  })

  describe('viewMode 切回 personal 同步', () => {
    it('viewMode 切到 team 再切回 personal, 下次 fetchFiles 透传 personal', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, viewMode } = useDriveFiles()

      // 模拟用户点 🌐 团队共享盘
      viewMode.value = 'team'
      await fetchFiles()
      expect(fetchCalls).toHaveLength(1)
      expect(viewFromUrl(fetchCalls[0].url)).toBe('team')

      // 模拟用户点回 📁 我的网盘
      viewMode.value = 'personal'
      await fetchFiles()
      expect(fetchCalls).toHaveLength(2)
      expect(viewFromUrl(fetchCalls[1].url)).toBe('personal')
    })
  })
})