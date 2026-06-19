<template>
  <section v-if="paper.abstract" class="paper-abstract">
    <div class="abstract-header">
      <span class="abstract-label">摘要</span>
      <span v-if="paper.abstract.length" class="abstract-length">{{ paper.abstract.length }} 字</span>
    </div>
    <div class="abstract-text" v-html="renderedAbstract"></div>
    <div v-if="paper.keywords?.length" class="abstract-keywords">
      <span class="keywords-label">关键词</span>
      <el-tag
        v-for="kw in paper.keywords"
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
import { autoLinkContent } from '@/utils/paperAdapter'

const props = defineProps({
  paper: { type: Object, required: true },
})

// 自动链接 DOI/URL/邮箱
const renderedAbstract = computed(() => autoLinkContent(props.paper.abstract || ''))
</script>

<style scoped>
.paper-abstract {
  background: linear-gradient(135deg, #FFF8F5 0%, #FFFDFB 100%);
  border: 1px solid rgba(255, 122, 92, 0.12);
  border-left: 4px solid var(--color-primary);
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 24px;
}

.abstract-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.abstract-label {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-primary);
}

.abstract-length {
  font-size: 12px;
  color: #9CA3AF;
}

.abstract-text {
  font-size: 15px;
  line-height: 1.85;
  color: #1F2937;
  word-break: break-word;
}

.abstract-text :deep(.auto-link) {
  color: #2563EB;
  text-decoration: none;
}

.abstract-text :deep(.auto-link:hover) {
  text-decoration: underline;
}

.abstract-keywords {
  margin-top: 16px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding-top: 14px;
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
</style>
