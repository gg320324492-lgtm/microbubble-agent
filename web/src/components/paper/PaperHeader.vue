<template>
  <header class="paper-header">
    <!-- 顶部工具栏 -->
    <div class="paper-header-toolbar">
      <el-button text class="paper-back-btn" @click="$router.push('/knowledge')">
        <el-icon><ArrowLeft /></el-icon>
        <span>返回知识库</span>
      </el-button>

      <div class="paper-header-toolbar-right">
        <el-tag v-if="paper.status === 'analyzing'" size="small" type="warning" effect="light">
          <el-icon class="is-loading"><Loading /></el-icon> 分析中
        </el-tag>
        <el-tag v-else-if="paper.status === 'failed'" size="small" type="danger" effect="light">
          分析失败
        </el-tag>
        <el-tag v-else-if="paper.status === 'partial'" size="small" type="info" effect="light">
          <el-icon><InfoFilled /></el-icon> 部分完成
        </el-tag>
        <el-tag v-else-if="paper.status === 'done'" size="small" type="success" effect="light">
          <el-icon><CircleCheck /></el-icon> 已完成
        </el-tag>
        <el-tag v-else-if="paper.status === 'pending'" size="small" type="info" effect="plain">
          <el-icon><Clock /></el-icon> 待分析
        </el-tag>
        <el-tag v-if="paper.autoResearched" size="small" type="primary" effect="light">
          <el-icon><MagicStick /></el-icon> 自主研究
        </el-tag>
        <el-button
          v-if="paper.status === 'failed'"
          size="small"
          type="danger"
          plain
          :loading="reanalyzing"
          @click="$emit('reanalyze')"
        >重新分析</el-button>
        <!-- v28 step 93: 下载按钮移到顶部 toolbar（与状态/重新分析并列） -->
        <el-button
          v-if="paper.filePath"
          size="small"
          type="primary"
          plain
          :icon="Download"
          :loading="downloading"
          @click="$emit('download')"
        >下载原文件</el-button>
      </div>
    </div>

    <!-- 标题与分类 -->
    <h1 class="paper-title">{{ paper.title || '（无标题）' }}</h1>

    <!-- 元信息条 -->
    <div class="paper-meta-bar">
      <div v-if="paper.category" class="meta-item">
        <span class="meta-label">分类</span>
        <span class="meta-value category-chip">{{ paper.category }}</span>
      </div>
      <div v-if="paper.knowledgeType" class="meta-item">
        <span class="meta-label">类型</span>
        <span class="meta-value type-chip">{{ paper.knowledgeType }}</span>
      </div>
      <div v-if="paper.fileName" class="meta-item">
        <span class="meta-label">文件</span>
        <span class="meta-value file-name" :title="paper.fileName">{{ paper.fileName }}</span>
      </div>
      <div v-if="paper.fileType" class="meta-item">
        <span class="meta-label">格式</span>
        <span class="meta-value">{{ paper.fileType }}</span>
      </div>
      <div v-if="paper.uploadTime" class="meta-item">
        <span class="meta-label">上传</span>
        <span class="meta-value">{{ formatDate(paper.uploadTime) }}</span>
      </div>
    </div>

    <!-- 标签（如果 keywords 也在 AbstractCard 显示，这里只显示分类/类型标签，不重复论文关键词） -->
    <div v-if="headerTags.length" class="paper-tags">
      <el-tag
        v-for="tag in headerTags"
        :key="tag"
        size="small"
        effect="plain"
        round
        class="paper-tag"
      >#{{ tag }}</el-tag>
    </div>

    <!-- 审阅警告 -->
    <div v-if="paper.needsReview" class="paper-review-warning">
      <el-icon><WarningFilled /></el-icon>
      <span>该条目与其他知识存在矛盾，待人工审阅</span>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { ArrowLeft, Loading, CircleCheck, MagicStick, WarningFilled, InfoFilled, Clock, Download } from '@element-plus/icons-vue'
import { formatDate } from '@/utils/format'

const props = defineProps({
  paper: { type: Object, required: true },
  reanalyzing: { type: Boolean, default: false },
  downloading: { type: Boolean, default: false },
})

defineEmits(['reanalyze', 'download'])

// 标签去重：如果 AbstractCard 已显示论文关键词，Header 只显示分类/类型标签
// 如果 keywords 和 tags 重合度 >= 60%，Header 隐藏 tags
const headerTags = computed(() => {
  const tags = (props.paper.tags || []).map(t => t.toLowerCase().trim())
  const kws = (props.paper.keywords || []).map(k => k.toLowerCase().trim())
  if (!kws.length) return props.paper.tags || []
  if (!tags.length) return []
  // 计算重合度
  const overlap = tags.filter(t => kws.some(k => k === t || k.includes(t) || t.includes(k)))
  const ratio = overlap.length / Math.max(tags.length, 1)
  // 重合度 >= 60% → 隐藏 Header tags（AbstractCard 会显示 keywords）
  if (ratio >= 0.6) return []
  return props.paper.tags || []
})
</script>

<style scoped>
.paper-header {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: 24px 28px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  border: 1px solid var(--color-border-light);
  margin-bottom: 24px;
}

.paper-header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.paper-back-btn {
  color: var(--color-text-regular);
  font-size: 14px;
}

.paper-back-btn:hover {
  color: var(--color-primary);
}

.paper-header-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.paper-title {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.4;
  color: #1F2937;
  margin: 0 0 16px;
  max-width: 100%;
  word-break: break-word;
}

.paper-meta-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 12px 0;
  border-top: 1px solid var(--color-border-light);
  border-bottom: 1px solid var(--color-border-light);
  margin-bottom: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.meta-label {
  color: #9CA3AF;
  font-size: 12px;
}

.meta-value {
  color: #1F2937;
  font-weight: 500;
}

.category-chip {
  background: var(--color-primary);
  color: #fff;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.type-chip {
  background: var(--color-accent);
  color: #fff;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.file-name {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.paper-tag {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border: none;
}

.paper-review-warning {
  margin-top: 12px;
  padding: 10px 14px;
  background: var(--color-danger-bg);
  border: 1px solid #fab6b6;
  color: #c45656;
  border-radius: 8px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

@media (max-width: 768px) {
  .paper-header {
    padding: 16px;
  }
  .paper-title {
    font-size: 20px;
  }
  .file-name {
    max-width: 160px;
  }
}
</style>
