<template>
  <div class="knowledge-view">
    <!-- 铁律 31: 全项目 tab 必须用 <TabStrip> 替代 <el-tabs> -->
    <div class="tab-strip-wrapper">
      <TabStrip v-model="activeTab" :items="tabItems" aria-label="知识库视图切换" />
    </div>

    <!-- ===== 知识库 tab ===== -->
    <div v-show="activeTab === 'knowledge'" role="tabpanel"
      :aria-labelledby="`tab-strip-knowledge`" class="tab-panel">
      <!-- 工具栏 -->
      <KnowledgeToolbar
        :categories="categories"
        @search="handleSearch"
        @create="showCreateDialog = true"
        @upload="showUploadDialog = true"
        @qa="openQADialog"
        @entities="activeTab = 'entities'"
        @filter="handleFilter"
        @go-drive="$router.push('/drive')"
      />

      <!-- Dashboard -->
      <KnowledgeDashboard
        :categories="categories"
        :recent-items="knowledgeList"
        :active-category="filterCategory"
        :active-source-type="filterSourceType"
        :source-type-stats="statsData.source_types || {}"
        :loading="loading"
        :load-error="loadError"
        @filter-category="handleCategoryFilter"
        @filter-source-type="handleSourceTypeFilter"
        @filter-time="handleTimeFilter"
        @show-entities="activeTab = 'entities'"
        @show-hypotheses="activeTab = 'hypotheses'"
        @show-all-categories="showAllCategories = true"
        @view-detail="handleViewDetail"
        @edit="editKnowledge"
        @delete="handleDeleteKnowledge"
        @download="downloadFile"
        @retry="fetchKnowledge"
        @navigate="handleDashboardNavigate"
      />

      <!-- 健康度摘要 -->
      <div class="health-summary" v-if="!loading">
        <el-tag type="info" size="small" effect="plain">📚 知识 {{ total }}</el-tag>
        <el-tag type="success" size="small" effect="plain">🔗 实体 {{ entityTotal }}</el-tag>
        <el-tag type="warning" size="small" effect="plain">🧪 假设 {{ hypothesisTotal }}</el-tag>
        <el-tag type="primary" size="small" effect="plain">📐 公式 {{ formulaTotal }}</el-tag>
        <el-tag type="info" size="small" effect="plain">📁 分类 {{ categories.length }}</el-tag>
        <!-- v2 PR3: 跳转 chip 到网盘 -->
        <el-tag
          class="health-summary-drive-chip"
          type="danger"
          size="small"
          effect="plain"
          @click="$router.push('/drive')"
          style="cursor: pointer;"
        >
          📁 网盘 →
        </el-tag>
      </div>

      <div v-if="total > pageSize" class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchKnowledge"
        />
      </div>
    </div>

    <!-- ===== 实体图谱 Tab (v77 P2.6-E.3 拆分到 KnowledgeEntityTab.vue) ===== -->
    <div v-show="activeTab === 'entities'" role="tabpanel"
      :aria-labelledby="`tab-strip-entities`" class="tab-panel">
      <KnowledgeEntityTab
        ref="entityTabRef"
        :entity-list="entityList"
        :entity-total="entityTotal"
        :entity-page="entityPage"
        :entity-graph-data="entityGraphData"
        @refresh="handleEntityRefresh"
        @show-entity-detail="showEntityDetail"
      />
    </div>

    <!-- ===== 假设 Tab (v77 P2.6-E.3 拆分到 KnowledgeHypothesisTab.vue) ===== -->
    <div v-show="activeTab === 'hypotheses'" role="tabpanel"
      :aria-labelledby="`tab-strip-hypotheses`" class="tab-panel">
      <KnowledgeHypothesisTab
        ref="hypothesisTabRef"
        :hypothesis-list="hypothesisList"
        :hypothesis-total="hypothesisTotal"
        :hypothesis-page="hypothesisPage"
        @refresh="handleHypothesisRefresh"
      />
    </div>

    <!-- ===== 公式计算 Tab (v77 P2.6-E.3 拆分到 KnowledgeFormulaTab.vue) ===== -->
    <div v-show="activeTab === 'formulas'" role="tabpanel"
      :aria-labelledby="`tab-strip-formulas`" class="tab-panel">
      <KnowledgeFormulaTab
        ref="formulaTabRef"
        :formula-list="formulaList"
        :formula-total="formulaTotal"
        :formula-page="formulaPage"
        :formula-categories="formulaCategories"
        @refresh="handleFormulaRefresh"
      />
    </div>

    <!-- ===== 我的长期记忆 Tab (v77 P2.6-E.3 拆分到 KnowledgeMemoryTab.vue) ===== -->
    <div v-show="activeTab === 'memory'" role="tabpanel"
      :aria-labelledby="`tab-strip-memory`" class="tab-panel">
      <KnowledgeMemoryTab ref="memoryTabRef" />
    </div>

    <!-- 添加/编辑知识对话框 (v77 P2.6-E.3 拆分到 KnowledgeCreateDialog.vue) -->
    <KnowledgeCreateDialog
      v-model="showCreateDialog"
      :editing-item="editingKnowledge"
      :categories="categories"
      :hot-tags="hotTags"
      :is-mobile="isMobile"
      @saved="onCreateSaved"
    />

    <!-- AI 问答对话框 -->
    <KnowledgeQADialog
      v-model:visible="showQADialog"
      :is-mobile="isMobile"
      @navigate="router.push('/knowledge/' + $event)"
    />

    <!-- 文件上传对话框 -->
    <KnowledgeUploadDialog
      v-model:visible="showUploadDialog"
      :is-mobile="isMobile"
      @success="onUploadSuccess"
    />

    <!-- Entity detail dialog -->
    <el-dialog v-model="showEntityDetailDialog" title="实体详情" width="600px">
      <div v-if="entityDetail">
        <div class="entity-triple-large">
          <span class="entity-subject">{{ entityDetail.subject }}</span>
          <span class="entity-predicate">→ {{ entityDetail.predicate }} →</span>
          <span class="entity-object">{{ entityDetail.object }}</span>
        </div>
        <div v-if="entityDetail.condition" class="entity-condition-text">条件: {{ entityDetail.condition }}</div>
        <el-divider />
        <div class="entity-detail-section">
          <h4>来源文档 ({{ entityDetail.sources?.length || 0 }})</h4>
          <div v-for="src in entityDetail.sources" :key="src.id" class="source-item clickable" @click="router.push('/knowledge/' +src.id); showEntityDetailDialog = false">
            {{ src.title }}
            <el-tag size="small">{{ src.category }}</el-tag>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * KnowledgeView.vue — 知识库主入口（v77 P2.6-E.3 简化版）
 *
 * v77 P2.6-E.3: 1599 行 → ~300 行（拆分 4 tabs + 1 dialog 到 components/knowledge/）
 * 5 个 tab 子组件:
 *   - KnowledgeToolbar (已存在)
 *   - KnowledgeDashboard (已存在)
 *   - KnowledgeEntityTab (v77 P2.6-E.3 新增)
 *   - KnowledgeHypothesisTab (v77 P2.6-E.3 新增)
 *   - KnowledgeFormulaTab (v77 P2.6-E.3 新增)
 *   - KnowledgeMemoryTab (v77 P2.6-E.3 新增)
 * 1 个 dialog 抽出:
 *   - KnowledgeCreateDialog (v77 P2.6-E.3 新增)
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { Document, Share, MagicStick, Histogram, Memo } from '@element-plus/icons-vue'
import { useKnowledge } from '@/composables/useKnowledge'
import { useSearchAnalyticsStore } from '@/stores/useSearchAnalytics'
import TabStrip from '@/components/common/TabStrip.vue'
import KnowledgeToolbar from '@/components/knowledge/KnowledgeToolbar.vue'
import KnowledgeDashboard from '@/components/knowledge/KnowledgeDashboard.vue'
import KnowledgeEntityTab from '@/components/knowledge/KnowledgeEntityTab.vue'
import KnowledgeHypothesisTab from '@/components/knowledge/KnowledgeHypothesisTab.vue'
import KnowledgeFormulaTab from '@/components/knowledge/KnowledgeFormulaTab.vue'
import KnowledgeMemoryTab from '@/components/knowledge/KnowledgeMemoryTab.vue'
import KnowledgeCreateDialog from '@/components/knowledge/KnowledgeCreateDialog.vue'
import KnowledgeQADialog from './knowledge/KnowledgeQADialog.vue'
import KnowledgeUploadDialog from './knowledge/KnowledgeUploadDialog.vue'

