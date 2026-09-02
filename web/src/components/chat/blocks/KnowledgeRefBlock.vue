<script setup>
/**
 * KnowledgeRefBlock.vue — 知识库引用卡
 *
 * P3-RAGUX retry (W100 +33):
 * - score 三档视觉信号 + 5 类 category icon
 * - score/date/category 排序并持久化到 localStorage
 * - 桌面 hover 300ms 详情面板 + 移动端 tap modal
 * - 所有设备统一跳转 /knowledge/:id
 *
 * 兼容保留:
 * - CHAT-P1-E snippet tooltip
 * - W99-RAG-2 citation 段落级高亮
 * - W101 role=list/listitem、键盘激活与 heading 语义
 */
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useIsMobile } from '@/composables/useIsMobile'

const props = defineProps({
  block: { type: Object, required: true },
  citations: {
    type: Array,
    default: () => [],
  },
})

const router = useRouter()
const { isMobile } = useIsMobile()

const results = computed(() => props.block?.data?.results || [])
const citations = computed(() => props.citations || [])

const SORT_STORAGE_KEY = 'kb_ref_sort'
const SORT_OPTIONS = Object.freeze([
  { value: 'score_desc', label: '按相关度' },
  { value: 'date_desc', label: '按最新' },
  { value: 'category', label: '按类别' },
])
const sortMode = ref('score_desc')

const CATEGORY_ICONS = Object.freeze({
  research: '🔬',
  experiment: '⚗️',
  review: '📖',
  paper: '📄',
  thesis: '🎓',
})

const stripHtml = (html) => {
  if (!html) return ''
  return String(html).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

const normalizeDate = (value) => {
  if (!value) return 0
  const timestamp = new Date(value).getTime()
  return Number.isNaN(timestamp) ? 0 : timestamp
}

const formatDate = (value) => {
  if (!value) return ''
  const timestamp = normalizeDate(value)
  if (!timestamp) return String(value)
  const date = new Date(timestamp)
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
}

const getCategoryIcon = (category) => {
  if (!category) return '📁'
  return CATEGORY_ICONS[String(category).toLowerCase().trim()] || '📁'
}

const getScoreClass = (score) => {
  if (score == null) return 'score-neutral'
  const percentage = Number(score) * 100
  if (percentage >= 80) return 'score-high'
  if (percentage >= 60) return 'score-med'
  return 'score-low'
}

const formatScore = (score) => {
  if (score == null) return '未知'
  return `${(Number(score) * 100).toFixed(0)}%`
}

const persistSort = (value) => {
  if (!SORT_OPTIONS.some((option) => option.value === value)) return
  sortMode.value = value
  try {
    localStorage.setItem(SORT_STORAGE_KEY, value)
  } catch {
    // localStorage 不可用时保留当前会话排序，不阻断引用浏览。
  }
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(SORT_STORAGE_KEY)
    if (SORT_OPTIONS.some((option) => option.value === saved)) {
      sortMode.value = saved
    }
  } catch {
    // localStorage 不可用时沿用默认相关度排序。
  }
})

const sortedResults = computed(() => {
  const sorted = [...results.value]

  if (sortMode.value === 'date_desc') {
    return sorted.sort((a, b) => normalizeDate(b.created_at) - normalizeDate(a.created_at))
  }

  if (sortMode.value === 'category') {
    return sorted.sort((a, b) => {
      const categoryDiff = String(a.category || '').localeCompare(String(b.category || ''))
      if (categoryDiff !== 0) return categoryDiff
      return Number(b.score || 0) - Number(a.score || 0)
    })
  }

  return sorted.sort((a, b) => Number(b.score || 0) - Number(a.score || 0))
})

const getSnippet = (result) => {
  if (result.snippet) return String(result.snippet)
  return stripHtml(result.content).slice(0, 200)
}

const getTooltipContent = (result) => {
  const snippet = getSnippet(result)
  return snippet.length > 60 ? `${snippet.slice(0, 60)}...` : snippet
}

