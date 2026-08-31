<template>
  <div class="mobile-knowledge-view mg-page">
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
      ref="knowledgeMainRef"
      class="knowledge-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- W68 G-2 (2026-07-24): 下拉刷新指示器, pullDistance/isRefreshing 来自 usePullToRefresh -->
      <div
        v-if="isPulling || isRefreshing"
        class="knowledge-pull-indicator"
        :class="{ 'is-active': isRefreshing }"
        :style="{ height: Math.min(pullDistance, 80) + 'px' }"
        :aria-label="isRefreshing ? '刷新中' : '下拉刷新'"
      >
        <span class="pull-glyph" :class="{ spin: isRefreshing }">{{ isRefreshing ? '⟳' : '↓' }}</span>
        <span class="pull-text">{{ isRefreshing ? '刷新中…' : '松手刷新' }}</span>
      </div>

      <!-- 铁律 31: tab 条统一用 <TabStrip> 替代自定义 .tab-bar -->
      <div class="tab-bar-wrapper">
        <TabStrip
          v-model="activeTab"
          :items="tabItems"
          :scroll="true"
          aria-label="知识库视图切换"
          @change="switchTab"
        />
      </div>

      <!-- Tab: 知识库 -->
      <div v-if="activeTab === 'knowledge'" class="mg-rise mg-stagger-1">
        <CardList
          :items="knowledgeList"
          :field-config="knowledgeFieldConfig"
          :loading="loading"
          empty-icon="📚"
          empty-title="暂无知识条目"
          empty-hint="点击 + 添加或上传文件"
          @item-click="viewDetail"
        >
          <template #item-actions="{ item, idx }">
            <!-- W99 N-6 改进 (3): top-1 推荐结果徽章 (移动端首条) -->
            <div v-if="idx === 0" class="item-top-result" aria-label="最相关结果">
              <span class="top-result-glyph" aria-hidden="true">★</span>
              <span class="top-result-text">推荐</span>
            </div>
            <div class="item-actions">
              <button type="button" class="item-btn" @click.stop="editKnowledge(item)">✏️</button>
              <button type="button" class="item-btn danger" @click.stop="deleteKnowledge(item)">🗑</button>
            </div>
          </template>
        </CardList>
      </div>

      <!-- Tab: 实体图谱 -->
      <div v-else-if="activeTab === 'entities'" class="info-pane mg-rise mg-stagger-1">
        <div class="info-icon">🔗</div>
        <h3>实体关系图谱</h3>
        <p class="info-hint">复杂的力导向图建议在桌面端查看</p>
        <p class="info-hint">点击下方按钮切换到桌面版</p>
        <button
          type="button"
          class="action-btn mg-btn-glass"
          @click="$router.push('/knowledge?desktop=true')"
        >在桌面查看</button>
      </div>

      <!-- Tab: 假设 -->
      <div v-else-if="activeTab === 'hypotheses'" class="mg-rise mg-stagger-1">
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
      <div v-else-if="activeTab === 'formulas'" class="mg-rise mg-stagger-1">
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
        <div class="info-pane mg-rise mg-stagger-1">
          <div class="info-icon">💚</div>
          <h3>知识库健康度</h3>
          <p class="info-hint">检测过期、重复、矛盾的条目</p>
          <p class="info-hint">完整分析请访问桌面端</p>
        </div>
      </div>

      <!-- Tab: 我的长期记忆 (v28 step 68) -->
      <div v-else-if="activeTab === 'memory'" class="mg-rise mg-stagger-1">
        <div class="memory-mobile-toolbar">
          <input
            v-model="memorySearch.keyword"
            type="search"
            placeholder="搜索记忆内容..."
            class="memory-mobile-search"
            @keyup.enter="fetchMemories"
          />
          <select v-model="memorySearch.type" class="memory-mobile-select" @change="fetchMemories">
            <option value="">全部类型</option>
            <option value="preference">偏好</option>
            <option value="user_fact">用户事实</option>
            <option value="task_ctx">任务上下文</option>
            <option value="entity">实体关系</option>
          </select>
        </div>

        <div v-if="memoryLoading && memoryList.length === 0" class="memory-mobile-loading">
          <div v-for="i in 3" :key="i" class="skeleton-card">
            <div class="skeleton-line w-40" />
            <div class="skeleton-line w-90" />
          </div>
        </div>

        <div v-else-if="memoryList.length === 0" class="empty-state-mobile">
          <div class="empty-icon">🧠</div>
          <div class="empty-title">还没有记忆</div>
          <div class="empty-hint">与小气对话时会自动学习</div>
        </div>

        <div v-else class="memory-mobile-list">
          <article v-for="item in memoryList" :key="item.id" class="memory-mobile-card mg-glass">
            <div class="memory-mobile-header">
              <span class="memory-mobile-type mg-chip" :class="`type-${item.memory_type}`">
                {{ memoryTypeNameMap[item.memory_type] || item.memory_type }}
              </span>
              <span class="memory-mobile-imp">⭐ {{ Math.round((item.importance || 0) * 100) }}%</span>
            </div>
            <div v-if="item.key" class="memory-mobile-key">🔑 {{ item.key }}</div>
            <p class="memory-mobile-content">{{ item.content }}</p>
            <div class="memory-mobile-footer">
              <span class="memory-mobile-time">{{ formatDateTime(item.created_at) }}</span>
              <button type="button" class="memory-mobile-forget" @click.stop="forgetMemory(item)">遗忘</button>
            </div>
          </article>
        </div>

        <div v-if="memoryTotal > memoryPageSize" class="pagination-mobile">
          <button type="button" class="page-btn" :disabled="memoryCurrentPage <= 1" @click="memoryCurrentPage--; fetchMemories()">上一页</button>
          <span class="page-info">{{ memoryCurrentPage }} / {{ Math.ceil(memoryTotal / memoryPageSize) }}</span>
          <button type="button" class="page-btn" :disabled="memoryCurrentPage >= Math.ceil(memoryTotal / memoryPageSize)" @click="memoryCurrentPage++; fetchMemories()">下一页</button>
        </div>
      </div>
    </main>

    <MobileFab :actions="fabActions" />

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

    <!-- 手动添加知识 Sheet -->
    <MobileFormSheet
      v-model="showManualSheet"
      title="手动添加知识"
      :fields="manualFields"
      v-model:form="manualForm"
      submit-text="保存"
      :submitting="manualSaving"
      @submit="onManualSubmit"
    />

    <!-- AI 研究 Sheet -->
    <MobileFormSheet
      v-model="showResearchSheet"
      title="AI 自动研究"
      :fields="researchFields"
      v-model:form="researchForm"
      submit-text="开始研究"
      :submitting="researchRunning"
      @submit="onResearchSubmit"
    />

    <input
      ref="uploadInputRef"
      type="file"
      accept=".pdf,.docx,.xlsx,.pptx,.txt,.md"
      hidden
      aria-label="选择知识文件"
      title="选择知识文件"
      @change="onUploadFile"
    />
    <!-- PR4.3: 网盘模式上传 input (任何文件类型, 不入库只归档) -->
    <input
      ref="driveUploadInputRef"
      type="file"
      multiple
      hidden
      aria-label="选择网盘文件"
      title="选择网盘文件"
      @change="onDriveUploadFile"
    />
    <!-- PR4.7: 拍照上传 input (capture=environment 调起后置摄像头) -->
    <input
      ref="cameraInputRef"
      type="file"
      accept="image/*"
      capture="environment"
      hidden
      aria-label="拍照上传"
      title="拍照上传"
      @change="onCameraCapture"
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