const {
  knowledgeList, total, currentPage, pageSize, loading,
  searchQuery, filterCategory, filterSourceType,  // #043
  statsData, categories, hotTags, loadError,  // 2026-06-30
  entityList, entityTotal, entityPage, entityGraphData,
  hypothesisList, hypothesisTotal, hypothesisPage,
  formulaList, formulaTotal, formulaPage, formulaCategories,
  fetchKnowledge, fetchCategories, fetchStats, deleteKnowledge: deleteKnowledgeApi,
  searchEntities, fetchEntityGraph, fetchHypotheses,
  fetchFormulas, fetchFormulaCategories
} = useKnowledge()

const isMobile = ref(window.innerWidth <= 768)
const showCreateDialog = ref(false)
const showQADialog = ref(false)
const showUploadDialog = ref(false)
const editingKnowledge = ref(null)
const showAllCategories = ref(false)

const activeTab = ref('knowledge')
const route = useRoute()
const router = useRouter()

// 铁律 29: URL ?tab= 同步双向（VALID_TABS 白名单 + watch + replace）
const VALID_TABS = ['knowledge', 'entities', 'hypotheses', 'formulas', 'memory']
if (route.query.tab && VALID_TABS.includes(String(route.query.tab))) {
  activeTab.value = String(route.query.tab)
}

