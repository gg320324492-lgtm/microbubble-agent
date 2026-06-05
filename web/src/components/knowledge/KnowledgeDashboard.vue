<template>
  <div class="knowledge-dashboard">
    <!-- 统计卡片组 -->
    <div class="stats-grid">
      <div class="stat-card stat-total" @click="$emit('filter-category', '')">
        <div class="stat-icon">📚</div>
        <div class="stat-content">
          <div class="stat-number">{{ stats.total || 0 }}</div>
          <div class="stat-label">总知识量</div>
        </div>
        <div class="stat-ring">
          <svg viewBox="0 0 36 36">
            <path class="ring-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
            <path class="ring-fill" :style="{ strokeDasharray: `${Math.min(100, (stats.total || 0) / 2)}, 100` }" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
          </svg>
        </div>
      </div>

      <div class="stat-card stat-recent" @click="$emit('filter-time', 'week')">
        <div class="stat-icon">📝</div>
        <div class="stat-content">
          <div class="stat-number">{{ stats.recent_count || 0 }}</div>
          <div class="stat-label">本周新增</div>
        </div>
        <div class="stat-trend" v-if="stats.recent_count > 0">
          <span class="trend-up">↑</span>
        </div>
      </div>

      <div class="stat-card stat-entities" @click="$emit('show-entities')">
        <div class="stat-icon">🔬</div>
        <div class="stat-content">
          <div class="stat-number">{{ stats.entity_count || 0 }}</div>
          <div class="stat-label">实体三元组</div>
        </div>
      </div>

      <div class="stat-card stat-formulas">
        <div class="stat-icon">📐</div>
        <div class="stat-content">
          <div class="stat-number">{{ stats.formula_count || 0 }}</div>
          <div class="stat-label">公式库</div>
        </div>
      </div>
    </div>

    <!-- 可视化图表区域 -->
    <div class="charts-section">
      <!-- 分类分布饼图 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">📊 分类分布</h3>
        </div>
        <div class="chart-body">
          <div class="pie-chart">
            <svg viewBox="0 0 100 100">
              <circle v-for="(seg, i) in pieSegments" :key="i"
                :cx="50" :cy="50" :r="40"
                fill="none"
                :stroke="seg.color"
                stroke-width="12"
                :stroke-dasharray="`${seg.length} ${seg.gap}`"
                :stroke-dashoffset="seg.offset"
                class="pie-segment"
                :style="{ animationDelay: `${i * 100}ms` }"
              />
            </svg>
            <div class="pie-center">
              <div class="pie-total">{{ categories.length }}</div>
              <div class="pie-label">分类</div>
            </div>
          </div>
          <div class="pie-legend">
            <div v-for="(cat, i) in topCategories" :key="cat.name" class="legend-item">
              <span class="legend-dot" :style="{ background: chartColors[i % chartColors.length] }"></span>
              <span class="legend-name">{{ cat.name }}</span>
              <span class="legend-count">{{ cat.count }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 知识增长趋势 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">📈 增长趋势</h3>
          <div class="chart-tabs">
            <span class="chart-tab" :class="{ active: trendPeriod === 'week' }" @click="trendPeriod = 'week'">周</span>
            <span class="chart-tab" :class="{ active: trendPeriod === 'month' }" @click="trendPeriod = 'month'">月</span>
          </div>
        </div>
        <div class="chart-body">
          <div class="bar-chart">
            <div v-for="(bar, i) in trendBars" :key="i" class="bar-item">
              <div class="bar-wrapper">
                <div class="bar-fill" :style="{ height: bar.height + '%', animationDelay: `${i * 50}ms` }"></div>
              </div>
              <div class="bar-label">{{ bar.label }}</div>
            </div>
          </div>
          <div class="trend-summary">
            <div class="trend-item">
              <span class="trend-value">+{{ stats.recent_count || 0 }}</span>
              <span class="trend-label">本周新增</span>
            </div>
            <div class="trend-item">
              <span class="trend-value">{{ Math.round((stats.total || 0) / 4) }}</span>
              <span class="trend-label">月均增长</span>
            </div>
          </div>
        </div>
      </div>
    </div>

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
import { ref, computed } from 'vue'
import KnowledgeCard from './KnowledgeCard.vue'

const props = defineProps({
  stats: { type: Object, default: () => ({}) },
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

// 图表颜色
const chartColors = ['#FF7A5C', '#FFB347', '#5470c6', '#91cc75', '#ee6666', '#73c0de', '#fc8452', '#9a60b4']

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

// 饼图数据
const topCategories = computed(() => {
  return props.categories.slice(0, 6)
})

const pieSegments = computed(() => {
  const total = props.categories.reduce((sum, c) => sum + c.count, 0)
  if (total === 0) return []

  const segments = []
  let currentOffset = 25 // 从顶部开始

  props.categories.slice(0, 6).forEach((cat, i) => {
    const percentage = (cat.count / total) * 100
    const circumference = 2 * Math.PI * 40 // r=40

    segments.push({
      length: (percentage / 100) * circumference,
      gap: circumference - (percentage / 100) * circumference,
      offset: -currentOffset,
      color: chartColors[i % chartColors.length]
    })

    currentOffset += (percentage / 100) * circumference
  })

  return segments
})

// 趋势图数据
const trendPeriod = ref('week')

const trendBars = computed(() => {
  // 模拟数据 - 实际应从 API 获取
  const weekData = [
    { label: '一', value: 3 },
    { label: '二', value: 5 },
    { label: '三', value: 2 },
    { label: '四', value: 7 },
    { label: '五', value: 4 },
    { label: '六', value: 1 },
    { label: '日', value: 6 }
  ]

  const monthData = [
    { label: '1周', value: 12 },
    { label: '2周', value: 18 },
    { label: '3周', value: 15 },
    { label: '4周', value: 22 }
  ]

  const data = trendPeriod.value === 'week' ? weekData : monthData
  const maxValue = Math.max(...data.map(d => d.value), 1)

  return data.map(d => ({
    ...d,
    height: (d.value / maxValue) * 100
  }))
})

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

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}

.stat-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-xs);
  position: relative;
  overflow: hidden;
}

