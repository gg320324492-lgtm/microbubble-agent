<template>
  <div class="knowledge-view">
    <header class="header">
      <div class="header-left">
        <h2>知识库</h2>
        <p>管理和查阅文档资料</p>
      </div>
      <div class="header-right">
        <button class="btn btn-primary">➕ 上传文档</button>
      </div>
    </header>

    <div class="search-bar">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索知识库..."
        class="input"
      />
      <button class="btn btn-secondary">搜索</button>
    </div>

    <div class="knowledge-grid">
      <div v-for="item in knowledgeItems" :key="item.id" class="knowledge-card">
        <div class="card-icon">📚</div>
        <h3>{{ item.title }}</h3>
        <p>{{ item.description }}</p>
        <div class="card-meta">
          <span class="tag">{{ item.category }}</span>
          <span class="date">{{ item.created_at }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const searchQuery = ref('')
const knowledgeItems = ref([
  {
    id: 1,
    title: '微纳米气泡基础知识',
    description: '介绍微纳米气泡的基本概念、生成方法和应用领域',
    category: '基础知识',
    created_at: '2026-06-01'
  },
  {
    id: 2,
    title: '实验操作规范',
    description: '实验室安全操作规程和设备使用指南',
    category: '操作规范',
    created_at: '2026-05-28'
  },
  {
    id: 3,
    title: '数据分析方法',
    description: '常用数据分析方法和工具介绍',
    category: '数据分析',
    created_at: '2026-05-25'
  }
])
</script>

<style scoped>
.knowledge-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-left p {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.search-bar {
  display: flex;
  gap: 12px;
}

.search-bar .input {
  flex: 1;
}

.knowledge-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.knowledge-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
}

.knowledge-card:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.card-icon {
  font-size: 32px;
  margin-bottom: 16px;
}

.knowledge-card h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.knowledge-card p {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: 16px;
}

.card-meta {
  display: flex;
  justify-content: space-between;
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
</style>
