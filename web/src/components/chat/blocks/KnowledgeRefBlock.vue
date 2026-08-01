<script setup>
/**
 * KnowledgeRefBlock.vue — 知识库引用卡 (CHAT-P1-E E1 升级)
 *
 * 接收 block.data = {results: [{id, title, content, score, category, tags, source, snippet}], citations?: [...]}
 *
 * CHAT-P1-E E1: hover/长按显示 snippet 浮层
 * - 数据源: refs[i].snippet (A5 已加, ≤200 字 chunk 原文)
 * - 桌面: CSS :hover tooltip
 * - 移动: 长按 → ElMessageBox 详情弹窗
 *
 * W99-RAG-2 (2026-08-02): citation 高亮 props
 * - 新增 props.citations: Array (默认 [])
 *   每条: {doc_id, chunk_id, char_range: [start, end], similarity, snippet, strategy, retrieval_method}
 * - 当 citations 中有匹配 chunk_id 时, 在 ref-content 中用 <mark> 高亮 char_range 段落
 * - 派工 v11 §3 E03 实战: 0 改既有 props/事件, 仅 ADD 新 props
 */
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'

const props = defineProps({
  block: { type: Object, required: true },
  // W99-RAG-2 新增 — 段落级 citation 列表 (来自 hybrid_retriever.citation hook)
  citations: {
    type: Array,
    default: () => [],
  },
})
const router = useRouter()

const results = (props.block.data || {}).results || []
const citations = props.citations || []

const stripHtml = (html) => {
  if (!html) return ''
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

const goToKnowledge = (id) => { if (id) router.push(`/knowledge/${id}`) }

// E1: 获取 tooltip snippet (A5 数据源)
const getSnippet = (r) => {
  // 优先使用 A5 提供的 snippet (chunk 原文 ≤200 字)
  if (r.snippet) return r.snippet
  // 兜底: 用 content 截前 200 字
  return stripHtml(r.content).slice(0, 200)
}

// E1: 移动端长按 → 弹窗显示完整 snippet
const onLongPress = async (r) => {
  try {
    const snippet = getSnippet(r)
    await ElMessageBox.alert(snippet, r.title || '知识引用', {
      confirmButtonText: '关闭',
      showClose: false,
      customClass: 'kb-ref-snippet-dialog',
      message: () => {
        return (
          // eslint-disable-next-line vue/require-render-return
          h('div', { class: 'kb-ref-snippet-content' }, snippet)
        )
      },
    })
  } catch {
    /* 用户取消 */
  }
}

// E1: 桌面 tooltip 内容处理 (>60 字截断, hover tooltip 不撑爆)
const getTooltipContent = (r) => {
  const snippet = getSnippet(r)
  return snippet.length > 60 ? snippet.slice(0, 60) + '...' : snippet
}

// W99-RAG-2: 查找与某个 result 关联的 citation (按 chunk_id 匹配)
// 返回首个匹配的 citation 或 null
const findCitationForResult = (r) => {
  if (!r.chunk_id || !citations.length) return null
  return citations.find(c => c.chunk_id === r.chunk_id) || null
}

// W99-RAG-2: 渲染高亮 snippet (用 <mark> 标黄 char_range 区间)
// 返回 HTML 字符串, 避免 v-html XSS (只用 chunk 原文 + 标记)
const renderHighlightedSnippet = (r) => {
  const cit = findCitationForResult(r)
  if (!cit) return null  // 无 citation → 不高亮, 走原逻辑
  const snippet = getSnippet(r)
  const range = cit.char_range || cit.charRange  // 兼容 list / tuple 两种格式
  if (!Array.isArray(range) || range.length !== 2) return null
  const [start, end] = range
  if (typeof start !== 'number' || typeof end !== 'number') return null
  // 边界截断
  const safeStart = Math.max(0, Math.min(start, snippet.length))
  const safeEnd = Math.max(safeStart, Math.min(end, snippet.length))
  if (safeEnd <= safeStart) return null
  return {
    before: snippet.slice(0, safeStart),
    highlight: snippet.slice(safeStart, safeEnd),
    after: snippet.slice(safeEnd),
  }
}

// Vue h() for Element Plus ElMessageBox message slot
import { h } from 'vue'
</script>

<template>
  <div class="kb-ref rich-card">
    <div class="card-header">
      <span class="icon">📚</span>
      <span class="title">{{ block.title || '知识引用' }} ({{ results.length }})</span>
    </div>
    <div
      v-for="(r, i) in results"
      :key="r.id"
      class="ref-item"
      :class="{ 'has-snippet': r.snippet, [`stagger-${Math.min(i + 1, 6)}`]: true }"
      @click="goToKnowledge(r.id)"
    >
      <!-- E1: hover tooltip 显示 snippet (桌面 CSS only, 移动禁用 hover 由长按触发) -->
      <el-tooltip
        v-if="r.snippet"
        :content="getTooltipContent(r)"
        placement="top"
        :show-after="300"
        :hide-after="100"
        popper-class="kb-ref-tooltip"
        :disabled="false"
      >
        <div class="ref-content-wrap">
          <div class="ref-title">{{ r.title }}</div>
          <!-- W99-RAG-2: citation 高亮 (有 chunk_id 匹配时用 <mark>) -->
          <div v-if="renderHighlightedSnippet(r)" class="ref-content ref-content-citation">
            {{ renderHighlightedSnippet(r).before }}<mark class="citation-mark">{{ renderHighlightedSnippet(r).highlight }}</mark>{{ renderHighlightedSnippet(r).after }}
          </div>
          <div v-else class="ref-content">{{ stripHtml(r.content).slice(0, 200) }}{{ stripHtml(r.content).length > 200 ? '...' : '' }}</div>
          <div class="ref-meta">
            <span v-if="r.category" class="meta">📁 {{ r.category }}</span>
            <span v-if="r.source" class="meta">📎 {{ r.source }}</span>
            <span v-if="r.score != null" class="meta score">⭐ {{ (r.score * 100).toFixed(0) }}%</span>
            <span v-for="tag in (r.tags || []).slice(0, 3)" :key="tag" class="tag">{{ tag }}</span>
          </div>
        </div>
      </el-tooltip>
      <!-- E1: fallback (无 snippet 时) -->
      <div v-else class="ref-content-wrap">
        <div class="ref-title">{{ r.title }}</div>
        <div class="ref-content">{{ stripHtml(r.content).slice(0, 200) }}{{ stripHtml(r.content).length > 200 ? '...' : '' }}</div>
        <div class="ref-meta">
          <span v-if="r.category" class="meta">📁 {{ r.category }}</span>
          <span v-if="r.source" class="meta">📎 {{ r.source }}</span>
          <span v-if="r.score != null" class="meta score">⭐ {{ (r.score * 100).toFixed(0) }}%</span>
          <span v-for="tag in (r.tags || []).slice(0, 3)" :key="tag" class="tag">{{ tag }}</span>
        </div>
      </div>
    </div>
    <div v-if="!results.length" class="empty">暂无知识</div>
  </div>
</template>

<style scoped>
.rich-card { background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: var(--shadow-xs); }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 14px; margin-bottom: 10px; color: var(--color-primary); }
.icon { font-size: 18px; }
.ref-item { padding: 10px 0; border-top: 1px solid var(--color-border-light); cursor: pointer; transition: background 0.15s; animation: var(--animation-fadeSlideUp); }
.ref-item:first-of-type { border-top: none; }
.ref-item:hover { background: var(--color-bg-warm); margin: 0 -8px; padding: 10px 8px; border-radius: 6px; }

