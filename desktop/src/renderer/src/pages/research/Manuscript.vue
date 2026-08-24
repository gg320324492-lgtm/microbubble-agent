<script lang="ts">
import type { Manuscript as SnapshotManuscript, WritingIssue as SnapshotWritingIssue } from '../../services/research/manuscript.service'

interface ManuscriptSnapshot {
  manuscript: SnapshotManuscript | null
  issues: SnapshotWritingIssue[]
}

const manuscriptSnapshotCache = new WeakMap<object, ManuscriptSnapshot>()
const manuscriptLoadQueue = new WeakMap<object, Promise<void>>()

function cloneSnapshot(manuscript: SnapshotManuscript | null, issues: SnapshotWritingIssue[]): ManuscriptSnapshot {
  return {
    manuscript: manuscript ? {
      ...manuscript,
      sections: manuscript.sections.map(section => ({ ...section, citations: [...section.citations] })),
      figures: manuscript.figures.map(figure => ({ ...figure })),
      highlights: [...manuscript.highlights]
    } : null,
    issues: issues.map(issue => ({ ...issue }))
  }
}
</script>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'
import { manuscriptService, type WritingIssue } from '../../services/research/manuscript.service'
import { useManuscriptStore } from '../../stores/research/manuscript.store'

const store = useManuscriptStore()
const snapshot = ref<ManuscriptSnapshot | null>(manuscriptSnapshotCache.get(store) ?? null)
const loadState = ref<'loading' | 'ready' | 'error'>(snapshot.value ? 'ready' : 'loading')
const refreshError = ref(false)
const isLoadingManuscript = ref(false)
const generatingKey = ref<string | null>(null)
const generatedPreviews = ref<Record<string, string>>({})
const generationErrors = ref<Record<string, boolean>>({})
let alive = true
let loadRequestSequence = 0
let generationRequestSequence = 0

const manuscript = computed(() => snapshot.value?.manuscript ?? null)
const sections = computed(() => manuscript.value?.sections ?? [])
const issues = computed(() => snapshot.value?.issues ?? [])
const highlights = computed(() => manuscript.value?.highlights ?? [])
const wordCount = computed(() => manuscript.value?.wordCount ?? 0)
const activeSection = computed(() => sections.value.find(section => section.sectionType === store.activeSection) ?? sections.value[0])
const activeGenerationKey = computed(() => manuscript.value && activeSection.value ? `${manuscript.value.manuscriptId}:${activeSection.value.sectionType}` : '')
const hasGeneratedPreview = computed(() => Object.prototype.hasOwnProperty.call(generatedPreviews.value, activeGenerationKey.value))
const activeGeneratedPreview = computed(() => generatedPreviews.value[activeGenerationKey.value] ?? '')
const citedSectionCount = computed(() => sections.value.filter(section => section.citations.length > 0).length)
const LANGUAGE_TYPES = new Set(['language', 'grammar', 'style', 'terminology'])
const LOGIC_TYPES = new Set(['logic', 'coherence', 'structure', 'repetition', 'missing_evidence'])
const CITATION_TYPES = new Set(['citation', 'weak_citation', 'missing_citation'])
const countIssues = (types: Set<string>) => issues.value.filter(issue => types.has(issue.type)).length

const reviewDimensions = computed(() => [
  { label: '语言', icon: 'manuscript' as const, conclusion: `${countIssues(LANGUAGE_TYPES)} 个问题`, suggestion: '检查句式与术语，逐项处理语言问题。' },
  { label: '逻辑', icon: 'progress' as const, conclusion: `${countIssues(LOGIC_TYPES)} 个问题`, suggestion: '检查论证衔接、重复内容与证据链。' },
  { label: '创新', icon: 'sparkles' as const, conclusion: '待进一步评估', suggestion: '当前接口没有创新性审阅结果，建议结合领域基线人工评估。' },
  { label: '引用', icon: 'citation' as const, conclusion: `${citedSectionCount.value} / ${sections.value.length} 个章节有引用`, suggestion: `${countIssues(CITATION_TYPES)} 个引用问题，优先补齐证据来源。` }
])