// TabStrip 配置（铁律 30: EP 图标 named import + 通过 props 传入）
const tabItems = [
  { key: 'knowledge',  label: '知识库',       icon: Document },
  { key: 'entities',   label: '实体图谱',     icon: Share },
  { key: 'hypotheses', label: '科研假设',     icon: MagicStick },
  { key: 'formulas',   label: '公式计算',     icon: Histogram },
  { key: 'memory',     label: '我的长期记忆', icon: Memo },
]

const searchAnalytics = useSearchAnalyticsStore()

// Entity tab 状态
const showEntityDetailDialog = ref(false)
const entityDetail = ref(null)

// 子组件 refs（v77 P2.6-E.3: 用于 watch activeTab 时主动 fetch）
const entityTabRef = ref(null)
const hypothesisTabRef = ref(null)
const formulaTabRef = ref(null)
const memoryTabRef = ref(null)

// ── 搜索和筛选 ──
const handleSearch = async (query) => {
  searchQuery.value = query
  currentPage.value = 1
  await fetchKnowledge()
  const topIds = knowledgeList.value.map(k => k.id)
  if (topIds.length > 0) {
    searchAnalytics.startSearch(query, topIds, 'knowledge_search')
  }
}

const handleViewDetail = (id) => {
  const position = knowledgeList.value.findIndex(k => k.id === id) + 1
  if (position > 0) {
    searchAnalytics.recordClick(id, position)
  }
  router.push('/knowledge/' + id)
}

// v2 PR3: KB Dashboard 跳转 chip (📁 网盘 → /drive) — 走 router.push
const handleDashboardNavigate = (route) => {
  router.push(route)
}

const handleFilter = (filters) => {
  // #043: filter-source-type 与 filter-category 互斥
  if (filters.sourceType) {
    filterSourceType.value = filters.sourceType
    filterCategory.value = ''
  } else if (filters.category) {
    filterCategory.value = filters.category
    filterSourceType.value = ''
  } else {
    filterCategory.value = ''
    filterSourceType.value = ''
  }
  currentPage.value = 1
  fetchKnowledge()
}

const handleCategoryFilter = (category) => {
  filterCategory.value = category
  filterSourceType.value = ''  // #043: 互斥
  currentPage.value = 1
  fetchKnowledge()
}

const handleSourceTypeFilter = (sourceType) => {
  // #043: 自动拓展 chip 点击
  filterSourceType.value = sourceType
  filterCategory.value = ''  // 互斥
  currentPage.value = 1
  fetchKnowledge()
}

const handleTimeFilter = (range) => {
  console.log('Time filter:', range)
}

// ── 增删改 ──
const editKnowledge = (item) => {
  editingKnowledge.value = item
  showCreateDialog.value = true
}