import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { formatDateTime } from '@/utils/format'
import { Document, Share, MagicStick, Histogram, Memo, DataLine } from '@element-plus/icons-vue'
import TabStrip from '@/components/common/TabStrip.vue'
import PageHeader from '@/components/mobile/PageHeader.vue'
import CardList from '@/components/mobile/CardList.vue'
import MobileSearchSheet from '@/components/mobile/MobileSearchSheet.vue'
import MobileActionSheet from '@/components/mobile/MobileActionSheet.vue'
import MobileFab from '@/components/mobile/MobileFab.vue'
// W68 G-2 (2026-07-24): 下拉刷新 composable
import { usePullToRefresh } from '@/composables/usePullToRefresh'
// W99 N-6 改进 (2): 移动端埋点接通 (复用桌面 store 协议)
import { useSearchAnalyticsStore } from '@/stores/useSearchAnalytics'

const router = useRouter()
const route = useRoute()
const activeTab = ref('knowledge')

// 铁律 29: URL ?tab= 同步双向（VALID_TABS 白名单 + watch + replace）
const VALID_TABS = ['knowledge', 'entities', 'hypotheses', 'formulas', 'memory', 'health']  // PR8: drive tab moved to /m-drive
if (route.query.tab && VALID_TABS.includes(String(route.query.tab))) {
  activeTab.value = String(route.query.tab)
}

