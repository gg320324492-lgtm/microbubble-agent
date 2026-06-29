<template>
  <div class="knowledge-view">
    <el-tabs v-model="activeTab" type="border-card" class="knowledge-tabs">
      <el-tab-pane label="知识库" name="knowledge" lazy>
        <!-- 工具栏 -->
        <KnowledgeToolbar
          :categories="categories"
          @search="handleSearch"
          @create="showCreateDialog = true"
          @upload="showUploadDialog = true"
          @qa="openQADialog"
          @entities="activeTab = 'entities'"
          @filter="handleFilter"
        />

        <!-- Dashboard -->
        <KnowledgeDashboard
          :categories="categories"
          :recent-items="knowledgeList"
          :active-category="filterCategory"
          :active-source-type="filterSourceType"
          :source-type-stats="statsData.source_types || {}"
          :loading="loading"
          @filter-category="handleCategoryFilter"
          @filter-source-type="handleSourceTypeFilter"
          @filter-time="handleTimeFilter"
          @show-entities="activeTab = 'entities'"
          @show-hypotheses="activeTab = 'hypotheses'"
          @show-all-categories="showAllCategories = true"
          @show-all="showAllKnowledge = true"
          @view-detail="handleViewDetail"
          @edit="editKnowledge"
          @delete="handleDeleteKnowledge"
          @download="downloadFile"
        />

        <!-- 健康度摘要 -->
        <div class="health-summary" v-if="!loading">
          <el-tag type="info" size="small" effect="plain">📚 知识 {{ total }}</el-tag>
          <el-tag type="success" size="small" effect="plain">🔗 实体 {{ entityTotal }}</el-tag>
          <el-tag type="warning" size="small" effect="plain">🧪 假设 {{ hypothesisTotal }}</el-tag>
          <el-tag type="primary" size="small" effect="plain">📐 公式 {{ formulaTotal }}</el-tag>
          <el-tag type="info" size="small" effect="plain">📁 分类 {{ categories.length }}</el-tag>
        </div>

        <div v-if="showAllKnowledge && total > pageSize" class="pagination">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            @current-change="fetchKnowledge"
          />
        </div>
      </el-tab-pane>

      <!-- ===== 实体图谱 Tab (v77 P2.6-E.3 拆分到 KnowledgeEntityTab.vue) ===== -->
      <el-tab-pane label="实体图谱" name="entities" lazy>
        <KnowledgeEntityTab
          ref="entityTabRef"
          :entity-list="entityList"
          :entity-total="entityTotal"
          :entity-page="entityPage"
          :entity-graph-data="entityGraphData"
          @refresh="handleEntityRefresh"
          @show-entity-detail="showEntityDetail"
        />
      </el-tab-pane>

      <!-- ===== 假设 Tab (v77 P2.6-E.3 拆分到 KnowledgeHypothesisTab.vue) ===== -->
      <el-tab-pane label="科研假设" name="hypotheses" lazy>
        <KnowledgeHypothesisTab
          ref="hypothesisTabRef"
          :hypothesis-list="hypothesisList"
          :hypothesis-total="hypothesisTotal"
          :hypothesis-page="hypothesisPage"
          @refresh="handleHypothesisRefresh"
        />
      </el-tab-pane>

      <!-- ===== 公式计算 Tab (v77 P2.6-E.3 拆分到 KnowledgeFormulaTab.vue) ===== -->
      <el-tab-pane label="公式计算" name="formulas" lazy>
        <KnowledgeFormulaTab
          ref="formulaTabRef"
          :formula-list="formulaList"
          :formula-total="formulaTotal"
          :formula-page="formulaPage"
          :formula-categories="formulaCategories"
          @refresh="handleFormulaRefresh"
        />
      </el-tab-pane>

      <!-- ===== 我的长期记忆 Tab (v77 P2.6-E.3 拆分到 KnowledgeMemoryTab.vue) ===== -->
      <el-tab-pane label="我的长期记忆" name="memory" lazy>
        <KnowledgeMemoryTab ref="memoryTabRef" />
      </el-tab-pane>
    </el-tabs>

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
import { useKnowledge } from '@/composables/useKnowledge'
import { useSearchAnalyticsStore } from '@/stores/useSearchAnalytics'
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
  statsData, categories, hotTags,
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
const showAllKnowledge = ref(false)

const activeTab = ref('knowledge')
const route = useRoute()
const router = useRouter()
if (route.query.tab === 'memory') activeTab.value = 'memory'

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
watch([filterCategory, filterSourceType], () => {
  currentPage.value = 1
  fetchKnowledge()
})

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
})

const handleResize = () => {
  isMobile.value = window.innerWidth <= 768
}

onMounted(() => {
  fetchKnowledge()
  fetchStats()
  fetchCategories()
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

.knowledge-tabs {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.knowledge-tabs :deep(.el-tabs__header) {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  margin: 0;
}

.knowledge-tabs :deep(.el-tabs__item) {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  padding: 0 var(--space-5);
  height: 48px;
  line-height: 48px;
}

.knowledge-tabs :deep(.el-tabs__item.is-active) {
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}

.knowledge-tabs :deep(.el-tabs__active-bar) {
  background: var(--color-primary);
}

.knowledge-tabs :deep(.el-tabs__content) {
  padding: var(--space-4);
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
  .knowledge-tabs :deep(.el-tabs__content) {
    padding: var(--space-3);
  }
}
</style>

<style>
/* v69 P1b: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
[data-theme="dark"] .knowledge-tabs :deep(.el-tabs__header) {
  background: var(--color-bg-card);
}
[data-theme="dark"] .health-summary {
  background: var(--color-bg-card);
  border-color: var(--color-border-light);
}
</style>