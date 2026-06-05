<template>
  <div class="knowledge-view">
    <el-tabs v-model="activeTab" type="border-card" class="knowledge-tabs">
      <el-tab-pane label="知识库" name="knowledge">
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
          :stats="dashboardStats"
          :categories="categories"
          :recent-items="knowledgeList"
          :active-category="filterCategory"
          :loading="loading"
          @filter-category="handleCategoryFilter"
          @filter-time="handleTimeFilter"
          @show-entities="activeTab = 'entities'"
          @show-hypotheses="activeTab = 'hypotheses'"
          @show-all-categories="showAllCategories = true"
          @show-all="showAllKnowledge = true"
          @view-detail="$router.push('/knowledge/' + $event)"
          @edit="editKnowledge"
          @delete="handleDeleteKnowledge"
          @download="downloadFile"
        />

        <!-- 分页（查看全部时显示） -->
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

      <!-- ===== 实体图谱 Tab ===== -->
      <el-tab-pane label="实体图谱" name="entities">
        <el-card class="filter-card">
          <el-row :gutter="12">
            <el-col :span="5">
              <el-input v-model="entitySearch.subject" name="entitySearch-subject" placeholder="主体" clearable @keyup.enter="searchEntitiesLocal" />
            </el-col>
            <el-col :span="5">
              <el-input v-model="entitySearch.predicate" name="entitySearch-predicate" placeholder="关系" clearable @keyup.enter="searchEntitiesLocal" />
            </el-col>
            <el-col :span="6">
              <el-input v-model="entitySearch.keyword" name="entitySearch-keyword" placeholder="关键字搜索" clearable @keyup.enter="searchEntitiesLocal" />
            </el-col>
            <el-col :span="4">
              <el-button type="primary" @click="searchEntitiesLocal">搜索实体</el-button>
            </el-col>
            <el-col :span="4">
              <el-button @click="fetchEntityGraphLocal">图谱视图</el-button>
            </el-col>
          </el-row>
        </el-card>

        <el-card v-if="entityGraphData.nodes.length > 0" class="entity-graph-card">
          <div ref="entityGraphRef" class="entity-graph-container"></div>
        </el-card>

        <el-card class="entity-list-card">
          <div v-if="entityList.length === 0" class="empty-state">
            <el-empty description="暂无实体数据。上传文档后系统将自动提取知识三元组并跨文档合并。" />
          </div>
          <div v-else class="entity-grid">
            <div v-for="e in entityList" :key="e.id" class="entity-card clickable" @click="showEntityDetail(e.id)">
              <div class="entity-triple">
                <span class="entity-subject">{{ e.subject }}</span>
                <span class="entity-predicate">→ {{ e.predicate }} →</span>
                <span class="entity-object">{{ e.object }}</span>
              </div>
              <div v-if="e.condition" class="entity-condition-text">条件: {{ e.condition }}</div>
              <div class="entity-meta">
                <span>{{ e.source_count }} 篇文档</span>
                <span>{{ e.occurrence_count }} 次出现</span>
                <el-progress :percentage="Math.round(e.confidence * 100)" :stroke-width="4" :show-text="false" style="width:80px" />
              </div>
            </div>
          </div>
          <el-pagination v-if="entityTotal > 0" v-model:current-page="entityPage" :page-size="20"
            :total="entityTotal" layout="total, prev, pager, next" @current-change="searchEntitiesLocal" style="margin-top:12px" />
        </el-card>
      </el-tab-pane>

      <!-- ===== 假设 Tab ===== -->
      <el-tab-pane label="科研假设" name="hypotheses">
        <el-card class="filter-card">
          <el-row :gutter="12" align="middle">
            <el-col :span="4">
              <el-select v-model="hypothesisFilter.status" name="hypothesisFilter-status" placeholder="状态" clearable @change="fetchHypotheses">
                <el-option label="已提出" value="proposed" />
                <el-option label="已验证" value="validated" />
                <el-option label="已否决" value="rejected" />
              </el-select>
            </el-col>
            <el-col :span="4">
              <el-select v-model="hypothesisFilter.priority" name="hypothesisFilter-priority" placeholder="优先级" clearable @change="fetchHypotheses">
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
                <el-option label="低" value="low" />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-input v-model="hypothesisTopic" name="hypothesisTopic" placeholder="研究领域（留空=全局）" clearable />
            </el-col>
            <el-col :span="5">
              <el-button type="primary" :loading="hypothesisGenerating" @click="generateHypotheses">
                <el-icon><MagicStick /></el-icon> 生成假设
              </el-button>
            </el-col>
          </el-row>
        </el-card>

        <div v-if="hypothesisGenerating" class="qa-loading">🔬 正在分析实体关系并生成假设...</div>

        <div v-else class="hypothesis-grid">
          <div v-for="h in hypothesisList" :key="h.id" class="hypothesis-card" :class="'hypothesis-' + h.status">
            <div class="hypothesis-header">
              <el-tag :type="hypothesisStatusTag(h.status)" size="small">{{ hypothesisStatusLabel(h.status) }}</el-tag>
              <el-tag :type="h.priority === 'high' ? 'danger' : h.priority === 'medium' ? 'warning' : 'info'" size="small" effect="plain">
                {{ h.priority === 'high' ? '高优先' : h.priority === 'medium' ? '中优先' : '低优先' }}
              </el-tag>
              <span class="hypothesis-confidence">{{ Math.round(h.confidence * 100) }}%</span>
            </div>
            <div class="hypothesis-statement">{{ h.statement }}</div>
            <div v-if="h.rationale" class="hypothesis-rationale"><strong>推导依据:</strong> {{ h.rationale }}</div>
            <div v-if="h.suggested_experiment" class="hypothesis-experiment"><strong>实验建议:</strong> {{ h.suggested_experiment }}</div>
            <div class="hypothesis-actions" v-if="h.status === 'proposed'">
              <el-button size="small" type="success" @click="validateHypothesis(h.id, 'validated')">验证通过</el-button>
              <el-button size="small" type="danger" @click="validateHypothesis(h.id, 'rejected')">否决</el-button>
            </div>
          </div>
        </div>
        <el-pagination v-if="hypothesisTotal > 0" v-model:current-page="hypothesisPage" :page-size="20"
          :total="hypothesisTotal" layout="total, prev, pager, next" @current-change="fetchHypotheses" style="margin-top:12px" />
      </el-tab-pane>

      <!-- ===== 公式计算 Tab ===== -->
      <el-tab-pane label="公式计算" name="formulas">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card class="formula-list-card">
              <div class="formula-list-header">
                <div class="formula-filter-row">
                  <el-tree-select
                    v-model="formulaCategoryFilter"
                    :data="formulaCategories"
                    :props="{ label: 'display_name', value: 'id', children: 'children' }"
                    placeholder="全部分类"
                    clearable
                    filterable
                    style="width:160px"
                    @change="fetchFormulas"
                  />
                  <el-select v-model="formulaSourceFilter" name="formulaSourceFilter" placeholder="来源" clearable @change="fetchFormulas" style="width:100px">
                    <el-option label="内置公式" value="builtin" />
                    <el-option label="文档提取" value="extracted" />
                  </el-select>
                  <el-input v-model="formulaKeyword" name="formulaKeyword" placeholder="搜索公式" clearable @keyup.enter="fetchFormulas" style="width:150px" />
                </div>
              </div>
              <div v-if="formulaList.length === 0" class="empty-state">
                <el-empty description="暂无公式。上传含数学公式的文档后系统将自动提取。" />
              </div>
              <div v-for="f in formulaList" :key="f.id" class="formula-item"
                :class="{ 'formula-selected': selectedFormula?.id === f.id }" @click="selectFormula(f)">
                <div class="formula-name">{{ f.name }}</div>
                <div class="formula-latex">{{ f.formula_latex }}</div>
                <div class="formula-meta">
                  <el-tag size="small">{{ f.domain || '未分类' }}</el-tag>
                  <el-tag v-if="f.source_type === 'builtin'" size="small" type="success" style="margin-left:4px">内置</el-tag>
                  <el-tag v-else-if="f.source_type === 'extracted'" size="small" type="info" style="margin-left:4px">提取</el-tag>
                  <span class="formula-unit">→ {{ f.result_unit }}</span>
                </div>
                <div v-if="f.category_name" class="formula-category-path">{{ f.category_name }}</div>
              </div>
              <el-pagination v-if="formulaTotal > 20" v-model:current-page="formulaPage" :page-size="20"
                :total="formulaTotal" layout="prev, pager, next" size="small" @current-change="fetchFormulas" />
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card v-if="selectedFormula" class="calculator-card">
              <h3>{{ selectedFormula.name }}</h3>
              <div v-if="selectedFormula.category_name" class="calc-category-path">分类: {{ selectedFormula.category_name }}</div>
              <div class="formula-meta" style="margin-top:4px">
                <el-tag v-if="selectedFormula.source_type === 'builtin'" size="small" type="success">内置公式</el-tag>
                <el-tag v-else-if="selectedFormula.source_type === 'extracted'" size="small" type="info">文档提取</el-tag>
              </div>
              <div class="calculator-formula">{{ selectedFormula.formula_latex }}</div>
              <el-divider />
              <el-form label-width="150px">
                <el-form-item v-for="(meta, varName) in selectedFormula.variables" :key="varName"
                  :label="`${meta.description || varName} (${meta.unit || ''})`">
                  <el-input-number v-model="calcInputs[varName]" :step="0.1" :precision="4" style="width:180px" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="calcLoading" @click="runCalculation">计算</el-button>
                </el-form-item>
              </el-form>
              <div v-if="calcResult" class="calc-result">
                <div class="calc-value">
                  结果: <strong>{{ calcResult.value }}</strong> <span class="calc-unit">{{ calcResult.unit }}</span>
                </div>
                <div v-if="calcResult.steps" class="calc-steps">
                  <div class="steps-title">计算步骤</div>
                  <div v-for="(step, i) in calcResult.steps" :key="i" class="calc-step">
                    <span class="step-var">{{ step.variable }}</span> = {{ step.value }} {{ step.unit }}
                  </div>
                </div>
                <div v-if="selectedFormula.knowledge_id" class="calc-source">来源: <a @click="$router.push('/knowledge/' +selectedFormula.knowledge_id)">知识条目 #{{ selectedFormula.knowledge_id }}</a></div>
              </div>
            </el-card>
            <el-card v-else class="calculator-card">
              <el-empty description="请从左侧选择一个公式" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

    </el-tabs>

    <!-- 添加/编辑知识对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingKnowledge ? '编辑知识' : '添加知识'"
      :width="isMobile ? '90vw' : '600px'"
      top="8vh"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form :model="knowledgeForm" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="knowledgeForm.title" name="knowledgeForm-title" placeholder="请输入标题" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="knowledgeForm.category" name="knowledgeForm-category" placeholder="选择分类" filterable allow-create clearable>
            <el-option-group label="预设分类">
              <el-option label="📄 论文" value="论文" />
              <el-option label="🔬 方法" value="方法" />
              <el-option label="📏 标准" value="标准" />
              <el-option label="📖 综述" value="综述" />
              <el-option label="💡 案例" value="案例" />
              <el-option label="❓ FAQ" value="FAQ" />
              <el-option label="📝 笔记" value="笔记" />
              <el-option label="📚 手册" value="手册" />
            </el-option-group>
            <el-option-group label="动态分类" v-if="categories.length > 0">
              <el-option
                v-for="cat in categories"
                :key="cat.name"
                :label="`${cat.name} (${cat.count})`"
                :value="cat.name"
              />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="knowledgeForm.tags" name="knowledgeForm-tags"
            multiple
            filterable
            allow-create
            placeholder="输入标签"
          >
            <el-option
              v-for="tag in hotTags"
              :key="tag.name"
              :label="`${tag.name} (${tag.count})`"
              :value="tag.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input
            v-model="knowledgeForm.content" name="knowledgeForm-content"
            type="textarea"
            :rows="8"
            placeholder="请输入知识内容"
          />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="knowledgeForm.source" name="knowledgeForm-source" placeholder="来源链接或文件路径" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveKnowledge">{{ editingKnowledge ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>

    <!-- AI 问答对话框 -->
    <KnowledgeQADialog
      v-model:visible="showQADialog"
      :is-mobile="isMobile"
      @navigate="$router.push('/knowledge/' + $event)"
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
          <div v-for="src in entityDetail.sources" :key="src.id" class="source-item clickable" @click="$router.push('/knowledge/' +src.id); showEntityDetailDialog = false">
            {{ src.title }}
            <el-tag size="small">{{ src.category }}</el-tag>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import axios from 'axios'
