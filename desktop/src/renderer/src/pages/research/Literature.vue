<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import CitationCard from '../../components/research/CitationCard.vue'
import EvidenceCard from '../../components/research/EvidenceCard.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'
import type { DocumentItem } from '../../services/research/knowledge.service'
import { literatureService } from '../../services/research/literature.service'
import { useKnowledgeStore } from '../../stores/research/knowledge.store'

type PageState = 'loading' | 'empty' | 'error' | null
type SummaryState = 'loading' | 'error' | null

const store = useKnowledgeStore()
const pageState = ref<PageState>('loading')
const summaryStates = reactive<Record<string, SummaryState>>({})
const summaries = reactive<Record<string, string>>({})
const summaryRequestSequences = reactive<Record<string, number>>({})
const citationDocumentId = ref<string | null>(null)
const citationDialog = ref<HTMLElement | null>(null)
let citationTrigger: HTMLElement | null = null

const summaryState = computed<SummaryState>(() =>
  store.selectedDocumentId ? summaryStates[store.selectedDocumentId] ?? null : null
)
const summary = computed(() =>
  store.selectedDocumentId ? summaries[store.selectedDocumentId] ?? '' : ''
)

const selectedAssessment = computed(() =>
  store.selectedDocumentId
    ? store.assessments.find(item => item.documentId === store.selectedDocumentId)
    : undefined
)

const assessmentRows = computed(() => {
  const item = selectedAssessment.value
  if (!item) return []
  return [
    { label: '可靠性', score: item.reliabilityScore },
    { label: '证据', score: item.evidenceScore },
    { label: '方法论', score: item.methodologyScore }
  ]
})

function documentRelevance(document: DocumentItem): number {
  return document.relevance ?? document.credibility
}

const sortedDocuments = computed(() =>
  [...store.filteredDocuments].sort((left, right) => documentRelevance(right) - documentRelevance(left))
)

function assessment(documentId: string) {
  return store.assessments.find(item => item.documentId === documentId)
}

function evidenceStars(documentId: string): number {
  const item = assessment(documentId)
  if (!item) return 0
  const average = (item.reliabilityScore + item.evidenceScore + item.methodologyScore) / 3
  return Math.max(1, Math.min(5, Math.round(average * 5)))
}

async function loadPage() {
  pageState.value = 'loading'
  try {
    await Promise.all([store.loadDocuments(), store.loadAssessments()])
    pageState.value = store.totalDocuments === 0 ? 'empty' : null
  } catch {
    pageState.value = 'error'
  }
}

function selectDocument(id?: string) {
  if (!id) return
  store.selectDocument(id)
}

async function analyzePaper() {
  const documentId = store.selectedDocumentId
  if (!documentId || summaryStates[documentId] === 'loading') return
  const requestSequence = (summaryRequestSequences[documentId] ?? 0) + 1
  summaryRequestSequences[documentId] = requestSequence
  summaryStates[documentId] = 'loading'
  try {
    const result = await literatureService.summarizePaper(documentId)
    if (summaryRequestSequences[documentId] !== requestSequence) return
    summaries[documentId] = result
    summaryStates[documentId] = null
  } catch {
    if (summaryRequestSequences[documentId] !== requestSequence) return
    summaryStates[documentId] = 'error'
  }
}

function citationFocusableElements(): HTMLElement[] {
  if (!citationDialog.value) return []
  return Array.from(citationDialog.value.querySelectorAll<HTMLElement>(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  ))
}

async function openCitation(documentId?: string) {
  if (!documentId) return
  const activeElement = document.activeElement
  citationTrigger = activeElement instanceof HTMLElement && activeElement.matches('[data-testid^="citation-location-"]')
    ? activeElement
    : document.querySelector(`[data-testid="citation-location-${documentId}"]`)
  citationDocumentId.value = documentId
  await nextTick()
  const firstFocusable = citationFocusableElements()[0]
  if (firstFocusable) firstFocusable.focus()
  else citationDialog.value?.focus()
}