const findCitationForResult = (result) => {
  if (!result.chunk_id || !citations.value.length) return null
  return citations.value.find((citation) => citation.chunk_id === result.chunk_id) || null
}

const renderHighlightedSnippet = (result) => {
  const citation = findCitationForResult(result)
  if (!citation) return null

  const snippet = getSnippet(result)
  const range = citation.char_range || citation.charRange
  if (!Array.isArray(range) || range.length !== 2) return null

  const [start, end] = range
  if (typeof start !== 'number' || typeof end !== 'number') return null

  const safeStart = Math.max(0, Math.min(start, snippet.length))
  const safeEnd = Math.max(safeStart, Math.min(end, snippet.length))
  if (safeEnd <= safeStart) return null

  return {
    before: snippet.slice(0, safeStart),
    highlight: snippet.slice(safeStart, safeEnd),
    after: snippet.slice(safeEnd),
  }
}

const relatedLabel = (item) => {
  if (typeof item === 'string' || typeof item === 'number') return String(item)
  return item?.title || item?.id || ''
}

const getDetailSummary = (result) => result.summary || stripHtml(result.content) || getSnippet(result)

const getDetailContent = (result) => {
  const sections = []
  const summary = getDetailSummary(result)
  const entities = (result.entities || []).slice(0, 8).map(String)
  const related = (result.related || []).slice(0, 5).map(relatedLabel).filter(Boolean)

  if (summary) sections.push(summary)
  if (entities.length) sections.push(`关键实体：${entities.join('、')}`)
  if (related.length) sections.push(`关联知识：${related.join(' / ')}`)
  if (result.created_at) sections.push(`收录时间：${formatDate(result.created_at)}`)

  return sections.join('\n\n') || '暂无详情'
}

const renderDetailMessage = (result) => {
  const summary = getDetailSummary(result)
  const entities = (result.entities || []).slice(0, 8).map(String)
  const related = (result.related || []).slice(0, 5).map(relatedLabel).filter(Boolean)

  return h('div', { class: 'kb-ref-detail-content' }, [
    summary
      ? h('section', { class: 'detail-section' }, [
          h('div', { class: 'detail-label' }, '摘要'),
          h('div', { class: 'detail-text' }, summary),
        ])
      : null,
    entities.length
      ? h('section', { class: 'detail-section' }, [
          h('div', { class: 'detail-label' }, '关键实体'),
          h(
            'div',
            { class: 'detail-tags' },
            entities.map((entity) => h('span', { class: 'detail-tag', key: entity }, entity)),
          ),
        ])
      : null,
    related.length
      ? h('section', { class: 'detail-section' }, [
          h('div', { class: 'detail-label' }, '关联知识'),
          h('div', { class: 'detail-text' }, related.join(' / ')),
        ])
      : null,
    result.created_at
      ? h('section', { class: 'detail-section' }, [
          h('div', { class: 'detail-label' }, '收录时间'),
          h('div', { class: 'detail-text' }, formatDate(result.created_at)),
        ])
      : null,
  ])
}

const hasKnowledgeId = (result) => result?.id !== undefined && result?.id !== null && result.id !== ''

const navigateToKnowledge = (result) => {
  // WP1 (2026-09-02): 会议来源命中 — 跳会议详情页而非知识库
  if (result?.retrieval_method === 'meeting' && result?.meeting_id) {
    router.push(`/meetings/${result.meeting_id}`)
    return
  }
  // WP2 (2026-09-02): drive 来源命中 — 跳网盘
  if (result?.retrieval_method === 'drive') {
    router.push('/drive')
    return
  }
  if (!hasKnowledgeId(result)) return
  router.push(`/knowledge/${encodeURIComponent(String(result.id))}`)
}

const showMobileModal = async (result) => {
  if (!isMobile.value) return

  try {
    await ElMessageBox.alert(getDetailContent(result), result.title || '知识引用', {
      confirmButtonText: hasKnowledgeId(result) ? '查看知识' : '关闭',
      showClose: true,
      closeOnClickModal: true,
      customClass: 'kb-ref-detail-dialog',
      message: () => renderDetailMessage(result),
    })
    navigateToKnowledge(result)
  } catch {
    // 用户关闭详情时留在当前对话。
  }
}

