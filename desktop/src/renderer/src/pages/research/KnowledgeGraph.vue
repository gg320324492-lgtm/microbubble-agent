<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch, type ComponentPublicInstance } from 'vue'
import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'
import { useKnowledgeStore } from '../../stores/research/knowledge.store'

const store = useKnowledgeStore()
const loadState = ref<'loading' | 'ready' | 'error'>(store.documents.length ? 'ready' : 'loading')
const refreshError = ref(false)
const loading = ref(false)
const currentPage = ref(0)
const focusedNodeIndex = ref(0)
const graphNodeElements = new Map<string, SVGGElement>()
const PAGE_SIZE = 24
const GRAPH_COLUMNS = 3
const GRAPH_HEIGHT = 600
type EntityType = 'paper' | 'experiment' | 'dataset' | 'report' | 'other'

const typeLabels: Record<EntityType, string> = {
  paper: '论文', experiment: '实验', dataset: '数据集', report: '报告', other: '其他'
}
const typeStatuses: Record<EntityType, 'info' | 'warning' | 'success' | 'neutral'> = {
  paper: 'info', experiment: 'warning', dataset: 'success', report: 'neutral', other: 'neutral'
}
const typeIcons = {
  paper: 'document', experiment: 'experiment', dataset: 'data', report: 'evidence', other: 'document'
} as const
function normalizeEntityType(type: unknown): EntityType {
  if (type === 'paper' || type === 'experiment' || type === 'dataset' || type === 'report') return type
  return 'other'
}
const totalPages = computed(() => Math.max(1, Math.ceil(store.documents.length / PAGE_SIZE)))
const pageStart = computed(() => currentPage.value * PAGE_SIZE)
const visibleDocuments = computed(() => store.documents.slice(pageStart.value, pageStart.value + PAGE_SIZE))
const pageRange = computed(() => {
  if (!store.documents.length) return '当前显示 0–0，共 0'
  return `当前显示 ${pageStart.value + 1}–${pageStart.value + visibleDocuments.value.length}，共 ${store.documents.length}`
})
const nodePositions = computed(() => {
  return visibleDocuments.value.map((document, index) => {
    const column = index % GRAPH_COLUMNS
    const row = Math.floor(index / GRAPH_COLUMNS)
    return { document, entityType: normalizeEntityType(document.type), x: 105 + column * 195, y: 48 + row * 72 }
  })
})

function selectDocument(id: string): void {
  store.selectDocument(id)
}
function registerGraphNode(id: string, element: Element | ComponentPublicInstance | null): void {
  if (element instanceof Element && element.tagName.toLowerCase() === 'g') {
    graphNodeElements.set(id, element as SVGGElement)
  } else {
    graphNodeElements.delete(id)
  }
}
function focusNode(index: number): void {
  const bounded = Math.max(0, Math.min(index, nodePositions.value.length - 1))
  const targetId = nodePositions.value[bounded]?.document.id
  focusedNodeIndex.value = bounded
  if (targetId) void nextTick(() => graphNodeElements.get(targetId)?.focus())
}
function onNodeKeydown(event: KeyboardEvent, id: string, index: number): void {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    selectDocument(id)
    return
  }
  let target = index
  if (event.key === 'ArrowRight') target = index + 1
  else if (event.key === 'ArrowLeft') target = index - 1
  else if (event.key === 'ArrowDown') target = index + GRAPH_COLUMNS
  else if (event.key === 'ArrowUp') target = index - GRAPH_COLUMNS
  else if (event.key === 'Home') target = 0
  else if (event.key === 'End') target = nodePositions.value.length - 1
  else return
  event.preventDefault()
  focusNode(target)
}
function changePage(delta: number): void {
  const nextPage = Math.max(0, Math.min(currentPage.value + delta, totalPages.value - 1))
  if (nextPage === currentPage.value) return
  currentPage.value = nextPage
  focusedNodeIndex.value = 0
}
async function loadGraph(): Promise<void> {
  if (loading.value) return
  loading.value = true
  const hasRetainedEntities = store.documents.length > 0
  if (!hasRetainedEntities) loadState.value = 'loading'
  try {
    await store.loadDocuments()
    currentPage.value = Math.min(currentPage.value, totalPages.value - 1)
    focusedNodeIndex.value = 0
    loadState.value = 'ready'
    refreshError.value = false
  } catch {
    if (store.documents.length) {
      loadState.value = 'ready'
      refreshError.value = true
    } else {
      loadState.value = 'error'
    }
  } finally {
    loading.value = false
  }
}
watch(() => store.documents.length, () => {
  currentPage.value = Math.min(currentPage.value, totalPages.value - 1)
  focusedNodeIndex.value = 0
})
onMounted(loadGraph)
</script>

