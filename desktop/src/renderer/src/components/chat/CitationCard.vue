<script setup lang="ts">
/**
 * CitationCard (Phase 3-C2 + Phase 4-C: Knowledge Hot Path Enhancement).
 *
 * 单条 RAG 引用的展示卡.
 * - 严禁 v-html (snippet/title 走 Vue 文本插值自动 escape)
 * - Score: 仅 valid (0..1) 显示百分比 (空 -> 隐藏)
 * - Click 行为:
 *   - url 优先 -> window.open(_blank) -> 走 main setWindowOpenHandler -> shell.openExternal
 *   - knowledgeId 优先 -> emit('knowledge-open', id) (Phase 4+ 接 knowledge 路由, 当前无 listener)
 *   - 都无: 卡片 disabled (无 click)
 *
 * Phase 4-C: cachedHint 可选 prop (来自 knowledgeService cache).
 *   - 命中 -> 显示 category (从 KnowledgeResponse 拉)
 *   - 未命中 -> 维持 Phase 3-C1 形态 (citation 自身 title/snippet)
 */
import { computed } from 'vue'
import { hasValidScore, toPercent } from '../../utils/citation'
import type { StreamCitationEntry } from '@shared/chat-types'
import type { KnowledgeResponse } from '@shared/knowledge-types'

interface Props {
  citation: StreamCitationEntry
  index?: number
  cachedHint?: KnowledgeResponse | null
}
const props = withDefaults(defineProps<Props>(), { index: 0, cachedHint: null })

const emit = defineEmits<{
  /** Phase 4+ 接 knowledge 路由时, ChatView 监听 + router.push */
  'knowledge-open': [knowledgeId: number]
}>()

const title = computed(() => props.citation.title || `引用 #${props.citation.knowledgeId}`)
const snippet = computed(() => (props.citation.snippet ?? '').trim())
const url = computed(() => props.citation.url ?? '')
const scorePercent = computed(() => toPercent(props.citation.score))
const sourceLabel = computed(() => {
  const s = props.citation.source
  if (!s) return '知识库'
  switch (s) {
    case 'kb': return '知识库'
    case 'memory': return '记忆'
    case 'auto_research': return '自动检索'
    default: return s
  }
})
const kind = computed<'url' | 'kb' | 'none'>(() => {
  if (url.value) return 'url'
  if (typeof props.citation.knowledgeId === 'number') return 'kb'
  return 'none'
})
const hasScore = computed(() => hasValidScore(props.citation))
/** 高分 (>=0.7) 给个视觉强调: alpha 1.0; 低分 <0.7 alpha 0.85 */
const scoreAlpha = computed(() => {
  if (!hasScore.value) return 1
  const s = props.citation.score as number
  return s >= 0.7 ? 1 : 0.85
})
/** Phase 4-C: 是否命中 knowledgeService cache. */
const hasCachedHint = computed(() => props.cachedHint != null)

function onClick(): void {
  if (url.value) {
    // _blank 触发 main 的 setWindowOpenHandler, 自动 shell.openExternal
    window.open(url.value, '_blank', 'noopener,noreferrer')
    return
  }
  if (typeof props.citation.knowledgeId === 'number') {
    emit('knowledge-open', props.citation.knowledgeId)
    return
  }
  // 无 url / knowledgeId: 静默 no-op (Phase 3-C2 不实现 placeholder)
}
</script>

<template>
  <button
    type="button"
    :class="['citation-card', `citation-card--${kind}`, { 'citation-card--cached': hasCachedHint }]"
    :disabled="kind === 'none'"
    :style="{ opacity: scoreAlpha }"
    @click="onClick"
  >
    <div class="citation-card__head">
      <span class="citation-card__index">[{{ index + 1 }}]</span>
      <span class="citation-card__title">{{ title }}</span>
      <span v-if="scorePercent" class="citation-card__score" :title="`score: ${props.citation.score?.toFixed?.(2) ?? ''}`">
        {{ scorePercent }}
      </span>
    </div>
    <div v-if="snippet" class="citation-card__snippet">{{ snippet }}</div>
    <div class="citation-card__meta">
      <span class="citation-card__source">📁 {{ sourceLabel }}</span>
      <span v-if="cachedHint?.category" class="citation-card__category">{{ cachedHint.category }}</span>
      <span class="citation-card__jump" :data-kind="kind">
        {{ kind === 'url' ? '↗ 打开' : kind === 'kb' ? '→ 详情' : '🔒' }}
      </span>
    </div>
  </button>
</template>

<style scoped>
.citation-card {
  display: block;
  width: 100%;
  text-align: left;
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.22);
  border-radius: 6px;
  padding: 0.6rem 0.75rem;
  color: #cbd5e1;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s, border-color 0.15s, transform 0.05s;
  margin-bottom: 0.4rem;
}
.citation-card:last-child { margin-bottom: 0; }
.citation-card:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.12);
  border-color: rgba(99, 102, 241, 0.45);
}
.citation-card:active:not(:disabled) {
  transform: translateY(1px);
}
.citation-card:disabled {
  cursor: default;
  opacity: 0.7;
}
.citation-card--none {
  background: rgba(148, 163, 184, 0.04);
  border-color: rgba(148, 163, 184, 0.18);
}
.citation-card--cached {
  /* Phase 4-C: 缓存命中时给个更亮边框, 区分未缓存状态 */
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.04);
}

.citation-card__head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}
.citation-card__index {
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.72rem;
  flex-shrink: 0;
}
.citation-card__title {
  font-size: 0.88rem;
  font-weight: 600;
  color: #c7d2fe;
  flex: 1;
  word-break: break-word;
  min-width: 0;
}
/* Phase 3-C2: score pill 在 head 行右侧 (高分暖色, 低分冷色) */
.citation-card__score {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  flex-shrink: 0;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
  border: 1px solid rgba(251, 191, 36, 0.3);
}
.citation-card__score:empty { display: none; }

.citation-card__snippet {
  font-size: 0.8rem;
  line-height: 1.5;
  color: #94a3b8;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 0.4rem;
}

.citation-card__meta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.7rem;
  color: #64748b;
}
.citation-card__source {
  flex: 1;
}
.citation-card__jump {
  margin-left: auto;
  font-size: 0.7rem;
}
.citation-card__jump[data-kind='url'] { color: #f97316; }
.citation-card__jump[data-kind='kb'] { color: #94a3b8; }
.citation-card__jump[data-kind='none'] { color: #475569; }
.citation-card__category {
  background: rgba(16, 185, 129, 0.15);
  color: #5eead4;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-size: 0.7rem;
  /* Phase 4-C: cache 命中的小标签 */
}
</style>
