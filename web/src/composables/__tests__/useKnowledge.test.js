import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useKnowledge } from '../useKnowledge'

// Mock axios
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
  }
}))

import axios from 'axios'

describe('useKnowledge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchKnowledge 成功更新列表', async () => {
    const mockData = {
      items: [{ id: 1, title: '微纳米气泡', category: '基础概念' }],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 }
    }
    axios.get.mockResolvedValue({ data: mockData })

    const { knowledgeList, fetchKnowledge, loading, total } = useKnowledge()
    await fetchKnowledge()

    expect(knowledgeList.value).toEqual(mockData.items)
    expect(total.value).toBe(1)
    expect(loading.value).toBe(false)
  })

  it('fetchKnowledge 失败后 loading 重置', async () => {
    axios.get.mockRejectedValue(new Error('Network error'))

    const { fetchKnowledge, loading } = useKnowledge()
    try {
      await fetchKnowledge()
    } catch {}

    expect(loading.value).toBe(false)
  })

  it('fetchCategories 获取分类', async () => {
    const mockCategories = [
      { name: '基础概念', count: 10 },
      { name: '实验方法', count: 5 }
    ]
    axios.get.mockResolvedValue({ data: { categories: mockCategories } })

    const { categories, fetchCategories } = useKnowledge()
    await fetchCategories()

    expect(categories.value).toEqual(mockCategories)
  })

  it('fetchStats 获取统计', async () => {
    const mockStats = { total: 15, categories: { '基础概念': 10, '实验方法': 5 } }
    axios.get.mockResolvedValue({ data: mockStats })

    const { statsData, fetchStats } = useKnowledge()
    await fetchStats()

    expect(statsData.value).toEqual(mockStats)
  })

  it('deleteKnowledge 调用 DELETE 并刷新', async () => {
    axios.delete.mockResolvedValue({})
    axios.get.mockResolvedValue({ data: { items: [], pagination: { total: 0 } } })

    const { deleteKnowledge } = useKnowledge()
    await deleteKnowledge(1)

    expect(axios.delete).toHaveBeenCalledWith('/api/v1/knowledge/1')
  })

  it('searchEntities 获取实体列表', async () => {
    const mockEntities = {
      items: [{ id: 1, name: 'Zeta电位', type: '概念' }],
      total: 1
    }
    axios.get.mockResolvedValue({ data: mockEntities })

    const { entityList, entityTotal, searchEntities } = useKnowledge()
    await searchEntities()

    expect(entityList.value).toEqual(mockEntities.items)
    expect(entityTotal.value).toBe(1)
  })

  it('fetchHypotheses 获取假设列表', async () => {
    const mockHypotheses = {
      items: [{ id: 1, title: '假设1', status: 'proposed' }],
      total: 1
    }
    axios.get.mockResolvedValue({ data: mockHypotheses })

    const { hypothesisList, hypothesisTotal, fetchHypotheses } = useKnowledge()
    await fetchHypotheses()

    expect(hypothesisList.value).toEqual(mockHypotheses.items)
    expect(hypothesisTotal.value).toBe(1)
  })

  it('fetchFormulas 获取公式列表', async () => {
    const mockFormulas = {
      items: [{ id: 1, name: 'Young-Laplace方程', category: '气泡力学' }],
      total: 1
    }
    axios.get.mockResolvedValue({ data: mockFormulas })

    const { formulaList, formulaTotal, fetchFormulas } = useKnowledge()
    await fetchFormulas()

    expect(formulaList.value).toEqual(mockFormulas.items)
    expect(formulaTotal.value).toBe(1)
  })

  it('状态变量正确初始化', () => {
    const { knowledgeList, total, currentPage, pageSize, loading, searchQuery, filterCategory } = useKnowledge()

    expect(knowledgeList.value).toEqual([])
    expect(total.value).toBe(0)
    expect(currentPage.value).toBe(1)
    expect(pageSize.value).toBe(20)
    expect(loading.value).toBe(false)
    expect(searchQuery.value).toBe('')
    expect(filterCategory.value).toBe('')
  })
})