const activateResult = (result) => {
  if (isMobile.value) return showMobileModal(result)
  navigateToKnowledge(result)
}

const activeDetail = ref(null)
let detailTimer = null

const hoverDetail = (result) => {
  if (isMobile.value) return
  if (detailTimer) clearTimeout(detailTimer)
  detailTimer = setTimeout(() => {
    activeDetail.value = result.id
    detailTimer = null
  }, 300)
}

const cancelHoverDetail = () => {
  if (detailTimer) {
    clearTimeout(detailTimer)
    detailTimer = null
  }
  activeDetail.value = null
}

onUnmounted(cancelHoverDetail)
</script>

<template>
  <div
    class="kb-ref rich-card"
    role="list"
    aria-label="知识库引用列表"
    @mouseleave="cancelHoverDetail"
  >
    <div class="card-header" role="heading" aria-level="3">
      <span class="icon" aria-hidden="true">📚</span>
      <span class="title">{{ block.title || '知识引用' }} ({{ results.length }})</span>
      <div v-if="results.length > 1" class="sort-control">
        <label class="sort-label" for="kb-ref-sort-select">排序</label>
        <select
          id="kb-ref-sort-select"
          class="sort-select"
          :value="sortMode"
          aria-label="引用块排序方式"
          @change="persistSort($event.target.value)"
        >
          <option v-for="option in SORT_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>
    </div>

    <div
      v-for="(result, index) in sortedResults"
      :key="result.id"
      class="ref-item"
      :class="[
        getScoreClass(result.score),
        {
          'has-snippet': result.snippet,
          [`stagger-${Math.min(index + 1, 6)}`]: true,
        },
      ]"
      role="listitem"
      tabindex="0"
      :aria-label="`知识引用 ${index + 1}: ${result.title || '无标题'}, 相似度 ${formatScore(result.score)}`"
      @click="activateResult(result)"
      @keydown.enter.prevent="activateResult(result)"
      @keydown.space.prevent="activateResult(result)"
      @mouseenter="hoverDetail(result)"
    >
      <el-tooltip
        v-if="result.snippet"
        :content="getTooltipContent(result)"
        placement="top"
        :show-after="300"
        :hide-after="100"
        popper-class="kb-ref-tooltip"
        :disabled="isMobile"
      >
        <div class="ref-content-wrap">
          <div class="ref-title">
            <span class="cat-icon" :title="result.category || '未分类'" aria-hidden="true">
              {{ getCategoryIcon(result.category) }}
            </span>
            <span class="title-text">{{ result.title }}</span>
          </div>
          <div v-if="renderHighlightedSnippet(result)" class="ref-content ref-content-citation">
            {{ renderHighlightedSnippet(result).before }}<mark class="citation-mark">{{ renderHighlightedSnippet(result).highlight }}</mark>{{ renderHighlightedSnippet(result).after }}
          </div>
          <div v-else class="ref-content">
            {{ stripHtml(result.content).slice(0, 200) }}{{ stripHtml(result.content).length > 200 ? '...' : '' }}
          </div>
          <div class="ref-meta">
            <span v-if="result.category" class="meta category">{{ result.category }}</span>
            <span v-if="result.source" class="meta">📎 {{ result.source }}</span>
            <span
              v-if="result.score != null"
              class="meta score-badge"
              :class="getScoreClass(result.score)"
            >
              {{ formatScore(result.score) }}
            </span>
            <span v-for="tag in (result.tags || []).slice(0, 3)" :key="tag" class="tag">
              {{ tag }}
            </span>
          </div>
        </div>
      </el-tooltip>

      <div v-else class="ref-content-wrap">
        <div class="ref-title">
          <span class="cat-icon" :title="result.category || '未分类'" aria-hidden="true">
            {{ getCategoryIcon(result.category) }}
          </span>
          <span class="title-text">{{ result.title }}</span>
        </div>
        <div class="ref-content">
          {{ stripHtml(result.content).slice(0, 200) }}{{ stripHtml(result.content).length > 200 ? '...' : '' }}
        </div>
        <div class="ref-meta">
          <span v-if="result.category" class="meta category">{{ result.category }}</span>
          <span v-if="result.source" class="meta">📎 {{ result.source }}</span>
          <span
            v-if="result.score != null"
            class="meta score-badge"
            :class="getScoreClass(result.score)"
          >
            {{ formatScore(result.score) }}
          </span>
          <span v-for="tag in (result.tags || []).slice(0, 3)" :key="tag" class="tag">
            {{ tag }}
          </span>
        </div>
      </div>

      <div
        v-if="activeDetail === result.id && !isMobile"
        class="detail-panel"
        role="tooltip"
        @click.stop
      >
        <div class="detail-header">
          <span class="detail-cat-icon" aria-hidden="true">{{ getCategoryIcon(result.category) }}</span>
          <span class="detail-title">{{ result.title }}</span>
        </div>
        <section v-if="getDetailSummary(result)" class="detail-section">
          <div class="detail-label">摘要</div>
          <div class="detail-text">{{ getDetailSummary(result) }}</div>
        </section>
        <section v-if="(result.entities || []).length" class="detail-section">
          <div class="detail-label">关键实体</div>
          <div class="detail-tags">
            <span
              v-for="entity in (result.entities || []).slice(0, 8)"
              :key="entity"
              class="detail-tag"
            >
              {{ entity }}
            </span>
          </div>
        </section>
        <section v-if="(result.related || []).length" class="detail-section">
          <div class="detail-label">关联知识</div>
          <div class="detail-text">
            {{ (result.related || []).slice(0, 5).map(relatedLabel).filter(Boolean).join(' / ') }}
          </div>
        </section>
        <section v-if="result.created_at" class="detail-section">
          <div class="detail-label">收录时间</div>
          <div class="detail-text">{{ formatDate(result.created_at) }}</div>
        </section>
      </div>
    </div>

    <div v-if="!results.length" class="empty">暂无知识</div>
  </div>
