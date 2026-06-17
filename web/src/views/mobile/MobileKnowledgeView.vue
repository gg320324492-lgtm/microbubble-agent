<template>
  <div class="mobile-knowledge-view">
    <PageHeader title="知识库" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action"
          aria-label="搜索"
          title="搜索"
          @click="showSearch = true"
        >🔍</button>
        <button
          type="button"
          class="header-action primary"
          aria-label="新建"
          title="新建"
          @click="showCreateSheet = true"
        >+</button>
      </template>
    </PageHeader>

    <main
      class="knowledge-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- Tabs -->
      <div class="tab-bar">
        <button
          v-for="t in tabs"
          :key="t.name"
          type="button"
          class="tab-item"
          :class="{ active: activeTab === t.name }"
          @click="switchTab(t.name)"
        >
          {{ t.label }}
        </button>
      </div>

      <!-- Tab: 知识库 -->
      <div v-if="activeTab === 'knowledge'">
        <CardList
          :items="knowledgeList"
          :field-config="knowledgeFieldConfig"
          :loading="loading"
          empty-icon="📚"
          empty-title="暂无知识条目"
          empty-hint="点击 + 添加或上传文件"
          @item-click="viewDetail"
        >
          <template #item-actions="{ item }">
            <div class="item-actions">
              <button type="button" class="item-btn" @click.stop="editKnowledge(item)">✏️</button>
              <button type="button" class="item-btn danger" @click.stop="deleteKnowledge(item)">🗑</button>
            </div>
          </template>
        </CardList>
      </div>

      <!-- Tab: 实体图谱 -->
      <div v-else-if="activeTab === 'entities'" class="info-pane">
        <div class="info-icon">🔗</div>
        <h3>实体关系图谱</h3>
        <p class="info-hint">复杂的力导向图建议在桌面端查看</p>
        <p class="info-hint">点击下方按钮切换到桌面版</p>
        <button
          type="button"
          class="action-btn"
          @click="$router.push('/knowledge?desktop=true')"
        >在桌面查看</button>
      </div>

      <!-- Tab: 假设 -->
      <div v-else-if="activeTab === 'hypotheses'">
        <CardList
          :items="hypotheses"
          :field-config="hypothesisFieldConfig"
          :loading="loadingHypotheses"
          empty-icon="💡"
          empty-title="暂无假设"
          @item-click="viewHypothesis"
        />
      </div>

      <!-- Tab: 公式 -->
      <div v-else-if="activeTab === 'formulas'">
        <CardList
          :items="formulas"
          :field-config="formulaFieldConfig"
          :loading="loadingFormulas"
          empty-icon="🧮"
          empty-title="暂无公式"
          @item-click="viewFormula"
        />
      </div>

      <!-- Tab: 健康度 -->
      <div v-else-if="activeTab === 'health'">
        <div class="info-pane">
          <div class="info-icon">💚</div>
          <h3>知识库健康度</h3>
          <p class="info-hint">检测过期、重复、矛盾的条目</p>
          <p class="info-hint">完整分析请访问桌面端</p>
        </div>
      </div>
    </main>

    <!-- 搜索 Sheet -->
    <MobileSearchSheet
      v-model="showSearch"
      v-model:keyword="searchKeyword"
      title="搜索知识"
      placeholder="搜索标题/内容/标签..."
      :filters="searchFilters"
      v-model:filters="activeFilters"
      @confirm="onSearchConfirm"
      @reset="onSearchReset"
    />

    <!-- 创建/编辑 Sheet -->
    <MobileActionSheet
      v-model="showCreateSheet"
      title="添加知识"
      :actions="createActions"
      @select="onCreateAction"
    />
  </div>
</template>

<script setup>
/**
 * MobileKnowledgeView.vue — 移动端知识库
 *
 * PR #8b: 5 tab 简化版（实体图谱禁用显示"在桌面查看"）
 * - 知识库列表（CardList）
 * - 实体图谱（简化提示）
 * - 假设列表
 * - 公式列表
 * - 健康度（简化）
 */

import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import PageHeader from '@/components/mobile/PageHeader.vue'
import CardList from '@/components/mobile/CardList.vue'
import MobileSearchSheet from '@/components/mobile/MobileSearchSheet.vue'
import MobileActionSheet from '@/components/mobile/MobileActionSheet.vue'

const router = useRouter()
const activeTab = ref('knowledge')

const knowledgeList = ref([])
const hypotheses = ref([])
const formulas = ref([])
const loading = ref(false)
const loadingHypotheses = ref(false)
const loadingFormulas = ref(false)

const showSearch = ref(false)
const showCreateSheet = ref(false)
const searchKeyword = ref('')
const activeFilters = ref({ category: '' })

const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const tabs = [
  { name: 'knowledge', label: '📚 知识' },
  { name: 'entities', label: '🔗 实体' },
  { name: 'hypotheses', label: '💡 假设' },
  { name: 'formulas', label: '🧮 公式' },
  { name: 'health', label: '💚 健康' },
]

const searchFilters = computed(() => [
  {
    key: 'category',
    label: '分类',
    options: [
      { value: '', label: '全部' },
      { value: 'microbubble', label: '🔬 微纳米气泡' },
      { value: 'water', label: '💧 水处理' },
      { value: 'agriculture', label: '🌾 农业' },
      { value: 'disinfection', label: '🧪 消毒' },
      { value: 'measurement', label: '📏 测量' },
      { value: 'application', label: '🏭 应用' },
    ],
  },
])

