<!-- KnowledgeFormulaTab.vue — v77 P2.6-E.3 拆分自 KnowledgeView.vue -->
<template>
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
        <el-pagination v-if="formulaTotal > 20" :current-page="formulaPage" :page-size="20"
          :total="formulaTotal" layout="prev, pager, next" size="small" @current-change="(p) => $emit('page-change', p)" />
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
          <div v-if="selectedFormula.knowledge_id" class="calc-source">来源: <a @click="goToKnowledge(selectedFormula.knowledge_id)">知识条目 #{{ selectedFormula.knowledge_id }}</a></div>
        </div>
      </el-card>
      <el-card v-else class="calculator-card">
        <el-empty description="请从左侧选择一个公式" />
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
/**
 * KnowledgeFormulaTab.vue — 公式计算 tab（v77 P2.6-E.3 从 KnowledgeView.vue 拆分）
 *
 * 父组件: KnowledgeView.vue (lazy-loaded tab-pane)
 * Props: formulaList / formulaTotal / formulaPage / formulaCategories（来自 useKnowledge composable）
 * Emits: refresh / select-formula / formula-calculated
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({
  formulaList: { type: Array, required: true },
  formulaTotal: { type: Number, required: true },
  formulaPage: { type: Number, required: true },
  formulaCategories: { type: Array, default: () => [] },
})

const emit = defineEmits(['refresh', 'page-change'])

const router = useRouter()

const formulaCategoryFilter = ref(null)
const formulaKeyword = ref('')
const formulaSourceFilter = ref('')
const selectedFormula = ref(null)
const calcInputs = ref({})
const calcResult = ref(null)
const calcLoading = ref(false)

const fetchFormulas = async () => {
  try {
    const params = {
      page: props.formulaPage,
      page_size: 20,
    }
    if (formulaCategoryFilter.value) params.category_id = formulaCategoryFilter.value
    if (formulaSourceFilter.value) params.source_type = formulaSourceFilter.value
    if (formulaKeyword.value) params.keyword = formulaKeyword.value
    const res = await axios.get('/api/v1/knowledge/formulas', { params })
    emit('refresh', {
      list: res.data.items || [],
      total: res.data.total || 0,
    })
  } catch (e) {
    console.error('[KnowledgeFormulaTab] 获取公式失败:', e)
    ElMessage.error('获取公式失败')
  }
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
  } finally {
    calcLoading.value = false
  }
}

const goToKnowledge = (id) => {
  router.push('/knowledge/' + id)
}

defineExpose({ fetchFormulas })
</script>

<style scoped>
.formula-list-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.formula-list-header {
  margin-bottom: var(--space-3);
}

.formula-filter-row {
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

.empty-state {
  padding: var(--space-10) 0;
}
</style>

<style>
/* v77 P2.6-E.3: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
[data-theme="dark"] .calc-result {
  background: var(--color-success-bg);
}
[data-theme="dark"] .calc-steps {
  border-top-color: var(--color-border-light);
}
/* v69 P1b fix-2: formula 计算器面板 + 公式列表卡（el-card dark 覆盖未生效场景） */
[data-theme="dark"] .formula-list-card,
[data-theme="dark"] .calculator-card,
[data-theme="dark"] .formula-list-card .el-card__body,
[data-theme="dark"] .calculator-card .el-card__body {
  background-color: var(--color-bg-card);
  color: var(--color-text-primary);
}
/* el-empty SVG 默认浅色背景，filter:invert 适配 dark */
[data-theme="dark"] .el-empty__image svg,
[data-theme="dark"] .el-empty__image img {
  filter: invert(0.9) hue-rotate(180deg);
}
[data-theme="dark"] .el-empty__description p {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .formula-item {
  background: transparent;
}
[data-theme="dark"] .formula-item:hover {
  background: var(--color-info-bg);
}
[data-theme="dark"] .formula-selected {
  background: var(--color-primary-bg);
}
</style>