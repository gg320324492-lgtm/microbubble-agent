import { ref, computed } from 'vue'
import axios from 'axios'
import { useMemberStore } from '@/stores/member'

export function useKnowledge() {
  const knowledgeItems = ref([])
  const loading = ref(false)
  const error = ref(null)
  const filters = ref({
    category: 'all',
    keyword: '',
    sort: 'newest'
  })
  const currentPage = ref(1)
  const pageSize = ref(20)
  const total = ref(0)

  const memberStore = useMemberStore()

  // 计算属性
  const filteredItems = computed(() => {
    let result = [...knowledgeItems.value]

    // 按分类筛选
    if (filters.value.category && filters.value.category !== 'all') {
      result = result.filter(item => item.category === filters.value.category)
    }

    // 按关键词搜索
    if (filters.value.keyword) {
      const keyword = filters.value.keyword.toLowerCase()
      result = result.filter(item =>
        item.title.toLowerCase().includes(keyword) ||
        item.content.toLowerCase().includes(keyword) ||
        (item.tags && item.tags.some(tag => tag.toLowerCase().includes(keyword)))
      )
    }

    // 排序
    if (filters.value.sort === 'newest') {
      result.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    } else if (filters.value.sort === 'oldest') {
      result.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
    } else if (filters.value.sort === 'most_viewed') {
      result.sort((a, b) => (b.view_count || 0) - (a.view_count || 0))
    }

    return result
  })

  const paginatedItems = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    return filteredItems.value.slice(start, end)
  })

  const totalPages = computed(() => {
    return Math.ceil(filteredItems.value.length / pageSize.value)
  })

  const categories = computed(() => {
    const cats = new Set()
    knowledgeItems.value.forEach(item => {
      if (item.category) {
        cats.add(item.category)
      }
    })
    return Array.from(cats)
  })

  const tags = computed(() => {
    const tagSet = new Set()
    knowledgeItems.value.forEach(item => {
      if (item.tags) {
        item.tags.forEach(tag => tagSet.add(tag))
      }
    })
    return Array.from(tagSet)
  })

  const stats = computed(() => ({
    total: knowledgeItems.value.length,
    categories: categories.value.length,
    tags: tags.value.length
  }))

  // 获取知识列表
  const fetchKnowledge = async (params = {}) => {
    loading.value = true
    error.value = null
    try {
      const response = await axios.get('/api/v1/knowledge', { params })
      knowledgeItems.value = response.data.items || response.data
      total.value = response.data.total || knowledgeItems.value.length
    } catch (err) {
      error.value = err.response?.data?.detail || '获取知识列表失败'
      console.error('获取知识列表失败:', err)
    } finally {
      loading.value = false
    }
  }

  // 获取单个知识
  const fetchKnowledgeItem = async (itemId) => {
    try {
      const response = await axios.get(`/api/v1/knowledge/${itemId}`)
      const index = knowledgeItems.value.findIndex(item => item.id === itemId)
      if (index !== -1) {
        knowledgeItems.value[index] = response.data
      } else {
        knowledgeItems.value.push(response.data)
      }
      return response.data
    } catch (err) {
      console.error('获取知识详情失败:', err)
      return null
    }
  }

  // 创建知识
  const createKnowledge = async (knowledgeData) => {
    try {
      const response = await axios.post('/api/v1/knowledge', knowledgeData)
      knowledgeItems.value.unshift(response.data)
      return { success: true, data: response.data }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '创建知识失败'
      }
    }
  }

  // 更新知识
  const updateKnowledge = async (itemId, knowledgeData) => {
    try {
      const response = await axios.put(`/api/v1/knowledge/${itemId}`, knowledgeData)
      const index = knowledgeItems.value.findIndex(item => item.id === itemId)
      if (index !== -1) {
        knowledgeItems.value[index] = response.data
      }
      return { success: true, data: response.data }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '更新知识失败'
      }
    }
  }

  // 删除知识
  const deleteKnowledge = async (itemId) => {
    try {
      await axios.delete(`/api/v1/knowledge/${itemId}`)
      knowledgeItems.value = knowledgeItems.value.filter(item => item.id !== itemId)
      return { success: true }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '删除知识失败'
      }
    }
  }

  // 搜索知识
  const searchKnowledge = async (query) => {
    loading.value = true
    error.value = null
    try {
      const response = await axios.get('/api/v1/knowledge/search', {
        params: { q: query }
      })
      knowledgeItems.value = response.data
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || '搜索失败'
      console.error('搜索知识失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }

  // 语义搜索
  const semanticSearch = async (query) => {
    loading.value = true
    error.value = null
    try {
      const response = await axios.post('/api/v1/knowledge/semantic-search', {
        query
      })
      knowledgeItems.value = response.data
      return response.data
    } catch (err) {
      error.value = err.response?.data?.detail || '语义搜索失败'
      console.error('语义搜索失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }

  // 设置筛选条件
  const setFilters = (newFilters) => {
    filters.value = { ...filters.value, ...newFilters }
    currentPage.value = 1
  }

  // 重置筛选条件
  const resetFilters = () => {
    filters.value = {
      category: 'all',
      keyword: '',
      sort: 'newest'
    }
    currentPage.value = 1
  }

  // 设置分页
  const setPage = (page) => {
    currentPage.value = page
  }

  const setPageSize = (size) => {
    pageSize.value = size
    currentPage.value = 1
  }

  // 获取创建者姓名
  const getCreatorName = (creatorId) => {
    return memberStore.getMemberName(creatorId)
  }

  // 获取创建者头像
  const getCreatorAvatar = (creatorId) => {
    return memberStore.getMemberAvatar(creatorId)
  }

  // 获取创建者首字母
  const getCreatorInitial = (creatorId) => {
    return memberStore.getMemberInitial(creatorId)
  }

  return {
    knowledgeItems,
    loading,
    error,
    filters,
    currentPage,
    pageSize,
    total,
    filteredItems,
    paginatedItems,
    totalPages,
    categories,
    tags,
    stats,
    fetchKnowledge,
    fetchKnowledgeItem,
    createKnowledge,
    updateKnowledge,
    deleteKnowledge,
    searchKnowledge,
    semanticSearch,
    setFilters,
    resetFilters,
    setPage,
    setPageSize,
    getCreatorName,
    getCreatorAvatar,
    getCreatorInitial
  }
}