const knowledgeFieldConfig = computed(() => ({
  title: (k) => k.title,
  subtitle: (k) => `${getCategoryLabel(k.category)} · ${k.tags?.join(' ') || '无标签'}`,
  badge: (k) => ({
    label: k.is_auto_research ? '🤖 AI' : '手动',
    type: k.is_auto_research ? 'primary' : 'info',
  }),
  fields: (k) => [
    { key: 'category', label: '分类', value: getCategoryLabel(k.category) },
    { key: 'source', label: '来源', value: k.source || '—' },
  ],
}))

const hypothesisFieldConfig = computed(() => ({
  title: (h) => h.statement || h.text || '假设',
  subtitle: (h) => `${h.priority || '中'}优先级 · 置信度 ${((h.confidence || 0) * 100).toFixed(0)}%`,
  badge: (h) => ({
    label: getStatusLabel(h.status),
    type: h.status === 'validated' ? 'success' : h.status === 'rejected' ? 'danger' : 'warning',
  }),
}))

const formulaFieldConfig = computed(() => ({
  title: (f) => f.name || f.formula_id || '公式',
  subtitle: (f) => `${f.domain || '通用'} · ${f.variables?.length || 0} 个变量`,
  badge: (f) => ({ label: f.category || '公式', type: 'info' }),
}))

const createActions = [
  { name: '手动添加', icon: '✏️', color: '#FF7A5C' },
  { name: '上传文件', icon: '📁', color: '#67C23A' },
  { name: 'AI 自动研究', icon: '🤖', color: '#E6A23C' },
]

function getCategoryLabel(c) {
  return {
    microbubble: '微纳米气泡',
    water: '水处理',
    agriculture: '农业',
    disinfection: '消毒',
    measurement: '测量',
    application: '应用',
  }[c] || c || '未分类'
}

function getStatusLabel(s) {
  return { proposed: '待验证', validated: '已验证', rejected: '已否定' }[s] || s || '未知'
}

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'knowledge' && knowledgeList.value.length === 0) fetchKnowledge()
  if (tab === 'hypotheses' && hypotheses.value.length === 0) fetchHypotheses()
  if (tab === 'formulas' && formulas.value.length === 0) fetchFormulas()
}

async function fetchKnowledge() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (activeFilters.value.category) params.category = activeFilters.value.category
    const res = await axios.get('/api/v1/knowledge', { params })
    knowledgeList.value = res.data?.items || []
    total.value = res.data?.pagination?.total || 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function fetchHypotheses() {
  loadingHypotheses.value = true
  try {
    const res = await axios.get('/api/v1/hypothesis', { params: { page: 1, page_size: 20 } })
    hypotheses.value = res.data?.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loadingHypotheses.value = false
  }
}

async function fetchFormulas() {
  loadingFormulas.value = true
  try {
    const res = await axios.get('/api/v1/formula', { params: { page: 1, page_size: 20 } })
    formulas.value = res.data?.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loadingFormulas.value = false
  }
}

function onSearchConfirm({ keyword, filters }) {
  searchKeyword.value = keyword
  Object.assign(activeFilters.value, filters)
  currentPage.value = 1
  fetchKnowledge()
}

function onSearchReset() {
  searchKeyword.value = ''
  activeFilters.value = { category: '' }
  currentPage.value = 1
  fetchKnowledge()
}

function viewDetail(item) {
  router.push(`/knowledge/${item.id}`)
}

function viewHypothesis(item) {
  ElMessage.info('查看假设详情（开发中）')
}

function viewFormula(item) {
  ElMessage.info('查看公式详情（开发中）')
}

function editKnowledge(item) {
  ElMessage.info('编辑功能（开发中）')
}

async function deleteKnowledge(item) {
  try {
    await ElMessageBox.confirm(`确定删除"${item.title}"？`, '删除', {
      type: 'warning',
    })
    await axios.delete(`/api/v1/knowledge/${item.id}`)
    ElMessage.success('已删除')
    fetchKnowledge()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

function onCreateAction(action) {
  if (action.name === '手动添加') ElMessage.info('手动添加（开发中）')
  else if (action.name === '上传文件') ElMessage.info('上传文件（开发中）')
  else if (action.name === 'AI 自动研究') ElMessage.info('AI 研究（开发中）')
}

onMounted(() => {
  fetchKnowledge()
})
</script>

<style scoped>
.mobile-knowledge-view {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.knowledge-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* Tab bar */
.tab-bar {
  display: flex;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 4px;
  margin-bottom: 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.tab-bar::-webkit-scrollbar { display: none; }
.tab-item {
  flex-shrink: 0;
  padding: 8px 12px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  white-space: nowrap;
}
.tab-item.active {
  background: var(--color-primary);
  color: white;
  font-weight: var(--font-weight-medium, 500);
}

/* Header action */
.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
  margin-left: 4px;
}
.header-action:active { background: var(--color-primary-bg); }
.header-action.primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: white;
  font-weight: 600;
  font-size: 22px;
}

/* CardList slot */
.item-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}
.item-btn {
  flex: 1;
  padding: 6px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 12px;
  cursor: pointer;
  background: var(--color-bg-page);
  -webkit-tap-highlight-color: transparent;
}
.item-btn:active { opacity: 0.6; }
.item-btn.danger {
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
}

/* Info Pane（实体图谱 / 健康度） */
.info-pane {
  text-align: center;
  padding: 60px 20px;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
}
.info-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.info-pane h3 {
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0 0 12px;
}
.info-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 4px 0;
}
.action-btn {
  margin-top: 16px;
  padding: 10px 24px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  cursor: pointer;
}
.action-btn:active { opacity: 0.8; }
</style>