function severityLabel(issue: WritingIssue): string {
  if (issue.severity === 'high') return '高风险'
  if (issue.severity === 'medium') return '需关注'
  return '建议优化'
}
function severityStatus(issue: WritingIssue): 'error' | 'warning' | 'info' {
  if (issue.severity === 'high') return 'error'
  if (issue.severity === 'medium') return 'warning'
  return 'info'
}
async function loadManuscript(): Promise<void> {
  if (isLoadingManuscript.value) return
  const requestSequence = ++loadRequestSequence
  isLoadingManuscript.value = true
  const hasRetainedContent = Boolean(snapshot.value?.manuscript)
  if (!hasRetainedContent) loadState.value = 'loading'
  try {
    const previous = manuscriptLoadQueue.get(store) ?? Promise.resolve()
    const queued = previous.catch(() => undefined).then(() => store.loadManuscript())
    manuscriptLoadQueue.set(store, queued)
    await queued
    if (!alive || requestSequence !== loadRequestSequence) return
    const nextSnapshot = cloneSnapshot(store.manuscript, store.issues)
    manuscriptSnapshotCache.set(store, nextSnapshot)
    snapshot.value = nextSnapshot
    const nextSections = nextSnapshot.manuscript?.sections ?? []
    if (nextSections.length && !nextSections.some(section => section.sectionType === store.activeSection)) {
      store.setActiveSection(nextSections[0].sectionType)
    }
    loadState.value = 'ready'
    refreshError.value = false
  } catch {
    if (!alive || requestSequence !== loadRequestSequence) return
    if (snapshot.value?.manuscript) {
      loadState.value = 'ready'
      refreshError.value = true
    } else {
      loadState.value = 'error'
    }
  } finally {
    if (alive && requestSequence === loadRequestSequence) isLoadingManuscript.value = false
  }
}
async function generateContent(sectionType: string): Promise<void> {
  const currentManuscript = manuscript.value
  if (!currentManuscript || generatingKey.value) return
  const key = `${currentManuscript.manuscriptId}:${sectionType}`
  const requestSequence = ++generationRequestSequence
  generatingKey.value = key
  generationErrors.value = { ...generationErrors.value, [key]: false }
  try {
    const content = await manuscriptService.generateSection(sectionType, currentManuscript.title)
    if (!alive || requestSequence !== generationRequestSequence) return
    generatedPreviews.value = { ...generatedPreviews.value, [key]: content }
  } catch {
    if (alive && requestSequence === generationRequestSequence) {
      generationErrors.value = { ...generationErrors.value, [key]: true }
    }
  } finally {
    if (alive && requestSequence === generationRequestSequence) generatingKey.value = null
  }
}
onMounted(loadManuscript)
onUnmounted(() => {
  alive = false
  loadRequestSequence += 1
  generationRequestSequence += 1
})
</script>

