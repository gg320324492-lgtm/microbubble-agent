<script setup lang="ts">
/**
 * 首页 — 科研项目总览 Dashboard (Pinia store 驱动)。
 */
import { onMounted } from 'vue'
import { useProjectStore } from '../../stores/research/project.store'
import { useKnowledgeStore } from '../../stores/research/knowledge.store'
import { useDatasetStore } from '../../stores/research/dataset.store'
import { useManuscriptStore } from '../../stores/research/manuscript.store'
import ProjectCard from '../../components/research/ProjectCard.vue'
import InsightCard from '../../components/research/InsightCard.vue'
import ScientificMetric from '../../components/research/ScientificMetric.vue'
import Timeline from '../../components/research/Timeline.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const projectStore = useProjectStore()
const knowledgeStore = useKnowledgeStore()
const datasetStore = useDatasetStore()
const manuscriptStore = useManuscriptStore()

onMounted(async () => {
  await Promise.all([
    knowledgeStore.loadDocuments(),
    datasetStore.loadReport(),
    manuscriptStore.loadManuscript()
  ])
})

const insights = [
  { finding: '动力学模型选择可能不足', suggestion: '补充自由基验证实验，增加 ESR 检测', severity: 'warning' as const },
  { finding: 'pH 对降解率影响显著', suggestion: '建议增加 pH 梯度实验（5.0/6.0/7.0/8.0/9.0）', severity: 'info' as const },
]

const milestones = [
  { label: '文献检索与证据汇总', time: '2025-05-23', status: 'done' as const },
  { label: '实验设计与条件确定', time: '2025-05-30', status: 'done' as const },
  { label: '动力学拟合与结果', time: '2025-06-12', status: 'current' as const },
  { label: '机理与结论', time: '预计 2025-06-25', status: 'pending' as const },
  { label: '论文撰写与投稿', time: '预计 2025-07-15', status: 'pending' as const },
]

const warnings = [
  { message: '实验设备提醒：纳米气泡发生器（NB-3000）维护保养 2025-06-15 到期', severity: 'warning' as const },
  { message: '数据备份建议：建议备份当前项目数据集', severity: 'info' as const },
]
</script>

<template>
  <div class="dashboard">
    <div class="dashboard__hero">
      <div>
        <h1 class="dashboard__title">{{ projectStore.projectName }}</h1>
        <p class="dashboard__subtitle">{{ projectStore.currentProject.description }}</p>
      </div>
    </div>

    <div class="dashboard__stats">
      <ScientificMetric label="实验总数" :value="String(projectStore.currentProject.stats.experiments)" unit="次" trend="up" trendText="+4 本周" />
      <ScientificMetric label="数据集" :value="String(projectStore.currentProject.stats.datasets)" unit="个" trend="up" trendText="+2 本周" />
      <ScientificMetric label="文献管理" :value="String(projectStore.currentProject.stats.documents)" unit="篇" trend="up" trendText="+8 本周" />
      <ScientificMetric label="论文进度" value="45" unit="%" trend="up" trendText="进行中" />
    </div>

    <div class="dashboard__middle">
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">项目里程碑</h3>
        <Timeline :steps="milestones" />
      </div>
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">AI 科研洞察</h3>
        <InsightCard v-for="(ins, i) in insights" :key="i" v-bind="ins" />
      </div>
    </div>

    <div class="dashboard__bottom">
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">数据概览</h3>
        <div class="dashboard__data-row" v-if="datasetStore.quality">
          <span>数据完整度</span>
          <div class="dashboard__bar"><div class="dashboard__bar-fill" :style="{ width: (datasetStore.quality.completeness * 100) + '%' }" /></div>
          <span>{{ (datasetStore.quality.completeness * 100).toFixed(0) }}%</span>
        </div>
        <div class="dashboard__data-row">
          <span>模型拟合</span>
          <span class="dashboard__mono">{{ datasetStore.models[0]?.model ?? '—' }} (R²={{ datasetStore.models[0]?.rSquared?.toFixed(3) ?? '—' }})</span>
        </div>
      </div>
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">论文状态</h3>
        <div class="dashboard__data-row">
          <span>字数</span>
          <span>{{ manuscriptStore.wordCount.toLocaleString() }} 字</span>
        </div>
        <div class="dashboard__data-row">
          <span>写作问题</span>
          <StatusBadge :status="manuscriptStore.issueCount > 0 ? 'warning' : 'success'" :label="manuscriptStore.issueCount + ' 项待改进'" />
        </div>
        <div class="dashboard__data-row">
          <span>文献数量</span>
          <span>{{ knowledgeStore.totalDocuments }} 篇</span>
        </div>
      </div>
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">研究提醒</h3>
        <div class="dashboard__warning" v-for="(w, i) in warnings" :key="i">
          <StatusBadge :status="w.severity === 'warning' ? 'warning' : 'info'" :label="w.severity === 'warning' ? '设备提醒' : '建议'" />
          <span>{{ w.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard { padding: 24px 28px; max-width: 1200px; }
.dashboard__hero { margin-bottom: 24px; }
.dashboard__title { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: #0f172a; }
.dashboard__subtitle { margin: 0; font-size: 13px; color: #64748b; }
.dashboard__stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.dashboard__middle { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
.dashboard__bottom { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
.dashboard__card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; }
.dashboard__card-title { margin: 0 0 14px; font-size: 14px; font-weight: 600; color: #0f172a; }
.dashboard__data-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; padding: 6px 0; border-bottom: 1px solid #f1f5f9; color: #475569; }
.dashboard__bar { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; margin: 0 8px; }
.dashboard__bar-fill { height: 100%; background: #10b981; border-radius: 3px; }
.dashboard__mono { font-family: monospace; font-size: 12px; }
.dashboard__warning { display: flex; align-items: flex-start; gap: 8px; font-size: 12px; color: #334155; margin-bottom: 8px; }
</style>
