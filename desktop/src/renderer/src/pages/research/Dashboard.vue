<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AgentStatusPanel from '../../components/research/AgentStatusPanel.vue'
import DeviceStatusPanel from '../../components/research/DeviceStatusPanel.vue'
import EvidencePanel from '../../components/research/EvidencePanel.vue'
import ResearchMetricPanel from '../../components/research/ResearchMetricPanel.vue'
import ResearchPageHeader from '../../components/research/ResearchPageHeader.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import ResearchTimeline from '../../components/research/ResearchTimeline.vue'
import type { ResearchAgentStatusItem } from '../../components/research/AgentStatusPanel.vue'
import type { CitationItem, EvidenceItem } from '../../components/research/EvidencePanel.vue'
import type { ResearchMetricItem } from '../../components/research/ResearchMetricPanel.vue'
import type { ResearchTimelineItem } from '../../components/research/ResearchTimeline.vue'
import { useDatasetStore } from '../../stores/research/dataset.store'
import { useKnowledgeStore } from '../../stores/research/knowledge.store'
import { useManuscriptStore } from '../../stores/research/manuscript.store'
import { useProjectStore } from '../../stores/research/project.store'

const projectStore = useProjectStore()
const knowledgeStore = useKnowledgeStore()
const datasetStore = useDatasetStore()
const manuscriptStore = useManuscriptStore()
const loadError = ref('')

// [类 20.193] 2026-08-27: currentProject 可能为 null (用户首次启动 / 未迁移数据).
// 之前 Dashboard 直接 .name/.domain/.description 抛 TypeError → 整个 dashboard 渲染空白.
// 改: 包装 v-if, 没项目时显示空态. 同步初始化 loadProjects() 拉数据.
const hasProject = computed(() => projectStore.currentProject !== null)
const projectProgress = computed(() => projectStore.currentProject ? Math.round(projectStore.currentProject.progress * 100) : 0)
const isLoading = computed(() => knowledgeStore.isLoading || datasetStore.isLoading || manuscriptStore.isLoading)
const hasResearchData = computed(() => knowledgeStore.totalDocuments > 0 || datasetStore.report !== null || manuscriptStore.manuscript !== null)
const projectStatus = computed(() => {
  if (!projectStore.currentProject) return '未选择'
  const labels = { active: '进行中', planning: '规划中', completed: '已完成', paused: '已暂停' } as const
  return labels[projectStore.currentProject.status]
})

const researchMetrics = computed<ResearchMetricItem[]>(() => [
  {
    label: '证据覆盖',
    value: knowledgeStore.totalDocuments,
    unit: '篇',
    status: knowledgeStore.totalDocuments > 0 ? 'success' : 'neutral'
  },
  {
    label: '实验状态',
    value: datasetStore.report ? '已载入分析' : '暂无实验数据',
    status: datasetStore.report ? 'success' : 'neutral'
  },
  {
    label: '数据模型',
    value: datasetStore.models.length,
    unit: '个',
    status: datasetStore.models.length > 0 ? 'success' : 'neutral'
  },
  {
    label: '论文状态',
    value: manuscriptStore.manuscript ? '已载入草稿' : '暂无草稿',
    status: manuscriptStore.manuscript ? 'success' : 'neutral'
  }
])

const researchTimeline = computed<ResearchTimelineItem[]>(() => [])
const agentStatuses = computed<ResearchAgentStatusItem[]>(() => [])

const recentEvidence = computed<EvidenceItem[]>(() => datasetStore.conclusions.map((conclusion, index) => ({
  id: `${conclusion.observation}-${index}`,
  title: conclusion.observation,
  description: conclusion.interpretation,
  confidence: conclusion.confidence,
  source: '数据分析结论'
})))
const insightCitations = computed<CitationItem[]>(() => [])

async function loadDashboard(): Promise<void> {
  loadError.value = ''
  try {
    // [类 20.193] 先 loadProjects 拉当前项目 (其他数据都依赖 project context)
    await projectStore.loadProjects()
    await Promise.all([
      knowledgeStore.loadDocuments(),
      datasetStore.loadReport(async () => undefined),
      manuscriptStore.loadManuscript(async () => undefined)
    ])
  } catch (error) {
    console.error('[科研驾驶舱] 科研数据加载失败', error)
    loadError.value = '科研数据分析失败，请重试。'
  }
}

onMounted(loadDashboard)
</script>