.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}

.stat-total {
  background: linear-gradient(135deg, var(--color-primary-bg) 0%, #fff 100%);
  border-color: var(--color-primary-border);
}

.stat-recent {
  background: linear-gradient(135deg, var(--color-accent-bg) 0%, #fff 100%);
  border-color: rgba(255, 179, 71, 0.2);
}

.stat-entities {
  background: linear-gradient(135deg, #e8f4fd 0%, #fff 100%);
  border-color: rgba(84, 112, 198, 0.2);
}

.stat-formulas {
  background: linear-gradient(135deg, #f0f9eb 0%, #fff 100%);
  border-color: rgba(145, 204, 117, 0.2);
}

.stat-icon {
  font-size: 32px;
  flex-shrink: 0;
}

.stat-content {
  min-width: 0;
  flex: 1;
}

.stat-number {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-top: var(--space-1);
}

/* 环形进度条 */
.stat-ring {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 48px;
  height: 48px;
  opacity: 0.6;
}

.stat-ring svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.ring-bg {
  fill: none;
  stroke: var(--color-border);
  stroke-width: 3;
}

.ring-fill {
  fill: none;
  stroke: var(--color-primary);
  stroke-width: 3;
  stroke-linecap: round;
  transition: stroke-dasharray 1s ease;
}

/* 趋势箭头 */
.stat-trend {
  position: absolute;
  top: 12px;
  right: 12px;
}

.trend-up {
  color: var(--color-success);
  font-size: 18px;
  font-weight: bold;
}

/* 图表区域 */
.charts-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.chart-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  overflow: hidden;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-4) 0;
}

.chart-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0;
}

.chart-tabs {
  display: flex;
  gap: var(--space-1);
  background: var(--color-info-bg);
  border-radius: var(--radius-full);
  padding: 2px;
}

.chart-tab {
  padding: 4px 12px;
  font-size: var(--font-size-xs);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all var(--duration-fast);
  color: var(--color-text-secondary);
}

.chart-tab.active {
  background: var(--color-primary);
  color: #fff;
}

.chart-body {
  padding: var(--space-4);
}

/* 饼图 */
.pie-chart {
  position: relative;
  width: 140px;
  height: 140px;
  margin: 0 auto var(--space-3);
}

.pie-chart svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.pie-segment {
  animation: pieGrow 0.8s ease-out forwards;
  opacity: 0;
}

@keyframes pieGrow {
  from {
    opacity: 0;
    stroke-dasharray: 0 251.2;
  }
  to {
    opacity: 1;
  }
}

.pie-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.pie-total {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
}

.pie-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.pie-legend {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-name {
  flex: 1;
  color: var(--color-text-regular);
}

.legend-count {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

/* 柱状图 */
.bar-chart {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  height: 120px;
  margin-bottom: var(--space-3);
}

.bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
}

.bar-wrapper {
  width: 100%;
  height: 100px;
  background: var(--color-info-bg);
  border-radius: var(--radius-sm);
  position: relative;
  overflow: hidden;
}

.bar-fill {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(180deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  animation: barGrow 0.6s ease-out forwards;
  transform-origin: bottom;
}

@keyframes barGrow {
  from {
    transform: scaleY(0);
  }
  to {
    transform: scaleY(1);
  }
}

.bar-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.trend-summary {
  display: flex;
  justify-content: space-around;
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border-light);
}

.trend-item {
  text-align: center;
}

.trend-value {
  display: block;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}

.trend-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
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

  .charts-section {
    grid-template-columns: 1fr;
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

  .stat-ring {
    display: none;
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