<template>
  <div class="manuscript">
    <ResearchState v-if="loadState === 'loading'" data-testid="manuscript-state" state="loading" />
    <ResearchState v-else-if="loadState === 'error'" data-testid="manuscript-state" state="error" title="论文加载失败，请重试" description="未能读取论文与审阅问题，请重新加载。" @retry="loadManuscript" />
    <ResearchState v-else-if="!manuscript || sections.length === 0" data-testid="manuscript-state" state="empty" title="暂无论文章节" description="创建论文结构后，这里会显示连续正文与 SCI 审阅。" />

    <template v-else>
      <div v-if="refreshError" class="manuscript__retained-error" data-testid="manuscript-retained-error" role="alert">
        <span>论文刷新失败，请重试。已保留当前正文与审阅结果。</span>
        <button type="button" :disabled="isLoadingManuscript" @click="loadManuscript">{{ isLoadingManuscript ? '正在重新加载...' : '重新加载' }}</button>
      </div>
      <aside class="manuscript__outline" data-testid="manuscript-outline" aria-label="论文结构树">
        <div class="manuscript__eyebrow"><ResearchIcon name="manuscript" :size="16" />论文结构</div>
        <nav class="manuscript__sections" aria-label="论文章节">
          <button v-for="section in sections" :key="section.sectionType" class="manuscript__section" :class="{ 'manuscript__section--active': store.activeSection === section.sectionType }" type="button" :data-section-type="section.sectionType" :aria-current="store.activeSection === section.sectionType ? 'true' : undefined" @click="store.setActiveSection(section.sectionType)">
            <ResearchIcon :name="section.content ? 'check' : 'idle'" :size="15" :label="section.content ? '已有正文' : '暂无正文'" />
            <span>{{ section.title }}</span><span class="manuscript__section-citation">{{ section.citations.length }} 引用</span>
          </button>
        </nav>
        <dl class="manuscript__outline-stats">
          <div><dt>全文字数</dt><dd>{{ wordCount.toLocaleString() }} 字</dd></div>
          <div><dt>审阅问题</dt><dd>{{ issues.length }} 个</dd></div>
        </dl>
        <section class="manuscript__highlights" data-testid="manuscript-highlights" aria-labelledby="highlight-title">
          <h2 id="highlight-title">高亮总结</h2><p v-if="highlights.length === 0">暂无高亮结论</p>
          <ul v-else><li v-for="highlight in highlights" :key="highlight">{{ highlight }}</li></ul>
        </section>
      </aside>

      <section class="manuscript__editor" data-testid="manuscript-editor" aria-label="活动章节正文">
        <header class="manuscript__editor-header">
          <div><p class="manuscript__kicker">连续论文草稿</p><h1>{{ manuscript.title }}</h1></div>
          <div class="manuscript__editor-actions">
            <span class="manuscript__wordcount">{{ wordCount.toLocaleString() }} 字</span>
            <button data-testid="refresh-manuscript" type="button" :disabled="isLoadingManuscript" @click="loadManuscript">{{ isLoadingManuscript ? '正在刷新...' : '刷新论文' }}</button>
          </div>
        </header>
        <article v-if="activeSection" class="manuscript__article" data-testid="active-section-content">
          <header class="manuscript__article-header">
            <div><p>当前章节</p><h2>{{ activeSection.title }}</h2></div>
            <button class="manuscript__generate" data-testid="generate-section" type="button" :disabled="Boolean(generatingKey)" :aria-busy="generatingKey === activeGenerationKey ? 'true' : 'false'" @click="generateContent(activeSection.sectionType)">
              <ResearchIcon :name="generatingKey === activeGenerationKey ? 'running' : 'sparkles'" :size="16" />{{ generatingKey === activeGenerationKey ? '正在生成...' : 'AI 生成预览' }}
            </button>
          </header>
          <p class="manuscript__body">{{ activeSection.content || '本章节暂无正文。' }}</p>
          <section v-if="activeSection.citations.length" class="manuscript__citations" data-testid="active-citations" aria-label="当前章节引用">
            <ResearchIcon name="citation" :size="16" /><strong>引用</strong><span v-for="citation in activeSection.citations" :key="citation">{{ citation }}</span>
          </section>
          <p v-else class="manuscript__citation-empty">当前章节暂无引用，请在定稿前核对证据来源。</p>
          <section v-if="generationErrors[activeGenerationKey]" class="manuscript__generation-error" data-testid="manuscript-generate-error" role="alert">
            <span>生成失败，请重试。原正文未被修改。</span><button type="button" :disabled="Boolean(generatingKey)" @click="generateContent(activeSection.sectionType)">重新生成</button>
          </section>
          <section v-if="hasGeneratedPreview" class="manuscript__generated-preview" data-testid="generated-preview" aria-label="AI 生成预览">
            <div><ResearchIcon name="sparkles" :size="16" /> AI 生成预览</div><p>{{ activeGeneratedPreview || '本次未生成可用正文' }}</p><small>仅供审阅，当前接口未提供保存动作，未写入原正文。</small>
          </section>
        </article>
      </section>

      <aside class="manuscript__review" data-testid="manuscript-review" aria-label="SCI 审阅">
        <header><div class="manuscript__eyebrow"><ResearchIcon name="evidence" :size="16" />SCI 审阅</div><p>所有结论均来自当前论文与问题数据，不使用虚构评分。</p></header>
        <section class="manuscript__dimensions" aria-label="四维审阅结论">
          <article v-for="dimension in reviewDimensions" :key="dimension.label" class="manuscript__dimension" :data-review-dimension="dimension.label">
            <div class="manuscript__dimension-heading"><ResearchIcon :name="dimension.icon" :size="17" /><h2>{{ dimension.label }}</h2></div><strong>{{ dimension.conclusion }}</strong><p>{{ dimension.suggestion }}</p>
          </article>
        </section>
        <section class="manuscript__issues" aria-labelledby="issues-title">
          <div class="manuscript__issues-heading"><h2 id="issues-title">待改进建议</h2><span>{{ issues.length }}</span></div>
          <p v-if="issues.length === 0" class="manuscript__issue-empty">当前未返回写作问题。</p>
          <article v-for="(issue, index) in issues" v-else :key="`${issue.location}-${index}`" class="manuscript__issue" :data-issue-index="index">
            <div><StatusBadge :status="severityStatus(issue)" :label="severityLabel(issue)" /><span class="manuscript__issue-location">{{ issue.location }}</span></div><strong>{{ issue.description }}</strong><p>{{ issue.suggestion }}</p>
          </article>
        </section>
      </aside>
    </template>
  </div>
