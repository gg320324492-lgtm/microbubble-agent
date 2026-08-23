<template>
  <div class="agent-mock">
    <div class="architecture">
      <h3>多智能体架构</h3>
      <div class="arch-diagram">
        <div class="supervisor">研究主管 Agent</div>
        <div class="agent-row">
          <div class="agent-node" v-for="a in agents" :key="a.name" :class="a.status">
            <div class="agent-icon">{{ a.icon }}</div>
            <div class="agent-name">{{ a.name }}</div>
            <div class="agent-status">{{ statusLabel(a.status) }}</div>
            <div class="agent-task" v-if="a.task">{{ a.task }}</div>
          </div>
        </div>
      </div>
    </div>
    <div class="status-panel">
      <div class="agent-status-card" v-for="a in agents" :key="a.name">
        <div class="status-indicator" :class="a.status"></div>
        <div class="status-info">
          <div class="status-name">{{ a.name }}</div>
          <div class="status-detail">{{ a.status === 'running' ? a.task : '待命' }}</div>
        </div>
      </div>
    </div>
    <div class="task-panel">
      <h3>任务分配</h3>
      <div class="task-item" v-for="t in tasks" :key="t.name">
        <span class="task-name">{{ t.name }}</span>
        <span class="task-agent">{{ t.agent }}</span>
        <span class="task-status" :class="t.status">{{ t.status === 'running' ? '运行中' : '排队中' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const agents = [
  { name: '文献Agent', icon: '📚', status: 'running', task: '分析论文 Zhang 2024' },
  { name: '实验Agent', icon: '🧪', status: 'idle', task: null },
  { name: '数据Agent', icon: '📊', status: 'running', task: '拟合动力学模型' },
  { name: '写作Agent', icon: '✍️', status: 'idle', task: null },
  { name: '审稿Agent', icon: '🔍', status: 'idle', task: null }
]

const tasks = [
  { name: '文献检索', agent: '文献Agent', status: 'running' },
  { name: '数据拟合', agent: '数据Agent', status: 'running' },
  { name: '结果写作', agent: '写作Agent', status: 'queued' }
]

function statusLabel(s: string) {
  return s === 'running' ? '运行中' : '空闲'
}
</script>

<style scoped>
.agent-mock { padding: 24px; }
.architecture { margin-bottom: 24px; }
.arch-diagram { text-align: center; }
.supervisor { display: inline-block; background: #1e293b; color: white; padding: 10px 20px; border-radius: 8px; font-weight: 600; margin-bottom: 16px; }
.agent-row { display: flex; justify-content: center; gap: 12px; }
.agent-node { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; min-width: 100px; text-align: center; }
.agent-node.running { border-color: #10b981; background: #f0fdf4; }
.agent-icon { font-size: 20px; margin-bottom: 4px; }
.agent-name { font-size: 12px; font-weight: 500; }
.agent-status { font-size: 11px; }
.agent-node.running .agent-status { color: #10b981; }
.agent-node.idle .agent-status { color: #94a3b8; }
.agent-task { font-size: 10px; color: #64748b; margin-top: 2px; }
.status-panel { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
.agent-status-card { display: flex; align-items: center; gap: 8px; background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px; }
.status-indicator { width: 8px; height: 8px; border-radius: 50%; }
.status-indicator.running { background: #10b981; }
.status-indicator.idle { background: #94a3b8; }
.status-name { font-size: 13px; font-weight: 500; }
.status-detail { font-size: 11px; color: #64748b; }
.task-panel { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; }
.task-item { display: flex; justify-content: space-between; font-size: 13px; padding: 6px 0; border-bottom: 1px solid #f1f5f9; }
.task-agent { color: #64748b; }
.task-status.running { color: #10b981; }
.task-status.queued { color: #f59e0b; }
h3 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
</style>
