<template>
  <div class="dashboard-mock">
    <h1>科研项目总览</h1>
    <div class="stat-cards">
      <div class="stat-card" v-for="project in projects" :key="project.name">
        <div class="stat-label">{{ project.name }}</div>
        <div class="stat-value">{{ Math.round(project.progress * 100) }}%</div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: project.progress * 100 + '%' }"></div>
        </div>
        <div class="stat-status" :class="project.status">{{ statusLabel(project.status) }}</div>
      </div>
    </div>
    <div class="insight-cards">
      <div class="insight-card" v-for="insight in insights" :key="insight.finding">
        <div class="insight-finding">发现: {{ insight.finding }}</div>
        <div class="insight-suggestion">建议: {{ insight.suggestion }}</div>
      </div>
    </div>
    <div class="warning-panel" v-if="warnings.length">
      <h3>警告面板</h3>
      <div class="warning-item" v-for="w in warnings" :key="w.message">
        ⚠ {{ w.message }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const projects = [
  { name: 'O3-MNBs TC降解', progress: 0.75, status: 'active' },
  { name: '纳米气泡表征', progress: 0.3, status: 'planning' }
]

const insights = [
  { finding: '动力学模型选择可能不足', suggestion: '补充自由基验证实验' }
]

const warnings = [
  { type: 'data_quality', message: '浓度数据缺失 15%', severity: 'medium' }
]

function statusLabel(s: string) {
  return s === 'active' ? '进行中' : '规划中'
}
</script>

<style scoped>
.dashboard-mock { padding: 24px; }
.stat-cards { display: flex; gap: 16px; margin-bottom: 24px; }
.stat-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; min-width: 200px; }
.stat-label { font-size: 12px; color: #64748b; margin-bottom: 4px; }
.stat-value { font-size: 24px; font-weight: 600; color: #1e293b; }
.progress-bar { height: 4px; background: #e2e8f0; border-radius: 2px; margin: 8px 0; }
.progress-fill { height: 100%; background: #2563eb; border-radius: 2px; transition: width 0.3s; }
.stat-status { font-size: 12px; }
.stat-status.active { color: #10b981; }
.stat-status.planning { color: #f59e0b; }
.insight-cards { display: flex; gap: 16px; margin-bottom: 24px; }
.insight-card { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 16px; flex: 1; }
.insight-finding { font-weight: 500; margin-bottom: 4px; }
.insight-suggestion { font-size: 13px; color: #64748b; }
.warning-panel { background: #fefce8; border: 1px solid #fde68a; border-radius: 8px; padding: 16px; }
.warning-item { font-size: 13px; color: #92400e; margin-bottom: 4px; }
h1 { font-size: 20px; font-weight: 600; margin-bottom: 16px; }
h3 { font-size: 14px; font-weight: 500; margin-bottom: 8px; }
</style>
