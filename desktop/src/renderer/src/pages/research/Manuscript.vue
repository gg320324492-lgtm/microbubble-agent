<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useManuscriptStore } from '../../stores/research/manuscript.store'
import { useManuscriptLoader, type ManuscriptSection } from '../../composables/manuscript-loader'
import type { Manuscript, WritingIssue } from '../../../../shared/science/manuscript-schema'
import ResearchPageHeader from '../../components/research/ResearchPageHeader.vue'
import ResearchPanel from '../../components/research/ResearchPanel.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import ResearchMetricPanel from '../../components/research/ResearchMetricPanel.vue'
import ManuscriptOutlinePanel, { type OutlineSection } from '../../components/workspace/ManuscriptOutlinePanel.vue'
import ScientificEditorPanel, { type EditorSection } from '../../components/workspace/ScientificEditorPanel.vue'
import ReviewerInsightPanel, { type ReviewerIssue } from '../../components/workspace/ReviewerInsightPanel.vue'
import CitationLocationPanel, { type CitationItem } from '../../components/workspace/CitationLocationPanel.vue'
import FigureManagerPanel, { type FigureItem } from '../../components/workspace/FigureManagerPanel.vue'

const store = useManuscriptStore()
const { fetchManuscript, fetchIssues } = useManuscriptLoader()

async function loadFromService(): Promise<void> {
  store.setLoading(true)
  store.setError('')
  try {
    const [next, nextIssues] = await Promise.all([fetchManuscript(), fetchIssues()])
    store.setManuscript(next as Manuscript)
    store.setIssues(nextIssues as WritingIssue[])
  } catch (err) {
    store.setError(err instanceof Error ? err.message : '稿件加载失败')
  } finally {
    store.setLoading(false)
  }
}

onMounted(() => {
  void loadFromService()
})

const outlineSections = computed<OutlineSection[]>(() => {
  const sections = (store.sections ?? []) as ManuscriptSection[]
  return sections.map((section: ManuscriptSection) => ({
    sectionType: section.sectionType,
    title: section.title,
    status: 'complete',
    wordCount: countWords(section.content)
  }))
})

const activeSection = computed<EditorSection | null>(() => {
  const sections = (store.sections ?? []) as ManuscriptSection[]
  if (sections.length === 0) return null
  const found = sections.find((section: ManuscriptSection) => section.sectionType === store.activeSection)
  if (found) return found
  return sections[0] ?? null
})

const activeCitations = computed<CitationItem[]>(() => {
  const sections = (store.sections ?? []) as ManuscriptSection[]
  if (sections.length === 0) return []
  const target = sections.find((section: ManuscriptSection) => section.sectionType === store.activeSection) ?? sections[0]
  return parseCitations(target?.citations ?? [])
})

const figures = computed<FigureItem[]>(() => store.manuscript?.figures ?? [])

const issues = computed<ReviewerIssue[]>(() => store.issues ?? [])

const abstractText = computed(() => store.manuscript?.abstract ?? '')

const highlights = computed(() => store.highlights ?? [])

const wordCountForActive = computed(() => {
  if (!activeSection.value) return 0
  return countWords(activeSection.value.content)
})

const totalWordCount = computed(() => store.wordCount)

const isEmptyManuscript = computed(() => {
  const m = store.manuscript
  return m !== null && (m.sections ?? []).length === 0
})

const issueBreakdown = computed(() => ({
  high: issues.value.filter((i) => i.severity === 'high').length,
  medium: issues.value.filter((i) => i.severity === 'medium').length,
  low: issues.value.filter((i) => i.severity === 'low').length
}))

const issueSummaryMetrics = computed(() => [
  { label: '严重度分布·严重', value: String(issueBreakdown.value.high), status: issueBreakdown.value.high > 0 ? 'error' : undefined },
  { label: '严重度分布·中', value: String(issueBreakdown.value.medium) },
  { label: '严重度分布·轻', value: String(issueBreakdown.value.low) }
])



function countWords(text: string): number {
  if (!text) return 0
  return text.replace(/\s+/g, '').length
}

function parseCitations(raw: string[] | string): CitationItem[] {
  const list = Array.isArray(raw) ? raw : (typeof raw === 'string' ? [raw] : [])
  if (list.length === 0) return []
  return list.map((entry, index) => {
    const id = typeof entry === 'string' ? entry.replace(/[\[\]]/g, '').trim() : `ref-${index + 1}`
    return {
      refId: id || `ref-${index + 1}`,
      authors: '作者信息待补充',
      title: '文献标题信息待补充',
      journal: '期刊',
      year: new Date().getFullYear(),
      doi: undefined
    }
  })
}

function retry(): void {
  void loadFromService()
}
</script>

