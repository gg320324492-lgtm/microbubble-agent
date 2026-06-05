import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useTask } from '../useTask'

// Mock axios
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

import axios from 'axios'

describe('useTask', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchTasks 成功后更新列表和分页', async () => {
    const mockData = {
      items: [{ id: 1, title: '测试任务', status: 'in_progress' }],
      pagination: { page: 1, page_size: 100, total: 1, total_pages: 1 }
    }
    axios.get.mockResolvedValue({ data: mockData })

    const { tasks, fetchTasks, loading, total } = useTask()
    await fetchTasks()

    expect(tasks.value).toEqual(mockData.items)
    expect(total.value).toBe(1)
    expect(loading.value).toBe(false)
  })

  it('fetchTasks 失败后 loading 重置', async () => {
    axios.get.mockRejectedValue(new Error('Network error'))

    const { fetchTasks, loading } = useTask()
    try {
      await fetchTasks()
    } catch {}

    expect(loading.value).toBe(false)
  })

  it('createTask 调用 POST 并刷新列表', async () => {
    axios.post.mockResolvedValue({ data: { id: 2, title: '新任务' } })
    axios.get.mockResolvedValue({
      data: { items: [{ id: 2, title: '新任务' }], pagination: { total: 1 } }
    })

    const { createTask } = useTask()
    const result = await createTask({ title: '新任务' })

    expect(axios.post).toHaveBeenCalledWith('/api/v1/tasks', { title: '新任务' })
    expect(result.title).toBe('新任务')
  })

  it('deleteTask 调用 DELETE', async () => {
    axios.delete.mockResolvedValue({})
    axios.get.mockResolvedValue({ data: { items: [], pagination: { total: 0 } } })

    const { deleteTask } = useTask()
    await deleteTask(1)

    expect(axios.delete).toHaveBeenCalledWith('/api/v1/tasks/1')
  })

  it('restoreTask 调用 POST /restore', async () => {
    axios.post.mockResolvedValue({})
    axios.get.mockResolvedValue({ data: { items: [], pagination: { total: 0 } } })

    const { restoreTask } = useTask()
    await restoreTask(1)

    expect(axios.post).toHaveBeenCalledWith('/api/v1/tasks/1/restore')
  })

  it('activeTasks 和 doneTasks 正确过滤', () => {
    const { tasks, activeTasks, doneTasks } = useTask()
    tasks.value = [
      { id: 1, status: 'in_progress' },
      { id: 2, status: 'done' },
      { id: 3, status: 'in_progress' }
    ]

    expect(activeTasks.value).toHaveLength(2)
    expect(doneTasks.value).toHaveLength(1)
    expect(doneTasks.value[0].id).toBe(2)
  })

  it('filters 正确初始化', () => {
    const { filters } = useTask()

    expect(filters.value.status).toBe('')
    expect(filters.value.assignee_id).toBe('')
    expect(filters.value.project_id).toBe('')
    expect(filters.value.search).toBe('')
  })
})
