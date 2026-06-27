<template>
  <div
    class="knowledge-card"
    :class="[
      `card-source-${item.source_type || 'default'}`,
      `card-mode-${hasFile ? 'file' : 'normal'}`,
      { 'card-has-file': item.file_path }
    ]"
    @click="$emit('click', item)"
  >
    <!-- v28 step 74: 卡片顶部 - 文件 hero（上传的文件显示大图标）/ 或 缩略图 -->
    <div v-if="hasFile" class="card-file-hero" :style="{ background: fileHeroGradient }">
      <div class="file-hero-icon">{{ fileHeroIcon }}</div>
      <div class="file-hero-info">
        <div class="file-hero-type">{{ fileTypeLabel }}</div>
        <div v-if="item.image_count" class="file-hero-imgs">{{ item.image_count }} 张图</div>
      </div>
      <div class="file-hero-actions" @click.stop>
        <button class="hero-action-btn" title="下载原文件" @click="$emit('download', item)">
          <el-icon><Download /></el-icon>
        </button>
        <button class="hero-action-btn" title="编辑" @click="$emit('edit', item)">
          <el-icon><Edit /></el-icon>
        </button>
        <button class="hero-action-btn hero-action-danger" title="删除" @click="$emit('delete', item)">
          <el-icon><Delete /></el-icon>
        </button>
      </div>
    </div>
    <div v-else-if="item.thumbnail_url" class="card-thumbnail">
      <img :src="item.thumbnail_url" :alt="item.title" />
      <div v-if="item.image_count > 1" class="card-thumbnail-badge">+{{ item.image_count - 1 }}</div>
    </div>

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
      </div>

      <!-- 标题 -->
      <h3 class="card-title" :title="item.title">
        <span v-if="item.auto_researched" class="auto-research-badge" title="AI自动研究">🤖</span>
        {{ item.title }}
      </h3>

      <!-- 摘要 -->
      <p class="card-summary">
        {{ item.summary || item.snippet || '' }}
      </p>

      <!-- 标签 -->
      <div class="card-tags" v-if="item.tags?.length">
        <span
          v-for="tag in item.tags.slice(0, 4)"
          :key="tag"
          class="tag-chip"
        >{{ tag }}</span>
        <span v-if="item.tags.length > 4" class="tag-chip tag-more">+{{ item.tags.length - 4 }}</span>
      </div>

      <!-- 底部：时间 -->
      <div class="card-footer">
        <span class="card-time">{{ formatDate(item.created_at) }}</span>
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

// v28 step 74: 上传文件卡片专用 computed
const hasFile = computed(() => !!props.item.file_path)

const fileTypeInfo = computed(() => {
  const ft = props.item.file_type || ''
  if (ft === 'application/pdf' || ft.includes('pdf')) {
    return {
      icon: '📕',
      label: 'PDF',
      gradient: 'linear-gradient(135deg, #FEE2E2 0%, #FCA5A5 100%)',
      textColor: '#991B1B',
    }
  }
  if (ft.includes('word') || ft.includes('document') || ft.includes('msword')) {
    return {
      icon: '📘',
      label: 'Word',
      gradient: 'linear-gradient(135deg, #DBEAFE 0%, #93C5FD 100%)',
      textColor: '#1E40AF',
    }
  }
  if (ft.includes('presentation') || ft.includes('powerpoint') || ft.includes('ppt')) {
    return {
      icon: '📙',
      label: 'PPT',
      gradient: 'linear-gradient(135deg, #FEF3C7 0%, #FCD34D 100%)',
      textColor: '#92400E',
    }
  }
  if (ft.includes('excel') || ft.includes('spreadsheet')) {
    return {
      icon: '📗',
      label: 'Excel',
      gradient: 'linear-gradient(135deg, #D1FAE5 0%, #6EE7B7 100%)',
      textColor: '#065F46',
    }
  }
  return {
    icon: '📄',
    label: '文件',
    gradient: 'linear-gradient(135deg, #E5E7EB 0%, #9CA3AF 100%)',
    textColor: '#374151',
  }
})

