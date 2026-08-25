<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import ResearchPageShell from '../../components/research/ResearchPageShell.vue'
import ResearchPanel from '../../components/research/ResearchPanel.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import ScientificMetric from '../../components/research/ScientificMetric.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'
import { useDatasetStore } from '../../stores/research/dataset.store'
import { useExperimentStore } from '../../stores/research/experiment.store'
import { useKnowledgeStore } from '../../stores/research/knowledge.store'
import { useManuscriptStore } from '../../stores/research/manuscript.store'
import { useProjectStore } from '../../stores/research/project.store'
import { kineticModelLabel } from '../../utils/scientific-chart'

const projectStore = useProjectStore()
const knowledgeStore = useKnowledgeStore()
const datasetStore = useDatasetStore()
const manuscriptStore = useManuscriptStore()
const experimentStore = useExperimentStore()

const activeTab = ref<TabId>('overview')
const tabButtons = ref<HTMLButtonElement[]>([])
const loadError = ref('')
const tabs = [
  { id: 'overview', label: '项目概览', icon: 'home' },
  { id: 'literature', label: '文献', icon: 'literature' },
  { id: 'experiment', label: '实验', icon: 'experiment' },
  { id: 'data', label: '数据', icon: 'data' },
  { id: 'model', label: '模型', icon: 'model' },
  { id: 'manuscript', label: '论文', icon: 'manuscript' }
] as const
type TabId = (typeof tabs)[number]['id']

const projectProgress = computed(() => Math.round(projectStore.currentProject.progress * 100))
const isLoading = computed(() => knowledgeStore.isLoading || datasetStore.isLoading || manuscriptStore.isLoading || experimentStore.isLoading)
const hasWorkspaceData = computed(() => knowledgeStore.totalDocuments > 0 || datasetStore.report !== null || manuscriptStore.manuscript !== null || experimentStore.design !== null)
const projectStatus = computed(() => {
  const labels = { active: '进行中', planning: '规划中', completed: '已完成', paused: '已暂停' } as const
  return labels[projectStore.currentProject.status]
})
const workspaceAiStatus = computed(() => {
  if (isLoading.value) return 'AI 正在同步'
  if (loadError.value) return '研究数据同步失败'
  return '研究数据已就绪'
})

async function loadWorkspace(): Promise<void> {
  loadError.value = ''
  try {
    await Promise.all([
      knowledgeStore.loadDocuments(),
      datasetStore.loadReport(async () => undefined),
      manuscriptStore.loadManuscript(async () => undefined),
      experimentStore.loadDesign()
    ])
  } catch (error) {
    console.error('[项目空间] 项目数据加载失败', error)
    loadError.value = '项目数据加载失败，请重试。'
  }
}

function selectTab(id: TabId): void {
  activeTab.value = id
}

async function onTabKeydown(event: KeyboardEvent, index: number): Promise<void> {
  let nextIndex = index
  if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length
  else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length
  else if (event.key === 'Home') nextIndex = 0
  else if (event.key === 'End') nextIndex = tabs.length - 1
  else return

  event.preventDefault()
  activeTab.value = tabs[nextIndex].id
  await nextTick()
  tabButtons.value[nextIndex]?.focus()
}

onMounted(loadWorkspace)
</script>

