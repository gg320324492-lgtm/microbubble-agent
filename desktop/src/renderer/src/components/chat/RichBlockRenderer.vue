<script setup lang="ts">
/**
 * RichBlockRenderer (Phase 5-A: Agent Tool Renderer Foundation).
 *
 * 渲染 StreamRichBlock (Phase 3-B0 frozen). 安全策略:
 * - 0 v-html (CSP 不允许, 也避免 XSS)
 * - text -> Vue 文本插值 (auto escape)
 * - json -> JSON.stringify + text 插值
 * - markdown -> 复用 MarkdownViewer (Phase 2-Impl-2B 自写 parser, 0 v-html)
 * - 其它 type -> 安全 fallback (折叠 + type label)
 */
import { computed } from 'vue'
import { MarkdownViewer } from '../ui'
import type { StreamRichBlock } from '@shared/chat-types'

interface Props {
  block: StreamRichBlock
}
const props = defineProps<Props>()

const blockType = computed(() => props.block.type || 'unknown')
const title = computed(() => props.block.title ?? blockType.value)

const textContent = computed(() => {
  const d = props.block.data
  if (typeof d === 'string') return d
  if (d == null) return ''
  try {
    return JSON.stringify(d, null, 2)
  } catch (_e) {
    return String(d)
  }
})

const jsonContent = computed(() => {
  const d = props.block.data
  if (d == null) return ''
  try {
    return JSON.stringify(d, null, 2)
  } catch (_e) {
    return String(d)
  }
})

const isMarkdown = computed(() => blockType.value === 'markdown')
const isJson = computed(() => blockType.value === 'json')
const isText = computed(() => blockType.value === 'text')
</script>

<template>
  <div class="rich-block">
    <header class="rich-block__head">
      <span class="rich-block__icon">📦</span>
      <span class="rich-block__title">{{ title }}</span>
      <span class="rich-block__type">{{ blockType }}</span>
    </header>

    <div v-if="isMarkdown" class="rich-block__body">
      <MarkdownViewer :source="textContent" />
    </div>
    <div v-else-if="isJson" class="rich-block__body">
      <pre class="rich-block__json">{{ jsonContent }}</pre>
    </div>
    <div v-else-if="isText" class="rich-block__body rich-block__text">
      <pre>{{ textContent }}</pre>
    </div>
    <div v-else class="rich-block__body rich-block__unknown">
      <details>
        <summary>未知 rich_block.type: {{ blockType }}</summary>
        <pre>{{ jsonContent }}</pre>
      </details>
    </div>
  </div>
</template>

<style scoped>
.rich-block {
  margin: 0.4rem 0;
  background: rgba(168, 85, 247, 0.04);
  border: 1px solid rgba(168, 85, 247, 0.22);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
}
.rich-block__head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.4rem;
  font-size: 0.8rem;
}
.rich-block__icon { font-size: 0.95rem; }
.rich-block__title {
  font-weight: 600;
  color: #f1f5f9;
  flex: 1;
  word-break: break-word;
}
.rich-block__type {
  font-size: 0.7rem;
  background: rgba(168, 85, 247, 0.15);
  color: #d8b4fe;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  flex-shrink: 0;
}
.rich-block__body {
  font-size: 0.85rem;
}
.rich-block__body pre {
  margin: 0;
  padding: 0.5rem 0.7rem;
  background: #0b1220;
  border: 1px solid #1e293b;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.75rem;
  color: #cbd5e1;
  max-height: 280px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
.rich-block__text pre {
  margin: 0;
}
.rich-block__json {
  background: #0b1220;
  border: 1px solid #1e293b;
  border-radius: 4px;
  padding: 0.5rem 0.7rem;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.75rem;
  color: #cbd5e1;
  max-height: 280px;
  overflow: auto;
  white-space: pre-wrap;
}
.rich-block__unknown {
  /* fallback 不显式破坏, 走 details 折叠 */
}
.rich-block__unknown details {
  font-size: 0.75rem;
  color: #94a3b8;
}
.rich-block__unknown summary {
  cursor: pointer;
  user-select: none;
}
</style>
