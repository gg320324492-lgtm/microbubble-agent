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

    <!-- v28 step 109.38: 作者列表（含通讯作者标记 + 机构上标） -->
    <div v-if="paper.authors && paper.authors.length" class="paper-authors-block">
      <div class="authors-row">
        <span class="authors-label">
          <el-icon><User /></el-icon>
          作者
        </span>
        <span class="authors-list">
          <template v-for="(author, idx) in paper.authors" :key="idx">
            <span class="author-chip">
              <span class="author-name">{{ author.name }}</span>
              <sup class="author-aff">{{ author.affiliation }}</sup>
              <span v-if="author.isCorresponding" class="corresponding-mark" title="通讯作者">*</span>
            </span>
            <span v-if="idx < paper.authors.length - 1" class="author-sep">·</span>
          </template>
        </span>
      </div>
    </div>

    <!-- v28 step 109.38: 机构列表 -->
    <div v-if="paper.affiliations && paper.affiliations.length" class="paper-affiliations-block">
      <div class="affs-list">
        <div v-for="(aff, idx) in paper.affiliations" :key="idx" class="aff-item">
          <sup class="aff-marker">{{ aff.id }}</sup>
          <span class="aff-name">{{ aff.name }}</span>
        </div>
      </div>
    </div>

    <!-- v28 step 109.38: 期刊 / DOI 信息条 -->
    <div v-if="paper.journal && paper.journal.name" class="paper-journal-bar">
      <div class="journal-info">
        <el-icon class="journal-icon"><Reading /></el-icon>
        <span class="journal-name">{{ paper.journal.name }}</span>
        <span v-if="paper.journal.volume" class="journal-vol">{{ paper.journal.volume }}</span>
        <span v-if="paper.journal.year" class="journal-year">({{ paper.journal.year }})</span>
        <span v-if="paper.journal.articleId" class="journal-id">{{ paper.journal.articleId }}</span>
      </div>
      <a
        v-if="paper.doi"
        :href="`https://doi.org/${paper.doi}`"
        target="_blank"
        rel="noopener"
        class="doi-link"
        :title="`DOI: ${paper.doi}`"
      >
        <el-icon><Link /></el-icon>
        <span class="doi-text">doi:{{ paper.doi }}</span>
      </a>
    </div>

    <!-- 元信息条（分类/类型/文件/上传时间） -->
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
import { ArrowLeft, Loading, CircleCheck, MagicStick, WarningFilled, InfoFilled, Clock, Download, User, Reading, Link } from '@element-plus/icons-vue'
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
  box-shadow: var(--shadow-md);
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
  color: var(--color-text-primary);
  margin: 0 0 16px;
  max-width: 100%;
  overflow-wrap: anywhere;
}

/* ========== v28 step 109.38: 作者块 ========== */
.paper-authors-block {
  margin-bottom: 12px;
  padding: 12px 0;
  border-bottom: 1px dashed rgba(var(--color-primary-rgb), 0.15);
}

.authors-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.authors-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  padding-top: 2px;
}

.authors-list {
  display: inline-flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px 8px;
  flex: 1;
  min-width: 0;
  line-height: 1.7;
}

.author-chip {
  display: inline-flex;
  align-items: baseline;
  gap: 1px;
  font-size: 14px;
  color: var(--color-text-primary);
}

.author-name {
  font-weight: 500;
}

.author-aff {
  color: var(--color-primary);
  font-size: 11px;
  font-weight: 600;
  margin-left: 1px;
  line-height: 1;
  position: relative;
  top: -4px;
}

.corresponding-mark {
  color: var(--color-danger);
  font-size: 14px;
  font-weight: 700;
  margin-left: 2px;
  cursor: help;
}

.author-sep {
  color: var(--color-border-light);
  font-size: 12px;
}

/* ========== v28 step 109.38: 机构块 ========== */
.paper-affiliations-block {
  margin-bottom: 14px;
  padding-bottom: 14px;
  border-bottom: 1px dashed rgba(var(--color-primary-rgb), 0.15);
}

.affs-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.aff-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.aff-marker {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  margin-top: 3px;
}

.aff-name {
  flex: 1;
  min-width: 0;
}

/* ========== v28 step 109.38: 期刊 / DOI 条 ========== */
.paper-journal-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #FFF8F5 0%, #FFFDFB 100%);
  border-radius: 8px;
  border: 1px solid rgba(var(--color-primary-rgb), 0.15);
}

.journal-info {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 14px;
  color: var(--color-text-primary);
}

.journal-icon {
  color: var(--color-primary);
  font-size: 16px;
}

.journal-name {
  font-weight: 600;
  font-style: italic;
}

.journal-vol {
  color: var(--color-text-secondary);
  font-weight: 500;
}

.journal-year {
  color: var(--color-text-secondary);
  font-weight: 500;
}

.journal-id {
  color: var(--color-text-primary);
  font-weight: 600;
  font-family: 'Consolas', 'Monaco', monospace;
  background: rgba(var(--color-primary-rgb), 0.1);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.doi-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-primary);
  text-decoration: none;
  font-size: 13px;
  padding: 4px 10px;
  background: var(--color-bg-card);
  border: 1px solid rgba(var(--color-primary-rgb), 0.25);
  border-radius: 6px;
  transition: all 0.15s ease;
}

.doi-link:hover {
  background: var(--color-primary);
  color: var(--color-bg-card);
  border-color: var(--color-primary);
}

.doi-text {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}

/* ========== 元信息条 ========== */
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
  color: var(--color-text-placeholder);
  font-size: 12px;
}

.meta-value {
  color: var(--color-text-primary);
  font-weight: 500;
}

.category-chip {
  background: var(--color-primary);
  color: var(--color-bg-card);
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.type-chip {
  background: var(--color-accent);
  color: var(--color-bg-card);
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
  color: var(--color-danger);
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
  .author-name {
    font-size: 13px;
  }
  .paper-journal-bar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>