import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useMeeting } from '../useMeeting'

// Mock axios
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn()
  }
}))

import axios from 'axios'

describe('useMeeting', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchMeetings 成功更新列表', async () => {
    const mockData = {
      items: [{ id: 1, title: '测试会议', status: 'scheduled' }],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 }
    }
    axios.get.mockResolvedValue({ data: mockData })

    const { meetings, fetchMeetings, loading, total } = useMeeting()
    await fetchMeetings()

    expect(meetings.value).toEqual(mockData.items)
    expect(total.value).toBe(1)
    expect(loading.value).toBe(false)
  })

  it('fetchMeetings 失败后 loading 重置', async () => {
    axios.get.mockRejectedValue(new Error('Network error'))

    const { fetchMeetings, loading } = useMeeting()
    try {
      await fetchMeetings()
    } catch {}

    expect(loading.value).toBe(false)
  })

  it('fetchMeeting 获取单个会议', async () => {
    const mockMeeting = { id: 1, title: '测试会议' }
    axios.get.mockResolvedValue({ data: mockMeeting })

    const { fetchMeeting, currentMeeting } = useMeeting()
    const result = await fetchMeeting(1)

    expect(axios.get).toHaveBeenCalledWith('/api/v1/meetings/1')
    expect(result).toEqual(mockMeeting)
    expect(currentMeeting.value).toEqual(mockMeeting)
  })

  it('createMeeting 调用 POST 并刷新列表', async () => {
    axios.post.mockResolvedValue({ data: { id: 2, title: '新会议' } })
    axios.get.mockResolvedValue({
      data: { items: [{ id: 2, title: '新会议' }], pagination: { total: 1 } }
    })

    const { createMeeting } = useMeeting()
    const result = await createMeeting({ title: '新会议', start_time: '2026-06-05T10:00:00' })

    expect(axios.post).toHaveBeenCalledWith('/api/v1/meetings', { title: '新会议', start_time: '2026-06-05T10:00:00' })
    expect(result.title).toBe('新会议')
  })

  it('deleteMeeting 调用 DELETE', async () => {
    axios.delete.mockResolvedValue({})
    axios.get.mockResolvedValue({ data: { items: [], pagination: { total: 0 } } })

    const { deleteMeeting } = useMeeting()
    await deleteMeeting(1)

    expect(axios.delete).toHaveBeenCalledWith('/api/v1/meetings/1')
  })

  it('updateAgenda 调用 PATCH', async () => {
    axios.patch.mockResolvedValue({ data: { agenda: ['议题1', '议题2'] } })

    const { updateAgenda } = useMeeting()
    await updateAgenda(1, ['议题1', '议题2'])

    expect(axios.patch).toHaveBeenCalledWith('/api/v1/meetings/1/agenda', { agenda: ['议题1', '议题2'] })
  })

  it('状态变量正确初始化', () => {
    const { meetings, total, currentPage, pageSize, loading, keyword } = useMeeting()

    expect(meetings.value).toEqual([])
    expect(total.value).toBe(0)
    expect(currentPage.value).toBe(1)
    expect(pageSize.value).toBe(20)
    expect(loading.value).toBe(false)
    expect(keyword.value).toBe('')
  })
})
