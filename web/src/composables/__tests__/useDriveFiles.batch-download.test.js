/**
 * useDriveFiles.batch-download.test.js — v77 留尾清理 (2026-07-20)
 * 批量下载 stub 实装的 3 case 覆盖:
 * 1. 单选 (1 id) → POST batch-download {ids:[1]} + 触发浏览器下载
 * 2. 多选 (多 id) → POST batch-download {ids:[1,2,3]}
 * 3. 空选择 → 直接 return false, 不发请求 (上层 toolbar 已 disable)
 *
 * 复用后端 POST /api/v1/drive/files/batch-download (drive_files.py:931 已实装)
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

describe('useDriveFiles batchDownload (v77 留尾清理)', () => {
  let clickSpy

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // 模拟后端返回 blob + Content-Disposition
    mockAxiosPost.mockResolvedValue({
      data: new Blob(['zip-bytes'], { type: 'application/zip' }),
      headers: { 'content-disposition': "attachment; filename*=UTF-8''drive_alice_20260720.zip" },
    })
    // jsdom 没实现 URL.createObjectURL / revokeObjectURL
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    global.URL.revokeObjectURL = vi.fn()
    // 拦截 anchor click (不触发真实导航)
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  it('单选: batchDownload([1]) POST batch-download {ids:[1]} + 触发下载', async () => {
    const { useDriveFiles } = await import('@/composables/useDriveFiles')
    const { batchDownload } = useDriveFiles()

    const ret = await batchDownload([1])

    expect(ret).toBe(true)
    const callArgs = mockAxiosPost.mock.calls[0]
    expect(callArgs[0]).toBe('/api/v1/drive/files/batch-download')
    expect(callArgs[1]).toEqual({ ids: [1] })
    expect(callArgs[2].responseType).toBe('blob')
    expect(clickSpy).toHaveBeenCalledTimes(1)
    expect(global.URL.createObjectURL).toHaveBeenCalled()
    expect(global.URL.revokeObjectURL).toHaveBeenCalled()
  })

  it('多选: batchDownload([1,2,3]) POST batch-download {ids:[1,2,3]}', async () => {
    const { useDriveFiles } = await import('@/composables/useDriveFiles')
    const { batchDownload } = useDriveFiles()

    const ret = await batchDownload([1, 2, 3])

    expect(ret).toBe(true)
    const callArgs = mockAxiosPost.mock.calls[0]
    expect(callArgs[0]).toBe('/api/v1/drive/files/batch-download')
    expect(callArgs[1]).toEqual({ ids: [1, 2, 3] })
    expect(clickSpy).toHaveBeenCalledTimes(1)
  })

  it('空选择: batchDownload([]) return false, 不发请求 (disable 保护)', async () => {
    const { useDriveFiles } = await import('@/composables/useDriveFiles')
    const { batchDownload } = useDriveFiles()

    const retEmpty = await batchDownload([])
    const retNull = await batchDownload(null)

    expect(retEmpty).toBe(false)
    expect(retNull).toBe(false)
    expect(mockAxiosPost).not.toHaveBeenCalled()
    expect(clickSpy).not.toHaveBeenCalled()
  })
})
