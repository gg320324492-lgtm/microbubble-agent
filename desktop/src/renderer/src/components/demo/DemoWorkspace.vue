<script setup lang="ts">
/**
 * DemoWorkspace — Phase 8-M0-G
 * 演示模式总览: 研究目标 / 当前阶段 / AI 行动 / 实验状态 / 数据结果 / 论文进度
 * Props-only 组件, 禁止依赖 service / store.
 */
import { computed } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'
import ResearchPanel from '../research/ResearchPanel.vue'
import ResearchMetricPanel from '../research/ResearchMetricPanel.vue'
import type { ResearchMetricItem } from '../research/ResearchMetricPanel.vue'
import {
  DEMO_PROJECT,
  type DemoResearchProject,
  type DemoExperimentStep,
  type DemoExperimentGroup,
  type DemoManuscriptInfo,
  type ResearchStage
} from '../../services/demo/demo-project'

const props = withDefaults(defineProps<{
  project?: DemoResearchProject | null
}>(), { project: null })

const project = computed<DemoResearchProject>(() => props.project ?? DEMO_PROJECT)
const experiments = computed<DemoExperimentStep[]>(() => project.value.experiments)
const groups = computed<DemoExperimentGroup[]>(() => project.value.groups)
const manuscript = computed<DemoManuscriptInfo>(() => project.value.manuscript)

const stageLabel = computed<Record<ResearchStage, string>>(() => ({
  planning: '规划中', literature: '文献研究', experiment: '实验进行中',
  analysis: '数据分析', writing: '论文撰写', submitted: '已投稿'
}))

const completedSteps = computed(() => experiments.value.filter((e) => e.status === 'completed').length)

const metrics = computed<ResearchMetricItem[]>(() => [
  { label: '项目进度', value: project.value.progressPercent, unit: '%', status: 'success' },
  { label: '实验完成', value: `${completedSteps.value} / ${experiments.value.length}`, status: completedSteps.value > 0 ? 'success' : 'neutral' },
  { label: '实验分组', value: groups.value.length, unit: '组', status: 'neutral' },
  { label: '论文字数', value: manuscript.value.wordCount, unit: '字', status: 'warning' }
])

const aiActions = [
  { id: 'ai-1', label: '继续监测第二批验证实验', state: '进行中' },
  { id: 'ai-2', label: '完成一级动力学模型拟合', state: '已完成' },
  { id: 'ai-3', label: '草拟 Discussion 章节初稿', state: '待启动' }
]
</script>

