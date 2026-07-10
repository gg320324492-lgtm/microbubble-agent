/**
 * useDriveFiles.test.js — v2 PR6-P19 团队共享盘隔离 (is_team_shared)
 *
 * 覆盖 (3 case):
 * 1. fetchFiles 默认 view=personal (后端参数正确)
 * 2. fetchFiles 切到 view=team (后端参数 + viewMode ref 同步)
 * 3. instantUpload 传 isTeamShared=true 透传到后端
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const mockAxiosGet = vi.fn()
const mockAxiosPost = vi.fn()
const mockAxiosDelete = vi.fn()
const mockAxiosPut = vi.fn()

vi.mock('axios', () => ({
  default: {
    get: (...args) => mockAxiosGet(...args),
    post: (...args) => mockAxiosPost(...args),
    put: (...args) => mockAxiosPut(...args),
    delete: (...args) => mockAxiosDelete(...args),
  },
}))

describe('useDriveFiles v2 PR6-P19 (团队共享盘隔离)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockAxiosGet.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 50 } })
    mockAxiosPost.mockResolvedValue({ data: { instant: false, upload_url: '/api/v1/drive/files/upload' } })
  })

  describe('fetchFiles view 参数', () => {
    it('默认 viewMode=personal, fetchFiles 透传 view=personal 到后端', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, viewMode } = useDriveFiles()
      expect(viewMode.value).toBe('personal')

      await fetchFiles()

      // 验证 axios.get 收到 view: 'personal'
      const callArgs = mockAxiosGet.mock.calls[0]
      expect(callArgs[0]).toBe('/api/v1/drive/files')
      expect(callArgs[1].params.view).toBe('personal')
    })

    it('viewMode 切到 team 后, 下次 fetchFiles 透传 view=team', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, viewMode } = useDriveFiles()

      // 切视图
      viewMode.value = 'team'
      await fetchFiles()

      const callArgs = mockAxiosGet.mock.calls[0]
      expect(callArgs[1].params.view).toBe('team')
    })

    it('viewMode 切到 all 后, fetchFiles 透传 view=all (不过滤)', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles, viewMode } = useDriveFiles()

      viewMode.value = 'all'
      await fetchFiles()

      const callArgs = mockAxiosGet.mock.calls[0]
      expect(callArgs[1].params.view).toBe('all')
    })

    it('params 覆盖: DesktopDriveView 切到 team 时传 view=team 覆盖默认', async () => {
      const { useDriveFiles } = await import('@/composables/useDriveFiles')
      const { fetchFiles } = useDriveFiles()

      // 模拟 DesktopDriveView: fetchFiles({ view: 'team' })
      await fetchFiles({ view: 'team' })

      const callArgs = mockAxiosGet.mock.calls[0]
      expect(callArgs[1].params.view).toBe('team')
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
      expect(mockAxiosGet.mock.calls[0][1].params.view).toBe('team')

      // 模拟用户点回 📁 我的网盘
      viewMode.value = 'personal'
      await fetchFiles()
      expect(mockAxiosGet.mock.calls[1][1].params.view).toBe('personal')
    })
  })
})