// 铁律 30: EP 图标 named import + 通过 props 传入
const tabItems = [
  { key: 'knowledge',  label: '知识',     icon: Document },
  { key: 'entities',   label: '实体',     icon: Share },
  { key: 'hypotheses', label: '假设',     icon: MagicStick },
  { key: 'formulas',   label: '公式',     icon: Histogram },
  { key: 'memory',     label: '长期记忆', icon: Memo },
  { key: 'health',     label: '健康',     icon: DataLine },
]

// v28 step 68: 长期记忆 Tab 状态（合并自 MobileMemoryView）
const memoryList = ref([])
const memoryTotal = ref(0)
const memoryCurrentPage = ref(1)
const memoryPageSize = ref(20)
const memoryLoading = ref(false)
const memorySearch = ref({ keyword: '', type: '' })

const memoryTypeNameMap = {
  preference: '偏好',
  user_fact: '用户事实',
  task_ctx: '任务上下文',
  summary: '摘要',
  entity: '实体关系',
}

const fetchMemories = async () => {
  memoryLoading.value = true
  try {
    const params = {
      page: memoryCurrentPage.value,
      page_size: memoryPageSize.value,
    }
    if (memorySearch.value.keyword) params.keyword = memorySearch.value.keyword
    if (memorySearch.value.type) params.memory_type = memorySearch.value.type
    const res = await axios.get('/api/v1/memory', { params })
    memoryList.value = res.data.items || []
    memoryTotal.value = res.data.total || 0
  } catch (e) {
    console.error('[MobileKnowledgeView] 获取长期记忆失败:', e)
    ElMessage.error('获取长期记忆失败')
  } finally {
    memoryLoading.value = false
  }
}