<template>
  <section class="demo-workspace" aria-label="演示工作区总览">
    <header class="demo-workspace__hero">
      <span class="demo-workspace__badge" data-testid="demo-warning-label">
        <ResearchIcon name="warning" :size="14" />
        <span>{{ project.warningLabel }}</span>
      </span>
      <h1 class="demo-workspace__title">{{ project.name }}</h1>
      <p class="demo-workspace__domain">{{ project.domain }}</p>
      <p class="demo-workspace__description">{{ project.description }}</p>
    </header>

    <ResearchMetricPanel :items="metrics" title="演示项目概览" />

    <section class="demo-workspace__grid" aria-label="演示三栏总览">
      <ResearchPanel title="研究目标" subtitle="Objectives">
        <ol class="demo-workspace__objectives" role="list">
          <li v-for="(objective, idx) in project.objectives" :key="idx" class="demo-workspace__objective">
            <span class="demo-workspace__objective-marker">{{ idx + 1 }}</span>
            <span class="demo-workspace__objective-copy">{{ objective }}</span>
          </li>
        </ol>
      </ResearchPanel>

      <ResearchPanel title="研究阶段" subtitle="Stage">
        <div class="demo-workspace__stage">
          <span class="demo-workspace__stage-label">当前阶段</span>
          <strong class="demo-workspace__stage-value">{{ stageLabel[project.stage] }}</strong>
          <div class="demo-workspace__progress" role="progressbar" :aria-valuenow="project.progressPercent" aria-valuemin="0" aria-valuemax="100" :aria-label="`项目进度 ${project.progressPercent}%`">
            <span class="demo-workspace__progress-fill" :style="{ width: `${project.progressPercent}%` }" />
          </div>
        </div>
        <ul class="demo-workspace__ai-list" role="list">
          <li v-for="ai in aiActions" :key="ai.id" class="demo-workspace__ai-item">
            <ResearchIcon name="running" :size="14" />
            <span class="demo-workspace__ai-label">{{ ai.label }}</span>
            <span class="demo-workspace__ai-state" :data-state="ai.state">{{ ai.state }}</span>
          </li>
        </ul>
      </ResearchPanel>

      <ResearchPanel title="论文进度" subtitle="Manuscript">
        <dl class="demo-workspace__manuscript">
          <div><dt>题目</dt><dd>{{ manuscript.title }}</dd></div>
          <div><dt>目标期刊</dt><dd>{{ manuscript.targetJournal }}</dd></div>
          <div><dt>字数</dt><dd>{{ manuscript.wordCount }}</dd></div>
          <div><dt>章节</dt><dd>{{ manuscript.sectionCount }}</dd></div>
          <div><dt>图表</dt><dd>{{ manuscript.figureCount }}</dd></div>
        </dl>
      </ResearchPanel>
    </section>

    <ResearchPanel title="实验流程" subtitle="实验步骤与分组">
      <ol class="demo-workspace__steps" role="list">
        <li
          v-for="step in experiments"
          :key="step.id"
          class="demo-workspace__step"
          :data-status="step.status"
        >
          <span class="demo-workspace__step-marker">{{ step.status === 'completed' ? '✓' : step.status === 'in-progress' ? '…' : '·' }}</span>
          <span class="demo-workspace__step-name">{{ step.name }}</span>
          <span class="demo-workspace__step-status">{{ step.status === 'completed' ? '已完成' : step.status === 'in-progress' ? '进行中' : '待启动' }}</span>
          <span class="demo-workspace__step-date">{{ step.startDate }}{{ step.endDate ? ` ~ ${step.endDate}` : '' }}</span>
        </li>
      </ol>
      <div class="demo-workspace__groups" role="group" aria-label="实验分组">
        <span v-for="g in groups" :key="g.id" class="demo-workspace__group">
          <strong>{{ g.name }}</strong>
          <span>{{ g.replicates }} 重复 · {{ g.description }}</span>
        </span>
      </div>
    </ResearchPanel>
  </section>
</template>

<style scoped>
.demo-workspace { display: grid; gap: var(--research-space-5); min-width: 0; }
.demo-workspace__hero {
  display: grid;
  gap: var(--research-space-2);
  padding: var(--research-space-5);
  border: 1px solid var(--research-warning-100);
  border-radius: var(--research-radius-panel);
  background: linear-gradient(135deg, var(--research-warning-50) 0%, var(--research-bg-card) 60%);
}
.demo-workspace__badge {
  display: inline-flex;
  align-items: center;
  gap: var(--research-space-1);
  align-self: start;
  padding: 2px var(--research-space-2);
  border-radius: var(--research-radius-pill);
  background: var(--research-warning-500);
  color: var(--research-text-inverse);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-semibold);
}
.demo-workspace__title { margin: 0; color: var(--research-text-primary); font-size: var(--research-text-page-title); font-weight: var(--research-font-weight-bold); }
.demo-workspace__domain { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.demo-workspace__description { margin: var(--research-space-2) 0 0; color: var(--research-text-primary); font-size: var(--research-text-body); line-height: var(--research-line-height-body); }

.demo-workspace__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--research-grid-gap);
}
.demo-workspace__objectives { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--research-space-2); }
.demo-workspace__objective { display: grid; grid-template-columns: 24px 1fr; gap: var(--research-space-3); align-items: start; color: var(--research-text-primary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.demo-workspace__objective-marker { display: grid; place-items: center; width: 24px; height: 24px; border-radius: var(--research-radius-pill); background: var(--research-primary-50); color: var(--research-primary-700); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-bold); }
.demo-workspace__objective-copy { min-width: 0; }

.demo-workspace__stage { display: grid; gap: var(--research-space-2); margin-block-end: var(--research-space-4); }
.demo-workspace__stage-label { color: var(--research-text-muted); font-size: var(--research-text-xs); }
.demo-workspace__stage-value { color: var(--research-primary-700); font-size: var(--research-text-section-title); font-weight: var(--research-font-weight-bold); }
.demo-workspace__progress { height: 8px; overflow: hidden; border-radius: var(--research-radius-pill); background: var(--research-progress-track); }
.demo-workspace__progress-fill { display: block; height: 100%; background: linear-gradient(90deg, var(--research-progress-fill-start) 0%, var(--research-progress-fill-end) 100%); transition: width var(--research-duration-slow) var(--research-ease-emphasized); }

.demo-workspace__ai-list { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--research-space-2); }
.demo-workspace__ai-item { display: grid; grid-template-columns: 16px 1fr auto; gap: var(--research-space-2); align-items: center; padding: var(--research-space-2) var(--research-space-3); border-radius: var(--research-radius-sm); background: var(--research-bg-panel); color: var(--research-text-primary); font-size: var(--research-text-sm); }
.demo-workspace__ai-label { min-width: 0; }
.demo-workspace__ai-state { color: var(--research-text-muted); font-size: var(--research-text-xs); }
.demo-workspace__ai-state[data-state='已完成'] { color: var(--research-success-700); }
.demo-workspace__ai-state[data-state='进行中'] { color: var(--research-primary-700); }

