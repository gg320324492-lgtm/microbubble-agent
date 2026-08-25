<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useGraphLoader } from '../../composables/graph-loader'
import ResearchPageHeader from '../../components/research/ResearchPageHeader.vue'
import ResearchPanel from '../../components/research/ResearchPanel.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import ResearchMetricPanel from '../../components/research/ResearchMetricPanel.vue'
import KnowledgeGraphCanvas, { type GraphNode } from '../../components/research/KnowledgeGraphCanvas.vue'
import GraphNodePanel, { type GraphNodeDetail } from '../../components/research/GraphNodePanel.vue'
import GraphRelationPanel, { type GraphRelation } from '../../components/research/GraphRelationPanel.vue'
import EvidenceTracePanel, { type EvidenceItem } from '../../components/research/EvidenceTracePanel.vue'
import ReasoningPathPanel, { type ReasoningPath } from '../../components/research/ReasoningPathPanel.vue'
import GraphFilterPanel, { type GraphFilters } from '../../components/research/GraphFilterPanel.vue'

const { retrieveContext } = useGraphLoader()

// Alias for backward compatibility — composable is the only service layer

const entities = ref<GraphNode[]>([])
const relations = ref<GraphRelation[]>([])
const citations = ref<string[]>([])
const evidence = ref<EvidenceItem[]>([])
const selectedNode = ref<GraphNodeDetail | null>(null)
const reasoningPath = ref<ReasoningPath | null>(null)
const isLoading = ref(false)
const errorMessage = ref<string>('')

const filters = ref<GraphFilters>({
  entityTypes: ['Paper', 'Author', 'Method'],
  relationTypes: ['supports', 'causes', 'measured_by'],
  searchTerm: ''
})

async function loadGraph(): Promise<void> {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const ctx = await retrieveContext('ozone micro-nano bubble graph', 5)
    const snapshot = ctx as unknown as {
      entities?: GraphNode[]
      relations?: GraphRelation[]
      citations?: string[]
      evidence?: EvidenceItem[]
    }
    entities.value = Array.isArray(snapshot.entities) ? snapshot.entities : []
    relations.value = Array.isArray(snapshot.relations) ? snapshot.relations : []
    citations.value = Array.isArray(snapshot.citations) ? snapshot.citations : []
    evidence.value = Array.isArray(snapshot.evidence) ? snapshot.evidence : []
    if (entities.value.length > 0) {
      selectedNode.value = {
        id: entities.value[0].id,
        name: entities.value[0].name,
        type: entities.value[0].type,
        description: entities.value[0].description
      }
    }
    if (entities.value.length >= 2) {
      reasoningPath.value = {
        nodes: entities.value.slice(0, Math.min(3, entities.value.length)).map((e) => e.name),
        edges: relations.value.slice(0, 2).map((r) => ({ from: r.source, to: r.target, type: r.type })),
        conclusion: '从源实体到目标实体的推理路径'
      }
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '图谱加载失败'
  } finally {
    isLoading.value = false
  }
}

function retry(): void {
  void loadGraph()
}

import { ref } from 'vue'

onMounted(() => {
  void loadGraph()
})

const isEmptyGraph = computed(() => entities.value.length === 0)
const selectedNodeDetail = computed<GraphNodeDetail | null>(() => selectedNode.value)
const graphRelations = computed<GraphRelation[]>(() => relations.value)
const graphEvidence = computed<EvidenceItem[]>(() => evidence.value)
const graphPath = computed<ReasoningPath | null>(() => reasoningPath.value)
const graphFilters = computed<GraphFilters>(() => filters.value)
const graphCitations = computed<string[]>(() => citations.value)
const graphNodes = computed<GraphNode[]>(() => entities.value)
</script>

<template>
  <main class="knowledge-graph" data-research-theme="graph" aria-label="知识图谱工作台">
    <ResearchState
      v-if="isLoading"
      state="loading"
      title="加载图谱中"
      description="正在构建知识图谱"
    />

    <ResearchState
      v-else-if="errorMessage"
      state="error"
      title="图谱加载失败"
      :description="errorMessage"
      @retry="retry"
    />

    <ResearchState
      v-else-if="isEmptyGraph"
      state="empty"
      title="暂无节点"
      description="尚无图谱数据"
    />

    <template v-else>
      <ResearchPageHeader title="知识图谱工作台" subtitle="科研知识图谱三栏工作区" />

      <section class="knowledge-graph__meta" aria-label="图谱统计">
        <h2 class="knowledge-graph__meta-title">图谱统计</h2>
 <div class="knowledge-graph__meta-grid">
          <ResearchPanel title="节点">
            <ResearchMetricPanel
              :metrics="[
                { label: '节点数', value: String(graphNodes.length) },
                { label: '关系数', value: String(graphRelations.length) },
                { label: '引文数', value: String(graphCitations.length) }
              ]"
              title="图谱统计"
            />
          </ResearchPanel>
          <ResearchPanel title="检索">
            <p class="knowledge-graph__meta-label">过滤搜索</p>
            <GraphFilterPanel :filters="graphFilters" aria-label="图谱过滤面板" />
          </ResearchPanel>
        </div>
      </section>

      <section class="knowledge-graph__grid kg__workspace" aria-label="三栏工作区">
        <aside class="knowledge-graph__col knowledge-graph__col--canvas" aria-label="图谱画布">
          <KnowledgeGraphCanvas :entities="graphNodes" aria-label="知识图谱画布" />
          <GraphNodePanel :node="selectedNodeDetail" aria-label="节点详情面板" />
        </aside>

        <section class="knowledge-graph__col knowledge-graph__col--relations" aria-label="关系与路径">
          <GraphRelationPanel :relations="graphRelations" aria-label="关系列表面板" />
          <ReasoningPathPanel :path="graphPath" aria-label="推理路径面板" />
        </section>

        <aside class="knowledge-graph__col knowledge-graph__col--evidence" aria-label="证据面板">
          <EvidenceTracePanel :evidence="graphEvidence" aria-label="证据追踪面板" />
        </aside>
      </section>
    </template>
  </main>
</template>

<style scoped>
.knowledge-graph {
  min-width: 0;
  min-height: 100%;
  max-width: var(--research-content-max-width, 1680px);
  margin: 0 auto;
  padding: var(--research-page-gutter, 24px);
  overflow-x: clip;
  background: var(--research-bg-main);
}
.knowledge-graph:focus-visible {
  outline: none;
}
.knowledge-graph__meta {
  margin-bottom: var(--research-space-6);
  min-width: 0;
}
.knowledge-graph__meta-title {
  font-size: var(--research-text-card-title);
  font-weight: var(--research-font-weight-semibold);
  color: var(--research-text-primary);
  margin: 0 0 var(--research-space-3);
}
.knowledge-graph__meta-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--research-grid-gap);
}
.knowledge-graph__meta-label {
  font-size: var(--research-text-xs);
  color: var(--research-text-muted);
  margin: 0 0 var(--research-space-1);
}
.knowledge-graph__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}
.knowledge-graph__col {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
@media (max-width: 1480px) {
  .knowledge-graph__grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .knowledge-graph__meta-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (min-width: 1720px) {
  .knowledge-graph__grid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.2fr);
  }
  .knowledge-graph__meta-grid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}
@media (prefers-reduced-motion: reduce) {
  .knowledge-graph *,
  .knowledge-graph *::before,
  .knowledge-graph *::after {
    animation: none !important;
    transition: none !important;
  }
}
</style>