</template>

<style scoped>
.rich-card {
  position: relative;
  padding: 12px 14px;
  margin: 8px 0;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--color-primary);
  font-size: 14px;
  font-weight: 600;
  flex-wrap: wrap;
}

.icon {
  font-size: 18px;
}

.title {
  flex: 1;
  min-width: 80px;
}

.sort-control {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 400;
}

.sort-label {
  white-space: nowrap;
}

.sort-select {
  padding: 3px 24px 3px 8px;
  color: var(--color-text-regular);
  font: inherit;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-out);
}

.sort-select:hover {
  border-color: var(--color-primary);
}

.sort-select:focus-visible,
.ref-item:focus-visible {
  outline: var(--focus-outline-width) solid var(--focus-outline-color);
  outline-offset: var(--focus-outline-offset);
}

.ref-item {
  position: relative;
  padding: 10px 0 10px 10px;
  border-top: 1px solid var(--color-border-light);
  border-left: 2px solid var(--color-border-light);
  cursor: pointer;
  animation: var(--animation-fadeSlideUp);
  transition:
    background var(--duration-fast) var(--ease-out),
    border-color var(--duration-fast) var(--ease-out),
    transform var(--duration-fast) var(--ease-out);
}

.ref-item:first-of-type {
  border-top-color: transparent;
}

.ref-item:hover {
  background: var(--color-bg-warm);
  border-radius: var(--radius-md);
  transform: translateX(2px);
}

.ref-item.score-high {
  border-left-color: var(--color-success);
}

.ref-item.score-med {
  border-left-color: var(--color-warning);
}

.ref-item.score-low,
.ref-item.score-neutral {
  border-left-color: var(--color-info);
}

.ref-content-wrap {
  width: 100%;
}

