<template>
  <!-- v28 step 46: AbstractCard 极简化
       之前显示 4 个独立 section (摘要 / 关键词 / 核心概念 / 关联主题)，
       信息密度过高、重复显示相似内容、视觉杂乱。
       新设计（彻底精简）：
       1. 顶部一行：topic + 字数（紧凑元信息）
       2. 摘要正文
       3. 关键词 chips（合并 tags + 去重，最多 12 个）
       核心概念 / 关联主题 完全移除（与关键词高度重复）
  -->
  <section v-if="paper.abstract" class="paper-abstract">
    <!-- v28 step 109.36.9: 标题让用户知道这是 Abstract（之前只有 topic + 字数） -->
    <h2 class="abstract-title">
      <el-icon><Document /></el-icon>
      Abstract
    </h2>

    <!-- 顶部元信息行：topic + 字数 -->
    <div class="abstract-meta-row">
      <span v-if="topic" class="meta-topic">
        <el-icon><Aim /></el-icon>
        {{ topic }}
      </span>
      <span class="meta-length">{{ paper.abstract.length }} 字</span>
    </div>

    <!-- 摘要正文 -->
    <div class="abstract-text" v-html="renderedAbstract"></div>

    <!-- 关键词 chips（合并 + 去重 + 最多 12 个） -->
    <div v-if="keywords.length" class="abstract-keywords">
      <el-tag
        v-for="kw in keywords"
        :key="kw"
        size="small"
        effect="plain"
        round
        class="keyword-tag"
      >{{ kw }}</el-tag>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { Aim, Document } from '@element-plus/icons-vue'
import { autoLinkContent } from '@/utils/paperAdapter'

const props = defineProps({
  paper: { type: Object, required: true },
})

const renderedAbstract = computed(() => autoLinkContent(props.paper.abstract || ''))

// 关键词合并：tags + keywords 去重（最多 12 个）
const keywords = computed(() => {
  const arr = [
    ...(Array.isArray(props.paper.tags) ? props.paper.tags : []),
    ...(Array.isArray(props.paper.keywords) ? props.paper.keywords : []),
  ]
  return Array.from(new Set(arr)).slice(0, 12)
})

// v28 step 45 字段名兼容
const topic = computed(() => props.paper.topic || '')
</script>

<style scoped>
.paper-abstract {
  background: linear-gradient(135deg, #FFF8F5 0%, #FFFDFB 100%);
  border: 1px solid rgba(255, 122, 92, 0.12);
  border-left: 4px solid var(--color-primary);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 20px;
}

/* v28 step 109.36.9: Abstract 标题（让用户知道这段是什么） */
.abstract-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-primary);
  margin: 0 0 10px 0;
}

.abstract-title .el-icon {
  font-size: 18px;
}

.abstract-meta-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--color-text-secondary);
  flex-wrap: wrap;
}

.meta-topic {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-primary);
  font-weight: 600;
  font-size: 13px;
}

.meta-type {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(59, 130, 246, 0.08);
  color: var(--color-primary);
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 500;
}

.meta-length {
  margin-left: auto;
  font-size: 11px;
  color: var(--color-text-placeholder);
}

.abstract-text {
  font-size: 15px;
  line-height: 1.85;
  color: var(--color-text-primary);
  overflow-wrap: anywhere;
  margin-bottom: 10px;
}

.abstract-text :deep(.auto-link) {
  color: var(--color-primary);
  text-decoration: none;
}
.abstract-text :deep(.auto-link:hover) {
  text-decoration: underline;
}

.abstract-keywords {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding-top: 10px;
  border-top: 1px dashed rgba(255, 122, 92, 0.2);
}

.keywords-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
  margin-right: 4px;
}

.keyword-tag {
  background: var(--color-bg-card);
  color: var(--color-primary);
  border: 1px solid rgba(255, 122, 92, 0.3);
}
</style>