const forgetMemory = async (item) => {
  try {
    await ElMessageBox.confirm(`确定遗忘「${(item.content || '').slice(0, 30)}...」？`, '遗忘确认', {
      type: 'warning',
      confirmButtonText: '遗忘',
      cancelButtonText: '取消',
    })
    await axios.delete(`/api/v1/memory/${item.id}`)
    ElMessage.success('已遗忘')
    fetchMemories()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

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

// W68 G-2 (2026-07-24): 下拉刷新 hook, 监听 knowledgeMainRef 滚动容器
// refresh 回调直接调 fetchKnowledge() (已有 async 函数, 无需改实现)
// 注: fetchKnowledge 在此模块靠下方定义, 通过 nextTick 包裹保证 hookup 时已存在
const knowledgeMainRef = ref(null)
const { pullDistance, isPulling, isRefreshing } = usePullToRefresh(knowledgeMainRef, {
  threshold: 80,
  maxPull: 160,
  onRefresh: async () => {
    if (typeof fetchKnowledge === 'function') await fetchKnowledge()
  },
})

// PR8: 旧 tabs 数组同步移除 files, 兼容旧引用（如有）—— 推荐直接用 tabItems
const tabs = [
  { name: 'knowledge',  label: '知识',     icon: Document },
  { name: 'entities',   label: '实体',     icon: Share },
  { name: 'hypotheses', label: '假设',     icon: MagicStick },
  { name: 'formulas',   label: '公式',     icon: Histogram },
  { name: 'memory',     label: '长期记忆', icon: Memo },
  { name: 'health',     label: '健康',     icon: DataLine },
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

const fabActions = [
  { name: 'manual', label: 'Add knowledge', icon: '✏️', handler: () => { showManualSheet.value = true } },
  { name: 'upload', label: 'Upload file', icon: '📚', handler: () => uploadInputRef.value?.click() },
  { name: 'research', label: 'AI research', icon: '🤖', handler: () => { showResearchSheet.value = true } },
  { name: 'drive', label: 'Archive to drive', icon: '📁', handler: () => driveUploadInputRef.value?.click() },
]

const createActions = [
  // PR4.3: 1 个新增 ("📁 入网盘") + 现有 3 个保留 (向后兼容)
  // W68 第 14 批 C-2: 用 CSS 变量替代硬编码色值, dark mode 自动跟随
  { name: '手动添加', icon: '✏️', color: 'var(--color-primary)' },
  { name: '上传文件', icon: '📚', color: 'var(--color-success)', subtitle: '入知识库 + 自动解析' },  // PR4.3 标注语义
  { name: '拍照上传', icon: '📷', color: 'var(--color-info)', subtitle: '摄像头拍照入网盘' },  // PR4.7 capture API
  { name: 'AI 自动研究', icon: '🤖', color: 'var(--color-warning)' },
  { name: '入网盘', icon: '📁', color: 'var(--color-primary-light)', subtitle: '原始文件归档' },  // PR4.3 新增
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
  // TabStrip emit update:modelValue 已自动更新 activeTab, 不再手动赋值
  if (tab === 'knowledge' && knowledgeList.value.length === 0) fetchKnowledge()
  if (tab === 'hypotheses' && hypotheses.value.length === 0) fetchHypotheses()
  if (tab === 'formulas' && formulas.value.length === 0) fetchFormulas()
  if (tab === 'memory' && memoryList.value.length === 0 && !memoryLoading.value) fetchMemories()
}

// 铁律 29: tab → URL 同步（router.replace 不污染 history, 合并其他 query）
watch(activeTab, (tab) => {
  router.replace({ query: { ...route.query, tab } })
})

// 铁律 29: URL → tab 反向同步（浏览器前进/后退）
watch(() => route.query.tab, (t) => {
  if (t && VALID_TABS.includes(String(t)) && String(t) !== activeTab.value) {
    activeTab.value = String(t)
  }
})

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

// W99 N-6 改进 (2): 移动端搜索埋点接通 (同桌面 store)
//   每次搜索都触发 startSearch (含 0 结果场景), 切换 query 时先 reset
const searchAnalytics = useSearchAnalyticsStore()

function onSearchConfirm({ keyword, filters }) {
  searchKeyword.value = keyword
  Object.assign(activeFilters.value, filters)
  currentPage.value = 1
  fetchKnowledge()
  // fetchKnowledge 异步: 这里 await 不到, 用 microtask 后再读列表
  Promise.resolve().then(() => {
    const topIds = knowledgeList.value.map(k => k.id)
    searchAnalytics.reset()
    searchAnalytics.startSearch(keyword, topIds, 'mobile')
  })
}

function onSearchReset() {
  searchKeyword.value = ''
  activeFilters.value = { category: '' }
  currentPage.value = 1
  fetchKnowledge()
  searchAnalytics.reset()
}

// W99 N-6 改进 (2): 移动端点击埋点接通
//   CardList 传出 (item, idx), idx 即位置 (1-based)
//   与桌面协议对齐: recordClick(clickedId, position)
function viewDetail(item, idx) {
  if (typeof idx === 'number' && idx >= 0) {
    searchAnalytics.recordClick(item.id, idx + 1)
  }
  router.push(`/knowledge/${item.id}`)
}

function viewHypothesis(item) {
  // 假设详情：路由跳到桌面版（假设 detail Dialog 已在桌面 KnowledgeView 实现）
  // 桌面 URL：/knowledge，参数 ?hypothesisId=xxx 触发 dialog
  router.push({ path: '/knowledge', query: { tab: 'hypotheses', id: item.id } })
}

function viewFormula(item) {
  // 公式详情：路由跳到桌面版（公式计算器已在桌面 KnowledgeView 实现）
  router.push({ path: '/knowledge', query: { tab: 'formulas', id: item.id } })
}

function editKnowledge(item) {
  // 知识编辑：跳到桌面详情页（KnowledgeDetailView 内嵌编辑表单）
  router.push(`/knowledge/${item.id}?edit=true`)
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
  if (action.name === '手动添加') {
    showManualSheet.value = true
  } else if (action.name === '上传文件') {
    // PR4.3: 上传文件 = 入知识库 (自动解析 + embedding)
    uploadInputRef.value?.click()
  } else if (action.name === 'AI 自动研究') {
    showResearchSheet.value = true
  } else if (action.name === '入网盘') {
    // PR4.3: 走 drive 模式 (PR2.5/2.6 后端, 仅归档不入库)
    driveUploadInputRef.value?.click()
  } else if (action.name === '拍照上传') {
    // PR4.7: capture API 调起后置摄像头
    cameraInputRef.value?.click()
  }
}

// === 手动添加知识 ===
const showManualSheet = ref(false)
const manualSaving = ref(false)
const manualForm = ref({ title: '', content: '', category: '' })
const manualFields = [
  { key: 'title', label: '标题', type: 'text', required: true, placeholder: '知识标题' },
  { key: 'content', label: '内容', type: 'textarea', required: true, placeholder: '知识正文（支持 Markdown）' },
  {
    key: 'category',
    label: '分类',
    type: 'select',
    options: [
      { value: '', label: '未分类' },
      { value: 'microbubble', label: '微纳米气泡' },
      { value: 'water', label: '水处理' },
      { value: 'agriculture', label: '农业' },
      { value: 'disinfection', label: '消毒' },
      { value: 'measurement', label: '测量' },
      { value: 'application', label: '应用' },
    ],
  },
]
async function onManualSubmit() {
  if (!manualForm.value.title?.trim() || !manualForm.value.content?.trim()) {
    ElMessage.warning('标题和内容不能为空')
    return
  }
  manualSaving.value = true
  try {
    await axios.post('/api/v1/knowledge', {
      title: manualForm.value.title,
      content: manualForm.value.content,
      category: manualForm.value.category || null,
    })
    ElMessage.success('知识添加成功')
    showManualSheet.value = false
    manualForm.value = { title: '', content: '', category: '' }
    fetchKnowledge()
  } catch (e) {
    ElMessage.error('添加失败：' + (e.response?.data?.detail || e.message))
  } finally {
    manualSaving.value = false
  }
}

// === 上传文件 ===
const uploadInputRef = ref(null)
const driveUploadInputRef = ref(null)  // PR4.3: 网盘模式上传
const cameraInputRef = ref(null)  // PR4.7: 拍照上传

// PR4.3: 网盘模式上传 handler (走 drive API, storage_mode=drive, visibility=team)
async function onDriveUploadFile(e) {
  const files = Array.from(e.target.files || [])
  if (files.length === 0) return
  let success = 0
  for (const file of files) {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('storage_mode', 'drive')
      formData.append('visibility', 'team')
      await axios.post('/api/v1/drive/files/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      success++
    } catch (err) {
      console.error('Drive upload failed:', err)
    }
  }
  ElMessage.success(success > 0 ? `已上传 ${success}/${files.length} 个文件到网盘` : '上传失败')
  e.target.value = ''
}

// PR4.7: 拍照上传 handler (图片直接入网盘, visibility=team)
async function onCameraCapture(e) {
  // 复用 drive upload 但强制 image MIME
  await onDriveUploadFile(e)
  // 拍照后给提示, 让用户知道可以去网盘页 (/m-drive) 查看
  setTimeout(() => {
    if (e.target.files?.length > 0) {
      ElMessage.info('照片已归档到网盘，可在"网盘"页查看')
    }
  }, 1500)
}
async function onUploadFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件超过 50MB')
    e.target.value = ''
    return
  }
  const fd = new FormData()
  fd.append('file', file, file.name)
  const loading = ElMessage.info({ message: '上传中，请稍候...', duration: 0 })
  try {
    await axios.post('/api/v1/knowledge/upload', fd)
    ElMessage.success('文件上传成功，已自动提取知识')
    fetchKnowledge()
  } catch (err) {
    ElMessage.error('上传失败：' + (err.response?.data?.detail || err.message))
  } finally {
    loading.close()
    e.target.value = ''
  }
}

// === AI 自动研究 ===
const showResearchSheet = ref(false)
const researchRunning = ref(false)
const researchForm = ref({ topic: '' })
const researchFields = [
  { key: 'topic', label: '研究主题', type: 'textarea', required: true, placeholder: '如：微纳米气泡在农业消毒中的应用' },
]
async function onResearchSubmit() {
  if (!researchForm.value.topic?.trim()) {
    ElMessage.warning('请输入研究主题')
    return
  }
  researchRunning.value = true
  try {
    await axios.post('/api/v1/knowledge/research', { topic: researchForm.value.topic })
    ElMessage.success('研究完成，知识已入库')
    showResearchSheet.value = false
    researchForm.value = { topic: '' }
    fetchKnowledge()
    fetchHypotheses()
  } catch (e) {
    ElMessage.error('研究失败：' + (e.response?.data?.detail || e.message))
  } finally {
    researchRunning.value = false
  }
}

onMounted(() => {
  fetchKnowledge()
})
</script>

<style scoped>
/* 2026-08-31 液态毛玻璃升级: 颜色/圆角/阴影全部走 --mg-* token (mobile-glass.css),
   页面极光背景由根节点 .mg-page 提供, 此处不再设 background */
.mobile-knowledge-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.knowledge-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* W68 G-2 (2026-07-24): 下拉刷新指示器 */
.knowledge-pull-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  color: var(--mg-text-soft);
  transition: height 100ms ease;
  overflow: hidden;
}
.knowledge-pull-indicator.is-active {
  color: var(--mg-primary);
}
.pull-glyph {
  font-size: 18px;
  display: inline-block;
  transition: transform 200ms ease;
}
.pull-glyph.spin {
  animation: pull-spin 1s linear infinite;
}
@keyframes pull-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* TabStrip 容器（铁律 31: 替代原 .tab-bar 自定义）— 玻璃化见非 scoped 块 */
.tab-bar-wrapper {
  margin-bottom: 12px;
}

