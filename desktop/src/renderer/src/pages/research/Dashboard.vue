<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import type { ResearchIconName } from '../../components/icons/research-icons'
import ResearchPageShell from '../../components/research/ResearchPageShell.vue'
import ResearchPanel from '../../components/research/ResearchPanel.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import ScientificMetric from '../../components/research/ScientificMetric.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'
import { useDatasetStore } from '../../stores/research/dataset.store'
import { useKnowledgeStore } from '../../stores/research/knowledge.store'
import { useManuscriptStore } from '../../stores/research/manuscript.store'
import { useProjectStore } from '../../stores/research/project.store'

const projectStore = useProjectStore()
const knowledgeStore = useKnowledgeStore()
const datasetStore = useDatasetStore()
const manuscriptStore = useManuscriptStore()
const loadError = ref('')

const projectProgress = computed(() => Math.round(projectStore.currentProject.progress * 100))
const isLoading = computed(() => knowledgeStore.isLoading || datasetStore.isLoading || manuscriptStore.isLoading)
const hasResearchData = computed(() => knowledgeStore.totalDocuments > 0 || datasetStore.report !== null || manuscriptStore.manuscript !== null)
const projectStatus = computed(() => {
  const labels = { active: '进行中', planning: '规划中', completed: '已完成', paused: '已暂停' } as const
  return labels[projectStore.currentProject.status]
})
const aiCurrentTask = computed(() => {
  if (isLoading.value) return '正在同步项目证据与分析结果'
  if (loadError.value) return '数据同步需要重试'
  return hasResearchData.value ? '研究数据已完成同步' : '等待导入科研数据'
})

interface ResearchActivity {
  label: string
  detail: string
  icon: ResearchIconName
  ready: boolean
}

const researchActivities = computed<ResearchActivity[]>(() => [
  {
    label: '文献证据整理',
    detail: knowledgeStore.totalDocuments > 0 ? `已汇总 ${knowledgeStore.totalDocuments} 篇文献` : '尚无可整理的文献',
    icon: 'literature',
    ready: knowledgeStore.totalDocuments > 0
  },
  {
    label: '数据模型分析',
    detail: datasetStore.models.length > 0 ? `已获得 ${datasetStore.models.length} 个拟合模型` : '尚无模型分析结果',
    icon: 'data',
    ready: datasetStore.models.length > 0
  },
  {
    label: '论文质量审阅',
    detail: manuscriptStore.manuscript ? `当前有 ${manuscriptStore.issueCount} 项写作问题` : '尚无论文草稿',
    icon: 'manuscript',
    ready: manuscriptStore.manuscript !== null
  }
])

async function loadDashboard(): Promise<void> {
  loadError.value = ''
  try {
    await Promise.all([
      knowledgeStore.loadDocuments(),
      datasetStore.loadReport(),
      manuscriptStore.loadManuscript()
    ])
  } catch (error) {
    console.error('[科研首页] 科研数据加载失败', error)
    loadError.value = '科研数据分析失败，请重试。'
  }
}

onMounted(loadDashboard)
</script>

<template>
  <ResearchPageShell
    eyebrow="当前科研项目"
    title="科研首页"
    description="聚合项目证据、分析质量与写作进展，帮助你把握下一步研究重点。"
    :status="projectStatus"
  >
    <section class="dashboard__hero" aria-labelledby="dashboard-project-title">
      <div class="dashboard__hero-main">
        <span class="dashboard__hero-icon" aria-hidden="true"><ResearchIcon name="project" :size="22" /></span>
        <div>
          <p>当前科研项目</p>
          <h2 id="dashboard-project-title">{{ projectStore.currentProject.name }}</h2>
          <span>{{ projectStore.currentProject.description }}</span>
        </div>
      </div>
      <dl class="dashboard__hero-meta">
        <div><dt>研究方向</dt><dd>{{ projectStore.currentProject.domain }}</dd></div>
        <div><dt>AI 当前任务</dt><dd>{{ aiCurrentTask }}</dd></div>
      </dl>
      <div class="dashboard__progress-row">
        <span>项目进度</span>
        <strong>{{ projectProgress }}%</strong>
        <div role="progressbar" aria-label="项目进度" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="projectProgress">
          <span :style="{ width: `${projectProgress}%` }" />
        </div>
      </div>
    </section>

    <section class="dashboard__metrics" aria-label="科研关键指标">
      <ScientificMetric label="文献证据" :value="String(knowledgeStore.totalDocuments)" unit="篇" trend="stable" :trend-text="knowledgeStore.totalDocuments > 0 ? '已纳入证据库' : '等待导入'" />
      <ScientificMetric label="实验进展" :value="String(projectStore.currentProject.stats.experiments)" unit="次" trend="stable" :trend-text="projectStatus" />
      <ScientificMetric label="数据质量" :value="datasetStore.quality ? `${Math.round(datasetStore.quality.completeness * 100)}` : '—'" unit="%" trend="stable" :trend-text="datasetStore.quality ? `${datasetStore.quality.warnings.length} 项质量提醒` : '暂无分析'" />
      <ScientificMetric label="论文状态" :value="projectStore.currentProject.stats.manuscriptStatus" trend="stable" :trend-text="manuscriptStore.manuscript ? `${manuscriptStore.issueCount} 项待改进` : '暂无草稿'" />
    </section>

    <ResearchState v-if="isLoading" state="loading" />
    <ResearchState v-else-if="loadError" state="error" :description="loadError" @retry="loadDashboard" />
    <ResearchState v-else-if="!hasResearchData" state="empty" />

    <div v-else class="dashboard__workspace">
      <ResearchPanel title="AI 研究活动" subtitle="只呈现当前状态数据已确认的工作结果" tone="ai">
        <div class="dashboard__activity-list">
          <article v-for="activity in researchActivities" :key="activity.label" class="dashboard__activity">
            <span class="dashboard__activity-icon" aria-hidden="true"><ResearchIcon :name="activity.icon" :size="18" /></span>
            <div><strong>{{ activity.label }}</strong><p>{{ activity.detail }}</p></div>
            <StatusBadge :status="activity.ready ? 'success' : 'neutral'" :label="activity.ready ? '已同步' : '待数据'" />
          </article>
        </div>
      </ResearchPanel>

      <ResearchPanel title="研究洞察" subtitle="基于当前数据分析结论，不生成无证据判断" tone="primary">
        <div v-if="datasetStore.conclusions.length" class="dashboard__insights">
          <article v-for="insight in datasetStore.conclusions" :key="insight.observation" class="dashboard__insight">
            <div class="dashboard__insight-heading">
              <ResearchIcon name="evidence" :size="17" />
              <strong>{{ insight.observation }}</strong>
              <span>{{ Math.round(insight.confidence * 100) }}% 置信度</span>
            </div>
            <p>{{ insight.interpretation }}</p>
          </article>
        </div>
        <ResearchState v-else state="empty" title="暂无研究洞察" description="完成数据分析后，这里会呈现有依据的科研结论。" />
      </ResearchPanel>
    </div>
  </ResearchPageShell>