<template>
  <ResearchPageShell eyebrow="跨模块研究中枢" title="项目空间" description="在同一项目上下文中查看证据、实验、数据、模型与论文，不重建业务状态。">
    <section class="workspace__hero" aria-labelledby="workspace-project-title">
      <div class="workspace__identity">
        <span aria-hidden="true"><ResearchIcon name="project" :size="22" /></span>
        <div>
          <p>{{ projectStore.currentProject.domain }}</p>
          <h2 id="workspace-project-title">{{ projectStore.currentProject.name }}</h2>
          <strong>{{ projectStatus }} · {{ workspaceAiStatus }}</strong>
        </div>
      </div>
      <div class="workspace__progress">
        <div><span>项目进度</span><strong>{{ projectProgress }}%</strong></div>
        <div role="progressbar" aria-label="项目进度" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="projectProgress">
          <span :style="{ width: `${projectProgress}%` }" />
        </div>
      </div>
    </section>

    <div class="workspace__tabs" role="tablist" aria-label="项目工作区">
      <button
        v-for="(tab, index) in tabs"
        :id="`workspace-tab-${tab.id}`"
        :key="tab.id"
        ref="tabButtons"
        type="button"
        role="tab"
        :class="['workspace__tab', { 'is-active': activeTab === tab.id }]"
        :aria-selected="activeTab === tab.id"
        :aria-controls="`workspace-panel-${tab.id}`"
        :tabindex="activeTab === tab.id ? 0 : -1"
        @click="selectTab(tab.id)"
        @keydown="onTabKeydown($event, index)"
      >
        <ResearchIcon :name="tab.icon" :size="17" />
        {{ tab.label }}
      </button>
    </div>

    <ResearchState v-if="loadError" state="error" :description="loadError" @retry="loadWorkspace" />

    <section
      v-if="!loadError || hasWorkspaceData"
      :id="`workspace-panel-${activeTab}`"
      class="workspace__panel"
      role="tabpanel"
      :aria-labelledby="`workspace-tab-${activeTab}`"
      tabindex="0"
    >
      <template v-if="activeTab === 'overview'">
        <div class="workspace__stats">
          <ScientificMetric label="文献" :value="String(knowledgeStore.totalDocuments)" unit="篇" trend="stable" trend-text="当前证据库" />
          <ScientificMetric label="数据集" :value="String(projectStore.currentProject.stats.datasets)" unit="个" trend="stable" trend-text="项目记录" />
          <ScientificMetric label="实验" :value="String(projectStore.currentProject.stats.experiments)" unit="次" trend="stable" trend-text="项目记录" />
          <ScientificMetric label="论文" :value="projectStore.currentProject.stats.manuscriptStatus" trend="stable" :trend-text="`${manuscriptStore.issueCount} 项待改进`" />
        </div>
        <ResearchPanel title="项目概览" subtitle="当前项目的真实状态数据" tone="primary">
          <dl class="workspace__overview-list">
            <div><dt>研究方向</dt><dd>{{ projectStore.currentProject.domain }}</dd></div>
            <div><dt>项目状态</dt><dd>{{ projectStatus }}</dd></div>
            <div><dt>最佳模型</dt><dd>{{ datasetStore.models[0] ? kineticModelLabel(datasetStore.models[0].model) : '暂无模型' }}</dd></div>
            <div><dt>论文问题</dt><dd>{{ manuscriptStore.issueCount }} 项</dd></div>
          </dl>
        </ResearchPanel>
      </template>

      <template v-else-if="activeTab === 'literature'">
        <ResearchState v-if="knowledgeStore.isLoading" state="loading" />
        <ResearchState v-else-if="!knowledgeStore.documents.length" state="empty" title="暂无文献数据" description="导入文献后，可在项目空间中查看证据条目。" />
        <ResearchPanel v-else :title="`文献证据（${knowledgeStore.totalDocuments}）`" subtitle="来自当前知识数据源" tone="primary">
          <div class="workspace__document-list">
            <article v-for="document in knowledgeStore.documents" :key="document.id" class="workspace__document">
              <div><strong>{{ document.title }}</strong><p>{{ document.authors }} · {{ document.journal }} · {{ document.year }}</p></div>
              <StatusBadge status="success" :label="`可信度 ${Math.round(document.credibility * 100)}%`" />
            </article>
          </div>
        </ResearchPanel>
      </template>

      <template v-else-if="activeTab === 'experiment'">
        <ResearchState v-if="experimentStore.isLoading" state="loading" />
        <ResearchState v-else-if="!experimentStore.design" state="empty" title="暂无实验设计" description="创建实验设计后，这里会展示假设、变量和分组。" />
        <div v-else class="workspace__experiment-grid">
          <ResearchPanel title="研究假设" :subtitle="experimentStore.design.title" tone="ai">
            <ol class="workspace__hypotheses">
              <li v-for="hypothesis in experimentStore.design.hypotheses" :key="hypothesis.statement">
                <span>{{ hypothesis.statement }}</span><strong>{{ Math.round(hypothesis.confidence * 100) }}%</strong>
              </li>
            </ol>
          </ResearchPanel>
          <ResearchPanel title="实验变量" :subtitle="`${experimentStore.design.variables.length} 个变量`">
            <div class="workspace__variable" v-for="variable in experimentStore.design.variables" :key="variable.name">
              <strong>{{ variable.name }}</strong><span>{{ variable.range }} {{ variable.unit }}</span>
            </div>
          </ResearchPanel>
        </div>
      </template>

      <template v-else-if="activeTab === 'data'">
        <ResearchState v-if="datasetStore.isLoading" state="loading" />
        <ResearchState v-else-if="!datasetStore.statistics.length" state="empty" title="暂无数据分析" description="完成数据分析后，这里会展示统计结果。" />
        <div v-else class="workspace__data-grid">
          <article v-for="statistic in datasetStore.statistics" :key="statistic.metric" class="workspace__data-card">
            <span>{{ statistic.metric }}</span><strong>{{ statistic.value }}</strong><p>{{ statistic.interpretation }}</p>
          </article>
        </div>
      </template>

      <template v-else-if="activeTab === 'model'">
        <ResearchState v-if="datasetStore.isLoading" state="loading" />
        <ResearchState v-else-if="!datasetStore.models.length" state="empty" title="暂无模型结果" description="完成模型拟合后，这里会展示参数与拟合质量。" />
        <ResearchPanel v-else title="模型拟合" subtitle="来自当前数据分析结果" tone="success">
          <div class="workspace__model-list">
            <article v-for="model in datasetStore.models" :key="model.model">
              <div><strong>{{ kineticModelLabel(model.model) }}</strong><span>残差 {{ model.residualError }}</span></div>
              <span>R² = {{ model.rSquared.toFixed(4) }}</span>
              <StatusBadge :status="model.rSquared >= 0.9 ? 'success' : 'warning'" :label="model.rSquared >= 0.9 ? '拟合良好' : '需要复核'" />
            </article>
          </div>
        </ResearchPanel>
      </template>

      <template v-else>
        <ResearchState v-if="manuscriptStore.isLoading" state="loading" />
        <ResearchState v-else-if="!manuscriptStore.manuscript" state="empty" title="暂无论文草稿" description="创建论文后，可在项目空间中查看各章节进展。" />
        <ResearchPanel v-else :title="manuscriptStore.manuscript.title" :subtitle="`${manuscriptStore.wordCount.toLocaleString()} 字 · ${manuscriptStore.issueCount} 项待改进`" tone="ai">
          <div class="workspace__manuscript-list">
            <article v-for="section in manuscriptStore.sections" :key="section.sectionType">
              <strong>{{ section.title }}</strong><p>{{ section.content.slice(0, 180) }}</p>
            </article>
          </div>
        </ResearchPanel>
      </template>
    </section>
  </ResearchPageShell>
