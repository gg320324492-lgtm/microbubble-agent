// useFileRequests.test.js — v2 PR7 文件请求 composable 单测
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useFileRequests } from '@/composables/useFileRequests'

// axios mock
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import axios from 'axios'

describe('useFileRequests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchMy: 拉取成功填充 requests', async () => {
    axios.get.mockResolvedValue({
      data: {
        items: [
          { id: 1, title: 'req1', token: 'abc', submission_count: 0, active: true, is_active: true, expired: false },
          { id: 2, title: 'req2', token: 'def', submission_count: 1, active: true, is_active: true, expired: false },
        ],
        total: 2,
      }
    })
    const { requests, fetchMy, hasRequests } = useFileRequests()
    await fetchMy(false)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/file-requests/my', {
      params: { include_inactive: 'false' }
    })
    expect(requests.value).toHaveLength(2)
    expect(hasRequests.value).toBe(true)
  })

  it('fetchMy: include_inactive=true', async () => {
    axios.get.mockResolvedValue({ data: { items: [], total: 0 } })
    const { fetchMy } = useFileRequests()
    await fetchMy(true)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/file-requests/my', {
      params: { include_inactive: 'true' }
    })
  })

  it('fetchMy: 失败时 error 填 + 清空 requests', async () => {
    axios.get.mockRejectedValue(new Error('Network error'))
    const { requests, error, fetchMy } = useFileRequests()
    await fetchMy(false)
    expect(requests.value).toEqual([])
    expect(error.value).toContain('Network error')
  })

  it('createRequest: 成功后调用 fetchMy 刷新', async () => {
    axios.post.mockResolvedValue({ data: { id: 99, token: 'new' } })
    axios.get.mockResolvedValue({ data: { items: [], total: 0 } })
    const { createRequest, fetchMy, requests } = useFileRequests()
    await createRequest({ title: 'new' })
    expect(axios.post).toHaveBeenCalledWith('/api/v1/file-requests', { title: 'new' })
    expect(axios.get).toHaveBeenCalled()  // fetchMy 被调
    expect(requests.value).toEqual([])
  })

  it('createRequest: 422 detail 抛出 Error', async () => {
    axios.post.mockRejectedValue({ response: { data: { detail: 'title 不能为空' } } })
    const { createRequest } = useFileRequests()
    await expect(createRequest({ title: '' })).rejects.toThrow('title 不能为空')
  })

  it('deactivate: 成功返 true + 触发 fetchMy', async () => {
    axios.post.mockResolvedValue({ status: 204 })
    axios.get.mockResolvedValue({ data: { items: [], total: 0 } })
    const { deactivate } = useFileRequests()
    const ok = await deactivate(42)
    expect(ok).toBe(true)
    expect(axios.post).toHaveBeenCalledWith('/api/v1/file-requests/42/deactivate')
  })

  it('deactivate: 失败返 false', async () => {
    axios.post.mockRejectedValue(new Error('500'))
    const { deactivate, error } = useFileRequests()
    const ok = await deactivate(99)
    expect(ok).toBe(false)
    expect(error.value).toBeTruthy()
  })

  it('fetchPublicInfo: 公开端点无 Authorization 头', async () => {
    axios.get.mockResolvedValue({ data: { id: 1, title: 'pub', active: true } })
    const { fetchPublicInfo } = useFileRequests()
    const info = await fetchPublicInfo('abc123')
    expect(axios.get).toHaveBeenCalledWith('/api/v1/file-requests/abc123/info')
    expect(info.title).toBe('pub')
  })

  it('submitPublic: 传 FormData (multipart)', async () => {
    axios.post.mockResolvedValue({ data: { success: true, submission_count: 1 } })
    const { submitPublic } = useFileRequests()
    const fd = new FormData()
    fd.append('uploader_name', 'x')
    fd.append('file', new Blob(['a']), 'a.pdf')
    const r = await submitPublic('tk', fd)
    expect(axios.post).toHaveBeenCalledWith('/api/v1/file-requests/tk/submit', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    expect(r.success).toBe(true)
  })
})
