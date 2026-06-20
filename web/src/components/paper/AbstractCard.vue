<template>
  <!-- v28 step 44: 论文元数据卡片（重设计减少冗余）
       之前显示 4 个独立 section (摘要 / 关键词 / 核心概念 / 关联主题)，
       信息密度高但视觉杂乱，重复显示相似内容。
       现在改为：
       - 1 个 summary block（含摘要正文 + 关键标签 chips）
       - 元信息行（topic + 来源类型 + 字数）
       - 可折叠"更多"（key_concepts + related_topics 紧凑 grid）
  -->
  <section v-if="paper.abstract" class="paper-abstract">
    <!-- 顶部元信息行：topic + 类型 + 字数 -->
    <div class="abstract-meta-row">
      <span v-if="topic" class="meta-topic">
        <el-icon><Aim /></el-icon>
        {{ topic }}
      </span>
      <span v-if="fileType === 'application/pdf'" class="meta-type">
        <el-icon><Document /></el-icon> PDF
      </span>
      <span v-if="fileType?.includes('word')" class="meta-type">
        <el-icon><Document /></el-icon> Word
      </span>
      <span class="meta-length">{{ paper.abstract.length }} 字</span>
    </div>

    <!-- 摘要正文 -->
    <div class="abstract-text" v-html="renderedAbstract"></div>

    <!-- 关键词 chips（compact） -->
    <div v-if="keywords.length" class="abstract-keywords">
      <span class="keywords-label">关键词</span>
      <el-tag
        v-for="kw in keywords"
        :key="kw"
        size="small"
        effect="plain"
        round
        class="keyword-tag"
      >{{ kw }}</el-tag>
    </div>

    <!-- 可折叠：核心概念 + 关联主题（紧凑 grid） -->
    <details v-if="keyConcepts.length || relatedTopics.length" class="abstract-extras">
      <summary class="extras-toggle">
        <el-icon><MoreFilled /></el-icon>
        核心概念与关联主题（{{ keyConcepts.length + relatedTopics.length }} 项）
      </summary>
      <div v-if="keyConcepts.length" class="extras-section">
        <div class="extras-label">核心概念</div>
        <div class="extras-chips">
          <el-tag
            v-for="kc in keyConcepts"
            :key="kc"
            size="small"
            type="info"
            effect="plain"
            round
          >{{ kc }}</el-tag>
        </div>
      </div>
      <div v-if="relatedTopics.length" class="extras-section">
        <div class="extras-label">关联主题</div>
        <div class="extras-chips">
          <el-tag
            v-for="rt in relatedTopics"
            :key="rt"
            size="small"
            type="success"
            effect="plain"
            round
          >{{ rt }}</el-tag>
        </div>
      </div>
    </details>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { Aim, Document, MoreFilled } from '@element-plus/icons-vue'
import { autoLinkContent } from '@/utils/paperAdapter'

const props = defineProps({
  paper: { type: Object, required: true },
})

const renderedAbstract = computed(() => autoLinkContent(props.paper.abstract || ''))

// 关键词合并：tags 和 keywords 二选一（去重）
const keywords = computed(() => {
  const arr = [
    ...(Array.isArray(props.paper.tags) ? props.paper.tags : []),
    ...(Array.isArray(props.paper.keywords) ? props.paper.keywords : []),
  ]
  return Array.from(new Set(arr)).slice(0, 12)  // 最多 12 个
})

// v28 step 45: paperAdapter 转换字段名为 camelCase（keyConcepts / relatedTopics），
//              同时兼容旧 API 直接传 snake_case
const keyConcepts = computed(() => {
  const arr = props.paper.keyConcepts || props.paper.key_concepts
  return Array.isArray(arr) ? arr : []
})
const relatedTopics = computed(() => {
  const arr = props.paper.relatedTopics || props.paper.related_topics
  return Array.isArray(arr) ? arr : []
})
const topic = computed(() => props.paper.topic || props.paper.relatedKnowledge?.topic || '')

// v28 step 45: fileType 也兼容 camelCase/snake_case
const fileType = computed(() => props.paper.fileType || props.paper.file_type || '')
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

.abstract-meta-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #6B7280;
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
  color: #2563EB;
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 500;
}

.meta-length {
  margin-left: auto;
  font-size: 11px;
  color: #9CA3AF;
}

.abstract-text {
  font-size: 15px;
  line-height: 1.85;
  color: #1F2937;
  word-break: break-word;
  margin-bottom: 10px;
}

.abstract-text :deep(.auto-link) {
  color: #2563EB;
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
  color: #6B7280;
  font-weight: 500;
  margin-right: 4px;
}

.keyword-tag {
  background: #fff;
  color: var(--color-primary);
  border: 1px solid rgba(255, 122, 92, 0.3);
}

/* 折叠区域：核心概念 + 关联主题 */
.abstract-extras {
  margin-top: 10px;
  border-top: 1px dashed rgba(255, 122, 92, 0.2);
  padding-top: 8px;
}

.extras-toggle {
  cursor: pointer;
  font-size: 12.5px;
  color: #6B7280;
  user-select: none;
  list-style: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 0;
}

.extras-toggle::-webkit-details-marker {
  display: none;
}

.extras-toggle:hover {
  color: var(--color-primary);
}

.abstract-extras[open] .extras-toggle {
  margin-bottom: 8px;
}

.extras-section {
  margin-bottom: 8px;
}

.extras-label {
  font-size: 12px;
  color: #9CA3AF;
  margin-bottom: 4px;
}

.extras-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
