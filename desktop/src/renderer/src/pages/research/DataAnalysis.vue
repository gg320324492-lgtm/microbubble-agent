<script lang="ts">
import type { useDatasetStore as useDatasetStoreType } from '../../stores/research/dataset.store'

type DatasetStore = ReturnType<typeof useDatasetStoreType>

// Pinia actions cannot be changed here, so one flight is shared by every page
// instance observing the same store, including a replacement mount.
const reportFlights = new WeakMap<DatasetStore, Promise<void>>()

function acquireReportLoad(target: DatasetStore): Promise<void> {
  const current = reportFlights.get(target)
  if (current) return current

  const flight = target.loadReport()
  reportFlights.set(target, flight)
  const clear = () => {
    if (reportFlights.get(target) === flight) reportFlights.delete(target)
  }
  void flight.then(clear, clear)
  return flight
}
</script>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import ChartPanel from '../../components/research/ChartPanel.vue'
import ResearchPageShell from '../../components/research/ResearchPageShell.vue'
import ResearchPanel from '../../components/research/ResearchPanel.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import ScientificChart from '../../components/research/ScientificChart.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'
import type { FigureRecommendation, ModelFitResult } from '../../services/research/data-analysis.service'
import { useDatasetStore } from '../../stores/research/dataset.store'
import { buildKineticFitOption, describeKineticFit, kineticModelLabel } from '../../utils/scientific-chart'

const store = useDatasetStore()
const loadFailed = ref(false)
const importanceAvailable = ref(false)
let alive = true
let observationToken = 0

const sumFiniteValues = (values: Record<string, number> | undefined): number =>
  Object.values(values ?? {}).reduce((total, value) => total + (Number.isFinite(value) ? Math.max(0, value) : 0), 0)

const completeness = computed(() => {
  const value = store.quality?.completeness
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value ?? 0)) : 0
})
const missingValueCount = computed(() => sumFiniteValues(store.quality?.missingValues))
const outlierCount = computed(() => sumFiniteValues(store.quality?.outliers))
const warningCount = computed(() => store.quality?.warnings?.length ?? 0)
const importanceMaximum = computed(() => Math.max(0, ...store.importance.map(item => Number.isFinite(item.importance) ? item.importance : 0)))
const kineticModel = computed(() => store.models.find(model => model.model === 'first-order') ?? store.models[0] ?? null)
const kineticOption = computed(() => kineticModel.value ? buildKineticFitOption(kineticModel.value) : { series: [] })
const kineticChartDescription = computed(() => describeKineticFit(kineticModel.value))
const kineticSeriesEmpty = computed(() => {
  const series = kineticOption.value.series
  return !Array.isArray(series) || series.length === 0
})

const pageStatus = computed(() => {
  if (store.isLoading) return '分析中'
  if (loadFailed.value) return '分析异常'
  return store.report ? '分析完成' : '等待数据'
})

function safeFixed(value: number, digits: number): string {
  return Number.isFinite(value) ? value.toFixed(digits) : '待评估'
}

function isUnitValue(value: number): boolean {
  return Number.isFinite(value) && value >= 0 && value <= 1
}

function formatFitCredibility(value: number): string {
  return isUnitValue(value) ? value.toFixed(3) : '待评估'
}

function formatResidualRange(value: number): string {
  return Number.isFinite(value) && value >= 0 ? `±${value.toFixed(4)}` : '待评估'
}

function formatConfidence(value: number): string {
  return isUnitValue(value) ? `${Math.round(value * 100)}%` : '待评估'
}

function importanceWidth(value: number): string {
  if (!Number.isFinite(value) || importanceMaximum.value <= 0) return '0%'
  return `${Math.min(100, Math.max(0, value / importanceMaximum.value * 100))}%`
}

function figureType(figure: FigureRecommendation): 'line' | 'scatter' {
  return figure.type.includes('line') ? 'line' : 'scatter'
}

function isKineticFigure(figure: FigureRecommendation): boolean {
  return figure.type.includes('fit')
}

function modelQuality(model: ModelFitResult): { status: 'success' | 'warning' | 'neutral'; label: string } {
  if (!isUnitValue(model.rSquared)) return { status: 'neutral', label: '待评估' }
  if (model.rSquared >= 0.95) return { status: 'success', label: '拟合优秀' }
  if (model.rSquared >= 0.8) return { status: 'warning', label: '拟合可用' }
  return { status: 'neutral', label: '需要复核' }
}

