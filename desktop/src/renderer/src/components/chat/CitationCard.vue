<script setup lang="ts">
/**
 * CitationCard (Phase 3-C1).
 *
 * 单条 RAG 引用的展示卡.
 * - 严禁 v-html (snippet/title 走 Vue 文本插值自动 escape)
 * - 点击行为:
 *   - url 优先 -> window.open(_blank) -> 走 main setWindowOpenHandler -> shell.openExternal
 *   - knowledgeId 优先 -> Phase 4+ 知识详情路由 (此处仅占位, 不实现; 不跳)
 *
 * Phase 3-C1 不连接真实 Knowledge API / 不实现 router 跳转, 仅保留接口.
 */
import { computed } from 'vue'
import type { StreamCitationEntry } from '@shared/chat-types'

interface Props {
  citation: StreamCitationEntry
  index?: number
}
const props = withDefaults(defineProps<Props>(), { index: 0 })

const title = computed(() => props.citation.title || `引用 #${props.citation.knowledgeId}`)
const snippet = computed(() => (props.citation.snippet ?? '').trim())
const url = computed(() => props.citation.url ?? '')
const scorePercent = computed(() => {
  const s = props.citation.score
  if (typeof s !== 'number') return null
  return `${Math.round(s * 100)}%`
})
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

function onClick(): void {
  if (url.value) {
    // _blank 触发 main 的 setWindowOpenHandler, 自动 shell.openExternal
    window.open(url.value, '_blank', 'noopener,noreferrer')
    return
  }
  if (typeof props.citation.knowledgeId === 'number') {
    // Phase 4+ 留口: knowledge 详情路由
    // eslint-disable-next-line no-console
    console.info(
      '[CitationCard] knowledgeId 跳转 Phase 4+ 接入. id=',
      props.citation.knowledgeId
    )
    return
  }
  // 无 url / knowledgeId: 静默 no-op (Phase 3-C1 不实现 placeholder)
}
</script>

<template>
  <button
    type="button"
    :class="['citation-card', `citation-card--${kind}`]"
    :disabled="kind === 'none'"
    @click="onClick"
  >
    <div class="citation-card__head">
      <span class="citation-card__index">[{{ index + 1 }}]</span>
      <span class="citation-card__title">{{ title }}</span>
    </div>
    <div v-if="snippet" class="citation-card__snippet">{{ snippet }}</div>
    <div class="citation-card__meta">
      <span class="citation-card__source">📁 {{ sourceLabel }}</span>
      <span v-if="scorePercent" class="citation-card__score">{{ scorePercent }}</span>
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

.citation-card__head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
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
}

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
.citation-card__score {
  color: #fbbf24;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
.citation-card__jump {
  margin-left: auto;
  font-size: 0.7rem;
}
.citation-card__jump[data-kind='url'] { color: #f97316; }
.citation-card__jump[data-kind='kb'] { color: #94a3b8; }
.citation-card__jump[data-kind='none'] { color: #475569; }
</style>
