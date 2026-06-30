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
  const filterSourceType = ref('')  // #043: 自动拓展走 source_type 过滤, 与 category 互斥

  // 统计
  const statsData = ref({ total: 0, categories: {}, source_types: {} })
  const categories = ref([])
  const hotTags = ref([])

  // 2026-06-30 错误状态: 用于前端区分"加载失败"和"真无数据"两种空态
  const loadError = ref(null)

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
      // #043: 自动拓展走 source_type 过滤, 与 category 互斥 (同一时间只挂一个)
      if (filterSourceType.value) {
        queryParams.source_type = filterSourceType.value
        // 不传 category / has_file
      } else if (filterCategory.value === '论文') {
        // v28 step 73: "论文" chip 映射到 has_file=true（只显示真实上传文件）
        //   其他 category 值原样传给 API
        queryParams.has_file = true
        // 不传 category，避免和 has_file 叠加（LLM 自动归档的 [拓展] 也可能被标 category=论文）
      } else if (filterCategory.value) {
        queryParams.category = filterCategory.value
      }

      const res = await axios.get('/api/v1/knowledge', { params: queryParams })
      knowledgeList.value = res.data.items || []
      total.value = res.data.pagination?.total || res.data.total || 0
      loadError.value = null
    } catch (e) {
      // 2026-06-30 修复: 显式暴露错误, 让 UI 区分"接口失败"和"真没数据"
      // 旧版只在 finally 重置 loading, 失败时 knowledgeList=[] / total=0 与"真没数据"无差别
      console.error('[useKnowledge] fetchKnowledge failed:', e)
      loadError.value = e.response?.data?.detail || e.message || '加载知识列表失败'
      knowledgeList.value = []
      total.value = 0
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
      // 兜底空结构, 避免 health-summary tag 模板拿 undefined
      statsData.value = { total: 0, categories: {}, source_types: {} }
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
      const res = await axios.get('/api/v1/knowledge/entities/graph')
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
      const res = await axios.get('/api/v1/knowledge/formulas/categories')
      formulaCategories.value = res.data.categories || []
    } catch (e) {
      console.error('获取公式分类失败:', e)
    }
  }

  return {
    // 状态
    knowledgeList, total, currentPage, pageSize, loading,
    searchQuery, filterCategory, filterSourceType,  // #043
    statsData, categories, hotTags, loadError,  // 2026-06-30: loadError 区分失败 vs 空
    entityList, entityTotal, entityPage, entityGraphData,
    hypothesisList, hypothesisTotal, hypothesisPage,
    formulaList, formulaTotal, formulaPage, formulaCategories,
    // 方法
    fetchKnowledge, fetchCategories, fetchStats, deleteKnowledge,
    searchEntities, fetchEntityGraph, fetchHypotheses,
    fetchFormulas, fetchFormulaCategories
  }
}
