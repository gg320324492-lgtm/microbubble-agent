<!--
  KnowledgeHypothesisTab.vue — 科研假设 tab · 2026-09-13 档案墨线风重做

  重做要点 (用户报告: 布局空旷/风格不齐/共 9 条只显示 1 张/翻页无效):
  - 墨线档案头部行 + 状态戳 chips (全部/已提出/已验证/已否决) 取代 el-select 下拉
  - 修复初始 page_size=1 不重拉: onMounted 始终 fetchHypotheses()
  - 假设卡流 (响应式 grid): 状态戳/优先级戳/置信度大字/推导依据/实验建议,
    验证/否决按钮改墨线描边 (去大红大绿)
  - 生成假设保留原 API, 生成中 banner 墨线化

  契约不变:
  Props: hypothesisList / hypothesisTotal / hypothesisPage (来自 useKnowledge)
  Emits: page-change / refresh
  Expose: fetchHypotheses (父级 watch(activeTab) 调用)
-->
<template>
  <div class="hyp-tab">
    <!-- 头部行 -->
    <div class="hyp-head">
      <div>
        <div class="hyp-eyebrow">RESEARCH HYPOTHESES · 科研假设</div>
        <div class="hyp-title">科研假设工作台</div>
      </div>
      <button class="hyp-refresh" :disabled="hypothesisGenerating" @click="fetchHypotheses">
        <span class="hyp-refresh-glyph" :class="{ spin: refreshing }">⟳</span>
        刷新
      </button>
    </div>

    <!-- 状态戳过滤 + 优先级 + 研究领域 + 生成 -->
    <div class="hyp-filters">
      <div class="hyp-status-chips">
        <button
          class="hyp-chip"
          :class="{ on: hypothesisFilter.status === '' }"
          @click="setStatus('')"
        >全部</button>
        <button
          v-for="s in STATUS_LIST"
          :key="s.value"
          class="hyp-chip"
          :class="[{ on: hypothesisFilter.status === s.value }, 'st-' + s.value]"
          @click="setStatus(s.value)"
        >{{ s.label }}</button>
      </div>
      <div class="hyp-filter-right">
        <select v-model="hypothesisFilter.priority" class="hyp-select" @change="fetchHypotheses">
          <option value="">全部优先级</option>
          <option value="high">高优先级</option>
          <option value="medium">中优先级</option>
          <option value="low">低优先级</option>
        </select>
        <input
          v-model="hypothesisTopic"
          class="hyp-input"
          placeholder="研究领域（留空=全局）"
          @keyup.enter="generateHypotheses"
        />
        <button class="hyp-gen" :disabled="hypothesisGenerating" @click="generateHypotheses">
          <span v-if="!hypothesisGenerating">✨ 生成假设</span>
          <span v-else>🔬 正在生成…</span>
        </button>
      </div>
    </div>

    <!-- 生成中横幅 -->
    <div v-if="hypothesisGenerating" class="hyp-generating">
      <span class="spin-glyph">🔬</span>
      正在分析实体关系并生成假设… AI 通常需要 10-30 秒, 请稍候
    </div>

    <!-- 假设卡片流 -->
    <div v-if="!hypothesisGenerating && hypothesisList.length === 0" class="hyp-empty">
      <div class="hyp-empty-mark">∅</div>
      <div class="hyp-empty-t">暂无科研假设</div>
      <div class="hyp-empty-s">填写研究领域（或留空=全局）, 点击「生成假设」, AI 会基于知识库实体关系提出可验证的假设</div>
    </div>

    <div v-else class="hyp-grid">
      <div
        v-for="h in hypothesisList"
        :key="h.id"
        class="hyp-card"
        :class="'hyp-st-' + h.status"
      >
        <div class="hyp-card-top">
          <span class="hyp-stamp" :class="'hyp-stamp-' + h.status">{{ statusLabel(h.status) }}</span>
          <span v-if="h.priority" class="hyp-priority" :class="'hyp-pri-' + h.priority">{{ priorityLabel(h.priority) }}</span>
          <span class="hyp-conf">{{ Math.round((h.confidence || 0) * 100) }}%</span>
        </div>
        <div class="hyp-statement">{{ h.statement }}</div>
        <div v-if="h.rationale" class="hyp-block">
          <span class="hyp-block-label">推导依据</span>
          <p class="hyp-block-text">{{ h.rationale }}</p>
        </div>
        <div v-if="h.suggested_experiment" class="hyp-block">
          <span class="hyp-block-label">实验建议</span>
          <p class="hyp-block-text">{{ h.suggested_experiment }}</p>
        </div>
        <div class="hyp-card-foot">
          <span class="hyp-date">{{ fmtDate(h.created_at) }}</span>
          <div v-if="h.status === 'proposed'" class="hyp-actions">
            <button class="hyp-act ok" @click="validateHypothesis(h.id, 'validated')">✓ 验证通过</button>
            <button class="hyp-act no" @click="validateHypothesis(h.id, 'rejected')">✕ 否决</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="hypothesisTotal > 0" class="entity-pagination">
      <el-pagination
        :current-page="hypothesisPage"
        :page-size="20"
        :total="hypothesisTotal"
        layout="total, prev, pager, next"
        @current-change="(p) => $emit('page-change', p)"
      />
    </div>
  </div>
