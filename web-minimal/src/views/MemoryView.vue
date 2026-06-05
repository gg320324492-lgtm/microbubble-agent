<template>
  <div class="memory-view">
    <header class="header">
      <div class="header-left">
        <h2>长期记忆</h2>
        <p>AI 助手的长期记忆库</p>
      </div>
      <div class="header-right">
        <button class="btn btn-primary">➕ 添加记忆</button>
      </div>
    </header>

    <div class="search-bar">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索记忆..."
        class="input"
      />
      <button class="btn btn-secondary">搜索</button>
    </div>

    <div class="memory-list">
      <div v-for="memory in memories" :key="memory.id" class="memory-card">
        <div class="memory-content">
          <h3>{{ memory.title }}</h3>
          <p>{{ memory.content }}</p>
        </div>
        <div class="memory-meta">
          <span class="tag">{{ memory.category }}</span>
          <span class="date">{{ memory.created_at }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const searchQuery = ref('')
const memories = ref([
  {
    id: 1,
    title: '用户偏好设置',
    content: '用户喜欢简洁的界面风格，偏好深色主题',
    category: '偏好',
    created_at: '2026-06-01'
  },
  {
    id: 2,
    title: '常用命令',
    content: '用户经常使用任务管理和会议安排功能',
    category: '使用习惯',
    created_at: '2026-05-28'
  },
  {
    id: 3,
    title: '项目背景',
    content: '微纳米气泡研究项目，目标是开发新型气泡生成技术',
    category: '项目',
    created_at: '2026-05-25'
  }
])
</script>

<style scoped>
.memory-view {
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

.memory-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.memory-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
}

.memory-card:hover {
  box-shadow: var(--shadow-sm);
}

.memory-content h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.memory-content p {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: 16px;
}

.memory-meta {
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