<template>
  <section class="dashboard" aria-label="科研驾驶舱">
    <ResearchPageHeader
      eyebrow="当前科研项目"
      title="科研驾驶舱"
      description="聚合当前项目、研究证据和已接入的分析状态。"
      :status="projectStatus"
    />

    <section class="dashboard__focus" aria-labelledby="dashboard-focus-title">
      <div class="dashboard__focus-heading">
        <p class="dashboard__eyebrow">项目上下文</p>
        <h2 id="dashboard-focus-title">科研焦点</h2>
      </div>
      <dl v-if="hasProject" class="dashboard__focus-details">
        <div><dt>项目名称</dt><dd>{{ projectStore.currentProject.name }}</dd></div>
        <div><dt>研究领域</dt><dd>{{ projectStore.currentProject.domain }}</dd></div>
        <div><dt>研究目标</dt><dd>{{ projectStore.currentProject.description }}</dd></div>
        <div><dt>阶段</dt><dd>{{ projectStatus }}</dd></div>
        <div class="dashboard__focus-progress"><dt>进度</dt><dd>{{ projectProgress }}%</dd></div>
      </dl>
      <div v-else class="dashboard__focus-empty">
        <ResearchState
          state="empty"
          title="未选择项目"
          description="本地 SQLite projects 表为空, 或 loadProjects() 尚未返回. 请在 header 项目选择器中选择, 或迁移 PG 数据后刷新."
        />
      </div>
      <div v-if="hasProject" class="dashboard__progress" role="progressbar" aria-label="项目进度" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="projectProgress">
        <span class="dashboard__progress-fill" :style="{ width: `${projectProgress}%` }" />
      </div>
    </section>

    <template v-if="hasProject">
      <ResearchMetricPanel :items="researchMetrics" aria-label="科研关键指标" />

      <ResearchState v-if="isLoading && !hasResearchData" state="loading" />
      <ResearchState v-else-if="loadError && !hasResearchData" state="error" :description="loadError" @retry="loadDashboard" />
      <ResearchState v-else-if="!hasResearchData" state="empty" />
      <ResearchState v-if="loadError && hasResearchData" state="error" title="科研数据刷新失败，请重试" :description="loadError" @retry="loadDashboard" />

      <div class="dashboard__command-grid">
        <section class="dashboard__activity-column" aria-label="AI 研究活动">
          <ResearchTimeline :items="researchTimeline" aria-label="AI 研究活动时间线" />
          <AgentStatusPanel :agents="agentStatuses" aria-label="AI 研究活动状态" />
        </section>

        <aside class="dashboard__insight-column">
          <section class="dashboard__panel-section" aria-labelledby="dashboard-device-health">
            <h2 id="dashboard-device-health">设备健康</h2>
            <DeviceStatusPanel :devices="[]" variant="research" />
          </section>
          <section class="dashboard__panel-section" aria-labelledby="dashboard-recent-insights">
            <h2 id="dashboard-recent-insights">近期科学洞见</h2>
            <EvidencePanel :evidence="recentEvidence" :citations="insightCitations" aria-label="近期科学洞见与引用" />
          </section>
        </aside>
      </div>
    </template>
    <ResearchState
      v-else
      state="empty"
      title="未选择项目"
      description="请在 header 项目选择器中选择, 或运行 Phase 11 数据迁移."
    />
  </section>
</template>

<style scoped>
.dashboard {
  width: 100%;
  min-width: 0;
  max-width: var(--research-content-max-width);
  margin-inline: auto;
  padding: var(--research-page-gutter);
  overflow-x: clip;
}

.dashboard__focus,
.dashboard__activity-column,
.dashboard__insight-column,
.dashboard__panel-section {
  min-width: 0;
}

.dashboard__focus {
  display: grid;
  gap: var(--research-space-4);
  margin-block-end: var(--research-space-5);
  padding: var(--research-space-5);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}

.dashboard__eyebrow {
  margin: 0 0 var(--research-space-1);
  color: var(--research-coral-500);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-semibold);
  letter-spacing: .08em;
}

.dashboard__focus-heading h2,
.dashboard__panel-section > h2 {
  margin: 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
}

.dashboard__focus-details {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--research-space-3);
  margin: 0;
}

.dashboard__focus-details > div {
  min-width: 0;
  padding: var(--research-space-3);
  border-radius: var(--research-radius-card);
  background: var(--research-bg-panel);
}

.dashboard__focus-details dt {
  color: var(--research-text-secondary);
  font-size: var(--research-text-xs);
}

.dashboard__focus-details dd {
  margin: var(--research-space-1) 0 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-sm);
  font-weight: var(--research-font-weight-medium);
  line-height: var(--research-line-height-body);
  overflow-wrap: anywhere;
}

.dashboard__focus-details > div:nth-child(3) { grid-column: span 2; }
.dashboard__focus-progress dd { color: var(--research-primary-700); font-family: var(--research-font-scientific); }

.dashboard__progress {
  height: var(--research-space-2);
  overflow: hidden;
  border-radius: var(--research-radius-pill);
  background: var(--research-primary-100);
}

.dashboard__progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--research-primary-600);
  transition: width var(--research-duration-slow) var(--research-ease-emphasized);
}

.dashboard__command-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, .9fr);
  min-width: 0;
  gap: var(--research-grid-gap);
  margin-block-start: var(--research-space-5);
  overflow-x: clip;
}

.dashboard__activity-column,
.dashboard__insight-column { display: grid; align-content: start; gap: var(--research-grid-gap); }
.dashboard__panel-section { display: grid; gap: var(--research-space-3); }

@media (max-width: 1480px) {
  .dashboard__focus-details { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .dashboard__focus-details > div:nth-child(3) { grid-column: span 1; }
  .dashboard__command-grid { grid-template-columns: 1fr; }
}

@media (max-width: 900px) {
  .dashboard { padding: var(--research-space-4); }
  .dashboard__focus-details { grid-template-columns: 1fr; }
}

@media (min-width: 1720px) {
  .dashboard__command-grid { grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr); }
  .dashboard__focus { padding: var(--research-space-6); }
}

@media (prefers-reduced-motion: reduce) {
  .dashboard__progress-fill { transition: none; }
}
</style>
