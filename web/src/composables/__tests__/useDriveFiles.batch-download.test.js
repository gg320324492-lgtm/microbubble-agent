/**
 * useDriveFiles.batch-download.test.js — v77 留尾清理 (2026-07-20)
 * 批量下载 stub 实装的 3 case 覆盖:
 * 1. 单选 (1 id) → POST batch-download {ids:[1]} + 触发浏览器下载
 * 2. 多选 (多 id) → POST batch-download {ids:[1,2,3]}
 * 3. 空选择 → 直接 return false, 不发请求 (上层 toolbar 已 disable)
 * 4. axios reject → catch 转 Error('批量下载失败') 或 detail 文案 (跟 fetchFiles/deleteFile 风格统一)
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

  it('W1 修复: axios reject → throw Error(后端 detail 或 "批量下载失败") 兜底', async () => {
    // Case A: 后端返回带 detail 的 4xx/5xx (与 batchSoftDelete 等其他方法风格一致)
    mockAxiosPost.mockRejectedValueOnce({
      response: { data: { detail: '权限不足,无法下载该文件' } }
    })
    const { useDriveFiles: a } = await import('@/composables/useDriveFiles')
    const { batchDownload: dl1 } = a()
    await expect(dl1([1])).rejects.toThrow('权限不足,无法下载该文件')

    // Case B: 后端返回带 error.message 的 envelope (与 deleteFile/renameFile 风格一致)
    mockAxiosPost.mockRejectedValueOnce({
      response: { data: { error: { message: '文件不存在或已删除' } } }
    })
    const { useDriveFiles: b } = await import('@/composables/useDriveFiles')
    const { batchDownload: dl2 } = b()
    await expect(dl2([1])).rejects.toThrow('文件不存在或已删除')

    // Case C: 网络断开/无 response (axios fail raw) → fallback "批量下载失败"
    mockAxiosPost.mockRejectedValueOnce(new Error('Network Error'))
    const { useDriveFiles: c } = await import('@/composables/useDriveFiles')
    const { batchDownload: dl3 } = c()
    await expect(dl3([1])).rejects.toThrow('批量下载失败')

    // 关键断言: 失败时绝对不能触发浏览器下载 (anchor click 没被调)
    expect(clickSpy).not.toHaveBeenCalled()
  })
})