const downloadFile = async (item) => {
  try {
    const response = await axios.get(`/api/v1/knowledge/${item.id}/download`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', item.file_name || 'download')
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载失败')
  }
}

const handleDeleteKnowledge = async (item) => {
  try {
    await ElMessageBox.confirm('确定要删除这条知识吗？', '确认删除', { type: 'warning' })
    await deleteKnowledgeApi(item.id)
    ElMessage.success('知识删除成功')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const onUploadSuccess = () => {
  fetchKnowledge()
  fetchStats()
}

const onCreateSaved = () => {
  fetchKnowledge()
  fetchStats()
  fetchCategories()
}

const openQADialog = () => {
  showQADialog.value = true
}

// ── 子组件事件回调 ──
const handleEntityRefresh = (payload) => {
  if (payload.list !== undefined) {
    entityList.value = payload.list
    entityTotal.value = payload.total
  }
  if (payload.graph !== undefined) {
    entityGraphData.value = payload.graph
  }
}

const handleHypothesisRefresh = (payload) => {
  if (payload.list !== undefined) {
    hypothesisList.value = payload.list
    hypothesisTotal.value = payload.total
  }
}

const handleFormulaRefresh = (payload) => {
  if (payload.list !== undefined) {
    formulaList.value = payload.list
    formulaTotal.value = payload.total
  }
}

const showEntityDetail = async (id) => {
  try {
    const res = await axios.get(`/api/v1/knowledge/entities/${id}`)
    entityDetail.value = res.data
    showEntityDetailDialog.value = true
  } catch (e) { ElMessage.error('获取实体详情失败') }
}

// ── 监听 ──
// #043: filterCategory + filterSourceType 互斥, 任一变化都触发重新查询
// 2026-06-30: 加 deep + immediate 防止 ref 值相同但对象内存地址不同导致漏触发
watch([filterCategory, filterSourceType], () => {
  currentPage.value = 1
  fetchKnowledge()
}, { deep: true })

watch(searchQuery, (val) => {
  if (!val) {
    currentPage.value = 1
    fetchKnowledge()
  }
})

watch(activeTab, (tab) => {
  if (tab === 'entities') {
    if (entityTabRef.value) {
      entityTabRef.value.searchEntitiesLocal()
      entityTabRef.value.fetchEntityGraphLocal()
    }
  }
  if (tab === 'hypotheses') {
    hypothesisTabRef.value?.fetchHypotheses()
  }
  if (tab === 'formulas') {
    formulaTabRef.value?.fetchFormulas()
    fetchFormulaCategories()
  }
  if (tab === 'memory') {
    memoryTabRef.value?.fetchMemories()
  }
  // 铁律 29: tab → URL 同步（router.replace 不污染 history, 合并其他 query）
  router.replace({ query: { ...route.query, tab } })
})

// 铁律 29: URL → tab 反向同步（浏览器前进/后退）
watch(() => route.query.tab, (t) => {
  if (t && VALID_TABS.includes(String(t)) && String(t) !== activeTab.value) {
    activeTab.value = String(t)
  }
})

const handleResize = () => {
  isMobile.value = window.innerWidth <= 768
}

onMounted(() => {
  // 2026-06-30 修复: SPA 状态污染防御
  // useKnowledge 是 composable 不是 store, ref 跨 mount 持久存活。
  // 用户上次点过"✨ 自动拓展"chip → filterSourceType 永远停在 'auto_expansion'
  // → fetchKnowledge 拼 ?source_type=auto_expansion → 0 条 → "暂无知识" + 5 个全 0
  // 每次进入 /knowledge 都从干净状态开始, 与"chip 是临时过滤器"的产品语义一致
  filterSourceType.value = ''
  filterCategory.value = ''
  searchQuery.value = ''
  currentPage.value = 1

  fetchKnowledge()
  fetchStats()
  fetchCategories()
  // 2026-06-30 修复 D: 健康度摘要的 entity/hyp/formula total 同步
  // 旧版这三个 ref 永远停在 0 初值, 必须在 onMounted 主动 fetch (page_size=1 只拿 total)
  searchEntities({ page: 1, page_size: 1 })
  fetchHypotheses({ page: 1, page_size: 1 })
  fetchFormulas({ page: 1, page_size: 1 })

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.knowledge-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

/* TabStrip 容器（铁律 31: 替代 el-tabs border-card） */
.tab-strip-wrapper {
  display: flex;
  align-items: center;
}

/* TabPanel 容器（v-show 不重挂载子组件, 保留 ECharts/force-graph 状态） */
.tab-panel {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--space-4);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.health-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px;
  margin-bottom: var(--space-3);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.entity-triple-large {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--font-size-lg);
  margin-bottom: var(--space-4);
}

.entity-subject {
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}

.entity-predicate {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  padding: 2px 8px;
  background: var(--color-info-bg);
  border-radius: var(--radius-full);
}

.entity-object {
  color: var(--color-accent);
}

.entity-condition-text {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.entity-detail-section h4 {
  margin: 0 0 var(--space-3) 0;
  color: var(--color-text-primary);
}

.source-item {
  padding: var(--space-2) var(--space-3);
  background: var(--color-info-bg);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-2);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.source-item:hover {
  background: var(--color-primary-bg);
}

.clickable {
  cursor: pointer;
}

.pagination {
  margin-top: var(--space-5);
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .tab-panel {
    padding: var(--space-3);
  }
}
</style>

<style>
/* v69 P1b: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
/* 铁律 26: dark mode 覆盖必须非 scoped, scoped 块 data-v-xxx 干扰后代选择器 */
[data-theme="dark"] .tab-panel {
  background: var(--color-bg-card);
}
[data-theme="dark"] .health-summary {
  background: var(--color-bg-card);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .health-summary-drive-chip {
  background: var(--color-danger-bg, rgba(245, 108, 108, 0.12));
  color: var(--color-danger);
}
</style>

<!-- v2 PR3: 📁 网盘 chip hover 高亮 (scoped, 仅 light 主题需要) -->
<style scoped>
.health-summary-drive-chip:hover {
  opacity: 0.85;
  transform: translateY(-1px);
  transition: transform 0.15s var(--ease-out, ease);
}
</style>