async function closeCitation() {
  if (!citationDocumentId.value) return
  const trigger = citationTrigger
  citationDocumentId.value = null
  await nextTick()
  trigger?.focus()
}

function onCitationKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    void closeCitation()
    return
  }
  if (event.key !== 'Tab') return
  const focusable = citationFocusableElements()
  if (!focusable.length) {
    event.preventDefault()
    citationDialog.value?.focus()
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (citationDocumentId.value && event.key === 'Escape') {
    event.preventDefault()
    void closeCitation()
  }
}

onMounted(() => {
  document.addEventListener('keydown', onDocumentKeydown)
  void loadPage()
})
onUnmounted(() => document.removeEventListener('keydown', onDocumentKeydown))
</script>

<template>
  <section class="literature" aria-labelledby="literature-title">
    <div
      class="literature__content"
      data-testid="literature-content"
      :inert="citationDocumentId ? true : undefined"
      :aria-hidden="citationDocumentId ? 'true' : undefined"
    >
    <header class="literature__header">
      <div>
        <p class="literature__eyebrow">证据工作台</p>
        <h1 id="literature-title">文献证据工作区</h1>
        <p>检索论文、核对证据质量，并在稳定详情区完成 AI 辅助阅读。</p>
      </div>
      <div class="literature__total" aria-label="文献总数">
        <ResearchIcon name="literature" :size="18" />
        <strong>{{ store.totalDocuments }}</strong>
        <span>篇文献</span>
      </div>
    </header>

    <section
      v-if="pageState === 'loading'"
      class="literature__skeleton"
      data-testid="literature-loading-skeleton"
      role="status"
      aria-busy="true"
      aria-live="polite"
    >
      <span class="literature__visually-hidden">AI 正在分析文献，请稍候。</span>
      <article v-for="index in 3" :key="index" class="literature__skeleton-paper" aria-hidden="true">
        <span class="literature__skeleton-index" />
        <div><strong /><i /><i /></div>
      </article>
    </section>

    <ResearchState
      v-else-if="pageState"
      class="literature__empty"
      data-testid="literature-page-state"
      :state="pageState"
      :description="pageState === 'empty' ? '导入或检索文献后，可在这里建立科研证据链。' : undefined"
      @retry="loadPage"
    />

    <div v-else class="literature__workspace">
      <aside class="literature__library" data-testid="literature-library" aria-label="文献文件夹与搜索">
        <div class="literature__panel-heading">
          <ResearchIcon name="folder" :size="17" />
          <h2>研究文件夹</h2>
        </div>
        <label class="literature__search">
          <ResearchIcon name="search" :size="16" />
          <span class="literature__visually-hidden">搜索文献</span>
          <input
            data-testid="literature-search"
            type="search"
            placeholder="搜索题名或标签"
            :value="store.searchQuery"
            aria-label="搜索文献"
            @input="store.setSearch(($event.target as HTMLInputElement).value)"
            @keydown.esc="store.setSearch('')"
          />
        </label>
        <nav class="literature__folders" aria-label="研究文件夹列表">
          <div v-for="folder in store.folders" :key="folder.id" class="literature__folder" :data-folder-id="folder.id">
            <ResearchIcon name="folder" :size="15" />
            <span>{{ folder.name }}</span>
            <strong>{{ folder.count }}</strong>
          </div>
        </nav>
        <div class="literature__import-hint">
          <ResearchIcon name="upload" :size="18" />
          <div><strong>导入科研资料</strong><span>支持 PDF 与 Word 文档</span></div>
        </div>
      </aside>

      <main class="literature__detail" data-testid="literature-detail" aria-label="选中文献详情">
        <template v-if="store.selectedDocument">
          <div class="literature__paper-heading">
            <div>
              <span class="literature__paper-type">科研论文</span>
              <h2>{{ store.selectedDocument.title }}</h2>
              <p>{{ store.selectedDocument.authors }} · {{ store.selectedDocument.journal }} · {{ store.selectedDocument.year }}</p>
            </div>
            <button
              class="literature__analyze"
              data-testid="summarize-paper"
              type="button"
              :disabled="summaryState === 'loading'"
              :aria-busy="summaryState === 'loading'"
              @click="analyzePaper"
            >
              <ResearchIcon name="sparkles" :size="16" />
              {{ summaryState === 'loading' ? 'AI 正在分析...' : '生成 AI 摘要' }}
            </button>
          </div>

          <div class="literature__tags" aria-label="论文标签">
            <span v-for="tag in store.selectedDocument.tags" :key="tag">{{ tag }}</span>
          </div>

          <section class="literature__evidence-overview" aria-labelledby="evidence-overview-title">
            <div class="literature__section-heading">
              <div><p>证据质量</p><h3 id="evidence-overview-title">方法与证据核验</h3></div>
              <StatusBadge
                v-if="selectedAssessment"
                status="success"
                :label="`证据等级 ${evidenceStars(store.selectedDocument.id)}/5`"
              />
            </div>
            <div v-if="assessmentRows.length" class="literature__scores" data-testid="paper-assessment">
              <div v-for="item in assessmentRows" :key="item.label" class="literature__score-item">
                <span>{{ item.label }} {{ Math.round(item.score * 100) }}%</span>
                <div
                  role="progressbar"
                  :aria-label="`${item.label}评分`"
                  aria-valuemin="0"
                  aria-valuemax="100"
                  :aria-valuenow="Math.round(item.score * 100)"
                ><i :style="{ width: `${Math.max(0, Math.min(1, item.score)) * 100}%` }" /></div>
              </div>
            </div>
            <p v-else class="literature__muted">该论文尚未生成证据质量评估。</p>
          </section>

          <section v-if="selectedAssessment" class="literature__review-grid" aria-label="证据审阅结论">
            <EvidenceCard
              label="研究限制"
              :value="selectedAssessment.limitations.length ? selectedAssessment.limitations.join('；') : '暂未发现明确限制'"
              source="论文评估结果"
              :confidence="selectedAssessment.methodologyScore"
            />
            <EvidenceCard
              label="审阅关注"
              :value="selectedAssessment.concerns.length ? selectedAssessment.concerns.join('；') : '暂无额外关注项'"
              source="论文评估结果"
              :confidence="selectedAssessment.evidenceScore"
            />
          </section>
        </template>
        <ResearchState v-else state="empty" title="选择论文查看稳定详情" description="从右侧论文列表选择一篇文献，题名、作者与评估结果会在此持续显示。" />
      </main>

      <aside class="literature__evidence" data-testid="literature-evidence" aria-label="论文证据与 AI 摘要">
        <div class="literature__panel-heading">
          <ResearchIcon name="evidence" :size="17" />
          <h2>论文证据</h2>
          <span>{{ sortedDocuments.length }}</span>
        </div>
        <p class="literature__sort-note">按相关度呈现，证据等级来自真实论文评估。</p>
        <ResearchState
          v-if="summaryState === 'error'"
          data-testid="literature-summary-state"
          state="error"
          @retry="analyzePaper"
        />
        <section v-else-if="summary" class="literature__summary" data-testid="literature-summary" aria-live="polite">
          <div class="literature__summary-heading"><ResearchIcon name="sparkles" :size="16" /><h3>AI 摘要</h3></div>
          <p>{{ summary }}</p>
        </section>
        <div
          class="literature__cards"
          data-testid="literature-document-list"
          role="list"
          aria-label="按相关度排序的论文证据列表"
        >
          <CitationCard
            v-for="(document, index) in sortedDocuments"
            :key="document.id"
            :index="index + 1"
            :document-id="document.id"
            selectable
            :active="store.selectedDocumentId === document.id"
            :authors="document.authors"
            :title="document.title"
            :journal="document.journal"
            :year="document.year"
            :tags="document.tags"
            :cited-by="document.citations"
            :relevance="documentRelevance(document)"
            :evidence-level="evidenceStars(document.id)"
            location="原文定位待提取"
            @select="selectDocument"
            @open-location="openCitation"
          />
        </div>
      </aside>
    </div>
    </div>

    <section
      v-if="citationDocumentId"
      ref="citationDialog"
      class="literature__dialog-backdrop"
      data-testid="citation-dialog"
      role="dialog"
      aria-modal="true"
      aria-label="引用位置"
      tabindex="-1"
      @click.self="closeCitation"
      @keydown="onCitationKeydown"
    >
      <div
        class="literature__dialog"
      >
        <div class="literature__dialog-heading">
          <div><p>引用定位</p><h2>原文定位待提取</h2></div>
          <button data-testid="close-citation-dialog" type="button" aria-label="关闭引用位置" @click="closeCitation">
            <ResearchIcon name="error" :size="18" />
          </button>
        </div>
        <p>当前文献接口尚未提供页码、图表或段落定位。完成证据提取后将在此据实显示。</p>
        <div class="literature__dialog-actions">
          <button data-testid="confirm-citation-dialog" type="button" @click="closeCitation">返回文献证据</button>
        </div>
      </div>
    </section>
  </section>
