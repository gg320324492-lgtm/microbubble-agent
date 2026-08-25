<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useDatasetStore } from '../../stores/research/dataset.store'
import { useDataAnalysisLoader, type AnalysisReport, type VariableImportance } from '../../composables/data-analysis-loader'
import ResearchPageHeader from '../../components/research/ResearchPageHeader.vue'
import ResearchPanel from '../../components/research/ResearchPanel.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import ResearchMetricPanel from '../../components/research/ResearchMetricPanel.vue'
import DatasetPanel, { type DatasetInfo } from '../../components/research/DatasetPanel.vue'
import DataQualityPanel from '../../components/research/DataQualityPanel.vue'
import ScientificChartPanel from '../../components/research/ScientificChartPanel.vue'
import ModelFitPanel from '../../components/research/ModelFitPanel.vue'
import StatisticalSummaryPanel from '../../components/research/StatisticalSummaryPanel.vue'
import InterpretationPanel from '../../components/research/InterpretationPanel.vue'

const store = useDatasetStore()
const { fetchAnalysisReport, fetchVariableImportance } = useDataAnalysisLoader()

async function loadFromService(): Promise<void> {
  store.setLoading(true)
  store.setError('')
  try {
    const [report, importance] = await Promise.all([fetchAnalysisReport(), fetchVariableImportance()])
    store.setReport(report as AnalysisReport)
    store.setImportance(importance as VariableImportance[])
  } catch (err) {
    store.setError(err instanceof Error ? err.message : '分析数据加载失败')
  } finally {
    store.setLoading(false)
  }
}

async function loadReport(): Promise<void> {
  return loadFromService()
}

onMounted(() => {
  void loadFromService()
})

const datasetInfo = computed<DatasetInfo | null>(() => {
  const report = store.report as unknown as { variables?: string[] } | null
  if (!report) return null
  const variables = report.variables
  return {
    name: '科研数据集',
    description: '当前分析的数据集摘要',
    rows: 120,
    columns: variables?.length ?? 0,
    variables: variables ?? []
  }
})

const totalRows = computed(() => {
  const report = store.report as unknown as { rows?: number } | null
  return report?.rows ?? 0
})

const completenessPct = computed(() => {
  const q = store.quality
  if (!q) return 0
  return Math.round((q as { completeness: number }).completeness * 100)
})

const variableImportance = computed(() => {
  const importance = store.importance ?? []
  return [...importance].sort((a, b) => {
    const ai = (a as unknown as { importance: number }).importance
    const bi = (b as unknown as { importance: number }).importance
    return bi - ai
  })
})

const importanceMetrics = computed(() => {
  const top = variableImportance.value[0]
  if (!top) return []
  const topName = (top as unknown as { variable: string }).variable
  return [
    { label: '重要变量数', value: String(variableImportance.value.length) },
    { label: '首要变量', value: topName ?? '—' }
  ]
})
</script>

<template>
  <main class="data-analysis analysis-overview" data-testid="data-analysis-workspace" data-research-theme="analysis" aria-label="数据分析工作台" data-section="数据分析工作区">
    <ResearchState
      v-if="store.isLoading"
      data-testid="data-analysis-state"
      state="loading"
      title="加载分析数据中"
      description="正在从分析服务读取内容"
    />

    <ResearchState
      v-else-if="store.errorMessage"
      data-testid="data-analysis-state"
      state="error"
      title="分析数据加载失败"
      :description="store.errorMessage"
      @retry="loadReport"
    />

    <ResearchState
      v-else-if="store.isEmpty"
      data-testid="data-analysis-state"
      state="empty"
      title="暂无数据"
      description="请先运行数据分析"
    />

    <template v-else>
      <ResearchPageHeader title="数据分析工作台" subtitle="科研数据三栏分析视图" />

      <section class="data-analysis__meta" aria-label="分析元信息">
        <h2 class="data-analysis__meta-title">分析元信息</h2>
        <div class="data-analysis__meta-grid">
          <ResearchPanel title="数据集摘要">
            <p class="data-analysis__meta-label">总行数</p>
            <p class="data-analysis__meta-value">{{ totalRows }}</p>
            <p class="data-analysis__meta-label">完整度</p>
            <p class="data-analysis__meta-value">{{ completenessPct }}%</p>
          </ResearchPanel>
          <ResearchPanel title="重要变量">
            <ResearchMetricPanel
              v-if="importanceMetrics.length > 0"
              :metrics="importanceMetrics"
              title="Top 重要变量"
            />
            <p v-else class="data-analysis__empty-inline" role="status">暂无重要变量</p>
          </ResearchPanel>
        </div>
      </section>

      <section class="data-analysis__grid" aria-label="三栏工作区">
        <aside class="data-analysis__col data-analysis__col--dataset" aria-label="数据集管理">
          <DatasetPanel :dataset="datasetInfo" aria-label="数据集管理面板" />
          <DataQualityPanel :quality="store.quality" aria-label="数据质量面板" />
        </aside>

        <section class="data-analysis__col data-analysis__col--analysis" aria-label="分析工作区">
          <StatisticalSummaryPanel :statistics="store.statistics" aria-label="统计摘要面板" />
          <ScientificChartPanel :figures="store.figures" aria-label="科学图表规划面板" />
          <ModelFitPanel :models="store.models" aria-label="模型拟合面板" />
        </section>

        <aside class="data-analysis__col data-analysis__col--interpretation" aria-label="科学解读 / 科学解释">
          <InterpretationPanel :conclusions="store.conclusions" aria-label="AI 解释面板 · 科学解读" />
        </aside>
      </section>
    </template>
  </main>
</template>

<style scoped>
.data-analysis {
  min-width: 0;
  min-height: 100%;
  max-width: var(--research-content-max-width, 1680px);
  margin: 0 auto;
  padding: var(--research-page-gutter, 24px);
  overflow-x: clip;
  background: var(--research-bg-main);
}
.analysis-overview {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--research-grid-gap);
}
.data-analysis:focus-visible {
  outline: none;
}
.data-analysis__meta {
  margin-bottom: var(--research-space-6);
  min-width: 0;
}
.data-analysis__meta-title {
  font-size: var(--research-text-card-title);
  font-weight: var(--research-font-weight-semibold);
  color: var(--research-text-primary);
  margin: 0 0 var(--research-space-3);
}
.data-analysis__meta-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--research-grid-gap);
}
.data-analysis__meta-label {
  font-size: var(--research-text-xs);
  color: var(--research-text-muted);
  margin: 0 0 var(--research-space-1);
}
.data-analysis__meta-value {
  font-size: var(--research-text-body);
  color: var(--research-text-primary);
  margin: 0 0 var(--research-space-3);
}
.data-analysis__empty-inline {
  font-size: var(--research-text-sm);
  color: var(--research-text-muted);
  margin: 0;
}
.data-analysis__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}
.data-analysis__col {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.data-analysis__col--dataset,
.data-analysis__col--interpretation {
  align-items: stretch;
}
@media (max-width: 1480px) {
  .data-analysis__grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .data-analysis__meta-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (min-width: 1720px) {
  .data-analysis__grid {
    grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr) minmax(0, 1.65fr);
  }
  .data-analysis__meta-grid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}
@media (prefers-reduced-motion: reduce) {
  .data-analysis *,
  .data-analysis *::before,
  .data-analysis *::after {
    animation: none !important;
    transition: none !important;
  }
}
</style>
