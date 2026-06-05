<template>
  <div class="knowledge-health">
    <header class="header">
      <div class="header-left">
        <h3>健康检查</h3>
        <p>检查知识库的健康状态</p>
      </div>
      <div class="header-right">
        <button class="btn btn-primary" @click="runHealthCheck">运行检查</button>
      </div>
    </header>

    <div class="health-stats">
      <div class="stat-card">
        <div class="stat-icon success">✅</div>
        <div class="stat-value">{{ healthStats.healthy }}</div>
        <div class="stat-label">健康</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon warning">⚠️</div>
        <div class="stat-value">{{ healthStats.warning }}</div>
        <div class="stat-label">警告</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon danger">❌</div>
        <div class="stat-value">{{ healthStats.error }}</div>
        <div class="stat-label">错误</div>
      </div>
    </div>

    <div class="health-issues">
      <h3>问题列表</h3>
      <div class="issue-list">
        <div v-for="issue in issues" :key="issue.id" class="issue-item" :class="issue.level">
          <div class="issue-icon">
            <span v-if="issue.level === 'warning'">⚠️</span>
            <span v-else>❌</span>
          </div>
          <div class="issue-content">
            <h4>{{ issue.title }}</h4>
            <p>{{ issue.description }}</p>
          </div>
          <div class="issue-actions">
            <button class="btn btn-ghost btn-small">修复</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const healthStats = ref({
  healthy: 20,
  warning: 3,
  error: 1
})

const issues = ref([
  {
    id: 1,
    level: 'warning',
    title: '重复内容',
    description: '发现 2 篇内容高度相似的文档'
  },
  {
    id: 2,
    level: 'warning',
    title: '过期内容',
    description: '有 1 篇文档超过 6 个月未更新'
  },
  {
    id: 3,
    level: 'error',
    title: '缺失引用',
    description: '有 1 篇文档引用了不存在的资源'
  }
])

const runHealthCheck = () => {
  // 模拟健康检查
  console.log('运行健康检查...')
}
</script>

<style scoped>
.knowledge-health {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-left p {
  font-size: 13px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.health-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.stat-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
  text-align: center;
}

.stat-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.health-issues {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
}

.health-issues h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 16px;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.issue-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.issue-item:hover {
  background: var(--color-bg-hover);
}

.issue-item.warning {
  background: var(--color-warning-bg);
}

.issue-item.error {
  background: var(--color-danger-bg);
}

.issue-icon {
  font-size: 24px;
}

.issue-content {
  flex: 1;
}

.issue-content h4 {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.issue-content p {
  font-size: 13px;
  color: var(--color-text-secondary);
}

@media (max-width: 1024px) {
  .health-stats {
    grid-template-columns: 1fr;
  }
}
</style>
