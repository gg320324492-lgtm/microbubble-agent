<script setup lang="ts">
/**
 * 首页 — 科研项目总览 Dashboard。
 */
import ProjectCard from '../../components/research/ProjectCard.vue'
import InsightCard from '../../components/research/InsightCard.vue'
import ScientificMetric from '../../components/research/ScientificMetric.vue'
import Timeline from '../../components/research/Timeline.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const project = {
  name: 'O3-MNBs 强化四环素降解研究',
  description: '探索微纳米气泡臭氧技术对四环素类抗生素的降解效率与机理',
  progress: 0.68,
  status: 'active' as const,
}

const stats = [
  { label: '实验总数', value: '28', unit: '次', trend: 'up' as const, trendText: '+4 本周' },
  { label: '数据集', value: '12', unit: '个', trend: 'up' as const, trendText: '+2 本周' },
  { label: '文献管理', value: '156', unit: '篇', trend: 'up' as const, trendText: '+8 本周' },
  { label: '论文进度', value: '45', unit: '%', trend: 'up' as const, trendText: '进行中' },
]

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
    <!-- 项目标题 -->
    <div class="dashboard__hero">
      <div>
        <h1 class="dashboard__title">{{ project.name }}</h1>
        <p class="dashboard__subtitle">欢迎回来，以下是项目最新概览</p>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="dashboard__stats">
      <ScientificMetric v-for="s in stats" :key="s.label" v-bind="s" />
    </div>

    <!-- 中部：里程碑 + 任务 -->
    <div class="dashboard__middle">
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">项目里程碑</h3>
        <Timeline :steps="milestones" />
      </div>
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">本周任务</h3>
        <div class="dashboard__task-list">
          <div class="dashboard__task" v-for="(task, i) in ['分析 TC 微纳米气泡降解动力学数据', '拟合不同浓度下的降解模型', '更新实验记录与数据集', '撰写动力学分析报告']" :key="i">
            <StatusBadge :status="i < 3 ? 'success' : 'neutral'" :label="i < 3 ? '已完成' : '进行中'" />
            <span>{{ task }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部：AI 洞察 + 警告 -->
    <div class="dashboard__bottom">
      <div class="dashboard__card">
        <h3 class="dashboard__card-title">AI 科研洞察</h3>
        <InsightCard v-for="(ins, i) in insights" :key="i" v-bind="ins" />
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
.dashboard__bottom { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.dashboard__card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; }
.dashboard__card-title { margin: 0 0 14px; font-size: 14px; font-weight: 600; color: #0f172a; }
.dashboard__task-list { display: flex; flex-direction: column; gap: 10px; }
.dashboard__task { display: flex; align-items: center; gap: 10px; font-size: 13px; color: #334155; }
.dashboard__warning { display: flex; align-items: flex-start; gap: 10px; font-size: 13px; color: #334155; margin-bottom: 10px; }
</style>