const fileHeroIcon = computed(() => fileTypeInfo.value.icon)
const fileHeroGradient = computed(() => fileTypeInfo.value.gradient)
const fileTypeLabel = computed(() => fileTypeInfo.value.label)

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
/* v28 step 74: 卡片整体限高 ~280px（防止 title/tags 撑爆） */
.knowledge-card {
  display: flex;
  flex-direction: column;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  overflow: hidden;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
  height: 100%;
  min-height: 220px;
  max-height: 280px;
}

.knowledge-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
  transform: translateY(-3px);
}

/* v28 step 74: 文件 hero（顶部 PDF/Word/PPT 大图标 + 类型徽章 + 操作按钮） */
.card-file-hero {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  flex-shrink: 0;
  height: 64px;
  position: relative;
}

.file-hero-icon {
  font-size: 36px;
  line-height: 1;
  flex-shrink: 0;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
}

.file-hero-info {
  flex: 1;
  min-width: 0;
}

.file-hero-type {
  font-size: 14px;
  font-weight: 700;
  color: rgba(0, 0, 0, 0.75);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.file-hero-imgs {
  font-size: 11px;
  color: rgba(0, 0, 0, 0.55);
  margin-top: 2px;
}

.file-hero-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.knowledge-card:hover .file-hero-actions {
  opacity: 1;
}

.hero-action-btn {
  border: none;
  background: rgba(255, 255, 255, 0.5);
  color: var(--color-text-primary);
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-out);
}

.hero-action-btn:hover {
  background: rgba(255, 255, 255, 0.9);
  transform: scale(1.05);
}

.hero-action-btn :deep(svg) {
  width: 14px;
  height: 14px;
}

.hero-action-danger:hover {
  color: var(--color-danger);
}

/* 缩略图（Phase 7 多模态，无文件时显示） */
.card-thumbnail {
  position: relative;
  width: 100%;
  height: 80px;
  overflow: hidden;
  background: linear-gradient(135deg, #FAFAFA, #F3F4F6);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-thumbnail img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
}

.card-thumbnail-badge {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background: rgba(0, 0, 0, 0.7);
  /* stylelint-disable-next-line color-named */
  color: white;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
}

/* 卡片内容 - 占剩余高度 */
.card-body {
  flex: 1;
  padding: 10px 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  min-height: 0; /* 让 flex 子项能收缩 */
  overflow: hidden;
}

/* 头部 */
.card-header {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  flex-shrink: 0;
}

.card-category {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}

.category-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topic-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: var(--radius-full);
  font-size: 11px;
  background: var(--color-info-bg);
  color: var(--color-text-secondary);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 标题 - 限 2 行（v70 P0 急修：#1F2937 → token 响应主题） */
.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.45;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
  flex-shrink: 0;
}

.knowledge-card:hover .card-title {
  color: var(--color-primary);
}

.auto-research-badge {
  margin-right: 4px;
}

/* 摘要 - 限 2 行 */
.card-summary {
  font-size: 12.5px;
  color: var(--color-text-secondary);
  line-height: 1.55;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
  flex: 1;
  min-height: 0;
}

/* 标签 - 限 4 个 */
.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex-shrink: 0;
  max-height: 48px;
  overflow: hidden;
}

.tag-chip {
  display: inline-block;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  font-size: 11px;
  background: var(--color-info-bg);
  color: var(--color-text-regular);
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  padding-top: 6px;
  border-top: 1px solid var(--color-border-light);
  margin-top: auto;
  flex-shrink: 0;
}

.card-time {
  font-size: 11px;
  color: var(--color-text-secondary);
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

/* 响应式 */
@media (max-width: 768px) {
  .knowledge-card {
    min-height: 200px;
    max-height: 260px;
  }
}
</style>
