<template>
  <div class="knowledge-dashboard">
    <!-- 热门分类 -->
    <div class="categories-section">
      <div class="section-header">
        <h3 class="section-title">🏷️ 知识分类</h3>
        <el-button text size="small" @click="$emit('show-all-categories')">
          查看全部
        </el-button>
      </div>
      <div class="categories-scroll">
        <div
          class="category-chip"
          :class="{ 'category-active': activeCategory === '' }"
          @click="$emit('filter-category', '')"
        >
          📚 全部
        </div>
        <!-- 预设分类 -->
        <div
          v-for="cat in presetCategories"
          :key="cat.name"
          class="category-chip"
          :class="{ 'category-active': activeCategory === cat.name }"
          @click="$emit('filter-category', cat.name)"
        >
          {{ cat.icon }} {{ cat.name }}
          <span class="category-count" v-if="getCategoryCount(cat.name) > 0">{{ getCategoryCount(cat.name) }}</span>
        </div>
        <!-- 动态分类（排除已有的预设分类） -->
        <div
          v-for="cat in dynamicCategories"
          :key="cat.name"
          class="category-chip"
          :class="{ 'category-active': activeCategory === cat.name }"
          @click="$emit('filter-category', cat.name)"
        >
          {{ cat.name }}
          <span class="category-count">{{ cat.count }}</span>
        </div>
      </div>
    </div>

    <!-- 最近知识网格 -->
    <div class="recent-section">
      <div class="section-header">
        <h3 class="section-title">📋 最近知识</h3>
        <el-button text size="small" @click="$emit('show-all')">
          查看全部
        </el-button>
      </div>

      <div v-if="loading" class="loading-grid">
        <div v-for="n in 6" :key="n" class="skeleton-card">
          <div class="skeleton-line skeleton-short"></div>
          <div class="skeleton-line skeleton-medium"></div>
          <div class="skeleton-line skeleton-long"></div>
        </div>
      </div>

      <div v-else-if="recentItems.length === 0" class="empty-state">
        <el-empty description="暂无知识条目，点击上方按钮添加" />
      </div>

      <div v-else class="knowledge-grid">
        <KnowledgeCard
          v-for="item in recentItems"
          :key="item.id"
          :item="item"
          @click="$emit('view-detail', item.id)"
          @edit="$emit('edit', item)"
          @delete="$emit('delete', item)"
          @download="$emit('download', item)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import KnowledgeCard from './KnowledgeCard.vue'

const props = defineProps({
  categories: { type: Array, default: () => [] },
  recentItems: { type: Array, default: () => [] },
  activeCategory: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})

// 预设分类
const presetCategories = [
  { name: '论文', icon: '📄' },
  { name: '方法', icon: '🔬' },
  { name: '标准', icon: '📏' },
  { name: '综述', icon: '📖' },
  { name: '案例', icon: '💡' },
  { name: 'FAQ', icon: '❓' },
  { name: '笔记', icon: '📝' },
  { name: '手册', icon: '📚' }
]

// 动态分类（排除预设分类）
const dynamicCategories = computed(() => {
  const presetNames = presetCategories.map(c => c.name)
  return props.categories.filter(c => !presetNames.includes(c.name)).slice(0, 6)
})

// 获取分类数量
const getCategoryCount = (categoryName) => {
  const found = props.categories.find(c => c.name === categoryName)
  return found ? found.count : 0
}

defineEmits([
  'filter-category',
  'filter-time',
  'show-entities',
  'show-hypotheses',
  'show-all-categories',
  'show-all',
  'view-detail',
  'edit',
  'delete',
  'download'
])
</script>

<style scoped>
.knowledge-dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

/* 分类区域 */
.categories-section {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-xs);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}

.section-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0;
}

.categories-scroll {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  padding-bottom: var(--space-2);
  -webkit-overflow-scrolling: touch;
}

.categories-scroll::-webkit-scrollbar {
  height: 4px;
}

.categories-scroll::-webkit-scrollbar-track {
  background: var(--color-info-bg);
  border-radius: 2px;
}

.categories-scroll::-webkit-scrollbar-thumb {
  background: var(--color-text-placeholder);
  border-radius: 2px;
}

.category-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--color-info-bg);
  border-radius: var(--radius-full);
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--duration-fast) var(--ease-out);
  border: 1px solid transparent;
}

.category-chip:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border-color: var(--color-primary-border);
}

.category-active {
  background: var(--color-primary) !important;
  color: #fff !important;
  border-color: var(--color-primary) !important;
}

.category-active .category-count {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}

.category-count {
  font-size: 11px;
  padding: 1px 6px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: var(--radius-full);
  color: var(--color-text-secondary);
}

/* 最近知识区域 */
.recent-section {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-xs);
}

.knowledge-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

/* 加载骨架屏 */
.loading-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

.skeleton-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
}

.skeleton-line {
  height: 12px;
  background: linear-gradient(90deg, var(--color-info-bg) 25%, #e8e8e8 50%, var(--color-info-bg) 75%);
  background-size: 200% 100%;
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-3);
  animation: skeleton-loading 1.5s infinite;
}

.skeleton-short {
  width: 40%;
}

.skeleton-medium {
  width: 70%;
}

.skeleton-long {
  width: 100%;
  margin-bottom: 0;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 空状态 */
.empty-state {
  padding: var(--space-10) 0;
}

/* 响应式 */
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .knowledge-grid,
  .loading-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-3);
  }

  .stat-card {
    padding: var(--space-3);
  }

  .stat-icon {
    font-size: 24px;
  }

  .stat-number {
    font-size: var(--font-size-xl);
  }

  .knowledge-grid,
  .loading-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .stats-grid {
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
  }
}
</style>