function modelExplanation(model: ModelFitResult): string {
  if (model.model === 'first-order') return '一级动力学用于描述归一化浓度随时间的指数衰减，曲线仅由报告中的 k 参数推导。'
  if (model.model === 'zero-order') return '零级动力学结果保留用于模型比较；当前图表不推导缺少观测序列的零级曲线。'
  return '当前接口未提供该模型的可验证绘图规则，因此只展示报告中的拟合指标。'
}

async function loadReport(): Promise<void> {
  const token = ++observationToken
  loadFailed.value = false
  importanceAvailable.value = false
  try {
    await acquireReportLoad(store)
    if (alive && token === observationToken) importanceAvailable.value = true
  } catch {
    if (alive && token === observationToken) loadFailed.value = true
  }
}

onMounted(() => {
  void loadReport()
})

onUnmounted(() => {
  alive = false
  observationToken += 1
})
</script>

<template>
  <ResearchPageShell
    eyebrow="科研数据分析"
    title="数据分析工作区"
    description="读取现有分析报告，核查数据质量、变量贡献与动力学模型；本页不修改原始实验数据。"
    :status="pageStatus"
  >
    <div data-testid="data-analysis-workspace" class="analysis-workspace" aria-label="只读数据分析工作区">
      <ResearchState
        v-if="store.isLoading && !store.report"
        data-testid="data-analysis-state"
        state="loading"
        description="正在读取数据质量、统计结果与模型拟合报告。"
      />
      <ResearchState
        v-else-if="loadFailed && !store.report"
        data-testid="data-analysis-state"
        state="error"
        description="分析报告暂时不可用，已有数据不会被修改。"
        @retry="loadReport"
      />
      <ResearchState
        v-else-if="!store.report"
        data-testid="data-analysis-state"
        state="empty"
        description="请先通过既有数据流程导入实验数据，再回到此处查看分析结果。"
      />

      <template v-else>
        <ResearchState
          v-if="loadFailed"
          data-testid="data-analysis-retained-error"
          class="analysis-retained-error"
          state="error"
          description="部分分析数据读取失败，已保留成功读取的分析报告，可重新获取缺失结果。"
          @retry="loadReport"
        />
        <section class="analysis-overview" aria-label="数据质量与统计概览">
          <ResearchPanel title="数据质量" subtitle="所有指标均来自当前分析报告" tone="success">
            <div data-testid="analysis-quality" class="quality-grid">
              <article class="metric-card">
                <span>数据完整度</span>
                <strong>{{ (completeness * 100).toFixed(0) }}%</strong>
                <div class="metric-progress" role="progressbar" aria-label="数据完整度" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="Math.round(completeness * 100)"><span :style="{ width: `${completeness * 100}%` }" /></div>
              </article>
              <article class="metric-card"><span>缺失值</span><strong>{{ missingValueCount }}</strong><small>字段记录数</small></article>
              <article class="metric-card"><span>离群值</span><strong>{{ outlierCount }}</strong><small>报告识别数</small></article>
              <article class="metric-card"><span>质量警告</span><strong>{{ warningCount }}</strong><small>待复核事项</small></article>
            </div>
            <ul v-if="store.quality?.warnings.length" class="quality-warnings" aria-label="数据质量警告">
              <li v-for="warning in store.quality.warnings" :key="warning" class="quality-warning"><ResearchIcon name="warning" :size="15" />{{ warning }}</li>
            </ul>
          </ResearchPanel>

          <ResearchPanel title="统计分析" subtitle="报告输出的统计量与科研解释" tone="primary">
            <div v-if="store.statistics.length" class="statistics-list">
              <article v-for="statistic in store.statistics" :key="statistic.metric" :data-statistic="statistic.metric" class="statistic-row">
                <div><span>{{ statistic.metric }}</span><p>{{ statistic.interpretation }}</p></div>
                <strong>{{ statistic.value }}</strong>
              </article>
            </div>
            <p v-else class="section-empty">当前报告暂无统计结果</p>
          </ResearchPanel>
        </section>

        <ResearchPanel title="变量重要性" subtitle="读取当前分析状态中的变量贡献与可信信息" tone="primary">
          <div v-if="importanceAvailable && store.importance.length" class="importance-list">
            <article v-for="item in store.importance" :key="item.variable" :data-importance="item.variable" class="importance-row">
              <div class="importance-row__label"><strong>{{ item.variable }}</strong><span>{{ item.contribution }}</span></div>
              <div class="importance-row__track" aria-hidden="true"><span :style="{ width: importanceWidth(item.importance) }" /></div>
              <span class="importance-row__score">{{ safeFixed(item.importance, 2) }}</span>
              <span class="importance-row__confidence">可信度 {{ formatConfidence(item.confidence) }}</span>
            </article>
          </div>
          <p v-else class="section-empty">当前报告暂无变量重要性结果</p>
        </ResearchPanel>

        <ResearchPanel title="模型拟合" subtitle="指标来自报告，动力学曲线只使用有效 k 参数推导" tone="ai">
          <div v-if="store.models.length" class="model-grid">
            <article v-for="model in store.models" :key="model.model" :data-model="model.model" class="model-card">
              <header>
                <div><span class="model-card__eyebrow">动力学模型</span><h3>{{ kineticModelLabel(model.model) }}</h3></div>
                <StatusBadge :status="modelQuality(model).status" :label="modelQuality(model).label" />
              </header>
              <dl>
                <div><dt>拟合可信度 R²</dt><dd>{{ formatFitCredibility(model.rSquared) }}</dd></div>
                <div><dt>残差范围</dt><dd>{{ formatResidualRange(model.residualError) }}</dd></div>
                <div><dt>速率常数 k</dt><dd>{{ safeFixed(model.parameters.k, 4) }}</dd></div>
              </dl>
              <p>{{ modelExplanation(model) }}</p>
            </article>
          </div>
          <p v-else class="section-empty">当前报告暂无可比较模型</p>
        </ResearchPanel>

        <ResearchPanel title="科学图表" subtitle="图形建议与坐标含义来自当前报告" tone="primary">
          <div data-testid="analysis-figures" class="figure-grid">
            <ChartPanel v-for="figure in store.figures" :key="figure.title" :title="figure.title" :type="figureType(figure)" :description="`${figure.xVariable} × ${figure.yVariable}`">
              <ScientificChart v-if="isKineticFigure(figure)" :option="kineticOption" :empty="kineticSeriesEmpty" :ariaLabel="kineticChartDescription" />
              <div v-else class="figure-placeholder"><ResearchIcon name="data" :size="24" /><span>该图形建议来自分析报告，当前接口未提供可绘制的观测序列</span></div>
            </ChartPanel>
            <p v-if="!store.figures.length" class="section-empty">当前报告暂无图形建议</p>
          </div>
        </ResearchPanel>

        <ResearchPanel title="科学解读" subtitle="基于分析报告返回的结论与可信度" tone="success">
          <div v-if="store.conclusions.length" class="conclusion-list">
            <article v-for="(conclusion, index) in store.conclusions" :key="`${conclusion.observation}-${index}`" :data-conclusion="index" class="conclusion-card">
              <span class="conclusion-card__index">{{ String(index + 1).padStart(2, '0') }}</span>
              <div><h3>{{ conclusion.observation }}</h3><p>{{ conclusion.interpretation }}</p></div>
              <strong>{{ formatConfidence(conclusion.confidence) }}</strong>
            </article>
          </div>
          <p v-else class="section-empty">当前报告暂无科学结论</p>
        </ResearchPanel>
      </template>
    </div>
  </ResearchPageShell>