/* Header action — 玻璃胶囊 (搜索/新建) */
.header-action {
  width: 44px;
  height: 44px;
  border-radius: var(--mg-radius-pill);
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  box-shadow: var(--mg-shadow-sm);
  font-size: 18px;
  color: var(--mg-text);
  cursor: pointer;
  margin-left: 6px;
  transition: transform 150ms ease;
  -webkit-tap-highlight-color: transparent;
}
.header-action:active { transform: scale(0.94); }
.header-action.primary {
  background: var(--mg-gradient-btn);
  border-color: transparent;
  color: var(--mg-on-primary);
  font-weight: 800;
  font-size: 22px;
  box-shadow: var(--mg-primary-shadow);
}

/* CardList slot */
.item-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

/* W99 N-6 改进 (3): 移动端 top-1 推荐徽章 — 渐变紫胶囊 */
.item-top-result {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  align-self: flex-start;
  margin-bottom: 6px;
  padding: 3px 10px 3px 8px;
  border-radius: var(--mg-radius-pill);
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.4px;
  box-shadow: var(--mg-primary-shadow);
}
.item-top-result .top-result-glyph { font-size: 10.5px; line-height: 1; }
.item-top-result .top-result-text { line-height: 1; }
.item-btn {
  flex: 1;
  min-height: 44px;
  padding: 8px 6px;
  border-radius: var(--mg-radius-md);
  border: 1.5px solid var(--mg-glass-border);
  font-size: 12px;
  cursor: pointer;
  background: var(--mg-glass-bg-strong);
  color: var(--mg-primary);
  font-weight: 700;
  transition: transform 150ms ease, opacity 150ms ease;
  -webkit-tap-highlight-color: transparent;
}
.item-btn:active { transform: scale(0.97); opacity: 0.8; }
.item-btn.danger {
  background: var(--mg-danger-soft);
  border-color: transparent;
  color: var(--mg-danger);
}