<template>
  <section class="kg" aria-label="知识图谱">
    <header class="kg__header">
      <div>
        <p class="kg__eyebrow"><ResearchIcon name="graph" :size="17" />证据网络</p>
        <h1>知识图谱</h1>
        <p>基于当前知识库文献实体浏览；关系数据未提供时不推断连接。</p>
      </div>
      <div class="kg__summary" aria-label="知识库概况">
        <span>{{ store.totalDocuments }} 个真实实体</span><span>{{ store.folders.length }} 个知识分组</span>
      </div>
    </header>

    <ResearchState v-if="loadState === 'loading'" data-testid="knowledge-graph-state" state="loading" />
    <ResearchState v-else-if="loadState === 'error'" data-testid="knowledge-graph-state" state="error" title="知识图谱加载失败，请重试" description="未能读取知识库实体，页面没有保留虚构节点。" @retry="loadGraph" />
    <ResearchState v-else-if="store.documents.length === 0" data-testid="knowledge-graph-state" state="empty" title="暂无科研数据" description="导入文献后，可在这里浏览真实知识实体。" />

    <div v-else class="kg__workspace">
      <div v-if="refreshError" class="kg__retained-error" data-testid="knowledge-graph-retained-error" role="alert">
        <span>知识图谱刷新失败，请重试。已保留当前实体。</span><button type="button" :disabled="loading" @click="loadGraph">{{ loading ? '正在重新加载...' : '重新加载' }}</button>
      </div>
      <section class="kg__canvas" aria-labelledby="graph-canvas-title">
        <div class="kg__section-heading">
          <div><p>可交互画布</p><h2 id="graph-canvas-title">文献实体分布</h2></div>
          <span>回车键或空格键选择节点</span>
        </div>
        <div class="kg__pagination" aria-label="实体分页"><span data-testid="graph-page-range">{{ pageRange }}</span><div><button type="button" data-action="graph-previous-page" :disabled="currentPage === 0" @click="changePage(-1)">上一页</button><button type="button" data-action="graph-next-page" :disabled="currentPage >= totalPages - 1" @click="changePage(1)">下一页</button></div></div>
        <div class="kg__svg-scroll">
          <svg data-testid="knowledge-graph-svg" class="kg__svg" :viewBox="`0 0 600 ${GRAPH_HEIGHT}`" :data-canvas-height="GRAPH_HEIGHT" role="group" aria-labelledby="kg-title" aria-describedby="kg-description">
            <title id="kg-title">科研知识实体图</title>
            <desc id="kg-description">当前仅展示真实文献实体，暂无关系数据，因此不绘制实体连线。</desc>
            <g v-for="(node, index) in nodePositions" :key="node.document.id" :ref="element => registerGraphNode(node.document.id, element)" class="kg__node" :class="[`kg__node--${node.entityType}`, { 'kg__node--selected': store.selectedDocumentId === node.document.id }]" :transform="`translate(${node.x}, ${node.y})`" role="button" :tabindex="focusedNodeIndex === index ? 0 : -1" :aria-label="`选择文献实体：${node.document.title}`" :aria-pressed="store.selectedDocumentId === node.document.id ? 'true' : 'false'" :data-graph-entity="node.document.id" :data-entity-id="node.document.id" :data-entity-type="node.entityType" @click="focusedNodeIndex = index; selectDocument(node.document.id)" @keydown="onNodeKeydown($event, node.document.id, index)">
              <rect x="-92" y="-29" width="184" height="58" rx="12" />
              <ResearchIcon :name="typeIcons[node.entityType]" x="-79" y="-12" :size="20" />
              <text x="-50" y="-5">{{ node.document.title.length > 14 ? `${node.document.title.slice(0, 14)}…` : node.document.title }}</text>
              <text class="kg__node-meta" x="-50" y="16">{{ typeLabels[node.entityType] }} · {{ node.document.year }}</text>
              <text v-if="store.selectedDocumentId === node.document.id" class="kg__node-selected" x="31" y="-18">✓ 已选中</text>
            </g>
          </svg>
        </div>
      </section>

      <aside class="kg__inspector" aria-label="实体与关系检查器">
        <section class="kg__panel" data-testid="selected-entity">
          <div class="kg__section-heading"><div><p>实体检查器</p><h2>选中文献</h2></div></div>
          <div v-if="store.selectedDocument" class="kg__entity-detail">
            <ResearchIcon name="document" :size="24" />
            <h3>{{ store.selectedDocument.title }}</h3>
            <dl>
              <div><dt>作者</dt><dd>{{ store.selectedDocument.authors }}</dd></div>
              <div><dt>来源</dt><dd>{{ store.selectedDocument.journal }}</dd></div>
              <div><dt>年份</dt><dd>{{ store.selectedDocument.year }}</dd></div>
              <div><dt>引用</dt><dd>{{ store.selectedDocument.citations }}</dd></div>
            </dl>
            <div class="kg__tags"><span v-for="tag in store.selectedDocument.tags" :key="tag">{{ tag }}</span></div>
          </div>
          <p v-else class="kg__selection-empty">选择画布节点，查看真实文献字段。</p>
        </section>

        <section class="kg__panel" aria-labelledby="entity-list-title">
          <div class="kg__section-heading"><div><p>知识库来源</p><h2 id="entity-list-title">实体列表</h2></div></div>
          <ul class="kg__entities" data-testid="graph-entity-list" role="list">
            <li v-for="document in visibleDocuments" :key="document.id" role="listitem" :class="`kg__entity--${normalizeEntityType(document.type)}`" :data-entity-list-type="normalizeEntityType(document.type)" :data-entity-list-id="document.id" :aria-current="store.selectedDocumentId === document.id ? 'true' : undefined">
              <ResearchIcon :name="typeIcons[normalizeEntityType(document.type)]" :size="17" /><span>{{ document.title }}</span><StatusBadge :status="typeStatuses[normalizeEntityType(document.type)]" :label="typeLabels[normalizeEntityType(document.type)]" />
            </li>
          </ul>
        </section>
        <section class="kg__panel" data-testid="graph-relations-panel" aria-labelledby="relations-title">
          <div class="kg__section-heading"><div><p>可追溯关系</p><h2 id="relations-title">关系详情</h2></div></div>
          <div class="kg__relation-boundary" data-testid="graph-relations-state" role="status">
            <ResearchIcon name="idle" :size="18" /><div><strong>当前数据源暂未提供实体关系</strong><p>为保证科研事实可追溯，本页不会根据共同标签推测关系或绘制虚构边。</p></div>
          </div>
        </section>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.kg{min-width:0;min-height:100%;padding:var(--research-page-gutter);background:var(--research-bg-main);color:var(--research-text-primary)}.kg__header{display:flex;align-items:flex-end;justify-content:space-between;gap:var(--research-space-6);margin-block-end:var(--research-space-5)}.kg__header h1{margin:var(--research-space-1) 0;font-size:var(--research-text-page-title);letter-spacing:var(--research-letter-spacing-title)}.kg__header>div>p:last-child{margin:0;color:var(--research-text-secondary);font-size:var(--research-text-body)}.kg__eyebrow{display:flex;align-items:center;gap:var(--research-space-2);margin:0;color:var(--research-ai-700);font-size:var(--research-text-sm);font-weight:var(--research-font-weight-semibold)}.kg__summary{display:flex;gap:var(--research-space-2);flex-wrap:wrap;justify-content:flex-end}.kg__summary span{padding:var(--research-space-2) var(--research-space-3);border:1px solid var(--research-border-subtle);border-radius:var(--research-radius-pill);background:var(--research-bg-card);color:var(--research-text-secondary);font-size:var(--research-text-sm)}
