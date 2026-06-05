import { ref, computed } from 'vue'
import axios from 'axios'

export function useKnowledge() {
  // 状态
  const knowledgeList = ref([])
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const searchQuery = ref('')
  const filterCategory = ref('')

  // 统计
  const statsData = ref({ total: 0, categories: {} })
  const categories = ref([])
  const hotTags = ref([])

  // 实体图谱
  const entityList = ref([])
  const entityTotal = ref(0)
  const entityPage = ref(1)
  const entityGraphData = ref({ nodes: [], edges: [] })

  // 假设
  const hypothesisList = ref([])
  const hypothesisTotal = ref(0)
  const hypothesisPage = ref(1)

  // 公式
  const formulaList = ref([])
  const formulaTotal = ref(0)
  const formulaPage = ref(1)
  const formulaCategories = ref([])

  // API 调用
  const fetchKnowledge = async (params = {}) => {
    loading.value = true
    try {
      const queryParams = {
        page: currentPage.value,
        page_size: pageSize.value,
        ...params
      }
      if (searchQuery.value) queryParams.search = searchQuery.value
      if (filterCategory.value) queryParams.category = filterCategory.value

      const res = await axios.get('/api/v1/knowledge', { params: queryParams })
      knowledgeList.value = res.data.items || []
      total.value = res.data.pagination?.total || res.data.total || 0
    } finally {
      loading.value = false
    }
  }

  const fetchCategories = async () => {
    try {
      const res = await axios.get('/api/v1/knowledge/categories')
      categories.value = res.data.categories || []
    } catch (e) {
      console.error('获取分类失败:', e)
    }
  }

  const fetchStats = async () => {
    try {
      const res = await axios.get('/api/v1/knowledge/stats')
      statsData.value = res.data
    } catch (e) {
      console.error('获取统计失败:', e)
    }
  }

  const deleteKnowledge = async (id) => {
    await axios.delete(`/api/v1/knowledge/${id}`)
    await fetchKnowledge()
    await fetchStats()
  }

  const searchEntities = async (params = {}) => {
    loading.value = true
    try {
      const res = await axios.get('/api/v1/knowledge/entities', { params })
      entityList.value = res.data.items || []
      entityTotal.value = res.data.total || 0
    } finally {
      loading.value = false
    }
  }

  const fetchEntityGraph = async () => {
    try {
      const res = await axios.get('/api/v1/knowledge/entity-graph')
      entityGraphData.value = res.data
    } catch (e) {
      console.error('获取实体图谱失败:', e)
    }
  }

  const fetchHypotheses = async (params = {}) => {
    loading.value = true
    try {
      const res = await axios.get('/api/v1/knowledge/hypotheses', { params })
      hypothesisList.value = res.data.items || []
      hypothesisTotal.value = res.data.total || 0
    } finally {
      loading.value = false
    }
  }

  const fetchFormulas = async (params = {}) => {
    loading.value = true
    try {
      const res = await axios.get('/api/v1/knowledge/formulas', { params })
      formulaList.value = res.data.items || []
      formulaTotal.value = res.data.total || 0
    } finally {
      loading.value = false
    }
  }

  const fetchFormulaCategories = async () => {
    try {
      const res = await axios.get('/api/v1/knowledge/formula-categories')
      formulaCategories.value = res.data.categories || []
    } catch (e) {
      console.error('获取公式分类失败:', e)
    }
  }

  return {
    // 状态
    knowledgeList, total, currentPage, pageSize, loading,
    searchQuery, filterCategory,
    statsData, categories, hotTags,
    entityList, entityTotal, entityPage, entityGraphData,
    hypothesisList, hypothesisTotal, hypothesisPage,
    formulaList, formulaTotal, formulaPage, formulaCategories,
    // 方法
    fetchKnowledge, fetchCategories, fetchStats, deleteKnowledge,
    searchEntities, fetchEntityGraph, fetchHypotheses,
    fetchFormulas, fetchFormulaCategories
  }
}
