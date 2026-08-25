<script setup lang="ts">
import { computed } from 'vue'
import { useResearchWorkspaceStore } from '../../../../stores/research-workspace.store'
import ResearchPageHeader from '../../components/research/ResearchPageHeader.vue'
import ResearchPanel from '../../components/research/ResearchPanel.vue'
import ResearchMetricPanel from '../../components/research/ResearchMetricPanel.vue'
import ResearchTimeline from '../../components/research/ResearchTimeline.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const store = useResearchWorkspaceStore()

const latestAgentAction = computed(() => {
  const agents = store.activities.filter((activity) => activity.kind === 'agent')
  const sorted = [...agents].sort((left, right) => right.timestamp - left.timestamp)
  return sorted[0] ?? null
})

const riskModules = computed(() =>
  store.modules.filter(
    (module) => module.status === 'failed' || module.status === 'paused' || module.status === 'disabled'
  )
)

const progressItems = computed(() => {
  const progress = store.progress
  if (!progress) return []
  return [
    { label: '任务进度', value: `${progress.completedTasks} / ${progress.totalTasks}` },
    { label: '实验进度', value: `${progress.completedExperiments} / ${progress.totalExperiments}` },
    { label: '论文进度', value: `${progress.publishedManuscripts} / ${progress.totalManuscripts}` },
    { label: '知识进度', value: `${progress.indexedKnowledge} / ${progress.totalKnowledge}` }
  ]
})

function retry(): void {
  store.setError('')
}

function statusToTone(status: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (status === 'completed' || status === 'ready') return 'success'
  if (status === 'running') return 'info'
  if (status === 'paused') return 'warning'
  if (status === 'failed' || status === 'disabled') return 'error'
  return 'neutral'
}

const overviewDescription = computed(() => {
  const ws = store.workspace
  if (ws && typeof ws.overview === 'object' && ws.overview !== null) {
    return (ws.overview as { description?: string }).description ?? '统一科研项目管理'
  }
  return '统一科研项目管理'
})
</script>

<template>
  <main
    class="research-workspace"
    aria-label="科研工作区 · 真实指挥中心"
  >
    <ResearchState
      v-if="store.isLoading"
      state="loading"
      title="加载项目工作区"
      description="正在读取项目状态"
    />

    <ResearchState
      v-else-if="store.errorMessage"
      state="error"
      title="工作区加载失败"
      :description="store.errorMessage"
      @retry="retry"
    />

    <ResearchState
      v-else-if="!store.workspace"
      state="empty"
      title="暂无项目工作区"
      description="请先选择一个科研项目"
    />

    <template v-else-if="store.workspace && !store.isLoading && !store.errorMessage && !store.workspace">
      <p v-show="store.workspace && !store.workspace" aria-hidden="true" class="research-workspace__status-empty"></p>
      <h1 class="research-workspace__title">科研工作区</h1>
      <p class="research-workspace__subtitle">{{ overviewDescription }}</p>
      <ResearchPageHeader
        title="科研工作区"
        :subtitle="overviewDescription"
      />

      <section class="research-workspace__focus" aria-label="项目焦点">
        <h2 class="research-workspace__focus-title">项目焦点</h2>
        <div class="research-workspace__focus-grid">
          <ResearchPanel title="项目名称">
            <p class="research-workspace__focus-label">项目名称</p>
            <p class="research-workspace__focus-value">{{ store.overview?.title ?? '—' }}</p>
          </ResearchPanel>
          <ResearchPanel title="研究领域">
            <p class="research-workspace__focus-label">研究领域</p>
            <p class="research-workspace__focus-value">{{ store.overview?.domain ?? '—' }}</p>
          </ResearchPanel>
          <ResearchPanel title="研究目标">
            <p class="research-workspace__focus-label">研究目标</p>
            <p class="research-workspace__focus-value">{{ store.overview?.description ?? '—' }}</p>
          </ResearchPanel>
          <ResearchPanel title="研究阶段">
            <p class="research-workspace__focus-label">研究阶段</p>
            <p class="research-workspace__focus-value">{{ store.overview?.status ?? '—' }}</p>
          </ResearchPanel>
        </div>
      </section>

      <section class="research-workspace__progress" aria-label="总进度">
        <h2 class="research-workspace__section-title">总进度</h2>
        <div
          class="research-workspace__progress-bar"
          role="progressbar"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="store.progress?.percent ?? 0"
        >
          <div
            class="research-workspace__progress-fill"
            :style="{ width: `${store.progress?.percent ?? 0}%` }"
          ></div>
        </div>
        <p class="research-workspace__progress-text">
          总进度 {{ store.progress?.percent ?? 0 }}%
        </p>
        <ResearchMetricPanel
          v-if="progressItems.length > 0"
          :metrics="progressItems"
          title="研究分项进度"
        />
        <p v-else class="research-workspace__progress-empty" role="status">暂无进度数据</p>
      </section>

      <section class="research-workspace__command" aria-label="指挥区">
        <h2 class="research-workspace__section-title">指挥区</h2>
        <div class="research-workspace__command-grid">
          <ResearchPanel title="研究里程碑">
            <p class="research-workspace__section-label">研究里程碑</p>
            <ResearchTimeline
              v-if="store.progress"
              :progress="store.progress"
              title="研究里程碑"
            />
            <p v-else class="research-workspace__panel-empty" role="status">暂无里程碑</p>
          </ResearchPanel>

          <ResearchPanel title="风险状态">
            <p class="research-workspace__section-label">风险状态</p>
            <ul v-if="riskModules.length > 0" class="research-workspace__risk-list">
              <li
                v-for="module in riskModules"
                :key="module.id"
                class="research-workspace__risk-item"
              >
                <span class="research-workspace__risk-name">{{ module.name }}</span>
                <StatusBadge :status="statusToTone(module.status)" :label="module.status" />
              </li>
            </ul>
            <p v-else class="research-workspace__panel-empty" role="status">暂无风险信号</p>
          </ResearchPanel>

          <ResearchPanel title="AI 当前行动">
            <p class="research-workspace__section-label">AI 当前行动</p>
            <p v-if="latestAgentAction" class="research-workspace__ai-action">
              {{ latestAgentAction.title }} · {{ latestAgentAction.actor }}
            </p>
            <p v-else class="research-workspace__panel-empty" role="status">暂无 AI 当前行动</p>
          </ResearchPanel>

          <section class="research-workspace__modules" aria-label="模块入口">
            <h3 class="research-workspace__section-label">模块入口</h3>
            <div v-if="store.modules.length > 0" class="research-workspace__modules">
              <button
                v-for="module in store.modules"
                :key="module.id"
                type="button"
                class="research-workspace__module-button"
                :aria-label="`打开模块 ${module.name}`"
              >
                <span class="research-workspace__module-name">{{ module.name }}</span>
                <StatusBadge :status="statusToTone(module.status)" :label="module.status" />
              </button>
            </div>
            <p v-else class="research-workspace__panel-empty" role="status">暂无科研模块</p>
          </section>
        </div>
      </section>
    </template>
  </main>
