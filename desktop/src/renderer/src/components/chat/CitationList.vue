<script setup lang="ts">
/**
 * CitationList (Phase 3-C1).
 *
 * 渲染一组 citation 卡. 来源: 流式 streamingMessage.citations 或
 * 已完成消息 metadata.citations.
 *
 * 渲染规则:
 * - 0 citations: 渲染 nothing (DOM 干净)
 * - ≥1 citations: 列表 + 标题 "📚 引用 N 条"
 *
 * 与 MarkdownViewer 互补: 正文 markdown 解析由 MarkdownViewer 负责,
 * 引用列表由本组件单独渲染, 不嵌入 markdown 主体.
 */
import CitationCard from './CitationCard.vue'
import type { StreamCitationEntry } from '@shared/chat-types'

interface Props {
  citations: StreamCitationEntry[]
}
defineProps<Props>()
</script>

<template>
  <section v-if="citations && citations.length > 0" class="citation-list">
    <header class="citation-list__head">
      <span class="citation-list__icon">📚</span>
      <span class="citation-list__title">引用 {{ citations.length }} 条</span>
    </header>
    <div class="citation-list__items">
      <CitationCard
        v-for="(c, i) in citations"
        :key="`cit-${c.knowledgeId}-${i}`"
        :citation="c"
        :index="i"
      />
    </div>
  </section>
</template>

<style scoped>
.citation-list {
  margin-top: 0.6rem;
  padding-top: 0.6rem;
  border-top: 1px dashed rgba(99, 102, 241, 0.3);
}
.citation-list__head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
  font-size: 0.78rem;
  color: #94a3b8;
}
.citation-list__icon { font-size: 0.9rem; }
.citation-list__title { font-weight: 500; }
.citation-list__items {
  display: flex;
  flex-direction: column;
}
</style>
