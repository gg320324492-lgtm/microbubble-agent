<!-- KnowledgeHypothesisTab.vue — v77 P2.6-E.3 拆分自 KnowledgeView.vue -->
<template>
  <div>
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
    <el-pagination v-if="hypothesisTotal > 0" :current-page="hypothesisPage" :page-size="20"
      :total="hypothesisTotal" layout="total, prev, pager, next" @current-change="(p) => $emit('page-change', p)" style="margin-top:12px" />
  </div>
</template>

<script setup>
/**
 * KnowledgeHypothesisTab.vue — 科研假设 tab（v77 P2.6-E.3 从 KnowledgeView.vue 拆分）
 *
 * 父组件: KnowledgeView.vue (lazy-loaded tab-pane)
 * Props: hypothesisList / hypothesisTotal / hypothesisPage（来自 useKnowledge composable）
 */
import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'

const props = defineProps({
  hypothesisList: { type: Array, required: true },
  hypothesisTotal: { type: Number, required: true },
  hypothesisPage: { type: Number, required: true },
})

const emit = defineEmits(['page-change', 'refresh'])
// (unused)

const hypothesisFilter = ref({ status: '', priority: '' })
const hypothesisTopic = ref('')
const hypothesisGenerating = ref(false)

const fetchHypotheses = async () => {
  try {
    const params = {
      page: props.hypothesisPage,
      page_size: 20,
    }
    if (hypothesisFilter.value.status) params.status = hypothesisFilter.value.status
    if (hypothesisFilter.value.priority) params.priority = hypothesisFilter.value.priority
    if (hypothesisTopic.value) params.topic = hypothesisTopic.value
    const res = await axios.get('/api/v1/knowledge/hypotheses', { params })
    emit('refresh', {
      list: res.data.items || [],
      total: res.data.total || 0,
    })
  } catch (e) {
    console.error('[KnowledgeHypothesisTab] 获取假设失败:', e)
    ElMessage.error('获取假设失败')
  }
}

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

defineExpose({ fetchHypotheses })
</script>

<style scoped>
.filter-card {
  margin-bottom: var(--space-4);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.qa-loading {
  text-align: center;
  padding: var(--space-10);
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
}

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
</style>

<style>
/* v77 P2.6-E.3: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
[data-theme="dark"] .hypothesis-card {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .hypothesis-actions {
  border-top-color: var(--color-border-light);
}
</style>