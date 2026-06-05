<template>
  <div class="knowledge-dashboard">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">📚</div>
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">总文档数</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📁</div>
        <div class="stat-value">{{ stats.categories }}</div>
        <div class="stat-label">分类数</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">🏷️</div>
        <div class="stat-value">{{ stats.tags }}</div>
        <div class="stat-label">标签数</div>
      </div>
    </div>

    <div class="recent-documents">
      <h3>最近文档</h3>
      <div class="document-list">
        <div v-for="doc in recentDocs" :key="doc.id" class="document-item">
          <div class="doc-icon">📄</div>
          <div class="doc-content">
            <h4>{{ doc.title }}</h4>
            <p>{{ doc.description }}</p>
          </div>
          <div class="doc-meta">
            <span class="tag">{{ doc.category }}</span>
            <span class="date">{{ doc.date }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const stats = ref({
  total: 25,
  categories: 6,
  tags: 18
})

const recentDocs = ref([
  {
    id: 1,
    title: '微纳米气泡基础知识',
    description: '介绍微纳米气泡的基本概念、生成方法和应用领域',
    category: '基础知识',
    date: '2026-06-01'
  },
  {
    id: 2,
    title: '实验操作规范',
    description: '实验室安全操作规程和设备使用指南',
    category: '操作规范',
    date: '2026-05-28'
  },
  {
    id: 3,
    title: '数据分析方法',
    description: '常用数据分析方法和工具介绍',
    category: '数据分析',
    date: '2026-05-25'
  }
])
</script>

<style scoped>
.knowledge-dashboard {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.stats-grid {
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
  transition: all var(--duration-normal) var(--ease-out);
}

.stat-card:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
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

.recent-documents {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
}

.recent-documents h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 16px;
}

.document-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.document-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.document-item:hover {
  background: var(--color-bg-hover);
}

.doc-icon {
  font-size: 24px;
}

.doc-content {
  flex: 1;
}

.doc-content h4 {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.doc-content p {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.doc-meta {
  display: flex;
  gap: 12px;
  align-items: center;
}

.tag {
  padding: 4px 12px;
  background: var(--color-bg-active);
  border-radius: var(--radius-full);
  font-size: 12px;
  color: var(--color-text-secondary);
}

.date {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

@media (max-width: 1024px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
