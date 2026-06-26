<template>
  <section id="paper-related" class="related-knowledge">
    <header class="related-header">
      <h2 class="related-title">🔗 相关知识</h2>
      <span v-if="related.length" class="related-count">{{ related.length }} 条</span>
    </header>

    <div v-if="related.length" class="related-grid">
      <article
        v-for="item in related"
        :key="item.id"
        class="related-card"
        @click="$router.push('/knowledge/' + item.id)"
      >
        <div class="related-card-header">
          <h3 class="related-card-title">{{ item.title || '（无标题）' }}</h3>
          <el-tag
            size="small"
            :type="relationTagType(item.relation_type)"
            effect="light"
            class="related-card-score"
          >
            {{ relationLabel(item.relation_type) }} {{ scorePercent(item.score) }}%
          </el-tag>
        </div>
        <div v-if="item.reason" class="related-card-reason">{{ item.reason }}</div>
        <div v-if="item.summary" class="related-card-summary">{{ truncate(item.summary, 120) }}</div>
        <div v-if="item.category" class="related-card-category">
          <span class="category-chip">{{ item.category }}</span>
        </div>
      </article>
    </div>

    <div v-else class="related-empty">
      <el-icon class="related-empty-icon"><Connection /></el-icon>
      <p class="related-empty-text">暂无相关知识</p>
    </div>
  </section>
</template>

<script setup>
import { Connection } from '@element-plus/icons-vue'

defineProps({
  related: { type: Array, default: () => [] },
})

const relationTagType = (type) => {
  const map = {
    similar: 'success',
    supplements: 'warning',
    extends: '',
    supports: '',
    contradicts: 'danger',
    method_inherits: 'primary',
    cites: 'info',
    prerequisite: 'warning',
    compares: 'primary',
  }
  return map[type] || 'info'
}

const relationLabel = (type) => {
  const map = {
    similar: '相似',
    supplements: '补充',
    extends: '扩展',
    supports: '支持',
    contradicts: '矛盾',
    method_inherits: '方法继承',
    cites: '引用',
    prerequisite: '前置',
    compares: '对比',
  }
  return map[type] || type
}

const scorePercent = (s) => Math.round((s || 0) * 100)

const truncate = (text, n) => {
  if (!text) return ''
  return text.length > n ? text.slice(0, n) + '…' : text
}
</script>

<style scoped>
.related-knowledge {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  padding: 20px 24px;
  margin: 0 0 24px;
  box-shadow: var(--shadow-md);
}

.related-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.related-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.related-count {
  font-size: 12px;
  color: var(--color-text-placeholder);
}

.related-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.related-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.related-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 4px 12px rgba(255, 122, 92, 0.1);
  transform: translateY(-1px);
}

.related-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.related-card-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.4;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.related-card:hover .related-card-title {
  color: var(--color-primary);
}

.related-card-score {
  flex-shrink: 0;
}

.related-card-reason {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.related-card-summary {
  font-size: 12.5px;
  color: var(--color-text-placeholder);
  line-height: 1.6;
}

.related-card-category {
  margin-top: 4px;
}

.category-chip {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 4px;
}

.related-empty {
  text-align: center;
  padding: 32px 20px;
  color: var(--color-text-placeholder);
}

.related-empty-icon {
  font-size: 36px;
  color: var(--color-border-light);
  margin-bottom: 8px;
}

.related-empty-text {
  font-size: 13px;
  margin: 0;
}
</style>