<template>
  <main class="manuscript" data-research-theme="scada" aria-label="SCI 论文工作台">
    <ResearchState
      v-if="store.isLoading"
      state="loading"
      title="加载稿件中"
      description="正在从稿件服务读取内容"
    />

    <ResearchState
      v-else-if="store.errorMessage"
      state="error"
      title="稿件加载失败"
      :description="store.errorMessage"
      @retry="retry"
    />

    <ResearchState
      v-else-if="!store.manuscript"
      state="empty"
      title="暂无稿件"
      description="请先创建一个科研稿件"
    />

    <ResearchState
      v-else-if="isEmptyManuscript"
      state="empty"
      title="暂无章节"
      description="稿件尚未生成任何章节"
    />

    <template v-else>
      <ResearchPageHeader
        title="SCI 论文工作台"
        :subtitle="store.manuscript && store.manuscript.title ? store.manuscript.title : 'SCI 论文工作台'"
      />

      <section class="manuscript__meta" aria-label="稿件元信息">
        <h2 class="manuscript__meta-title">稿件元信息</h2>
        <div class="manuscript__meta-grid">
          <ResearchPanel title="标题与摘要">
            <p class="manuscript__meta-label">标题</p>
            <p class="manuscript__meta-value">{{ store.manuscript && store.manuscript.title ? store.manuscript.title : '—' }}</p>
            <p class="manuscript__meta-label">摘要</p>
            <p class="manuscript__meta-value manuscript__meta-value--abstract">
              {{ abstractText || '—' }}
            </p>
          </ResearchPanel>
          <ResearchPanel title="统计">
            <ResearchMetricPanel
              :metrics="[
                { label: '总字数', value: String(totalWordCount) },
                { label: '章节数', value: String(outlineSections.length) },
                { label: '图表数', value: String(figures.length) },
                { label: '问题数', value: String(issues.length) }
              ]"
              title="稿件统计"
            />
          </ResearchPanel>
          <ResearchPanel title="严重度分布">
            <ResearchMetricPanel :metrics="issueSummaryMetrics" title="严重度分布" />
          </ResearchPanel>
          <ResearchPanel title="高亮摘要">
            <ul v-if="highlights.length > 0" class="manuscript__highlights">
              <li v-for="(highlight, idx) in highlights" :key="idx" class="manuscript__highlight">
                {{ highlight }}
              </li>
            </ul>
            <p v-else class="manuscript__empty-inline" role="status">暂无高亮</p>
          </ResearchPanel>
        </div>
      </section>

      <section class="manuscript__grid" aria-label="三栏工作区">
        <aside class="manuscript__col manuscript__col--outline" aria-label="章节结构大纲">
          <ManuscriptOutlinePanel
            :sections="outlineSections"
            :active-section="store.activeSection"
            aria-label="章节结构大纲"
          />
        </aside>

        <section class="manuscript__col manuscript__col--editor" aria-label="论文正文编辑区">
          <ScientificEditorPanel
            :section="activeSection"
            :word-count="wordCountForActive"
            aria-label="论文正文编辑区"
          />
          <div class="manuscript__subs">
            <CitationLocationPanel
              :citations="activeCitations"
              aria-label="当前章节引用定位"
            />
            <FigureManagerPanel
              :figures="figures"
              aria-label="图表管理"
            />
          </div>
        </section>

        <aside class="manuscript__col manuscript__col--reviewer" aria-label="Reviewer 智能体">
          <ReviewerInsightPanel
            :issues="issues"
            aria-label="Reviewer 智能体审稿意见"
          />
          <p v-if="issues.length === 0" class="manuscript__empty-inline" role="status">暂无 Reviewer 意见</p>
        </aside>
      </section>
    </template>
  </main>
</template>

<style scoped>
.manuscript {
  min-width: 0;
  min-height: 100%;
  padding: var(--research-page-gutter);
  overflow-x: clip;
  background: var(--research-bg-main);
  display: grid;
  grid-template-columns: var(--research-rail-compact) var(--research-rail-standard) minmax(0, 1fr);
  gap: var(--research-grid-gap);
}
.manuscript:focus-visible {
  outline: none;
}
.manuscript__meta {
  margin-bottom: var(--research-space-6);
  min-width: 0;
}
.manuscript__meta-title {
  font-size: var(--research-text-card-title);
  font-weight: var(--research-font-weight-semibold);
  color: var(--research-text-primary);
  margin: 0 0 var(--research-space-3);
}
.manuscript__meta-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--research-grid-gap);
}
.manuscript__meta-label {
  font-size: var(--research-text-xs);
  color: var(--research-text-muted);
  margin: 0 0 var(--research-space-1);
}
.manuscript__meta-value {
  font-size: var(--research-text-body);
  color: var(--research-text-primary);
  margin: 0 0 var(--research-space-3);
}
.manuscript__meta-value--abstract {
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-reading);
  max-height: calc(var(--research-space-6) * 4);
  overflow: hidden;
  font-family: var(--research-font-serif);
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
}
.manuscript__highlights {
  list-style: disc;
  padding-left: var(--research-space-5);
  margin: 0;
}
.manuscript__highlight {
  font-size: var(--research-text-sm);
  color: var(--research-text-primary);
  margin-bottom: var(--research-space-1);
  line-height: var(--research-line-height-body);
}
.manuscript__empty-inline {
  font-size: var(--research-text-sm);
  color: var(--research-text-muted);
  margin: 0;
}
.manuscript__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, var(--research-rail-standard)) minmax(0, 1fr);
  gap: 16px;
  min-width: 0;
}
.manuscript__col {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.manuscript__col--editor {
  align-items: stretch;
}
.manuscript__subs {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}
@media (max-width: 1480px) {
  .manuscript__grid {
    grid-template-columns: minmax(220px, 1fr) minmax(0, 1.6fr) minmax(280px, 1fr);
  }
  .manuscript__meta-grid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
  .manuscript__subs {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (min-width: 1720px) {
  .manuscript__grid {
    grid-template-columns: minmax(240px, 1fr) minmax(0, 2.4fr) minmax(320px, 1.2fr);
  }
  .manuscript__meta-grid {
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr);
  }
  .manuscript__subs {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}
@media (prefers-reduced-motion: reduce) {
  .manuscript *,
  .manuscript *::before,
  .manuscript *::after {
    animation: none !important;
    transition: none !important;
  }
}
</style>