</template>

<style scoped>
.analysis-workspace { display: grid; min-width: 0; gap: var(--research-grid-gap); }
.analysis-retained-error { min-height: 148px; }
.analysis-overview { display: grid; min-width: 0; grid-template-columns: minmax(0, .9fr) minmax(0, 1.1fr); gap: var(--research-grid-gap); }
.quality-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--research-space-3); }
.metric-card { min-width: 0; padding: var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-panel); }
.metric-card > span, .metric-card small { display: block; color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.metric-card strong { display: block; margin-block: var(--research-space-1); color: var(--research-text-primary); font-family: var(--research-font-mono); font-size: var(--research-text-section-title); font-variant-numeric: tabular-nums; }
.metric-progress { height: 6px; margin-block-start: var(--research-space-3); overflow: hidden; border-radius: var(--research-radius-pill); background: var(--research-border-subtle); }
.metric-progress span { display: block; height: 100%; border-radius: inherit; background: var(--research-success-500); }
.quality-warnings { display: grid; gap: var(--research-space-2); margin: var(--research-space-4) 0 0; padding: 0; list-style: none; }
.quality-warning { display: flex; align-items: center; gap: var(--research-space-2); color: var(--research-text-primary); font-size: var(--research-text-sm); }
.quality-warning svg { color: var(--research-warning-600); }
.statistics-list, .importance-list, .conclusion-list { display: grid; gap: var(--research-space-3); }
.statistic-row { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--research-space-4); padding-block-end: var(--research-space-3); border-block-end: 1px solid var(--research-divider); }
.statistic-row:last-child { padding-block-end: 0; border-block-end: 0; }
.statistic-row span { color: var(--research-text-primary); font-size: var(--research-text-body); font-weight: var(--research-font-weight-medium); }
.statistic-row p { margin: var(--research-space-1) 0 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.statistic-row strong { flex: 0 0 auto; color: var(--research-primary-700); font-family: var(--research-font-mono); font-size: var(--research-text-card-title); font-variant-numeric: tabular-nums; }
.importance-row { display: grid; align-items: center; grid-template-columns: minmax(140px, .8fr) minmax(180px, 1.8fr) 54px 112px; gap: var(--research-space-3); }
.importance-row__label { min-width: 0; }
.importance-row__label strong, .importance-row__label span { display: block; }
.importance-row__label strong { color: var(--research-text-primary); font-size: var(--research-text-body); }
.importance-row__label span, .importance-row__confidence { color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.importance-row__track { height: 8px; overflow: hidden; border-radius: var(--research-radius-pill); background: var(--research-primary-50); }
.importance-row__track span { display: block; height: 100%; border-radius: inherit; background: var(--research-primary-500); }
.importance-row__score { color: var(--research-primary-700); font-family: var(--research-font-mono); font-weight: var(--research-font-weight-semibold); text-align: end; }
.importance-row__confidence { text-align: end; }
.model-grid, .figure-grid { display: grid; min-width: 0; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--research-grid-gap); }
.model-card { min-width: 0; padding: var(--research-space-5); border: 1px solid var(--research-ai-100); border-radius: var(--research-radius-card); background: var(--research-ai-50); }
.model-card header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--research-space-3); }
.model-card__eyebrow { color: var(--research-ai-600); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); letter-spacing: .06em; }
.model-card h3 { margin: var(--research-space-1) 0 0; color: var(--research-text-primary); font-size: var(--research-text-card-title); }
.model-card dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--research-space-2); margin: var(--research-space-4) 0; }
.model-card dl div { padding: var(--research-space-3); border-radius: var(--research-radius-input); background: var(--research-bg-card); }
.model-card dt { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.model-card dd { margin: var(--research-space-1) 0 0; color: var(--research-text-primary); font-family: var(--research-font-mono); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); }
.model-card > p { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.figure-placeholder { display: flex; min-height: 300px; align-items: center; justify-content: center; flex-direction: column; gap: var(--research-space-3); color: var(--research-text-secondary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); text-align: center; }
.conclusion-card { display: grid; align-items: start; grid-template-columns: 40px minmax(0, 1fr) auto; gap: var(--research-space-3); padding: var(--research-space-4); border: 1px solid var(--research-success-100); border-radius: var(--research-radius-card); background: var(--research-success-50); }
.conclusion-card__index { color: var(--research-success-600); font-family: var(--research-font-mono); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); }
.conclusion-card h3 { margin: 0; color: var(--research-text-primary); font-size: var(--research-text-body); }
.conclusion-card p { margin: var(--research-space-1) 0 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.conclusion-card > strong { color: var(--research-success-700); font-family: var(--research-font-mono); font-size: var(--research-text-sm); }
.section-empty { margin: 0; padding: var(--research-space-6); color: var(--research-text-secondary); font-size: var(--research-text-sm); text-align: center; }

@media (max-width: 1180px) {
  .analysis-overview { grid-template-columns: minmax(0, 1fr); }
  .importance-row { grid-template-columns: minmax(130px, .8fr) minmax(150px, 1.5fr) 48px 100px; }
}

@media (max-width: 900px) {
  .model-grid, .figure-grid { grid-template-columns: minmax(0, 1fr); }
  .importance-row { grid-template-columns: minmax(0, 1fr) auto; }
  .importance-row__track { grid-column: 1 / -1; grid-row: 2; }
  .importance-row__confidence { grid-column: 1 / -1; text-align: start; }
}

@media (min-width: 1720px) {
  .quality-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
</style>