.kg__workspace{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(280px,.75fr);gap:var(--research-grid-gap);min-width:0}.kg__canvas,.kg__panel{min-width:0;border:1px solid var(--research-border-subtle);border-radius:var(--research-radius-panel);background:var(--research-bg-card);box-shadow:var(--research-shadow-soft)}.kg__canvas{padding:var(--research-space-5)}.kg__section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--research-space-3)}.kg__section-heading p{margin:0 0 var(--research-space-1);color:var(--research-text-secondary);font-size:var(--research-text-xs)}.kg__section-heading h2{margin:0;font-size:var(--research-text-section-title)}.kg__section-heading>span{color:var(--research-text-secondary);font-size:var(--research-text-xs)}.kg__pagination{display:flex;align-items:center;justify-content:space-between;gap:var(--research-space-3);margin-block-start:var(--research-space-4);color:var(--research-text-secondary);font-size:var(--research-text-xs)}.kg__pagination>div{display:flex;gap:var(--research-space-2)}.kg__pagination button{padding:var(--research-space-2) var(--research-space-3);border:1px solid var(--research-border-strong);border-radius:var(--research-radius-button);background:var(--research-bg-card);color:var(--research-text-primary);font:inherit;cursor:pointer}.kg__pagination button:disabled{opacity:1;cursor:not-allowed;background:var(--research-bg-hover);border-color:var(--research-border-strong);color:var(--research-text-secondary)}.kg__svg-scroll{max-height:620px;overflow:auto;margin-block:var(--research-space-3)}.kg__svg{display:block;width:100%;height:auto;max-height:600px;border:1px solid var(--research-divider);border-radius:var(--research-radius-card);background:var(--research-bg-panel)}
.kg__node{cursor:pointer;outline:none}.kg__node rect{fill:var(--research-bg-card);stroke:var(--research-border-strong);stroke-width:1.5}.kg__node text{fill:var(--research-text-primary);font-size:var(--research-text-xs);font-weight:var(--research-font-weight-semibold)}.kg__node .kg__node-meta{fill:var(--research-text-secondary);font-size:var(--research-text-xs);font-weight:var(--research-font-weight-regular)}.kg__node .kg__node-selected{fill:var(--research-text-primary);font-size:var(--research-text-xs)}.kg__node--paper rect{fill:var(--research-primary-50);stroke:var(--research-primary-500)}.kg__node--experiment rect{fill:var(--research-warning-50);stroke:var(--research-warning-500)}.kg__node--dataset rect{fill:var(--research-success-50);stroke:var(--research-success-500)}.kg__node--report rect,.kg__node--other rect{fill:var(--research-bg-hover);stroke:var(--research-border-strong)}.kg__node:hover rect{stroke-width:2.5}.kg__node--selected rect{stroke-width:3;filter:drop-shadow(0 0 4px var(--research-ai-glow-soft))}.kg__node:focus-visible rect{stroke:var(--research-ai-600);stroke-width:3;filter:drop-shadow(0 0 5px var(--research-ai-glow-soft))}
.kg__relation-boundary{display:flex;align-items:flex-start;gap:var(--research-space-3);padding:var(--research-space-4);border:1px dashed var(--research-border-strong);border-radius:var(--research-radius-card);background:var(--research-bg-panel);color:var(--research-text-secondary)}.kg__relation-boundary strong{color:var(--research-text-primary);font-size:var(--research-text-sm)}.kg__relation-boundary p{margin:var(--research-space-1) 0 0;font-size:var(--research-text-xs);line-height:var(--research-line-height-body)}.kg__inspector{display:grid;align-content:start;gap:var(--research-grid-gap);min-width:0}.kg__panel{padding:var(--research-space-4)}.kg__entity-detail{margin-block-start:var(--research-space-4)}.kg__entity-detail>svg{color:var(--research-primary-600)}.kg__entity-detail h3{margin:var(--research-space-2) 0 var(--research-space-3);font-size:var(--research-text-card-title);line-height:var(--research-line-height-body)}.kg__entity-detail dl{display:grid;gap:var(--research-space-2);margin:0}.kg__entity-detail dl div{display:grid;grid-template-columns:48px minmax(0,1fr);gap:var(--research-space-2);font-size:var(--research-text-sm)}.kg__entity-detail dt{color:var(--research-text-secondary)}.kg__entity-detail dd{min-width:0;margin:0;overflow-wrap:anywhere}.kg__tags{display:flex;flex-wrap:wrap;gap:var(--research-space-1);margin-block-start:var(--research-space-3)}.kg__tags span{padding:3px 8px;border-radius:var(--research-radius-pill);background:var(--research-ai-50);color:var(--research-ai-700);font-size:var(--research-text-xs)}.kg__selection-empty{color:var(--research-text-secondary);font-size:var(--research-text-sm);line-height:var(--research-line-height-body)}
.kg__entities{display:grid;gap:var(--research-space-1);margin:var(--research-space-3) 0 0;padding:0;list-style:none}.kg__entities li{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:var(--research-space-2);width:100%;box-sizing:border-box;padding:var(--research-space-2);border:1px solid transparent;border-radius:var(--research-radius-button);color:var(--research-text-primary)}.kg__entities li>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.kg__entities li[aria-current="true"]{border-color:var(--research-primary-100);background:var(--research-primary-50)}
.kg__entity--paper>svg{color:var(--research-primary-600)}.kg__entity--experiment>svg{color:var(--research-warning-600)}.kg__entity--dataset>svg{color:var(--research-success-600)}.kg__entity--report>svg,.kg__entity--other>svg{color:var(--research-text-secondary)}.kg__retained-error{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;gap:var(--research-space-3);padding:var(--research-space-3) var(--research-space-4);border:1px solid var(--research-danger-100);border-radius:var(--research-radius-card);background:var(--research-danger-50);color:var(--research-danger-600);font-size:var(--research-text-sm)}.kg__retained-error button{padding:var(--research-space-2) var(--research-space-3);border:1px solid var(--research-danger-500);border-radius:var(--research-radius-button);background:var(--research-bg-card);color:var(--research-danger-600);font:inherit;font-weight:var(--research-font-weight-semibold);cursor:pointer}.kg__retained-error button:disabled{opacity:1;cursor:not-allowed;background:var(--research-bg-hover);border-color:var(--research-border-strong);color:var(--research-text-secondary);box-shadow:none}
@media(max-width:1480px){.kg__workspace{grid-template-columns:minmax(0,1.55fr) minmax(260px,.7fr)}.kg__canvas{padding:var(--research-space-4)}}
</style>
