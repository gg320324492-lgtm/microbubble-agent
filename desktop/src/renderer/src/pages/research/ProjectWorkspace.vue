<script setup lang="ts">
/**
 * 项目空间 — 研究项目工作台。
 * 集成项目信息 + 文献/实验/数据/论文快捷入口。
 */
import { ref, onMounted } from 'vue'
import { useProjectStore } from '../../stores/research/project.store'
import { useKnowledgeStore } from '../../stores/research/knowledge.store'
import { useDatasetStore } from '../../stores/research/dataset.store'
import { useManuscriptStore } from '../../stores/research/manuscript.store'
import { useExperimentStore } from '../../stores/research/experiment.store'
import ScientificMetric from '../../components/research/ScientificMetric.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const projectStore = useProjectStore()
const knowledgeStore = useKnowledgeStore()
const datasetStore = useDatasetStore()
const manuscriptStore = useManuscriptStore()
const experimentStore = useExperimentStore()

const activeTab = ref('overview')
const tabs = [
  { id: 'overview', label: '项目概览', icon: '📋' },
  { id: 'literature', label: '文献', icon: '📚' },
  { id: 'experiment', label: '实验', icon: '🧪' },
  { id: 'data', label: '数据', icon: '📊' },
  { id: 'manuscript', label: '论文', icon: '📝' },
]

onMounted(async () => {
  await Promise.all([
    knowledgeStore.loadDocuments(),
    datasetStore.loadReport(),
    manuscriptStore.loadManuscript(),
    experimentStore.loadDesign()
  ])
})

const milestones = [
  { label: '文献检索与证据汇总', status: 'done' as const },
  { label: '实验设计与条件确定', status: 'done' as const },
  { label: '动力学拟合与结果', status: 'current' as const },
  { label: '机理与结论', status: 'pending' as const },
  { label: '论文撰写与投稿', status: 'pending' as const },
]
</script>

<template>
  <div class="workspace">
    <!-- 项目头 -->
    <div class="workspace__header">
      <div>
        <h1 class="workspace__title">{{ projectStore.projectName }}</h1>
        <p class="workspace__domain">{{ projectStore.projectDomain }} · {{ projectStore.currentProject.status === 'active' ? '进行中' : '规划中' }}</p>
      </div>
      <div class="workspace__progress">
        <div class="workspace__progress-bar">
          <div class="workspace__progress-fill" :style="{ width: (projectStore.currentProject.progress * 100) + '%' }" />
        </div>
        <span>{{ Math.round(projectStore.currentProject.progress * 100) }}% 完成</span>
      </div>
    </div>

    <!-- 标签页 -->
    <div class="workspace__tabs">
      <div v-for="t in tabs" :key="t.id" class="workspace__tab" :class="{ 'workspace__tab--active': activeTab === t.id }" @click="activeTab = t.id">
        {{ t.icon }} {{ t.label }}
      </div>
    </div>

    <!-- 概览 -->
    <div v-if="activeTab === 'overview'" class="workspace__content">
      <div class="workspace__stats">
        <ScientificMetric label="文献" :value="String(knowledgeStore.totalDocuments)" unit="篇" />
        <ScientificMetric label="数据集" :value="String(projectStore.currentProject.stats.datasets)" unit="个" />
        <ScientificMetric label="实验" :value="String(projectStore.currentProject.stats.experiments)" unit="次" />
        <ScientificMetric label="模型 R²" :value="datasetStore.models[0]?.rSquared?.toFixed(3) ?? '—'" />
      </div>
      <div class="workspace__milestones">
        <h3>项目里程碑</h3>
        <div class="workspace__milestone" v-for="(m, i) in milestones" :key="i">
          <StatusBadge :status="m.status === 'done' ? 'success' : m.status === 'current' ? 'info' : 'neutral'"
                       :label="m.status === 'done' ? '✓ 已完成' : m.status === 'current' ? '● 进行中' : '○ 待开始'" />
          <span>{{ m.label }}</span>
        </div>
      </div>
    </div>

    <!-- 文献 -->
    <div v-if="activeTab === 'literature'" class="workspace__content">
      <h3>文献库 ({{ knowledgeStore.totalDocuments }})</h3>
      <div class="workspace__doc-list">
        <div class="workspace__doc-item" v-for="d in knowledgeStore.documents" :key="d.id">
          <div class="workspace__doc-title">{{ d.title }}</div>
          <div class="workspace__doc-meta">{{ d.authors }} · {{ d.journal }}, {{ d.year }}</div>
          <div class="workspace__doc-tags"><span v-for="t in d.tags" :key="t" class="workspace__tag">{{ t }}</span></div>
          <div class="workspace__doc-cred">可信度 {{ (d.credibility * 100).toFixed(0) }}%</div>
        </div>
      </div>
    </div>

    <!-- 实验 -->
    <div v-if="activeTab === 'experiment' && experimentStore.design" class="workspace__content">
      <h3>{{ experimentStore.design.title }}</h3>
      <div class="workspace__exp-section">
        <h4>假设</h4>
        <div v-for="(h, i) in experimentStore.design.hypotheses" :key="i" class="workspace__hypothesis">
          H{{ i + 1 }}: {{ h.statement }} <span class="workspace__conf">({{ (h.confidence * 100).toFixed(0) }}%)</span>
        </div>
      </div>
      <div class="workspace__exp-section">
        <h4>变量</h4>
        <div v-for="v in experimentStore.design.variables" :key="v.name" class="workspace__variable">
          <StatusBadge :status="v.type === 'dependent' ? 'info' : 'success'" :label="v.type === 'independent' ? '自' : v.type === 'dependent' ? '因' : '控'" />
          {{ v.name }} ({{ v.range }} {{ v.unit }})
        </div>
      </div>
      <div class="workspace__exp-section">
        <h4>推荐模型</h4>
        <StatusBadge status="info" :label="experimentStore.design.model.name + ' (置信度 ' + (experimentStore.design.model.confidence * 100).toFixed(0) + '%)'" />
      </div>
    </div>

    <!-- 数据 -->
    <div v-if="activeTab === 'data'" class="workspace__content">
      <h3>数据分析结果</h3>
      <div class="workspace__data-grid">
        <div class="workspace__data-card" v-for="s in datasetStore.statistics" :key="s.metric">
          <div class="workspace__data-label">{{ s.metric }}</div>
          <div class="workspace__data-value">{{ s.value }}</div>
          <div class="workspace__data-interp">{{ s.interpretation }}</div>
        </div>
      </div>
      <div class="workspace__exp-section" v-if="datasetStore.models.length">
        <h4>模型拟合</h4>
        <div v-for="m in datasetStore.models" :key="m.model" class="workspace__model-row">
          <span class="mono">{{ m.model }}</span>
          <span>R² = {{ m.rSquared }}</span>
          <StatusBadge :status="m.rSquared > 0.9 ? 'success' : 'warning'" :label="m.rSquared > 0.9 ? '拟合良好' : '拟合一般'" />
        </div>
      </div>
    </div>

    <!-- 论文 -->
    <div v-if="activeTab === 'manuscript'" class="workspace__content">
      <div v-if="manuscriptStore.manuscript">
        <h3>{{ manuscriptStore.manuscript.title }}</h3>
        <div class="workspace__ms-info">
          <span>{{ manuscriptStore.wordCount.toLocaleString() }} 字</span>
          <StatusBadge :status="manuscriptStore.issueCount > 0 ? 'warning' : 'success'" :label="manuscriptStore.issueCount + ' 个写作问题'" />
        </div>
        <div v-for="s in manuscriptStore.sections" :key="s.sectionType" class="workspace__ms-section">
          <h4>{{ s.title }}</h4>
          <p>{{ s.content.slice(0, 200) }}...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workspace { padding: 24px 28px; max-width: 1200px; }