/* Info Pane（实体图谱 / 健康度）— 玻璃卡 */
.info-pane {
  text-align: center;
  padding: 60px 20px;
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-lg);
  box-shadow: var(--mg-shadow);
}
.info-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.info-pane h3 {
  font-size: 16px;
  font-weight: 800;
  color: var(--mg-text-strong);
  margin: 0 0 12px;
}
.info-hint {
  font-size: 13px;
  color: var(--mg-text-soft);
  margin: 4px 0;
}
/* 视觉由 mg-btn-glass 提供, 此处仅几何尺寸 (触摸目标 ≥44px) */
.action-btn {
  margin-top: 16px;
  min-height: 44px;
  padding: 10px 24px;
  font-size: 14px;
  cursor: pointer;
}

/* v28 step 68: 长期记忆 Tab 移动端样式 */
.memory-mobile-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  padding: 0 4px;
}
.memory-mobile-search {
  flex: 1;
  min-width: 0;
  height: 44px;
  padding: 0 16px;
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-pill);
  background: var(--mg-glass-bg-strong);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  color: var(--mg-text);
  font-size: 14px;
  outline: none;
  font-family: inherit;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}
.memory-mobile-search::placeholder { color: var(--mg-text-faint); }
.memory-mobile-search:focus {
  border-color: var(--mg-primary);
  box-shadow: var(--mg-shadow-sm);
}
.memory-mobile-select {
  height: 44px;
  padding: 0 10px;
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-pill);
  background: var(--mg-glass-bg-strong);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  color: var(--mg-text);
  font-size: 13px;
}