.demo-workspace__manuscript { display: grid; gap: var(--research-space-2); margin: 0; }
.demo-workspace__manuscript > div { display: grid; grid-template-columns: 80px 1fr; gap: var(--research-space-3); padding-block-end: var(--research-space-2); border-block-end: 1px solid var(--research-divider-soft); }
.demo-workspace__manuscript > div:last-child { border-block-end: 0; padding-block-end: 0; }
.demo-workspace__manuscript dt { color: var(--research-text-muted); font-size: var(--research-text-xs); }
.demo-workspace__manuscript dd { margin: 0; color: var(--research-text-primary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); overflow-wrap: anywhere; }

.demo-workspace__steps { list-style: none; padding: 0; margin: 0 0 var(--research-space-4); display: grid; gap: var(--research-space-2); }
.demo-workspace__step {
  display: grid;
  grid-template-columns: 24px minmax(0, 1.4fr) auto auto;
  gap: var(--research-space-3);
  align-items: center;
  padding: var(--research-space-3);
  border-radius: var(--research-radius-sm);
  background: var(--research-bg-panel);
  font-size: var(--research-text-sm);
  color: var(--research-text-primary);
}
.demo-workspace__step[data-status='completed'] { background: var(--research-success-50); }
.demo-workspace__step[data-status='in-progress'] { background: var(--research-primary-50); border-left: 3px solid var(--research-primary-600); }
.demo-workspace__step-marker { display: grid; place-items: center; width: 24px; height: 24px; border-radius: var(--research-radius-pill); background: var(--research-bg-card); color: var(--research-text-secondary); font-family: var(--research-font-scientific); }
.demo-workspace__step-name { font-weight: var(--research-font-weight-medium); }
.demo-workspace__step-status { color: var(--research-text-muted); font-size: var(--research-text-xs); }
.demo-workspace__step-date { color: var(--research-text-muted); font-size: var(--research-text-xs); font-family: var(--research-font-scientific); }

.demo-workspace__groups { display: flex; flex-wrap: wrap; gap: var(--research-space-2); }
.demo-workspace__group { display: grid; gap: 2px; padding: var(--research-space-2) var(--research-space-3); border-radius: var(--research-radius-sm); background: var(--research-bg-panel); font-size: var(--research-text-xs); color: var(--research-text-secondary); min-width: 220px; }
.demo-workspace__group strong { color: var(--research-text-primary); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); }

@media (max-width: 1480px) {
  .demo-workspace__grid { grid-template-columns: minmax(0, 1fr); }
  .demo-workspace__step { grid-template-columns: 24px minmax(0, 1fr); }
  .demo-workspace__step-status, .demo-workspace__step-date { grid-column: 2 / -1; }
}
@media (min-width: 1720px) {
  .demo-workspace__grid { grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr) minmax(0, 1fr); }
}
@media (prefers-reduced-motion: reduce) {
  .demo-workspace__progress-fill { transition: none; }
}
</style>