</template>

<script setup>
/**
 * KnowledgeHypothesisTab.vue — 科研假设 tab (v77 P2.6-E.3 拆分; 2026-09-13 墨线重做)
 *
 * 数据流契约不变:
 * - Props: hypothesisList / hypothesisTotal / hypothesisPage (来自 useKnowledge)
 * - Emits: page-change / refresh
 * - Expose: fetchHypotheses (父级 watch(activeTab) 调用)
 * - 取数: axios 直连 /api/v1/knowledge/hypotheses, request.js 拦截器注入鉴权
 *
 * 2026-09-13 修复:
 * - 初始 page_size=1 只拉 1 条且切 tab 不重拉 → onMounted 始终全量拉取
 * - 状态过滤从 el-select 改为墨线状态戳 chips
 * - 翻页需父级接线 @page-change (KnowledgeView 已补 handleHypothesisPageChange)
 */
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({
  hypothesisList: { type: Array, required: true },
  hypothesisTotal: { type: Number, required: true },
  hypothesisPage: { type: Number, required: true },
})

const emit = defineEmits(['page-change', 'refresh'])

const STATUS_LIST = [
  { value: 'proposed', label: '已提出' },
  { value: 'validated', label: '已验证' },
  { value: 'rejected', label: '已否决' },
]

const hypothesisFilter = ref({ status: '', priority: '' })
const hypothesisTopic = ref('')
const hypothesisGenerating = ref(false)
const refreshing = ref(false)

const statusLabel = (s) => s === 'validated' ? '已验证' : s === 'rejected' ? '已否决' : '已提出'
const priorityLabel = (p) => ({ high: '高优先', medium: '中优先', low: '低优先' }[p] || p)

