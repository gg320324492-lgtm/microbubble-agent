<script setup lang="ts">
/**
 * TraceTimeline (Phase 5-B: Agent Timeline / Trace Renderer).
 *
 * 渲染 ChatMessage 的 agent trace (thinking / tool_call / tool_result /
 * citation / rich_block / answer). 时间顺序 fixed.
 *
 * 可折叠: completed message 默认 collapsed (summary 仅);
 *            streaming 时默认 expanded (流中看实时).
 *
 * Phase 5-B 不执行 tool / 不接 RAG / 不改 SSE schema.
 */
import { computed, ref } from 'vue'
import type { TraceItem } from '../../utils/chat-trace'
import { formatTraceSummary, summarizeTrace } from '../../utils/chat-trace'
import { MarkdownViewer } from '../ui'
import ToolCallCard from './ToolCallCard.vue'
import ToolResultCard from './ToolResultCard.vue'
import CitationList from './CitationList.vue'
import RichBlockRenderer from './RichBlockRenderer.vue'

interface Props {
  items: TraceItem[]
  /** Phase 5-B: 默认折叠. 流中场景可传 false */
  defaultCollapsed?: boolean
}
const props = withDefaults(defineProps<Props>(), { defaultCollapsed: true })

const collapsed = ref<boolean>(props.defaultCollapsed)

const summary = computed(() => summarizeTrace(props.items))
const summaryText = computed(() => formatTraceSummary(summary.value))
const isEmpty = computed(() => props.items.length === 0)

function toggle(): void {
  collapsed.value = !collapsed.value
}
</script>

<template>
  <div v-if="!isEmpty" :class="['trace-timeline', { 'is-collapsed': collapsed }]">
    <button
      type="button"
      class="trace-timeline__head"
      :aria-expanded="!collapsed"
      @click="toggle"
    >
      <span class="trace-timeline__icon">{{ collapsed ? '▶' : '▼' }}</span>
      <span class="trace-timeline__title">
        {{ collapsed ? '展开 Trace' : '收起 Trace' }}
      </span>
      <span v-if="summaryText && collapsed" class="trace-timeline__summary">
        {{ summaryText }}
      </span>
    </button>

    <div v-if="!collapsed" class="trace-timeline__body">
      <div v-for="item in items" :key="item.order" class="trace-timeline__item">
        <div v-if="item.kind === 'thinking'" class="trace-item trace-item--thinking">
          <span class="trace-item__icon">💭</span>
          <span class="trace-item__label">{{ item.label }}</span>
        </div>
        <div v-else-if="item.kind === 'tool_call'" class="trace-item trace-item--tool-call">
          <ToolCallCard :tool="item.tool" />
        </div>
        <div v-else-if="item.kind === 'tool_result'" class="trace-item trace-item--tool-result">
          <ToolResultCard :tool="item.tool" />
        </div>
        <div v-else-if="item.kind === 'citation'" class="trace-item trace-item--citation">
          <!-- 单条 citation 走 CitationList 渲染 (Phase 3-C1 兼容) -->
          <CitationList :citations="[item.citation]" />
        </div>
        <div v-else-if="item.kind === 'rich_block'" class="trace-item trace-item--rich-block">
          <RichBlockRenderer :block="item.block" />
        </div>
        <div v-else-if="item.kind === 'answer'" class="trace-item trace-item--answer">
          <MarkdownViewer :source="item.content" body-class="trace-md" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.trace-timeline {
  margin: 0.5rem 0;
  border: 1px solid rgba(99, 102, 241, 0.18);
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.04);
  overflow: hidden;
}
.trace-timeline.is-collapsed {
  background: rgba(99, 102, 241, 0.02);
}
.trace-timeline__head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: transparent;
  border: 0;
  color: #94a3b8;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.78rem;
  text-align: left;
}
.trace-timeline__head:hover {
  background: rgba(99, 102, 241, 0.06);
  color: #cbd5e1;
}
.trace-timeline__icon {
  font-size: 0.7rem;
  color: #64748b;
}
.trace-timeline__title {
  font-weight: 600;
  color: #c7d2fe;
}
.trace-timeline__summary {
  font-size: 0.72rem;
  color: #94a3b8;
  margin-left: 0.5rem;
}
.trace-timeline__body {
  padding: 0.6rem 0.75rem 0.75rem;
  border-top: 1px dashed rgba(99, 102, 241, 0.18);
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.trace-timeline__item {
  /* each item spacing, 视觉差异化由 item kind 内部组件处理 */
}
.trace-item {
  display: flex;
  align-items: flex-start;
}
.trace-item--thinking {
  background: rgba(251, 191, 36, 0.06);
  border-left: 2px solid #fbbf24;
  padding: 0.3rem 0.6rem;
  border-radius: 0 4px 4px 0;
  font-size: 0.82rem;
  color: #fde68a;
}
.trace-item--tool-call,
.trace-item--tool-result,
.trace-item--citation,
.trace-item--rich-block {
  /* 由内部组件样式控制 */
}
.trace-item--answer {
  /* MarkdownViewer 渲染 */
}
</style>

<style>
/* global style for trace-md body class (穿透 scoped) */
.trace-md {
  /* compact mode for trace timeline */
  font-size: 0.85rem;
}
</style>