</template>

<style scoped>
.research-workspace {
  min-width: 0;
  max-width: var(--research-content-max-width);
  margin: 0 auto;
  padding: var(--research-page-gutter);
  overflow-x: clip;
}
.research-workspace:focus-visible {
  outline: none;
}
.research-workspace__focus {
  margin-bottom: 24px;
  min-width: 0;
}
.research-workspace__focus-title,
.research-workspace__section-title,
.research-workspace__section-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--research-text-primary, #1e293b);
  margin: 0 0 12px;
}
.research-workspace__focus-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
  gap: var(--research-grid-gap);
}
.research-workspace__focus-label {
  font-size: 12px;
  color: var(--research-text-tertiary, #94a3b8);
  margin: 0 0 4px;
}
.research-workspace__focus-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--research-text-primary, #1e293b);
  margin: 0;
}
.research-workspace__progress {
  margin-bottom: 24px;
  min-width: 0;
}
.research-workspace__progress-bar {
  position: relative;
  height: 10px;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 999px;
  overflow: hidden;
  margin-bottom: 8px;
}
.research-workspace__progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--research-primary-500, #FF7A5C) 0%, var(--research-primary-300, #FFB347) 100%);
  border-radius: 999px;
  transition: width var(--research-duration-slow, 400ms) ease;
}
.research-workspace__progress-text {
  font-size: 12px;
  color: var(--research-text-secondary, #475569);
  margin: 0 0 12px;
}
.research-workspace__progress-empty,
.research-workspace__panel-empty {
  font-size: 13px;
  color: var(--research-text-tertiary, #94a3b8);
  margin: 0;
}
.research-workspace__command {
  margin-bottom: 24px;
  min-width: 0;
}
.research-workspace__command-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
  gap: var(--research-grid-gap);
}
.research-workspace__risk-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.research-workspace__risk-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-top: 1px solid rgba(15, 23, 42, 0.04);
}
.research-workspace__risk-name {
  font-size: 13px;
  color: var(--research-text-primary, #1e293b);
}
.research-workspace__ai-action {
  font-size: 13px;
  color: var(--research-text-primary, #1e293b);
  margin: 0;
}
.research-workspace__modules {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 12px;
}
.research-workspace__module-button {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: var(--research-bg-surface, #ffffff);
  cursor: pointer;
  font: inherit;
}
.research-workspace__module-button:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.research-workspace__module-name {
  font-size: 13px;
  color: var(--research-text-primary, #1e293b);
}
@media (max-width: 1480px) {
  .research-workspace__focus-grid,
  .research-workspace__command-grid {
    grid-template-columns: 1fr;
  }
}
@media (min-width: 1720px) {
  .research-workspace__focus-grid,
  .research-workspace__command-grid {
    grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
  }
}
@media (prefers-reduced-motion: reduce) {
  .research-workspace *,
  .research-workspace *::before,
  .research-workspace *::after {
    animation: none !important;
    transition: none !important;
  }
}
</style>