</template>

<style scoped>
.workspace__hero { display: grid; grid-template-columns: minmax(0, 1fr) minmax(240px, .45fr); align-items: center; gap: var(--research-space-6); margin-block-end: var(--research-space-5); padding: var(--research-space-5) var(--research-space-6); border: 1px solid var(--research-primary-100); border-radius: var(--research-radius-panel); background: var(--research-bg-card); box-shadow: var(--research-shadow-soft); }
.workspace__identity { display: flex; min-width: 0; align-items: center; gap: var(--research-space-3); }
.workspace__identity > span { display: grid; width: 44px; height: 44px; flex: 0 0 44px; place-items: center; border-radius: var(--research-radius-card); background: var(--research-primary-50); color: var(--research-primary-600); }
.workspace__identity div { min-width: 0; }
.workspace__identity p { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.workspace__identity h2 { overflow: hidden; margin: var(--research-space-1) 0; color: var(--research-text-primary); font-size: var(--research-text-section-title); text-overflow: ellipsis; white-space: nowrap; }
.workspace__identity strong { color: var(--research-ai-700); font-size: var(--research-text-sm); }
.workspace__progress > div:first-child { display: flex; justify-content: space-between; margin-block-end: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.workspace__progress strong { color: var(--research-primary-700); font-family: var(--research-font-mono); }
.workspace__progress > div:last-child { height: 7px; overflow: hidden; border-radius: var(--research-radius-pill); background: var(--research-primary-100); }
.workspace__progress > div:last-child span { display: block; height: 100%; border-radius: inherit; background: var(--research-primary-600); transition: width var(--research-duration-slow) var(--research-ease-emphasized); }
.workspace__tabs { display: flex; gap: var(--research-space-1); overflow-x: auto; margin-block-end: var(--research-space-5); padding: var(--research-space-1); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-card); }
.workspace__tab { display: inline-flex; min-height: 42px; flex: 1 0 auto; align-items: center; justify-content: center; gap: var(--research-space-2); padding: var(--research-space-2) var(--research-space-4); border: 0; border-radius: var(--research-radius-button); background: transparent; color: var(--research-text-secondary); font: inherit; font-size: 13px; font-weight: var(--research-font-weight-medium); cursor: pointer; }
.workspace__tab:hover { background: var(--research-bg-hover); color: var(--research-text-primary); }
.workspace__tab.is-active { background: var(--research-primary-50); color: var(--research-primary-700); box-shadow: var(--research-shadow-inset); }
.workspace__tab:focus-visible, .workspace__panel:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.workspace__panel { min-width: 0; }
.workspace__stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--research-grid-gap); margin-block-end: var(--research-grid-gap); }
.workspace__overview-list { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--research-space-3); margin: 0; }
.workspace__overview-list div { padding: var(--research-space-3); border-radius: var(--research-radius-button); background: var(--research-bg-panel); }
.workspace__overview-list dt { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.workspace__overview-list dd { margin: var(--research-space-1) 0 0; color: var(--research-text-primary); font-size: 13px; font-weight: var(--research-font-weight-semibold); }
.workspace__document-list, .workspace__model-list, .workspace__manuscript-list { display: grid; gap: var(--research-space-3); }
.workspace__document { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: var(--research-space-4); padding-block-end: var(--research-space-3); border-block-end: 1px solid var(--research-divider); }
.workspace__document strong, .workspace__model-list strong, .workspace__manuscript-list strong { color: var(--research-text-primary); font-size: 13px; }
.workspace__document p, .workspace__manuscript-list p { margin: var(--research-space-1) 0 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.workspace__experiment-grid { display: grid; grid-template-columns: minmax(0, .9fr) minmax(0, 1.1fr); gap: var(--research-grid-gap); }
.workspace__hypotheses { display: grid; gap: var(--research-space-3); margin: 0; padding-inline-start: var(--research-space-5); }
.workspace__hypotheses li { padding-inline-start: var(--research-space-2); color: var(--research-text-secondary); font-size: 13px; line-height: var(--research-line-height-body); }
.workspace__hypotheses strong { margin-inline-start: var(--research-space-2); color: var(--research-ai-700); font-family: var(--research-font-mono); }
.workspace__variable { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--research-space-3); padding-block: var(--research-space-2); border-block-end: 1px solid var(--research-divider); }
.workspace__variable strong { color: var(--research-text-primary); font-size: 13px; }
.workspace__variable span { color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.workspace__data-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--research-grid-gap); }
.workspace__data-card { min-width: 0; padding: var(--research-space-5); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-card); box-shadow: var(--research-shadow-soft); }
.workspace__data-card span { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.workspace__data-card strong { display: block; margin-block: var(--research-space-2); color: var(--research-primary-700); font-family: var(--research-font-mono); font-size: var(--research-text-section-title); }
.workspace__data-card p { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.workspace__model-list article { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: var(--research-space-4); padding-block-end: var(--research-space-3); border-block-end: 1px solid var(--research-divider); color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.workspace__model-list div span { display: block; margin-block-start: var(--research-space-1); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.workspace__manuscript-list article { padding-block-end: var(--research-space-3); border-block-end: 1px solid var(--research-divider); }

@media (max-width: 1480px) {
  .workspace__hero { grid-template-columns: minmax(0, 1fr) minmax(200px, .4fr); padding-inline: var(--research-space-5); }
  .workspace__tab { padding-inline: var(--research-space-3); }
  .workspace__stats, .workspace__overview-list { gap: var(--research-space-3); }
}
@media (min-width: 1720px) {
  .workspace__hero { padding: var(--research-space-6) var(--research-space-7); }
  .workspace__experiment-grid { grid-template-columns: minmax(0, .8fr) minmax(0, 1.2fr); }
}
@media (prefers-reduced-motion: reduce) {
  .workspace__progress > div:last-child span { transition: none; }
}
</style>
