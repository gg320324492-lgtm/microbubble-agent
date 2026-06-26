<template>
  <section id="paper-extractions" class="extraction-panel">
    <header class="extraction-header">
      <div class="extraction-title-wrap">
        <h2 class="extraction-title">🖼️ 多模态提取</h2>
        <div v-if="imageStats" class="extraction-stats">
          <el-tag size="small" type="success" effect="light" v-if="imageStats.done">
            <el-icon><CircleCheck /></el-icon> OCR 完成 {{ imageStats.done }}
          </el-tag>
          <el-tag size="small" type="danger" effect="light" v-if="imageStats.failed">
            <el-icon><CircleClose /></el-icon> 失败 {{ imageStats.failed }}
          </el-tag>
          <el-tag size="small" type="warning" effect="light" v-if="imageStats.pending">
            <el-icon><Loading /></el-icon> 处理中 {{ imageStats.pending }}
          </el-tag>
        </div>
      </div>
      <el-button
        v-if="!hasAnyExtraction"
        size="small"
        type="primary"
        plain
        :loading="extracting"
        @click="$emit('extract')"
      >
        <el-icon><MagicStick /></el-icon> 触发提取
      </el-button>
    </header>

    <!-- 无任何提取时：轻量空状态 -->
    <div v-if="!hasAnyExtraction && !loading" class="extraction-empty">
      <el-icon class="extraction-empty-icon"><Picture /></el-icon>
      <p class="extraction-empty-text">该知识条目尚未触发多模态提取（仅 PDF/PPTX 文件可提取）</p>
      <p class="extraction-empty-hint">点击右上角"触发提取"按钮开始解析图片、公式、表格、图表</p>
    </div>

    <div v-else-if="loading" class="extraction-loading">
      <el-skeleton :rows="3" animated />
    </div>

    <!-- 有内容时：tab 切换 -->
    <el-tabs v-else v-model="activeTab" class="extraction-tabs">
      <el-tab-pane name="images" :label="`核心图表 (${coreFigures.length})`" lazy>
        <div v-if="coreFigures.length" class="extraction-grid">
          <FigureCard
            v-for="fig in coreFigures"
            :key="fig.id"
            :figure="fig"
            :figure-no="fig.figureNo || `图 ${fig.imageId || fig.id}`"
            :caption="fig.caption"
            compact
          />
        </div>
        <el-empty v-else description="该知识条目暂无核心图表" :image-size="60" />
      </el-tab-pane>

      <!-- 封面/logo 弱化区（折叠） -->
      <el-tab-pane v-if="coverFigures.length" name="others" :label="`其他图片 (${coverFigures.length})`" lazy>
        <div class="cover-info">
          <el-icon class="cover-info-icon"><InfoFilled /></el-icon>
          <span>以下为封面、出版信息或装饰图片，论文核心内容不依赖这些图。</span>
        </div>
        <div class="extraction-grid extraction-grid-secondary">
          <FigureCard
            v-for="fig in coverFigures"
            :key="fig.id"
            :figure="fig"
            :figure-no="fig.label || '图'"
            :caption="fig.caption"
            compact
          />
        </div>
      </el-tab-pane>

      <el-tab-pane name="formulas" :label="`公式 (${formulas.length})`" lazy>
        <div v-if="formulas.length" class="extraction-list">
          <FormulaBlock
            v-for="f in formulas"
            :key="f.id"
            :formula="f"
            compact
          />
        </div>
        <el-empty v-else description="暂无公式提取" :image-size="60" />
      </el-tab-pane>

      <el-tab-pane name="tables" :label="`表格 (${tables.length})`" lazy>
        <div v-if="tables.length" class="extraction-list">
          <TableCard
            v-for="t in tables"
            :key="t.id"
            :table="t"
            compact
          />
        </div>
        <el-empty v-else description="暂无表格提取" :image-size="60" />
      </el-tab-pane>

      <el-tab-pane name="charts" :label="`图表 (${charts.length})`" lazy>
        <div v-if="charts.length" class="chart-list">
          <div v-for="c in charts" :key="c.id" class="chart-card">
            <div class="chart-header">
              <el-icon><DataAnalysis /></el-icon>
              <span class="chart-type">{{ typeLabel(c.kind) }}</span>
              <span v-if="c.page" class="chart-page">P{{ c.page }}</span>
              <span v-if="c.confidence" class="chart-confidence">置信度 {{ Math.round(c.confidence * 100) }}%</span>
            </div>
            <div class="chart-description">{{ c.description || c.contentText || '（无描述）' }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无图表描述" :image-size="60" />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<script setup>
import { ref, computed } from 'vue'
import { CircleCheck, CircleClose, Loading, MagicStick, Picture, DataAnalysis, InfoFilled } from '@element-plus/icons-vue'
import FigureCard from './FigureCard.vue'
import FormulaBlock from './FormulaBlock.vue'
import TableCard from './TableCard.vue'

const props = defineProps({
  paper: { type: Object, required: true },
  figures: { type: Array, default: () => [] },
  formulas: { type: Array, default: () => [] },
  tables: { type: Array, default: () => [] },
  charts: { type: Array, default: () => [] },
  imageStats: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  extracting: { type: Boolean, default: false },
})

defineEmits(['extract'])

const activeTab = ref('images')

// 核心图（figure 类型，非 cover/logo）
//   v28 step 109.15: 过滤 vision-page* 占位（id 是字符串占位，src 为空）
const coreFigures = computed(() => props.figures.filter(f => {
  if (f.kind === 'cover' || f.kind === 'logo') return false
  if (typeof f.id === 'string' && f.id.startsWith('vision-page')) return false
  if (!f.src) return false  // 没 src 的占位不显示
  return !f.kind || f.kind === 'figure'
}))
// 封面/出版信息/logo 弱化区
const coverFigures = computed(() => props.figures.filter(f => f.kind === 'cover' || f.kind === 'logo'))

const hasAnyExtraction = computed(() => {
  return props.figures.length > 0 ||
    props.formulas.length > 0 ||
    props.tables.length > 0 ||
    props.charts.length > 0
})

const typeLabel = (kind) => ({
  formula: '公式',
  table: '表格',
  chart: '图表',
  image_block: 'OCR 块',
}[kind] || kind)
</script>

<style scoped>
.extraction-panel {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  padding: 20px 24px;
  margin: 0 0 24px;
  box-shadow: var(--shadow-md);
}

.extraction-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.extraction-title-wrap {
  flex: 1;
  min-width: 0;
}

.extraction-title {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.extraction-stats {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.extraction-empty {
  text-align: center;
  padding: 32px 20px;
  color: var(--color-text-placeholder);
}

.extraction-empty-icon {
  font-size: 36px;
  color: #D1D5DB;
  margin-bottom: 8px;
}

.extraction-empty-text {
  font-size: 14px;
  margin: 8px 0 4px;
  color: var(--color-text-secondary);
}

.extraction-empty-hint {
  font-size: 12px;
  color: var(--color-text-placeholder);
  margin: 0;
}

.extraction-loading {
  padding: 16px 0;
}

/* 缩略图网格：每张卡片 16:10 比例 */
.extraction-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.extraction-grid-secondary {
  opacity: 0.7;
  margin-top: 8px;
}

.cover-info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #F9FAFB;
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.cover-info-icon {
  color: var(--color-text-placeholder);
}

.extraction-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chart-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chart-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-left: 3px solid #F59E0B;
  border-radius: 8px;
  padding: 12px 16px;
  transition: box-shadow 0.2s;
}

.chart-card:hover {
  box-shadow: var(--shadow-sm);
}

.chart-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--color-text-secondary);
  flex-wrap: wrap;
}

.chart-type {
  font-weight: 600;
  color: #F59E0B;
}

.chart-page {
  background: #F3F4F6;
  color: var(--color-text-secondary);
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 11px;
}

.chart-confidence {
  color: var(--color-text-placeholder);
  font-size: 11px;
}

.chart-description {
  font-size: 13px;
  line-height: 1.7;
  color: #4B5563;
  word-break: break-word;
  white-space: pre-wrap;
}
</style>
