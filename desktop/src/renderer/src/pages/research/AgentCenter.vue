<script setup lang="ts">
/**
 * 智能体中心 — 多智能体架构展示。
 */
import AgentCard from '../../components/research/AgentCard.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const agents = [
  { icon: '📚', name: '文献智能体', status: 'running' as const, task: '正在分析 Zhang 2024 论文' },
  { icon: '🧪', name: '实验智能体', status: 'idle' as const },
  { icon: '📊', name: '数据智能体', status: 'running' as const, task: '拟合动力学模型' },
  { icon: '✍️', name: '论文智能体', status: 'idle' as const },
  { icon: '🔍', name: '审稿智能体', status: 'idle' as const },
]

const tasks = [
  { name: '文献检索与分析', agent: '文献智能体', status: 'running' },
  { name: '数据拟合与统计', agent: '数据智能体', status: 'running' },
  { name: '实验方案优化', agent: '实验智能体', status: 'queued' },
  { name: '结果撰写', agent: '论文智能体', status: 'queued' },
]
</script>

<template>
  <div class="agents">
    <div class="agents__header">
      <h1 class="agents__title">智能体中心</h1>
      <StatusBadge status="info" label="5 个智能体" />
    </div>

    <!-- 架构图 -->
    <div class="agents__arch">
      <div class="agents__supervisor">
        <span class="agents__sup-icon">🧠</span>
        <span>科研主管智能体</span>
      </div>
      <div class="agents__line" />
      <div class="agents__row">
        <AgentCard v-for="a in agents" :key="a.name" v-bind="a" />
      </div>
    </div>

    <!-- 任务分配 -->
    <div class="agents__tasks">
      <h3>任务分配</h3>
      <div class="agents__task" v-for="t in tasks" :key="t.name">
        <span class="agents__task-name">{{ t.name }}</span>
        <span class="agents__task-agent">{{ t.agent }}</span>
        <StatusBadge :status="t.status === 'running' ? 'success' : 'neutral'" :label="t.status === 'running' ? '运行中' : '排队中'" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.agents { padding: 24px 28px; }
.agents__header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.agents__title { margin: 0; font-size: 20px; font-weight: 700; color: #0f172a; }
.agents__arch { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; margin-bottom: 20px; text-align: center; }
.agents__supervisor { display: inline-flex; align-items: center; gap: 8px; background: #0f172a; color: #fff; padding: 10px 20px; border-radius: 10px; font-weight: 600; font-size: 14px; }
.agents__sup-icon { font-size: 18px; }
.agents__line { width: 2px; height: 20px; background: #e2e8f0; margin: 0 auto 16px; }
.agents__row { display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }
.agents__tasks { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.agents__tasks h3 { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: #0f172a; }
.agents__task { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
.agents__task-name { font-weight: 500; color: #1e293b; }
.agents__task-agent { color: #64748b; }
</style>