import { useKnowledge } from '@/composables/useKnowledge'
import KnowledgeToolbar from '@/components/knowledge/KnowledgeToolbar.vue'
import KnowledgeDashboard from '@/components/knowledge/KnowledgeDashboard.vue'
import KnowledgeQADialog from './knowledge/KnowledgeQADialog.vue'
import KnowledgeUploadDialog from './knowledge/KnowledgeUploadDialog.vue'

// 使用 composable（共享状态 + API）
const {
  knowledgeList, total, currentPage, pageSize, loading,
  searchQuery, filterCategory,
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

// Tabs
const activeTab = ref('knowledge')

// Entity tab
const entitySearch = ref({ subject: '', predicate: '', keyword: '' })
const entityGraphRef = ref(null)
let entityChartInstance = null
const showEntityDetailDialog = ref(false)
const entityDetail = ref(null)

// Hypothesis tab
const hypothesisFilter = ref({ status: '', priority: '' })
const hypothesisTopic = ref('')
const hypothesisGenerating = ref(false)

// Formula tab
const formulaCategoryFilter = ref(null)
const formulaKeyword = ref('')
const formulaSourceFilter = ref('')
const formulaDomains = ref([])
const selectedFormula = ref(null)
const calcInputs = ref({})
const calcResult = ref(null)
const calcLoading = ref(false)

// 表单
const knowledgeForm = ref({
  title: '',
  category: '',
  tags: [],
  content: '',
  source: ''
})

// Dashboard 统计数据
const dashboardStats = computed(() => ({
  total: statsData.value.total || 0,
  recent_count: knowledgeList.value.length,
  entity_count: entityTotal.value || 0,
  hypothesis_count: hypothesisTotal.value || 0
}))

// ── 搜索和筛选 ──

const handleSearch = (query) => {
  searchQuery.value = query
  currentPage.value = 1
  fetchKnowledge()
}

const handleFilter = (filters) => {
  // 处理高级筛选
  if (filters.category) {
    filterCategory.value = filters.category
  }
  // 其他筛选条件可以扩展
  currentPage.value = 1
  fetchKnowledge()
}

const handleCategoryFilter = (category) => {
  filterCategory.value = category
  currentPage.value = 1
  fetchKnowledge()
}

const handleTimeFilter = (range) => {
  // 时间筛选逻辑
  console.log('Time filter:', range)
}

// ── 保存/编辑 ──

const saveKnowledge = async () => {
  if (!knowledgeForm.value.title || !knowledgeForm.value.content) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  try {
    if (editingKnowledge.value) {
      await axios.put(`/api/v1/knowledge/${editingKnowledge.value.id}`, knowledgeForm.value)
      ElMessage.success('知识更新成功')
    } else {
      await axios.post('/api/v1/knowledge', knowledgeForm.value)
      ElMessage.success('知识添加成功')
    }
    showCreateDialog.value = false
    editingKnowledge.value = null
    resetForm()
    fetchKnowledge()
    fetchStats()
    fetchCategories()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const editKnowledge = (item) => {
  editingKnowledge.value = item
  knowledgeForm.value = { ...item }
  showCreateDialog.value = true
}

const downloadFile = async (item) => {
  try {
    const response = await axios.get(`/api/v1/knowledge/${item.id}/download`, {
      responseType: 'blob'
    })
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

// ── 上传成功回调 ──
const onUploadSuccess = () => {
  fetchKnowledge()
  fetchStats()
}

const resetForm = () => {
  knowledgeForm.value = { title: '', category: '', tags: [], content: '', source: '' }
}

const openQADialog = () => {
  showQADialog.value = true
}

// ── 监听 ──

watch(filterCategory, () => {
  currentPage.value = 1
  fetchKnowledge()
})

watch(searchQuery, (val) => {
  if (!val) {
    currentPage.value = 1
    fetchKnowledge()
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

// ── Entity methods ──

const searchEntitiesLocal = async () => {
  try {
    const params = { ...entitySearch.value, page: entityPage.value, page_size: 20 }
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    await searchEntities(params)
  } catch (e) { ElMessage.error('实体搜索失败') }
}

const fetchEntityGraphLocal = async () => {
  try {
    await fetchEntityGraph()
    await nextTick()
    renderEntityGraph()
  } catch (e) { console.error('实体图谱加载失败:', e) }
}

const renderEntityGraph = async () => {
  if (!entityGraphRef.value || entityGraphData.value.nodes.length === 0) return
  const echarts = await import('echarts')
  if (entityChartInstance) entityChartInstance.dispose()
  entityChartInstance = echarts.init(entityGraphRef.value)
  const cats = [...new Set(entityGraphData.value.nodes.map(n => n.predicate || '其他'))]
  const colors = ['#FF7A5C', '#FFB347', '#5470c6', '#91cc75', '#ee6666', '#73c0de', '#fc8452']
  const option = {
    tooltip: { formatter: p => p.dataType === 'node' ? `${p.data.subject}<br/>${p.data.predicate} → ${p.data.object}` : `共现权重: ${p.data.weight || 1}` },
    legend: { data: cats.slice(0, 7), bottom: 0 },
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      force: { repulsion: 200, edgeLength: [100, 300] },
      data: entityGraphData.value.nodes.map(n => ({
        name: String(n.id), subject: n.subject, predicate: n.predicate, object: n.object,
        symbolSize: Math.max(15, Math.min(40, (n.occurrence_count || 1) * 6)),
        category: n.predicate || '其他', itemStyle: { color: colors[cats.indexOf(n.predicate || '其他') % colors.length] },
      })),
      categories: cats.slice(0, 7).map((c, i) => ({ name: c, itemStyle: { color: colors[i % colors.length] } })),
      links: entityGraphData.value.edges.map(e => ({ source: String(e.source), target: String(e.target), weight: e.weight })),
      lineStyle: { opacity: 0.4, curveness: 0.2 },
      label: { show: true, formatter: p => p.data.subject.length > 8 ? p.data.subject.slice(0, 8) + '...' : p.data.subject, fontSize: 10 },
    }],
  }
  entityChartInstance.setOption(option)
}

const showEntityDetail = async (id) => {
  try {
    const res = await axios.get(`/api/v1/knowledge/entities/${id}`)
    entityDetail.value = res.data
    showEntityDetailDialog.value = true
  } catch (e) { ElMessage.error('获取实体详情失败') }
}

// ── Hypothesis methods ──

const generateHypotheses = async () => {
  hypothesisGenerating.value = true
  try {
    await axios.post('/api/v1/knowledge/hypotheses', {
      topic: hypothesisTopic.value || null,
      count: 3,
    })
    hypothesisGenerating.value = false
    await fetchHypotheses()
    ElMessage.success('假设生成完成')
  } catch (e) {
    hypothesisGenerating.value = false
    ElMessage.error('假设生成失败')
  }
}

const hypothesisStatusTag = (s) => s === 'validated' ? 'success' : s === 'rejected' ? 'danger' : 'warning'
const hypothesisStatusLabel = (s) => s === 'validated' ? '已验证' : s === 'rejected' ? '已否决' : '已提出'

const validateHypothesis = async (id, status) => {
  try {
    await axios.post(`/api/v1/knowledge/hypotheses/${id}/validate`, { status })
    ElMessage.success(status === 'validated' ? '已标记为验证通过' : '已否决')
    await fetchHypotheses()
  } catch (e) { ElMessage.error('操作失败') }
}

// ── Formula methods ──

const fetchFormulaDomains = async () => {
  try {
    const res = await axios.get('/api/v1/knowledge/formulas/domains')
    formulaDomains.value = res.data || []
  } catch (e) { console.error('获取公式领域失败:', e) }
}

const selectFormula = (f) => {
  selectedFormula.value = f
  calcInputs.value = {}
  calcResult.value = null
  if (f.variables) {
    for (const [k, meta] of Object.entries(f.variables)) {
      calcInputs.value[k] = meta.default ?? 0
    }
  }
}

const runCalculation = async () => {
  if (!selectedFormula.value) return
  calcLoading.value = true
  calcResult.value = null
  try {
    const res = await axios.post('/api/v1/knowledge/formulas/calculate', {
      formula_id: selectedFormula.value.id,
      variables: calcInputs.value,
    })
    calcResult.value = res.data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '计算失败')
  } finally { calcLoading.value = false }
}

// ── Tab watcher ──

watch(activeTab, (tab) => {
  if (tab === 'entities') { searchEntitiesLocal(); fetchEntityGraphLocal() }
  if (tab === 'hypotheses') fetchHypotheses()
  if (tab === 'formulas') { fetchFormulas(); fetchFormulaCategories() }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (entityChartInstance) {
    entityChartInstance.dispose()
    entityChartInstance = null
  }
})
</script>

<style scoped>
.knowledge-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

/* ── Tabs ── */
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

/* ── Filter Card ── */
.filter-card {
  margin-bottom: var(--space-4);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

/* ── Entity ── */
.entity-graph-card {
  margin-bottom: var(--space-4);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.entity-graph-container {
  height: 400px;
  width: 100%;
}

.entity-list-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.entity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}

.entity-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
}

.entity-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
  transform: translateY(-2px);
}

.entity-triple {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  flex-wrap: wrap;
}

.entity-subject {
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}

.entity-predicate {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.entity-object {
  color: var(--color-accent);
}

.entity-condition-text {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.entity-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.entity-triple-large {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--font-size-lg);
  margin-bottom: var(--space-4);
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

/* ── Hypothesis ── */
.hypothesis-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-4);
}

.hypothesis-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
}

.hypothesis-card:hover {
  box-shadow: var(--shadow-md);
}

.hypothesis-proposed {
  border-left: 4px solid var(--color-warning);
}

.hypothesis-validated {
  border-left: 4px solid var(--color-success);
}

.hypothesis-rejected {
  border-left: 4px solid var(--color-danger);
}

.hypothesis-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.hypothesis-confidence {
  margin-left: auto;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}

.hypothesis-statement {
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
  line-height: 1.6;
  margin-bottom: var(--space-3);
}

.hypothesis-rationale,
.hypothesis-experiment {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: var(--space-2);
}

.hypothesis-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border-light);
}

/* ── Formula ── */
.formula-list-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.formula-list-header {
  margin-bottom: var(--space-3);
}

.filter-row {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.formula-item {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  margin-bottom: var(--space-2);
}

.formula-item:hover {
  background: var(--color-info-bg);
}

.formula-selected {
  background: var(--color-primary-bg);
  border: 1px solid var(--color-primary-border);
}

.formula-name {
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-1);
}

.formula-latex {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  font-family: 'Courier New', monospace;
  margin-bottom: var(--space-2);
}

.formula-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.formula-unit {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.formula-category-path {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: var(--space-1);
}

/* ── Calculator ── */
.calculator-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  position: sticky;
  top: var(--space-4);
}

.calculator-card h3 {
  margin: 0 0 var(--space-2) 0;
  color: var(--color-text-primary);
}

.calc-category-path {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.calculator-formula {
  font-size: var(--font-size-md);
  font-family: 'Courier New', monospace;
  color: var(--color-primary);
  padding: var(--space-3);
  background: var(--color-info-bg);
  border-radius: var(--radius-md);
  margin: var(--space-3) 0;
  text-align: center;
}

.calc-result {
  margin-top: var(--space-4);
  padding: var(--space-4);
  background: var(--color-success-bg);
  border-radius: var(--radius-md);
}

.calc-value {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.calc-unit {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.calc-steps {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border-light);
}

.steps-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
}

.calc-step {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-1);
}

.step-var {
  font-weight: var(--font-weight-medium);
  color: var(--color-primary);
}

.calc-source {
  margin-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.calc-source a {
  color: var(--color-primary);
  cursor: pointer;
}

.calc-source a:hover {
  text-decoration: underline;
}

/* ── Common ── */
.clickable {
  cursor: pointer;
}

.empty-state {
  padding: var(--space-10) 0;
}

.qa-loading {
  text-align: center;
  padding: var(--space-10);
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
}

.pagination {
  margin-top: var(--space-5);
  display: flex;
  justify-content: flex-end;
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .knowledge-tabs :deep(.el-tabs__content) {
    padding: var(--space-3);
  }

  .entity-grid,
  .hypothesis-grid {
    grid-template-columns: 1fr;
  }

  .filter-row {
    flex-direction: column;
  }
}
</style>