</template>

<style scoped>
.dashboard__hero { min-width: 0; margin-block-end: var(--research-space-5); padding: var(--research-space-6); border: 1px solid var(--research-primary-100); border-radius: var(--research-radius-panel); background: var(--research-bg-card); box-shadow: var(--research-shadow-soft); }
.dashboard__hero-main { display: flex; align-items: flex-start; gap: var(--research-space-4); }
.dashboard__hero-icon { display: grid; width: 44px; height: 44px; flex: 0 0 44px; place-items: center; border-radius: var(--research-radius-card); background: var(--research-primary-50); color: var(--research-primary-600); }
.dashboard__hero-main p { margin: 0 0 var(--research-space-1); color: var(--research-primary-600); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); }
.dashboard__hero-main h2 { margin: 0; color: var(--research-text-primary); font-size: var(--research-text-page-title); line-height: var(--research-line-height-tight); }
.dashboard__hero-main div > span { display: block; margin-block-start: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-body); line-height: var(--research-line-height-body); }
.dashboard__hero-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--research-space-4); margin-block: var(--research-space-5); }
.dashboard__hero-meta div { padding: var(--research-space-3) var(--research-space-4); border-radius: var(--research-radius-button); background: var(--research-bg-panel); }
.dashboard__hero-meta dt { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.dashboard__hero-meta dd { margin: var(--research-space-1) 0 0; color: var(--research-text-primary); font-size: 13px; font-weight: var(--research-font-weight-medium); }
.dashboard__progress-row { display: grid; grid-template-columns: auto auto minmax(0, 1fr); align-items: center; gap: var(--research-space-3); color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.dashboard__progress-row strong { color: var(--research-primary-700); font-family: var(--research-font-mono); }
.dashboard__progress-row > div { height: 7px; overflow: hidden; border-radius: var(--research-radius-pill); background: var(--research-primary-100); }
.dashboard__progress-row > div span { display: block; height: 100%; border-radius: inherit; background: var(--research-primary-600); transition: width var(--research-duration-slow) var(--research-ease-emphasized); }
.dashboard__metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--research-grid-gap); margin-block-end: var(--research-space-5); }
.dashboard__workspace { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.08fr); gap: var(--research-grid-gap); min-width: 0; }
.dashboard__activity-list, .dashboard__insights { display: grid; gap: var(--research-space-3); }
.dashboard__activity { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: var(--research-space-3); padding-block-end: var(--research-space-3); border-block-end: 1px solid var(--research-divider); }
.dashboard__activity:last-child { padding-block-end: 0; border: 0; }
.dashboard__activity-icon { display: grid; width: 34px; height: 34px; place-items: center; border-radius: var(--research-radius-button); background: var(--research-ai-50); color: var(--research-ai-600); }
.dashboard__activity strong { color: var(--research-text-primary); font-size: 13px; }
.dashboard__activity p { margin: var(--research-space-1) 0 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.dashboard__insight { padding: var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-panel); }
.dashboard__insight-heading { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: var(--research-space-2); color: var(--research-primary-600); }
.dashboard__insight-heading strong { color: var(--research-text-primary); font-size: 13px; }
.dashboard__insight-heading span { color: var(--research-success-700); font-family: var(--research-font-mono); font-size: var(--research-text-xs); }
.dashboard__insight p { margin: var(--research-space-2) 0 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }

@media (max-width: 1480px) {
  .dashboard__metrics { gap: var(--research-space-3); }
  .dashboard__workspace { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
}
@media (min-width: 1720px) {
  .dashboard__hero { padding: var(--research-space-7); }
}
@media (prefers-reduced-motion: reduce) {
  .dashboard__progress-row > div span { transition: none; }
}
</style>