.ref-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-primary);
  font-size: 14px;
  font-weight: 500;
}

.title-text {
  flex: 1;
  min-width: 0;
}

.cat-icon {
  flex-shrink: 0;
  font-size: 15px;
}

.ref-content {
  margin-top: 4px;
  color: var(--color-text-regular);
  font-size: 13px;
  line-height: 1.5;
}

.ref-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 7px;
  flex-wrap: wrap;
}

.meta {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.meta.category {
  color: var(--color-info);
}

.score-badge {
  padding: 1px 7px;
  border-radius: 999px;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.score-badge.score-high {
  color: var(--color-success);
  background: var(--color-success-bg);
}

.score-badge.score-med {
  color: var(--color-warning);
  background: var(--color-warning-bg);
}

.score-badge.score-low,
.score-badge.score-neutral {
  color: var(--color-info);
  background: var(--color-info-bg);
}

.tag,
.detail-tag {
  padding: 1px 6px;
  color: var(--color-text-regular);
  font-size: 11px;
  background: var(--color-bg-hover);
  border-radius: 999px;
}

.empty {
  padding: 20px 0;
  color: var(--color-text-secondary);
  font-size: 13px;
  text-align: center;
}

.citation-mark {
  padding: 1px 2px;
  color: inherit;
  font-weight: 500;
  background: rgba(var(--color-accent-rgb), 0.34);
  border-radius: 2px;
}

.ref-content-citation {
  position: relative;
}

.detail-panel {
  position: absolute;
  top: 0;
  right: -8px;
  z-index: 100;
  width: 320px;
  max-width: min(80vw, 320px);
  max-height: 420px;
  padding: 12px 14px;
  overflow-y: auto;
  color: var(--color-text-regular);
  font-size: 13px;
  pointer-events: none;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  transform: translateX(calc(100% + 8px));
  animation: detail-fade-in var(--duration-normal) var(--ease-out);
}

@keyframes detail-fade-in {
  from {
    opacity: 0;
    transform: translateX(calc(100% + 16px));
  }
  to {
    opacity: 1;
    transform: translateX(calc(100% + 8px));
  }
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-bottom: 7px;
  margin-bottom: 8px;
  color: var(--color-primary);
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid var(--color-border-light);
}

.detail-cat-icon {
  font-size: 16px;
}

.detail-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-section + .detail-section {
  margin-top: 10px;
}

.detail-label {
  margin-bottom: 3px;
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.detail-text {
  color: var(--color-text-regular);
  font-size: 12px;
  line-height: 1.55;
  word-break: break-all;
  overflow-wrap: anywhere;
}

.detail-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

[data-theme="dark"] .ref-item:hover {
  background: var(--color-bg-hover);
}

@media (max-width: 1023px) {
  .detail-panel {
    display: none;
  }

  .ref-item:hover {
    transform: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ref-item,
  .detail-panel {
    animation: none;
    transition: none;
  }
}
</style>

<style>
.kb-ref-tooltip {
  max-width: 360px !important;
  font-size: 12px !important;
  line-height: 1.5 !important;
  overflow-wrap: anywhere;
}

.kb-ref-detail-dialog .el-message-box__message {
  white-space: normal;
  overflow-wrap: anywhere;
}

.kb-ref-detail-content {
  max-height: 60vh;
  overflow-y: auto;
  color: var(--color-text-regular);
  font-size: 13px;
  line-height: 1.6;
}

.kb-ref-detail-content .detail-section + .detail-section {
  margin-top: 10px;
}

.kb-ref-detail-content .detail-label {
  margin-bottom: 4px;
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 600;
}

.kb-ref-detail-content .detail-text {
  color: var(--color-text-regular);
  font-size: 13px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.kb-ref-detail-content .detail-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.kb-ref-detail-content .detail-tag {
  padding: 1px 6px;
  color: var(--color-text-regular);
  font-size: 11px;
  background: var(--color-bg-hover);
  border-radius: 999px;
}
</style>
