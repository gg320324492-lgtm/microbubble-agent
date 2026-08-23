<script setup lang="ts">
/**
 * 首页 — 升级版：项目总览 + AI活动。
 */
import { onMounted } from 'vue'
import { useProjectStore } from '../../stores/research/project.store'
import { useKnowledgeStore } from '../../stores/research/knowledge.store'
import { useDatasetStore } from '../../stores/research/dataset.store'
import { useManuscriptStore } from '../../stores/research/manuscript.store'
import ScientificMetric from '../../components/research/ScientificMetric.vue'
import InsightCard from '../../components/research/InsightCard.vue'
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

const recentActivities = [
  { time: '09:32', label: '完成文献检索', icon: '📚', status: 'success' as const },
  { time: '09:35', label: '完成动力学分析', icon: '📊', status: 'success' as const },
  { time: '09:40', label: '生成实验方案', icon: '🧪', status: 'success' as const },
  { time: '09:45', label: '正在拟合模型', icon: '⚙️', status: 'running' as const },
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

    <!-- 统计卡片 -->
    <div class="dashboard__stats">
      <ScientificMetric label="文献" :value="String(knowledgeStore.totalDocuments)" unit="篇" trend="up" trendText="+8 本周" />
      <ScientificMetric label="实验" :value="String(projectStore.currentProject.stats.experiments)" unit="次" trend="up" trendText="+4 本周" />
      <ScientificMetric label="数据" :value="String(projectStore.currentProject.stats.datasets)" unit="个" trend="up" trendText="+2 本周" />
      <ScientificMetric label="模型 R²" :value="datasetStore.models[0]?.rSquared?.toFixed(3) ?? '—'" />
    </div>

    <div class="dashboard__middle">
      <!-- 最近 AI 活动 -->
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">最近 AI 活动</h3>
        <div class="dashboard__activity" v-for="(a, i) in recentActivities" :key="i">
          <span class="dashboard__activity-time">{{ a.time }}</span>
          <span class="dashboard__activity-icon">{{ a.icon }}</span>
          <span class="dashboard__activity-label">{{ a.label }}</span>
          <StatusBadge :status="a.status" :label="a.status === 'success' ? '完成' : '进行中'" />
        </div>
      </div>
      <!-- AI 洞察 -->
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">AI 科研洞察</h3>
        <InsightCard v-for="(ins, i) in insights" :key="i" v-bind="ins" />
      </div>
    </div>

    <div class="dashboard__bottom">
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">数据概览</h3>
        <div class="dashboard__data-row">
          <span>数据完整度</span>
          <span class="dashboard__mono">{{ ((datasetStore.quality?.completeness ?? 0) * 100).toFixed(0) }}%</span>
        </div>
        <div class="dashboard__data-row">
          <span>最佳模型</span>
          <span class="dashboard__mono">{{ datasetStore.models[0]?.model ?? '—' }}</span>
        </div>
        <div class="dashboard__data-row">
          <span>拟合优度 R²</span>
          <span class="dashboard__mono">{{ datasetStore.models[0]?.rSquared?.toFixed(3) ?? '—' }}</span>
        </div>
      </div>
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">论文状态</h3>
        <div class="dashboard__data-row"><span>字数</span><span>{{ manuscriptStore.wordCount.toLocaleString() }} 字</span></div>
        <div class="dashboard__data-row">
          <span>写作问题</span>
          <StatusBadge :status="manuscriptStore.issueCount > 0 ? 'warning' : 'success'" :label="manuscriptStore.issueCount + ' 项待改进'" />
        </div>
        <div class="dashboard__data-row"><span>文献数量</span><span>{{ knowledgeStore.totalDocuments }} 篇</span></div>
      </div>
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">科学解读</h3>
        <div class="dashboard__conclusion" v-for="c in datasetStore.conclusions.slice(0, 2)" :key="c.observation">
          <div class="dashboard__conc-obs">{{ c.observation }}</div>
          <div class="dashboard__conc-conf">置信度 {{ (c.confidence * 100).toFixed(0) }}%</div>
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
.dashboard__card-title { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: #0f172a; }
.dashboard__activity { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
.dashboard__activity-time { color: #94a3b8; font-size: 12px; min-width: 40px; }
.dashboard__activity-icon { font-size: 16px; }
.dashboard__activity-label { flex: 1; color: #1e293b; }
.dashboard__data-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; padding: 6px 0; border-bottom: 1px solid #f1f5f9; color: #475569; }
.dashboard__mono { font-family: monospace; font-size: 13px; font-weight: 600; color: #1e293b; }
.dashboard__conclusion { margin-bottom: 8px; padding: 8px 10px; background: #f8fafc; border-radius: 6px; }
.dashboard__conc-obs { font-size: 12px; font-weight: 500; color: #1e293b; }
.dashboard__conc-conf { font-size: 11px; color: #10b981; margin-top: 2px; }
</style>