</template>

<style scoped>
.manuscript{display:grid;grid-template-columns:minmax(0,var(--research-rail-compact)) minmax(0,1fr) minmax(0,var(--research-rail-standard));min-width:0;min-height:100%;background:var(--research-bg-main);color:var(--research-text-primary)}
.manuscript>.research-state{grid-column:1/-1;margin:var(--research-space-6)}.manuscript__outline,.manuscript__review,.manuscript__editor{min-width:0}.manuscript__outline,.manuscript__review{overflow:auto;padding:var(--research-space-5);background:var(--research-bg-panel)}.manuscript__outline{border-inline-end:1px solid var(--research-border-subtle)}.manuscript__review{border-inline-start:1px solid var(--research-border-subtle)}
.manuscript__eyebrow,.manuscript__kicker{display:flex;align-items:center;gap:var(--research-space-2);margin:0;color:var(--research-primary-700);font-size:var(--research-text-sm);font-weight:var(--research-font-weight-semibold)}.manuscript__sections{display:grid;gap:var(--research-space-1);margin-block:var(--research-space-4)}
.manuscript__section{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:var(--research-space-2);width:100%;padding:10px;border:1px solid transparent;border-radius:var(--research-radius-button);background:transparent;color:var(--research-text-secondary);font:inherit;text-align:start;cursor:pointer}.manuscript__section span:nth-child(2){overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.manuscript__section:hover{background:var(--research-bg-hover);color:var(--research-text-primary)}.manuscript__section--active{border-color:var(--research-primary-200);background:var(--research-primary-50);color:var(--research-primary-700);font-weight:var(--research-font-weight-semibold)}
.manuscript__section:focus-visible,.manuscript__generate:focus-visible,.manuscript__generation-error button:focus-visible{outline:none;box-shadow:var(--research-shadow-focus-primary)}.manuscript__section-citation{font-size:var(--research-text-xs);font-weight:var(--research-font-weight-regular)}.manuscript__outline-stats{display:grid;grid-template-columns:1fr 1fr;gap:var(--research-space-2);margin:0}.manuscript__outline-stats div{padding:var(--research-space-3);border:1px solid var(--research-border-subtle);border-radius:var(--research-radius-button);background:var(--research-bg-card)}.manuscript__outline-stats dt{color:var(--research-text-secondary);font-size:var(--research-text-xs)}.manuscript__outline-stats dd{margin:var(--research-space-1) 0 0;font-variant-numeric:tabular-nums;font-weight:var(--research-font-weight-semibold)}
.manuscript__highlights{margin-block-start:var(--research-space-5)}.manuscript__highlights h2,.manuscript__issues h2{margin:0;font-size:var(--research-text-card-title)}.manuscript__highlights ul{display:grid;gap:var(--research-space-2);margin:var(--research-space-3) 0 0;padding-inline-start:18px}.manuscript__highlights li,.manuscript__highlights p{color:var(--research-text-secondary);font-size:var(--research-text-sm);line-height:var(--research-line-height-body)}
.manuscript__editor{overflow:auto;padding:var(--research-space-7) clamp(24px,3vw,48px);background:var(--research-bg-card)}.manuscript__editor-header{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--research-space-4);padding-block-end:var(--research-space-5);border-block-end:1px solid var(--research-divider)}.manuscript__editor-header h1{max-width:700px;margin:var(--research-space-2) 0 0;font-size:var(--research-text-page-title);letter-spacing:var(--research-letter-spacing-title)}.manuscript__editor-actions{display:flex;align-items:center;gap:var(--research-space-2)}.manuscript__editor-actions button{padding:var(--research-space-2) var(--research-space-3);border:1px solid var(--research-border-strong);border-radius:var(--research-radius-button);background:var(--research-bg-card);color:var(--research-text-primary);font:inherit;font-weight:var(--research-font-weight-semibold);cursor:pointer}.manuscript__editor-actions button:disabled{opacity:1;cursor:not-allowed;border-color:var(--research-border-strong);background:var(--research-bg-hover);color:var(--research-text-secondary)}.manuscript__wordcount{flex:0 0 auto;color:var(--research-text-secondary);font-size:var(--research-text-sm);font-variant-numeric:tabular-nums}.manuscript__article{max-width:820px;margin:var(--research-space-7) auto}.manuscript__article-header{display:flex;align-items:center;justify-content:space-between;gap:var(--research-space-4)}.manuscript__article-header p{margin:0 0 var(--research-space-1);color:var(--research-text-secondary);font-size:var(--research-text-xs)}.manuscript__article-header h2{margin:0;font-size:var(--research-text-section-title)}
.manuscript__generate,.manuscript__generation-error button{display:inline-flex;align-items:center;gap:var(--research-space-2);padding:var(--research-space-2) var(--research-space-3);border:1px solid var(--research-ai-200);border-radius:var(--research-radius-button);background:var(--research-ai-50);color:var(--research-ai-700);font:inherit;font-weight:var(--research-font-weight-semibold);cursor:pointer}.manuscript__generate:disabled,.manuscript__generation-error button:disabled{cursor:not-allowed;opacity:1;border-color:var(--research-border-strong);background:var(--research-bg-hover);color:var(--research-text-secondary);box-shadow:none}.manuscript__body{min-height:240px;margin:var(--research-space-6) 0;color:var(--research-text-primary);font-family:var(--research-font-serif);font-size:16px;line-height:var(--research-line-height-reading);white-space:pre-line}
.manuscript__citations{display:flex;flex-wrap:wrap;align-items:center;gap:var(--research-space-2);padding:var(--research-space-3);border:1px solid var(--research-primary-100);border-radius:var(--research-radius-button);background:var(--research-primary-50);color:var(--research-primary-700);font-size:var(--research-text-sm)}.manuscript__citation-empty{padding:var(--research-space-3);border:1px dashed var(--research-warning-500);border-radius:var(--research-radius-button);color:var(--research-text-secondary);font-size:var(--research-text-sm)}.manuscript__generation-error{display:flex;align-items:center;justify-content:space-between;gap:var(--research-space-3);margin-block-start:var(--research-space-4);padding:var(--research-space-3);border:1px solid var(--research-danger-100);border-radius:var(--research-radius-button);background:var(--research-danger-50);color:var(--research-danger-600);font-size:var(--research-text-sm)}.manuscript__generated-preview{margin-block-start:var(--research-space-4);padding:var(--research-space-4);border:1px solid var(--research-ai-200);border-radius:var(--research-radius-card);background:var(--research-ai-50)}.manuscript__generated-preview>div{display:flex;align-items:center;gap:var(--research-space-2);color:var(--research-ai-700);font-weight:var(--research-font-weight-semibold)}.manuscript__generated-preview p{line-height:var(--research-line-height-body)}.manuscript__generated-preview small{color:var(--research-text-secondary)}
.manuscript__retained-error{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;gap:var(--research-space-3);padding:var(--research-space-3) var(--research-space-5);border-block-end:1px solid var(--research-danger-100);background:var(--research-danger-50);color:var(--research-danger-600);font-size:var(--research-text-sm)}.manuscript__retained-error button{padding:var(--research-space-2) var(--research-space-3);border:1px solid var(--research-danger-500);border-radius:var(--research-radius-button);background:var(--research-bg-card);color:var(--research-danger-600);font:inherit;font-weight:var(--research-font-weight-semibold);cursor:pointer}.manuscript__retained-error button:disabled{opacity:1;cursor:not-allowed;background:var(--research-bg-hover);border-color:var(--research-border-strong);color:var(--research-text-secondary);box-shadow:none}
.manuscript__review>header p{margin:var(--research-space-2) 0 var(--research-space-4);color:var(--research-text-secondary);font-size:var(--research-text-sm);line-height:var(--research-line-height-body)}.manuscript__dimensions{display:grid;gap:var(--research-space-2)}.manuscript__dimension{padding:var(--research-space-3);border:1px solid var(--research-border-subtle);border-radius:var(--research-radius-card);background:var(--research-bg-card);box-shadow:var(--research-shadow-soft)}.manuscript__dimension-heading{display:flex;align-items:center;gap:var(--research-space-2);color:var(--research-ai-700)}.manuscript__dimension h2{margin:0;font-size:var(--research-text-card-title)}.manuscript__dimension strong{display:block;margin-block-start:var(--research-space-2);font-size:var(--research-text-sm)}.manuscript__dimension p{margin:var(--research-space-1) 0 0;color:var(--research-text-secondary);font-size:var(--research-text-xs);line-height:var(--research-line-height-body)}
.manuscript__issues{margin-block-start:var(--research-space-5)}.manuscript__issues-heading{display:flex;align-items:center;justify-content:space-between;margin-block-end:var(--research-space-3)}.manuscript__issues-heading span{display:grid;min-width:24px;height:24px;place-items:center;border-radius:var(--research-radius-pill);background:var(--research-warning-50);color:var(--research-text-primary);font-size:var(--research-text-xs)}.manuscript__issue{margin-block-end:var(--research-space-2);padding:var(--research-space-3);border:1px solid var(--research-border-subtle);border-radius:var(--research-radius-button);background:var(--research-bg-card)}.manuscript__issue>div{display:flex;align-items:center;gap:var(--research-space-2)}.manuscript__issue-location{color:var(--research-text-secondary);font-size:var(--research-text-xs)}.manuscript__issue strong{display:block;margin-block-start:var(--research-space-2);font-size:var(--research-text-sm)}.manuscript__issue p,.manuscript__issue-empty{margin:var(--research-space-1) 0 0;color:var(--research-text-secondary);font-size:var(--research-text-xs);line-height:var(--research-line-height-body)}
@media(max-width:1480px){.manuscript{grid-template-columns:minmax(0,var(--research-rail-compact)) minmax(0,1fr) minmax(0,var(--research-rail-standard))}.manuscript__outline,.manuscript__review{padding:var(--research-space-4)}.manuscript__editor{padding-inline:var(--research-space-6)}}
@media(min-width:1720px){.manuscript{grid-template-columns:minmax(0,var(--research-rail-standard)) minmax(0,1fr) minmax(0,var(--research-rail-wide))}}
</style>