.memory-mobile-loading {
  padding: 0 4px;
}

.memory-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 4px;
}

/* 玻璃底/描边/blur 由模板上的 .mg-glass 提供, 此处只覆写圆角与内边距 */
.memory-mobile-card {
  border-radius: var(--mg-radius-md);
  padding: 13px 14px;
}

.memory-mobile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

/* 基础芯片形状由模板上的 .mg-chip 提供 (默认紫 = 偏好/摘要/实体) */
.memory-mobile-type.type-user_fact { color: var(--mg-success); background: var(--mg-success-soft); }
.memory-mobile-type.type-task_ctx { color: var(--mg-warning); background: var(--mg-warning-soft); }

.memory-mobile-imp {
  font-size: 11px;
  color: var(--mg-text-soft);
}

.memory-mobile-key {
  font-size: 11px;
  color: var(--mg-primary);
  margin-bottom: 4px;
}

.memory-mobile-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--mg-text);
  margin: 0 0 8px;
}

.memory-mobile-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--mg-text-soft);
}

.memory-mobile-forget {
  border: none;
  background: transparent;
  color: var(--mg-danger);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  min-height: 44px;
  padding: 10px 8px;
  -webkit-tap-highlight-color: transparent;
}
.memory-mobile-forget:active { opacity: 0.6; }

/* 空态 — 玻璃卡 (规范: emoji + --mg-text-soft 文案放 mg-glass 卡里) */
.empty-state-mobile {
  text-align: center;
  padding: 40px 16px;
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-lg);
  box-shadow: var(--mg-shadow-sm);
}
.empty-icon { font-size: 48px; opacity: 0.5; margin-bottom: 12px; }
.empty-title { font-size: 16px; font-weight: 800; color: var(--mg-text-strong); }
.empty-hint { font-size: 13px; color: var(--mg-text-soft); margin-top: 6px; }

.pagination-mobile {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 16px;
}
.page-btn {
  min-height: 44px;
  padding: 0 16px;
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-pill);
  background: var(--mg-glass-bg-strong);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  color: var(--mg-primary);
  font-weight: 700;
  font-size: 13px;
  box-shadow: var(--mg-shadow-sm);
  cursor: pointer;
  transition: transform 150ms ease;
  -webkit-tap-highlight-color: transparent;
}
.page-btn:active:not(:disabled) { transform: scale(0.97); }
.page-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.page-info { font-size: 13px; color: var(--mg-text-soft); }
</style>

<!-- v77 P2.6-B + W68 第 14 批 C-2: dark mode 跨组件统一（v60-v67 教训：必须非 scoped） -->
<style>
/* 2026-08-31 液态毛玻璃: 共享组件 (CardList / TabStrip) 内部元素玻璃化.
   非 scoped + 视图根 class 前缀 (规范 §视觉细节约定: 作用域前缀必须带视图根 class);
   .mobile-knowledge-view .knowledge-main 前缀 (0-4-0) 稳定压过组件 scoped 规则 (0-3-0 含属性选择器).
   mg token 自带 dark 变体, 无需额外 [data-theme="dark"] 覆盖. */
.mobile-knowledge-view .knowledge-main .tab-strip {
  background: var(--mg-glass-bg);
  border-color: var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  box-shadow: var(--mg-shadow-sm);
}
.mobile-knowledge-view .knowledge-main .tab-strip__item {
  color: var(--mg-text-soft);
}
.mobile-knowledge-view .knowledge-main .tab-strip__item.is-active {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  font-weight: 800;
  box-shadow: var(--mg-primary-shadow);
}

