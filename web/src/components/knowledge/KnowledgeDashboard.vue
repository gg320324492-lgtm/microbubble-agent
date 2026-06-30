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
          :class="{
            'category-active': cat.isSystem
              ? (activeSourceType === cat.sourceType)
              : (activeCategory === cat.name),
          }"
          @click="handleCategoryClick(cat)"
        >
          {{ cat.icon }} {{ cat.name }}
          <!-- 2026-06-30: system chip 0 也显示, 避免"自动拓展清空后整张图看起来是空白的".
               system chip 走 sourceTypeStats, 后端已显式补 0; 这里只对 system chip 强制显示 0,
               普通 category 走 categories 数组不存在即 0, 仍按 v-if 隐藏避免视觉噪音. -->
          <span
            v-if="cat.isSystem || getCategoryCount(cat.name) > 0"
            class="category-count"
            :class="{ 'category-count-empty': cat.isSystem && getCategoryCount(cat.name) === 0 }"
          >
            {{ getCategoryCount(cat.name) }}
          </span>
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
        <div class="section-actions">
          <!-- 2026-06-30 续集 5 (KB 数据清洁 C): dedup toggle (受控于 KnowledgeView + localStorage)
               默认 ON: 同 title 分组取 id 最小, 视觉去重.
               OFF: 全部显示 (调试/审计场景, 用户可临时切回看原始 3 份).
               注: stats 数字仍是物理行数, toggle 仅影响显示策略, 不动 DB. -->
          <el-switch
            :model-value="dedupEnabled"
            inline-prompt
            active-text="去重"
            inactive-text="全部"
            size="small"
            @update:model-value="(val) => $emit('toggle-dedup', val)"
          />
          <el-button text size="small" @click="$emit('show-all')">
            查看全部
          </el-button>
        </div>
      </div>

      <div v-if="loading" class="loading-grid">
        <div v-for="n in 6" :key="n" class="skeleton-card">
          <div class="skeleton-line skeleton-short"></div>
          <div class="skeleton-line skeleton-medium"></div>
          <div class="skeleton-line skeleton-long"></div>
        </div>
      </div>

      <!-- 2026-06-30 三态空态: loading / error / empty -->
      <div v-else-if="loadError" class="empty-state">
        <el-empty :description="`加载失败: ${loadError}`" :image-size="80">
          <el-button type="primary" @click="$emit('retry')">重试</el-button>
        </el-empty>
      </div>

      <div v-else-if="displayedItems.length === 0" class="empty-state">
        <el-empty description="暂无知识条目，点击上方按钮添加" />
      </div>

      <div v-else class="knowledge-grid">
        <KnowledgeCard
          v-for="item in displayedItems"
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
  activeSourceType: { type: String, default: '' },  // #043
  sourceTypeStats: { type: Object, default: () => ({}) },  // #043
  loading: { type: Boolean, default: false },
  loadError: { type: String, default: null },  // 2026-06-30: 三态空态 (loading/error/empty)
  // 2026-06-30 续集 5: dedup toggle (受控, 父级 KnowledgeView 是 localStorage source of truth)
  dedupEnabled: { type: Boolean, default: true }
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
  { name: '手册', icon: '📚' },
  // #043: 系统分类 (走 source_type 过滤不走 category)
  { name: '自动拓展', icon: '✨', isSystem: true, sourceType: 'auto_expansion' }
]

// #043: chip 点击分流 (system chip 走 source_type, 其他走 category)
const emit = defineEmits([
  'filter-category',
  'filter-source-type',
  'filter-time',
  'show-entities',
  'show-hypotheses',
  'show-all-categories',
  'show-all',
  'view-detail',
  'edit',
  'delete',
  'download',
  'retry',  // 2026-06-30: loadError 三态空态, 错误时重试
  'toggle-dedup'  // 2026-06-30 续集 5: dedup toggle ON/OFF, 父级同步 localStorage
])

const handleCategoryClick = (cat) => {
  // 2026-06-30 修复: chip 再点一次 = 清除过滤
  // 旧版只 emit 一次 → 用户点过 "✨ 自动拓展" 后 ref 永远停在 'auto_expansion'
  // → fetchKnowledge 永远拼 source_type=auto_expansion → 0 条 → 5 个统计全 0
  // 现在: 已 active 时再点 = emit 空字符串, 父级 handleFilter 走"清空"分支
  const isAlreadyActive = cat.isSystem
    ? (props.activeSourceType === cat.sourceType)
    : (props.activeCategory === cat.name)
  if (isAlreadyActive) {
    emit('filter-source-type', '')
    emit('filter-category', '')
    return
  }
  if (cat.isSystem) {
    emit('filter-source-type', cat.sourceType)
  } else {
    emit('filter-category', cat.name)
  }
}

// 动态分类（排除预设分类）
const dynamicCategories = computed(() => {
  const presetNames = presetCategories.map(c => c.name)
  return props.categories.filter(c => !presetNames.includes(c.name)).slice(0, 6)
})

// 获取分类数量 (system chip 从 sourceTypeStats 拿, 其他从 categories 拿)
const SYSTEM_CATEGORY_TO_SOURCE_TYPE = {
  '自动拓展': 'auto_expansion'
}

const getCategoryCount = (categoryName) => {
  // #043: 系统分类走 sourceTypeStats (如 auto_expansion 计数)
  const sourceTypeKey = SYSTEM_CATEGORY_TO_SOURCE_TYPE[categoryName]
  if (sourceTypeKey && props.sourceTypeStats?.[sourceTypeKey] !== undefined) {
    return props.sourceTypeStats[sourceTypeKey]
  }
  const found = props.categories.find(c => c.name === categoryName)
  return found ? found.count : 0
}

// 2026-06-30 续集 5 (KB 数据清洁 C 方案): 显示策略 computed
// dedup ON: 按 title 分组, 每组取 id 最小 (KB 后端已保证同 title md5 一致性, 故分组等价)
// dedup OFF: 全部显示 (调试/审计用, 用户可临时切回看原始 3 份)
// stats 数字 (props.recentItems.length) 不变, 不影响 total 显示
const displayedItems = computed(() => {
  if (!props.dedupEnabled) {
    return props.recentItems
  }
  // 按 title 分组, 取 id 最小
  const seen = new Map()  // title → item
  for (const item of props.recentItems) {
    const title = item.title || ''
    const cur = seen.get(title)
    if (!cur || item.id < cur.id) {
      seen.set(title, item)
    }
  }
  // 按 created_at 降序 (最近的在最上), 与原 recentItems 排序一致
  return Array.from(seen.values()).sort((a, b) => {
    const ta = a.created_at || ''
    const tb = b.created_at || ''
    return tb.localeCompare(ta)
  })
})
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
  color: var(--el-color-white) !important;
  border-color: var(--color-primary) !important;
}

.category-active .category-count {
  background: rgba(255, 255, 255, 0.2);
  color: var(--el-color-white);
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
  /* v28 step 74: auto-fill minmax 让卡片自适应列数（论文少时 2 列，内容多时 3-4 列） */
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}

/* 加载骨架屏 */
.loading-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
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
  position: relative;
  overflow: hidden;
  background: var(--color-info-bg);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-3);
}
.skeleton-line::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent 25%, #e8e8e8 50%, transparent 75%);
  animation: skeleton-loading 1.5s infinite;
  border-radius: inherit;
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
