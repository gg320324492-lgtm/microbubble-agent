<script setup lang="ts">
/**
 * CitationList (Phase 3-C2: sort + knowledge-open relay).
 *
 * 渲染一组 citation 卡:
 *   - 0 citations: 渲染 nothing (DOM 干净)
 *   - ≥1 citations: sort by score desc (Phase 3-C2) + "📚 引用 N 条" 标题
 *
 * 与 MarkdownViewer 互补: 正文 markdown 由 MarkdownViewer 负责,
 * 引用列表单独渲染, 不嵌入 markdown 主体.
 *
 * Phase 3-C2: 通过 emit('knowledge-open', id) 把 knowledgeId 回调给上层
 * (ChatView 可选监听), Phase 4+ 接 router.
 */
import { computed } from 'vue'
import CitationCard from './CitationCard.vue'
import { sortCitations } from '../../utils/citation'
import type { StreamCitationEntry } from '@shared/chat-types'

interface Props {
  citations: StreamCitationEntry[]
}
const props = defineProps<Props>()

const emit = defineEmits<{
  'knowledge-open': [knowledgeId: number]
}>()

const sorted = computed(() => sortCitations(props.citations))
</script>

<template>
  <section v-if="sorted && sorted.length > 0" class="citation-list">
    <header class="citation-list__head">
      <span class="citation-list__icon">📚</span>
      <span class="citation-list__title">引用 {{ sorted.length }} 条</span>
    </header>
    <div class="citation-list__items">
      <CitationCard
        v-for="(c, i) in sorted"
        :key="`cit-${c.knowledgeId}-${i}`"
        :citation="c"
        :index="i"
        @knowledge-open="(id) => emit('knowledge-open', id)"
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