/* 条目卡 = mg-glass 列表卡 (规范: radius-md + padding 13px 14px) */
.mobile-knowledge-view .knowledge-main .list-item {
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-md);
  box-shadow: var(--mg-shadow-sm);
  padding: 13px 14px;
  transition: transform 150ms ease, background 150ms ease;
}
.mobile-knowledge-view .knowledge-main .list-item:active {
  background: var(--mg-glass-bg-strong);
  transform: scale(0.97);
}
.mobile-knowledge-view .knowledge-main .item-title {
  color: var(--mg-text-strong);
}
.mobile-knowledge-view .knowledge-main .item-subtitle,
.mobile-knowledge-view .knowledge-main .field-key,
.mobile-knowledge-view .knowledge-main .item-meta {
  color: var(--mg-text-soft);
}
.mobile-knowledge-view .knowledge-main .field-value {
  color: var(--mg-text);
}
.mobile-knowledge-view .knowledge-main .item-arrow {
  color: var(--mg-text-faint);
}
/* 分类/来源等次要信息 badge → 胶囊化 (颜色仍走 badge--* 语义 class, 保留原色语义) */
.mobile-knowledge-view .knowledge-main .badge-tag {
  border-radius: var(--mg-radius-pill);
}

/* CardList 空态 / 底部加载 玻璃化 */
.mobile-knowledge-view .knowledge-main .empty-state {
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-lg);
  box-shadow: var(--mg-shadow-sm);
}
.mobile-knowledge-view .knowledge-main .empty-state .empty-title {
  color: var(--mg-text);
}
.mobile-knowledge-view .knowledge-main .empty-state .empty-hint {
  color: var(--mg-text-soft);
}
.mobile-knowledge-view .knowledge-main .load-more {
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-pill);
  color: var(--mg-primary);
  font-weight: 700;
}
.mobile-knowledge-view .knowledge-main .end-hint {
  color: var(--mg-text-faint);
}

/* 知识库 tab / 卡片 / 搜索 / 分页 / 上传 dialog / action item / 空态在 dark 模式适配 */
/* 铁律 26: 旧 .tab-bar / .tab-item 已迁移到 TabStrip, dark mode 由 TabStrip 组件自身处理 */
[data-theme="dark"] .search-input {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .knowledge-card {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .knowledge-card:active {
  background: var(--color-bg-hover);
}
[data-theme="dark"] .knowledge-card .card-title {
  color: var(--color-text-primary);
}
[data-theme="dark"] .knowledge-card .card-snippet {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .knowledge-card .card-meta {
  color: var(--color-text-placeholder);
}
[data-theme="dark"] .knowledge-card .tag {
  background: var(--color-bg-page);
  color: var(--color-text-secondary);
}
[data-theme="dark"] .page-btn {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .page-btn:not(:disabled):active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
[data-theme="dark"] .page-info {
  color: var(--color-text-secondary);
}
/* W68 第 14 批 C-2: 上传 dialog / action sheet / 加载态 / 空态 在 dark 适配 */
[data-theme="dark"] .upload-overlay,
[data-theme="dark"] .dialog-overlay {
  background: rgba(0, 0, 0, 0.5);
}
[data-theme="dark"] .upload-panel,
[data-theme="dark"] .dialog-panel {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
}
[data-theme="dark"] .upload-panel h3,
[data-theme="dark"] .dialog-panel h3 {
  color: var(--color-text-primary);
}
[data-theme="dark"] .upload-action {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border-color: var(--color-border);
}
[data-theme="dark"] .upload-action:active {
  background: var(--color-bg-hover);
}
[data-theme="dark"] .upload-action .action-name {
  color: var(--color-text-primary);
}
[data-theme="dark"] .upload-action .action-subtitle {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .upload-cancel,
[data-theme="dark"] .dialog-cancel {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
}
[data-theme="dark"] .empty-state,
[data-theme="dark"] .loading-state,
[data-theme="dark"] .error-state {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .empty-title {
  color: var(--color-text-primary);
}
[data-theme="dark"] .knowledge-card .card-title-text {
  color: var(--color-text-primary);
}
</style>