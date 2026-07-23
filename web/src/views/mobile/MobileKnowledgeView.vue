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

      <!-- Tab: 我的长期记忆 (v28 step 68) -->
      <div v-else-if="activeTab === 'memory'">
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
          <article v-for="item in memoryList" :key="item.id" class="memory-mobile-card">
            <div class="memory-mobile-header">
              <span class="memory-mobile-type" :class="`type-${item.memory_type}`">
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
  { name: '手动添加', icon: '✏️', color: 'var(--color-primary)' },
  { name: '上传文件', icon: '📚', color: '#67C23A', subtitle: '入知识库 + 自动解析' },  // PR4.3 标注语义
  { name: '拍照上传', icon: '📷', color: '#909399', subtitle: '摄像头拍照入网盘' },  // PR4.7 capture API
  { name: 'AI 自动研究', icon: '🤖', color: '#E6A23C' },
  { name: '入网盘', icon: '📁', color: '#409EFF', subtitle: '原始文件归档' },  // PR4.3 新增
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

/* W68 G-2 (2026-07-24): 下拉刷新指示器 */
.knowledge-pull-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary, #666);
  transition: height 100ms ease;
  overflow: hidden;
}
.knowledge-pull-indicator.is-active {
  color: var(--color-primary, #FF7A5C);
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

/* TabStrip 容器（铁律 31: 替代原 .tab-bar 自定义） */
.tab-bar-wrapper {
  margin-bottom: 12px;
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
  /* stylelint-disable-next-line color-named */
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
  /* stylelint-disable-next-line color-named */
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  cursor: pointer;
}
.action-btn:active { opacity: 0.8; }

/* v28 step 68: 长期记忆 Tab 移动端样式 */
.memory-mobile-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  padding: 0 4px;
}
.memory-mobile-search {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-bg-card);
  font-size: 14px;
}
.memory-mobile-select {
  height: 36px;
  padding: 0 8px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-bg-card);
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

.memory-mobile-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 10px;
  padding: 12px 14px;
}

.memory-mobile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.memory-mobile-type {
  display: inline-flex;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
}
.memory-mobile-type.type-preference { background: var(--color-primary-bg); color: var(--color-primary); }
.memory-mobile-type.type-user_fact { background: var(--color-success-bg); color: var(--color-success); }
.memory-mobile-type.type-task_ctx { background: var(--color-warning-bg); color: var(--color-warning); }
.memory-mobile-type.type-summary { background: var(--color-primary-bg); color: var(--color-primary); }
.memory-mobile-type.type-entity { background: var(--color-primary-bg); color: var(--color-primary); }

.memory-mobile-imp {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.memory-mobile-key {
  font-size: 11px;
  color: var(--color-primary);
  margin-bottom: 4px;
}

.memory-mobile-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-primary);
  margin: 0 0 8px;
}

.memory-mobile-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.memory-mobile-forget {
  border: none;
  background: transparent;
  color: var(--color-danger);
  font-size: 12px;
  cursor: pointer;
}

.empty-state-mobile {
  text-align: center;
  padding: 40px 16px;
}
.empty-icon { font-size: 48px; opacity: 0.5; margin-bottom: 12px; }
.empty-title { font-size: 16px; font-weight: 600; color: var(--color-text-primary); }
.empty-hint { font-size: 13px; color: var(--color-text-secondary); margin-top: 6px; }

.pagination-mobile {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 16px;
}
.page-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-card);
  font-size: 13px;
  cursor: pointer;
}
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 13px; color: var(--color-text-secondary); }
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
/* 知识库 tab / 卡片 / 搜索 / 分页在 dark 模式适配 */
/* 铁律 26: 旧 .tab-bar / .tab-item 已迁移到 TabStrip, dark mode 由 TabStrip 组件自身处理 */
[data-theme="dark"] .search-input {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border-color: var(--color-border-light);
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
[data-theme="dark"] .page-btn {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .page-btn:not(:disabled):active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
</style>