</template>

<style scoped>
.literature { min-width: 0; padding: var(--research-page-gutter); color: var(--research-text-primary); }
.literature__content { min-width: 0; }
.literature__header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--research-space-5); margin-bottom: var(--research-space-5); }
.literature__eyebrow,
.literature__header h1,
.literature__header p,
.literature__panel-heading h2,
.literature__paper-heading h2,
.literature__paper-heading p,
.literature__section-heading p,
.literature__section-heading h3,
.literature__summary h3,
.literature__summary p,
.literature__dialog-heading p,
.literature__dialog-heading h2 { margin: 0; }
.literature__eyebrow { color: var(--research-primary-600); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-bold); letter-spacing: .08em; text-transform: uppercase; }
.literature__header h1 { margin-top: var(--research-space-1); font-size: var(--research-text-page-title); letter-spacing: var(--research-letter-spacing-title); }
.literature__header > div > p:last-child { margin-top: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-body); }
.literature__total { display: flex; align-items: baseline; gap: var(--research-space-2); padding: var(--research-space-3) var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-card); color: var(--research-text-secondary); }
.literature__total svg { align-self: center; color: var(--research-primary-600); }
.literature__total strong { color: var(--research-text-primary); font-size: var(--research-text-section-title); font-variant-numeric: tabular-nums; }
.literature__workspace { display: grid; min-width: 0; grid-template-columns: minmax(0, 228px) minmax(0, 1fr) minmax(0, 360px); gap: var(--research-grid-gap); align-items: start; }
.literature__library,
.literature__detail,
.literature__evidence { min-width: 0; overflow: hidden; border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-panel); background: var(--research-bg-card); box-shadow: var(--research-shadow-soft); }
.literature__library,
.literature__evidence { max-height: calc(100vh - var(--research-header-height) - 160px); overflow: auto; padding: var(--research-space-4); }
.literature__detail { min-height: 570px; padding: var(--research-space-6); }
.literature__skeleton { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--research-grid-gap); padding: var(--research-space-5); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-panel); background: var(--research-bg-card); box-shadow: var(--research-shadow-soft); }
.literature__skeleton-paper { display: flex; gap: var(--research-space-3); min-width: 0; padding: var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-panel); }
.literature__skeleton-index { width: 38px; height: 28px; flex: 0 0 38px; border-radius: var(--research-radius-pill); background: var(--research-primary-100); }
.literature__skeleton-paper div { display: grid; min-width: 0; flex: 1; gap: var(--research-space-2); }
.literature__skeleton-paper strong,
.literature__skeleton-paper i { display: block; height: 10px; border-radius: var(--research-radius-pill); background: var(--research-border-subtle); }
.literature__skeleton-paper strong { width: 88%; height: 14px; background: var(--research-border-strong); }
.literature__skeleton-paper i:last-child { width: 64%; }
.literature__panel-heading { display: flex; align-items: center; gap: var(--research-space-2); margin-bottom: var(--research-space-4); }
.literature__panel-heading svg { color: var(--research-primary-600); }
.literature__panel-heading h2 { flex: 1; font-size: var(--research-text-card-title); }
.literature__panel-heading > span { color: var(--research-text-secondary); font-size: var(--research-text-xs); font-variant-numeric: tabular-nums; }
.literature__search { display: flex; align-items: center; gap: var(--research-space-2); padding-inline: var(--research-space-3); border: 1px solid var(--research-border-strong); border-radius: var(--research-radius-input); background: var(--research-bg-panel); }
.literature__search:focus-within { border-color: var(--research-primary-500); box-shadow: var(--research-shadow-focus-primary); }
.literature__search svg { color: var(--research-text-secondary); }
.literature__search input { width: 100%; min-width: 0; height: 38px; border: 0; outline: 0; background: transparent; color: var(--research-text-primary); font: inherit; font-size: var(--research-text-sm); }
.literature__folders { display: grid; gap: var(--research-space-2); margin-top: var(--research-space-4); }
.literature__folder { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: var(--research-space-2); padding: var(--research-space-2) var(--research-space-3); border-radius: var(--research-radius-input); color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.literature__folder svg { color: var(--research-primary-500); }
.literature__folder strong { color: var(--research-text-secondary); font-size: var(--research-text-xs); font-variant-numeric: tabular-nums; }
.literature__import-hint { display: flex; gap: var(--research-space-3); margin-top: var(--research-space-6); padding: var(--research-space-3); border: 1px dashed var(--research-border-strong); border-radius: var(--research-radius-card); background: var(--research-bg-panel); }
.literature__import-hint svg { color: var(--research-primary-600); }
.literature__import-hint div { display: grid; gap: var(--research-space-1); }
.literature__import-hint strong { font-size: var(--research-text-sm); }
.literature__import-hint span { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.literature__paper-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--research-space-4); }
.literature__paper-type { display: inline-flex; margin-bottom: var(--research-space-2); padding: var(--research-space-1) var(--research-space-2); border-radius: var(--research-radius-pill); background: var(--research-primary-50); color: var(--research-primary-700); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); }
.literature__paper-heading h2 { max-width: 760px; font-size: var(--research-text-section-title); line-height: var(--research-line-height-tight); }
.literature__paper-heading p { margin-top: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.literature__analyze { display: inline-flex; align-items: center; gap: var(--research-space-2); min-height: 38px; padding: var(--research-space-2) var(--research-space-4); border: 1px solid var(--research-ai-500); border-radius: var(--research-radius-button); background: var(--research-ai-500); color: var(--research-text-inverse); font: inherit; font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); cursor: pointer; white-space: nowrap; }
.literature__analyze:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-ai); }
.literature__analyze:disabled { border-color: var(--research-border-strong); background: var(--research-bg-hover); color: var(--research-text-secondary); cursor: not-allowed; }
.literature__tags { display: flex; flex-wrap: wrap; gap: var(--research-space-2); margin-top: var(--research-space-4); }
.literature__tags span { padding: var(--research-space-1) var(--research-space-2); border-radius: var(--research-radius-pill); background: var(--research-bg-hover); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.literature__evidence-overview { margin-top: var(--research-space-6); padding: var(--research-space-5); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-panel); }
.literature__section-heading { display: flex; align-items: center; justify-content: space-between; gap: var(--research-space-3); }
.literature__section-heading p { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.literature__section-heading h3 { margin-top: var(--research-space-1); font-size: var(--research-text-card-title); }
.literature__scores { display: grid; gap: var(--research-space-3); margin-top: var(--research-space-4); }
.literature__score-item { display: grid; grid-template-columns: 96px minmax(0, 1fr); align-items: center; gap: var(--research-space-3); }
.literature__score-item > span { color: var(--research-text-secondary); font-size: var(--research-text-sm); font-variant-numeric: tabular-nums; }
.literature__score-item > div { height: 7px; overflow: hidden; border-radius: var(--research-radius-pill); background: var(--research-border-subtle); }
.literature__score-item i { display: block; height: 100%; border-radius: inherit; background: var(--research-success-500); }
.literature__muted { color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.literature__review-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--research-space-4); margin-top: var(--research-space-4); }
.literature__summary { margin-bottom: var(--research-space-4); padding: var(--research-space-4); border: 1px solid var(--research-ai-100); border-radius: var(--research-radius-card); background: var(--research-ai-50); }
.literature__summary-heading { display: flex; align-items: center; gap: var(--research-space-2); color: var(--research-ai-700); }
.literature__summary h3 { font-size: var(--research-text-card-title); }
.literature__summary p { margin-top: var(--research-space-2); color: var(--research-text-primary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.literature__cards { display: grid; gap: var(--research-space-3); }
.literature__sort-note { margin: calc(var(--research-space-2) * -1) 0 var(--research-space-4); color: var(--research-text-secondary); font-size: var(--research-text-xs); line-height: var(--research-line-height-body); }
.literature__dialog-backdrop { position: fixed; z-index: var(--research-z-modal); inset: 0; display: grid; place-items: center; padding: var(--research-space-6); background: var(--research-overlay); }
.literature__dialog { width: min(460px, 100%); padding: var(--research-space-6); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-panel); outline: 0; background: var(--research-bg-elevated); box-shadow: var(--research-shadow-floating); }
.literature__dialog:focus-visible { box-shadow: var(--research-shadow-floating), var(--research-shadow-focus-primary); }
.literature__dialog-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--research-space-4); }
.literature__dialog-heading p { color: var(--research-primary-600); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-bold); }
.literature__dialog-heading h2 { margin-top: var(--research-space-1); font-size: var(--research-text-section-title); }
.literature__dialog-heading button { display: grid; width: 34px; height: 34px; place-items: center; border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-button); background: var(--research-bg-card); color: var(--research-text-secondary); cursor: pointer; }
.literature__dialog-heading button:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.literature__dialog > p { margin: var(--research-space-4) 0 0; color: var(--research-text-secondary); font-size: var(--research-text-body); line-height: var(--research-line-height-body); }
.literature__dialog-actions { display: flex; justify-content: flex-end; margin-top: var(--research-space-5); }
.literature__dialog-actions button { min-height: 38px; padding: var(--research-space-2) var(--research-space-4); border: 1px solid var(--research-primary-500); border-radius: var(--research-radius-button); background: var(--research-primary-500); color: var(--research-text-inverse); font: inherit; font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); cursor: pointer; }
.literature__dialog-actions button:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.literature__visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); clip-path: inset(50%); white-space: nowrap; }

@media (max-width: 1480px) {
  .literature__workspace { grid-template-columns: minmax(0, 208px) minmax(0, 1fr) minmax(0, 320px); gap: var(--research-space-3); }
  .literature__detail { padding: var(--research-space-5); }
  .literature__review-grid { grid-template-columns: minmax(0, 1fr); }
}

@media (min-width: 1720px) {
  .literature__workspace { grid-template-columns: minmax(0, 248px) minmax(0, 1fr) minmax(0, 390px); }
}

@media (prefers-reduced-motion: reduce) {
  .literature *, .literature *::before, .literature *::after { scroll-behavior: auto !important; }
}
</style>