.workspace__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.workspace__title { margin: 0; font-size: 22px; font-weight: 700; color: #0f172a; }
.workspace__domain { margin: 0; font-size: 13px; color: #64748b; }
.workspace__progress { text-align: right; font-size: 12px; color: #64748b; }
.workspace__progress-bar { width: 120px; height: 6px; background: #f1f5f9; border-radius: 3px; margin-bottom: 4px; margin-left: auto; }
.workspace__progress-fill { height: 100%; background: #3b82f6; border-radius: 3px; }
.workspace__tabs { display: flex; gap: 4px; border-bottom: 1px solid #e5e7eb; margin-bottom: 20px; }
.workspace__tab { padding: 10px 16px; font-size: 13px; color: #64748b; cursor: pointer; border-bottom: 2px solid transparent; transition: all .15s; }
.workspace__tab--active { color: #2563eb; border-bottom-color: #2563eb; font-weight: 500; }
.workspace__tab:hover { color: #1e293b; }
.workspace__content { }
.workspace__stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.workspace__milestones { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.workspace__milestones h3 { margin: 0 0 12px; font-size: 14px; font-weight: 600; }
.workspace__milestone { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; color: #334155; }
.workspace__doc-list { display: flex; flex-direction: column; gap: 8px; }
.workspace__doc-item { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px; }
.workspace__doc-title { font-size: 14px; font-weight: 500; color: #1e293b; margin-bottom: 4px; }
.workspace__doc-meta { font-size: 12px; color: #64748b; margin-bottom: 6px; }
.workspace__doc-tags { display: flex; gap: 4px; margin-bottom: 6px; }
.workspace__tag { font-size: 11px; padding: 2px 8px; background: #eff6ff; color: #2563eb; border-radius: 4px; }
.workspace__doc-cred { font-size: 12px; color: #10b981; font-weight: 500; }
.workspace__exp-section { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
.workspace__exp-section h4 { margin: 0 0 8px; font-size: 13px; font-weight: 600; }
.workspace__hypothesis { font-size: 13px; color: #334155; margin-bottom: 6px; }
.workspace__conf { color: #10b981; font-size: 12px; }
.workspace__variable { font-size: 13px; display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.workspace__data-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.workspace__data-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
.workspace__data-label { font-size: 11px; color: #94a3b8; }
.workspace__data-value { font-size: 16px; font-weight: 600; color: #1e293b; }
.workspace__data-interp { font-size: 11px; color: #64748b; }
.workspace__model-row { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
.mono { font-family: 'JetBrains Mono', monospace; }
.workspace__ms-info { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; font-size: 13px; color: #64748b; }
.workspace__ms-section { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px; margin-bottom: 10px; }
.workspace__ms-section h4 { margin: 0 0 6px; font-size: 13px; font-weight: 600; }
.workspace__ms-section p { margin: 0; font-size: 13px; color: #64748b; line-height: 1.5; }
</style>