const fmtDate = (d) => {
  if (!d) return ''
  const date = new Date(String(d).replace(' ', 'T'))
  if (isNaN(date)) return String(d).slice(0, 10)
  const now = new Date()
  const days = Math.floor((now - date) / 86400000)
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

const setStatus = (v) => {
  hypothesisFilter.value.status = v
  fetchHypotheses()
}

const fetchHypotheses = async () => {
  refreshing.value = true
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
  } finally {
    refreshing.value = false
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

const validateHypothesis = async (id, status) => {
  try {
    await axios.post(`/api/v1/knowledge/hypotheses/${id}/validate`, { status })
    ElMessage.success(status === 'validated' ? '已标记为验证通过' : '已否决')
    await fetchHypotheses()
  } catch (e) { ElMessage.error('操作失败') }
}

// 2026-09-13 修复: 挂载时始终全量拉取 — 旧版依赖父级 init 的 page_size=1
// (只拉 1 条) 且切 tab 无重拉 → 用户永远只看到 1 张假设卡
onMounted(() => {
  fetchHypotheses()
})

defineExpose({ fetchHypotheses })
</script>

<style scoped>
/* ═══ 墨线档案 · 页面配色④令牌自动继承 (.knowledge-view 覆盖) ═══ */
.hyp-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
  animation: fadeSlideUp var(--duration-slow, .3s) ease-out both;
}

/* 头部行 */
.hyp-head { display: flex; justify-content: space-between; align-items: flex-end; }
.hyp-eyebrow {
  font-family: Consolas, 'SFMono-Regular', monospace;
  font-size: 10px; letter-spacing: .3em; color: var(--color-text-secondary);
}
.hyp-title {
  font-family: 'Noto Serif SC', 'Songti SC', 'SimSun', serif;
  font-size: 21px; font-weight: 700; letter-spacing: .05em; line-height: 1.3;
  margin-top: 2px;
}
.hyp-refresh {
  font-size: 12.5px; padding: 7px 16px; border-radius: 3px; cursor: pointer;
  background: var(--color-bg-card); color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  display: inline-flex; align-items: center; gap: 7px;
}
.hyp-refresh:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); }
.hyp-refresh:disabled { opacity: .55; cursor: wait; }
.hyp-refresh-glyph { display: inline-block; }
.hyp-refresh-glyph.spin { animation: hyp-spin 1s linear infinite; }
@keyframes hyp-spin { to { transform: rotate(360deg); } }

