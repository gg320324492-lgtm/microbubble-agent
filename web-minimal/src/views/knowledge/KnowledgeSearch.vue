<template>
  <div class="knowledge-search">
    <div class="search-bar">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索知识库..."
        class="input"
        @keyup.enter="handleSearch"
      />
      <button class="btn btn-primary" @click="handleSearch">搜索</button>
    </div>

    <div v-if="results.length > 0" class="search-results">
      <div class="results-header">
        <h3>搜索结果</h3>
        <span>找到 {{ results.length }} 条结果</span>
      </div>
      <div class="results-list">
        <div v-for="result in results" :key="result.id" class="result-item">
          <div class="result-icon">📄</div>
          <div class="result-content">
            <h4>{{ result.title }}</h4>
            <p>{{ result.description }}</p>
            <div class="result-meta">
              <span class="tag">{{ result.category }}</span>
              <span class="relevance">相关度: {{ result.relevance }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="searchQuery && !loading" class="empty-state">
      <div class="icon">🔍</div>
      <p>未找到相关结果</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const searchQuery = ref('')
const loading = ref(false)
const results = ref([])

const handleSearch = async () => {
  if (!searchQuery.value.trim()) return

  loading.value = true
  // 模拟搜索
  setTimeout(() => {
    results.value = [
      {
        id: 1,
        title: '微纳米气泡基础知识',
        description: '介绍微纳米气泡的基本概念、生成方法和应用领域',
        category: '基础知识',
        relevance: 95
      },
      {
        id: 2,
        title: '气泡生成技术',
        description: '各种气泡生成技术的比较和选择指南',
        category: '技术文档',
        relevance: 85
      }
    ]
    loading.value = false
  }, 500)
}
</script>

<style scoped>
.knowledge-search {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.search-bar {
  display: flex;
  gap: 12px;
}

.search-bar .input {
  flex: 1;
}

.search-results {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border);
}

.results-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.results-header span {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.results-list {
  display: flex;
  flex-direction: column;
}

.result-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border);
  transition: all var(--duration-fast) var(--ease-out);
}

.result-item:last-child {
  border-bottom: none;
}

.result-item:hover {
  background: var(--color-bg-hover);
}

.result-icon {
  font-size: 24px;
  margin-top: 4px;
}

.result-content {
  flex: 1;
}

.result-content h4 {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.result-content p {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: 8px;
}

.result-meta {
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

.relevance {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: var(--color-text-tertiary);
}

.empty-state .icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-state p {
  font-size: 14px;
}
</style>