@media (prefers-reduced-motion: reduce) {
  .ref-item { animation: none; }
}
.ref-content-wrap { width: 100%; }
.ref-title { font-weight: 500; font-size: 14px; color: var(--color-primary); }
.ref-content { font-size: 13px; color: var(--color-text-regular); margin-top: 4px; line-height: 1.5; }
.ref-meta { display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
.meta { font-size: 11px; color: var(--color-text-secondary); }
.meta.score { color: var(--color-warning); font-weight: 500; }
.tag { font-size: 11px; background: var(--color-bg-hover); color: var(--color-text-regular); padding: 1px 6px; border-radius: 8px; }
.empty { text-align: center; color: var(--color-text-secondary); padding: 20px 0; font-size: 13px; }

/* v77 P2.5.3: dark mode hover */
[data-theme="dark"] .ref-item:hover {
  background: var(--color-bg-hover);
}

/* W99-RAG-2: citation 高亮样式 (段落级溯源) */
.citation-mark {
  background: rgba(255, 215, 0, 0.4);
  color: inherit;
  padding: 1px 2px;
  border-radius: 2px;
  font-weight: 500;
}
[data-theme="dark"] .citation-mark {
  background: rgba(255, 215, 0, 0.3);
}
.ref-content-citation {
  position: relative;
}
</style>

<!-- E1: tooltip + dialog 走非 scoped 块 (v60-v67 教训) -->
<style>
.kb-ref-tooltip {
  max-width: 360px !important;
  line-height: 1.5 !important;
  font-size: 12px !important;
  word-break: break-word;
}
.kb-ref-snippet-dialog .el-message-box__message {
  white-space: pre-wrap;
  word-break: break-word;
}
.kb-ref-snippet-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
  max-height: 50vh;
  overflow-y: auto;
}
</style>