/* 过滤行 */
.hyp-filters {
  display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between;
  background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: 4px;
  padding: 12px 16px;
}
.hyp-status-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.hyp-chip {
  font-size: 12.5px; padding: 4px 15px; border-radius: 9999px; cursor: pointer;
  border: 1px dashed var(--color-border); background: transparent; color: var(--color-text-secondary);
}
.hyp-chip:hover { border-color: var(--color-primary); color: var(--color-primary); }
.hyp-chip.on {
  border-style: solid; border-color: var(--color-primary);
  background: var(--color-primary); color: #fff; font-weight: 600;
}
.hyp-filter-right { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.hyp-select {
  background: var(--color-bg-card); color: var(--color-text-primary);
  border: 1px solid var(--color-border); border-radius: 3px;
  padding: 7px 10px; font-size: 13px; outline: none;
}
.hyp-input {
  background: var(--color-bg-card); color: var(--color-text-primary);
  border: 1px solid var(--color-border); border-radius: 3px;
  padding: 7px 12px; font-size: 13px; outline: none; width: 220px;
}
.hyp-input::placeholder { color: var(--color-text-placeholder); }
.hyp-input:focus { border-color: var(--color-primary); }
.hyp-gen {
  font-size: 13px; padding: 8px 18px; border-radius: 3px; cursor: pointer;
  background: var(--color-primary); color: #fff; border: none; font-weight: 600;
  white-space: nowrap;
}
.hyp-gen:hover:not(:disabled) { background: var(--color-primary-light); }
.hyp-gen:disabled { opacity: .6; cursor: wait; }

/* 生成中横幅 */
.hyp-generating {
  display: flex; align-items: center; gap: 10px;
  background: var(--color-bg-card); border: 1px dashed var(--color-primary);
  border-radius: 4px; padding: 12px 16px; color: var(--color-text-primary); font-size: 13px;
}
.spin-glyph { display: inline-block; animation: hyp-pulse 1.2s ease-in-out infinite; }
@keyframes hyp-pulse { 0%, 100% { opacity: .4; } 50% { opacity: 1; } }

/* 假设卡片流 */
.hyp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
}
.hyp-card {
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: 4px; padding: 16px 18px 13px;
  display: flex; flex-direction: column; gap: 10px;
  transition: transform .2s ease-out, box-shadow .2s ease-out;
}
.hyp-card:hover { transform: translateY(-2px); box-shadow: 0 8px 22px rgba(22, 35, 42, 0.12); }
.hyp-st-proposed { border-top: 3px solid #c99a3a; }
.hyp-st-validated { border-top: 3px solid var(--color-primary); }
.hyp-st-rejected { border-top: 3px solid var(--color-danger); }

.hyp-card-top { display: flex; align-items: center; gap: 8px; }
.hyp-stamp {
  font-family: Consolas, monospace; font-size: 10px; letter-spacing: .1em;
  border-radius: 2px; padding: 2px 9px;
}
.hyp-stamp-proposed { border: 1px dashed #c99a3a; color: #a37c22; }
.hyp-stamp-validated { border: 1px solid var(--color-primary); color: var(--color-primary); }
.hyp-stamp-rejected { border: 1px solid var(--color-danger); color: var(--color-danger); }
.hyp-priority {
  font-size: 11px; border: 1px dashed var(--line, var(--color-border));
  border-radius: 9999px; padding: 0 9px; color: var(--color-text-secondary);
}
.hyp-pri-high { color: var(--color-danger); border-color: rgba(245, 108, 108, .45); }
.hyp-conf {
  margin-left: auto; font-family: Consolas, monospace; font-size: 16px;
  font-weight: 700; color: var(--color-primary);
}

.hyp-statement {
  font-family: 'Noto Serif SC', 'Songti SC', 'SimSun', serif;
  font-size: 14.5px; font-weight: 700; line-height: 1.7;
}

.hyp-block { border-top: 1px dashed var(--color-border); padding-top: 8px; }
.hyp-block-label {
  font-family: Consolas, monospace; font-size: 10px; letter-spacing: .2em;
  color: var(--color-text-secondary);
}
.hyp-block-text {
  font-size: 12.5px; color: var(--color-text-regular); line-height: 1.7;
  margin: 4px 0 0; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;
}

.hyp-card-foot {
  margin-top: auto; padding-top: 9px; border-top: 1px dashed var(--color-border);
  display: flex; justify-content: space-between; align-items: center;
}
.hyp-date { font-family: Consolas, monospace; font-size: 10px; color: var(--color-text-secondary); }
.hyp-actions { display: flex; gap: 8px; }
.hyp-act {
  font-size: 12px; padding: 5px 13px; border-radius: 3px; cursor: pointer;
  font-weight: 600;
}
.hyp-act.ok {
  background: var(--color-primary); color: #fff; border: 1px solid var(--color-primary);
}
.hyp-act.ok:hover { background: var(--color-primary-light); }
.hyp-act.no {
  background: transparent; color: var(--color-danger); border: 1px solid rgba(245, 108, 108, .5);
}
.hyp-act.no:hover { background: rgba(245, 108, 108, .08); }

/* 空态 */
.hyp-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px; padding: 60px 20px; text-align: center;
  background: var(--color-bg-card); border: 1px dashed var(--color-border); border-radius: 4px;
}
.hyp-empty-mark { font-family: Consolas, monospace; font-size: 34px; color: var(--color-text-placeholder); }
.hyp-empty-t { font-weight: 700; font-size: 14px; }
.hyp-empty-s { font-size: 12px; color: var(--color-text-secondary); max-width: 460px; }

/* 分页 (与实体 tab 同款: 居中 + dashed 顶线 + 暗色可读) */
.entity-pagination {
  display: flex; justify-content: center;
  border-top: 1px dashed var(--color-border);
  padding: 8px 12px;
  background: var(--color-bg-card); border-radius: 4px;
}
</style>

<style>
/* 暗色主题分页可读性 (同实体 tab) */
[data-theme="dark"] .entity-pagination .el-pager li {
  color: var(--color-text-regular) !important;
}
[data-theme="dark"] .entity-pagination .el-pager li.is-active {
  color: #fff !important;
  background-color: var(--color-primary) !important;
}
</style>
