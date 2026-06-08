<template>
  <div
    class="knowledge-card"
    :class="[
      `card-source-${item.source_type || 'default'}`,
      { 'card-has-file': item.file_path }
    ]"
    @click="$emit('click', item)"
  >
    <!-- 左侧彩色条 -->
    <div class="card-accent" :style="{ background: accentColor }"></div>

    <!-- 卡片内容 -->
    <div class="card-body">
      <!-- 头部：分类 + 状态 -->
      <div class="card-header">
        <div class="card-category">
          <span class="category-badge" :style="{ background: accentColor + '15', color: accentColor }">
            {{ categoryIcon }} {{ item.category || '未分类' }}
          </span>
          <span v-if="item.topic" class="topic-badge">{{ item.topic }}</span>
          <el-tag
            v-if="item.analysis_status === 'pending' || item.analysis_status === 'analyzing'"
            size="small"
            type="warning"
            effect="light"
          >
            <span class="status-dot status-analyzing"></span> 分析中
          </el-tag>
          <el-tag
            v-if="item.analysis_status === 'failed'"
            size="small"
            type="danger"
            effect="light"
          >
            失败
          </el-tag>
        </div>
        <div class="card-source-icon" :title="sourceLabel">
          {{ sourceIcon }}
        </div>
      </div>

      <!-- 标题 -->
      <h3 class="card-title">
        <span v-if="item.auto_researched" class="auto-research-badge" title="AI自动研究">🤖</span>
        {{ item.title }}
      </h3>

      <!-- 摘要 -->
      <p class="card-summary">
        {{ item.summary || (item.content ? item.content.substring(0, 120) + '...' : '') }}
      </p>

      <!-- 标签 -->
      <div class="card-tags" v-if="item.tags?.length">
        <span
          v-for="tag in item.tags.slice(0, 3)"
          :key="tag"
          class="tag-chip"
        >{{ tag }}</span>
        <span v-if="item.tags.length > 3" class="tag-chip tag-more">+{{ item.tags.length - 3 }}</span>
      </div>

      <!-- 底部：时间 + 操作 -->
      <div class="card-footer">
        <span class="card-time">{{ formatDate(item.created_at) }}</span>
        <div class="card-actions" @click.stop>
          <el-button
            v-if="item.file_path"
            text
            type="success"
            size="small"
            aria-label="下载"
            @click="$emit('download', item)"
          >
            <el-icon><Download /></el-icon>
          </el-button>
          <el-button
            text
            type="primary"
            size="small"
            aria-label="编辑"
            @click="$emit('edit', item)"
          >
            <el-icon><Edit /></el-icon>
          </el-button>
          <el-button
            text
            type="danger"
            size="small"
            aria-label="删除"
            @click="$emit('delete', item)"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Download, Edit, Delete } from '@element-plus/icons-vue'

const props = defineProps({
  item: { type: Object, required: true }
})

defineEmits(['click', 'edit', 'delete', 'download'])

// 分类颜色映射
// 分类颜色映射
const categoryColors = {
  '微纳米气泡': '#FF7A5C',
  '水处理': '#5470c6',
  '农业': '#91cc75',
  '消毒': '#ee6666',
  '测量': '#73c0de',
  '应用': '#fc8452',
  '论文': '#3b82f6',
  '方法': '#8b5cf6',
  '标准': '#f59e0b',
  '综述': '#10b981',
  '案例': '#f97316',
  'FAQ': '#ec4899',
  '笔记': '#6366f1',
  '手册': '#14b8a6'
}

// 分类图标映射
const categoryIcons = {
  '论文': '📄',
  '方法': '🔬',
  '标准': '📏',
  '综述': '📖',
  '案例': '💡',
  'FAQ': '❓',
  '笔记': '📝',
  '手册': '📚'
}

const accentColor = computed(() => {
  const cat = props.item.category
  return categoryColors[cat] || '#FF7A5C'
})

const categoryIcon = computed(() => {
  return categoryIcons[props.item.category] || ''
})

const sourceIcon = computed(() => {
  const icons = {
    'file': '📄',
    'conversation': '💬',
    'auto_research': '🤖',
    'paper': '📝',
    'notes': '📋',
    'manual': '📖',
  }
  return icons[props.item.source_type] || '📚'
})

const sourceLabel = computed(() => {
  const labels = {
    'file': '文件上传',
    'conversation': '对话记录',
    'auto_research': 'AI自动研究',
    'paper': '论文',
    'notes': '笔记',
    'manual': '手册',
  }
  return labels[props.item.source_type] || '知识库'
})

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  if (days < 30) return `${Math.floor(days / 7)}周前`

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.knowledge-card {
  display: flex;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  overflow: hidden;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.knowledge-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
  transform: translateY(-3px);
}

.knowledge-card:hover .card-accent {
  width: 6px;
}

/* 左侧彩色条 */
.card-accent {
  width: 4px;
  min-height: 100%;
  transition: width var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}

/* 卡片内容 */
.card-body {
  flex: 1;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

/* 头部 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-2);
}

.card-category {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.category-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
}

.topic-badge {
  display: inline-block;
  padding: 2px var(--space-2);
  border-radius: var(--radius-full);
  font-size: 11px;
  background: var(--color-info-bg);
  color: var(--color-text-secondary);
  margin-left: var(--space-1);
}

.card-source-icon {
  font-size: 18px;
  opacity: 0.7;
  flex-shrink: 0;
}

/* 标题 */
.card-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: #2563eb;
  line-height: 1.4;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-title:hover {
  color: #1d4ed8;
}

.auto-research-badge {
  margin-right: var(--space-1);
  font-size: var(--font-size-sm);
}

/* 摘要 */
.card-summary {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 标签 */
.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.tag-chip {
  display: inline-block;
  padding: 2px var(--space-2);
  border-radius: var(--radius-full);
  font-size: 11px;
  background: var(--color-info-bg);
  color: var(--color-text-regular);
  transition: all var(--duration-fast) var(--ease-out);
}

.tag-chip:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.tag-more {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

/* 底部 */
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border-light);
}

.card-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.card-actions {
  display: flex;
  gap: var(--space-1);
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.knowledge-card:hover .card-actions {
  opacity: 1;
}

/* 状态指示器 */
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 4px;
}

.status-analyzing {
  background: var(--color-warning);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 响应式 */
@media (max-width: 768px) {
  .card-body {
    padding: var(--space-3);
  }

  .card-actions {
    opacity: 1;
  }
}
</style>
