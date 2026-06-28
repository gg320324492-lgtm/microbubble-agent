<!-- KnowledgeEntityTab.vue — v77 P2.6-E.3 拆分自 KnowledgeView.vue -->
<template>
  <div>
    <el-card class="filter-card">
      <el-row :gutter="12">
        <el-col :span="5">
          <el-input v-model="entitySearch.subject" name="entitySearch-subject" placeholder="主体" clearable @keyup.enter="searchEntitiesLocal" />
        </el-col>
        <el-col :span="5">
          <el-input v-model="entitySearch.predicate" name="entitySearch-predicate" placeholder="关系" clearable @keyup.enter="searchEntitiesLocal" />
        </el-col>
        <el-col :span="6">
          <el-input v-model="entitySearch.keyword" name="entitySearch-keyword" placeholder="关键字搜索" clearable @keyup.enter="searchEntitiesLocal" />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="searchEntitiesLocal">搜索实体</el-button>
        </el-col>
        <el-col :span="4">
          <el-button @click="fetchEntityGraphLocal" :loading="entityGraphLoading">刷新图谱</el-button>
        </el-col>
      </el-row>
    </el-card>

    <div class="entity-linked-view">
      <div class="entity-graph-panel">
        <div class="panel-header">
          <h3 class="panel-title">🔗 关系网络</h3>
          <span class="panel-hint">点击节点查看详情</span>
        </div>
        <div v-if="entityGraphData.nodes.length === 0" class="graph-empty">
          <el-empty description="暂无图谱数据，点击「加载图谱」" :image-size="80" />
        </div>
        <div v-else ref="entityGraphRef" class="entity-graph-container"></div>
      </div>

      <div class="entity-list-panel">
        <div class="panel-header">
          <h3 class="panel-title">📋 实体列表</h3>
          <span class="panel-count">{{ entityList.length }} 个实体</span>
        </div>
        <div v-if="entityList.length === 0" class="list-empty">
          <el-empty description="暂无实体数据" :image-size="60" />
        </div>
        <div v-else class="entity-list-scroll">
          <div
            v-for="e in entityList"
            :key="e.id"
            class="entity-card"
            :class="{ 'entity-card-active': selectedEntityId === e.id }"
            @click="handleEntityClick(e)"
          >
            <div class="entity-triple">
              <span class="entity-subject">{{ e.subject }}</span>
              <span class="entity-predicate">{{ e.predicate }}</span>
              <span class="entity-object">{{ e.object }}</span>
            </div>
            <div v-if="e.condition" class="entity-condition-text">条件: {{ e.condition }}</div>
            <div class="entity-meta">
              <span class="meta-item">{{ e.source_count }} 篇文档</span>
              <span class="meta-item">{{ e.occurrence_count }} 次出现</span>
              <span class="meta-confidence">
                <el-progress :percentage="Math.round(e.confidence * 100)" :stroke-width="3" :show-text="false" style="width:60px" />
              </span>
            </div>
          </div>
        </div>
        <el-pagination
          v-if="entityTotal > 0"
          :current-page="entityPage"
          :page-size="20"
          :total="entityTotal"
          layout="total, prev, pager, next"
          @current-change="(p) => $emit('page-change', p)"
          class="entity-pagination"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * KnowledgeEntityTab.vue — 实体图谱 tab（v77 P2.6-E.3 从 KnowledgeView.vue 拆分）
 *
 * 父组件: KnowledgeView.vue (lazy-loaded tab-pane)
 * Props: entityList / entityTotal / entityPage / entityGraphData（来自 useKnowledge composable）
 *
 * 关键点:
 * - ECharts instance 在组件内部 lifecycle 管理 (onBeforeUnmount dispose)
 * - 父组件不再持有 entityChartInstance 引用（v60-v67 教训：避免跨组件状态共享）
 */
import { ref, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({
  entityList: { type: Array, required: true },
  entityTotal: { type: Number, required: true },
  entityPage: { type: Number, required: true },
  entityGraphData: { type: Object, required: true },
})

const emit = defineEmits(['refresh', 'show-entity-detail', 'page-change'])

const entitySearch = ref({ subject: '', predicate: '', keyword: '' })
const entityGraphRef = ref(null)
let entityChartInstance = null
const entityGraphLoading = ref(false)
const selectedEntityId = ref(null)

const searchEntitiesLocal = async () => {
  try {
    const params = { ...entitySearch.value, page: props.entityPage, page_size: 20 }
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    const res = await axios.get('/api/v1/knowledge/entities', { params })
    emit('refresh', {
      list: res.data.items || [],
      total: res.data.total || 0,
    })
  } catch (e) { ElMessage.error('实体搜索失败') }
}

const fetchEntityGraphLocal = async () => {
  entityGraphLoading.value = true
  try {
    const res = await axios.get('/api/v1/knowledge/entities/graph', {
      params: { limit: 100 }
    })
    emit('refresh', { graph: res.data || { nodes: [], edges: [] } })
    // 等待 DOM 更新 + Vue emit 完成
    await new Promise(r => setTimeout(r, 100))
    await renderEntityGraph()
    entityGraphLoading.value = false
  } catch (e) {
    console.error('实体图谱加载失败:', e)
    entityGraphLoading.value = false
  }
}

const renderEntityGraph = async () => {
  if (!entityGraphRef.value || props.entityGraphData.nodes.length === 0) return
  const echarts = await import('echarts')
  if (entityChartInstance) entityChartInstance.dispose()
  entityChartInstance = echarts.init(entityGraphRef.value)
  const cats = [...new Set(props.entityGraphData.nodes.map(n => n.predicate || '其他'))]
  const colors = ['#FF7A5C', '#FFB347', '#5470c6', '#91cc75', '#ee6666', '#73c0de', '#fc8452']
  const option = {
    tooltip: { formatter: p => p.dataType === 'node' ? `${p.data.subject}<br/>${p.data.predicate} → ${p.data.object}` : `共现权重: ${p.data.weight || 1}` },
    legend: { data: cats.slice(0, 7), bottom: 0 },
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      force: { repulsion: 200, edgeLength: [100, 300] },
      data: props.entityGraphData.nodes.map(n => ({
        name: String(n.id), subject: n.subject, predicate: n.predicate, object: n.object, entityId: n.id,
        symbolSize: Math.max(15, Math.min(40, (n.occurrence_count || 1) * 6)),
        category: n.predicate || '其他', itemStyle: { color: colors[cats.indexOf(n.predicate || '其他') % colors.length] },
      })),
      categories: cats.slice(0, 7).map((c, i) => ({ name: c, itemStyle: { color: colors[i % colors.length] } })),
      links: props.entityGraphData.edges.map(e => ({ source: String(e.source), target: String(e.target), weight: e.weight })),
      lineStyle: { opacity: 0.4, curveness: 0.2 },
      label: { show: true, formatter: p => p.data.subject.length > 8 ? p.data.subject.slice(0, 8) + '...' : p.data.subject, fontSize: 10 },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3 }
      }
    }],
  }
  entityChartInstance.setOption(option)

  entityChartInstance.on('click', (params) => {
    if (params.dataType === 'node' && params.data.entityId) {
      selectedEntityId.value = params.data.entityId
      const card = document.querySelector(`.entity-card-active`)
      if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' })
      emit('show-entity-detail', params.data.entityId)
    }
  })
}

const handleEntityClick = (entity) => {
  selectedEntityId.value = entity.id
  if (entityChartInstance && props.entityGraphData.nodes.length > 0) {
    const nodeIndex = props.entityGraphData.nodes.findIndex(n => n.id === entity.id)
    if (nodeIndex >= 0) {
      entityChartInstance.dispatchAction({
        type: 'highlight',
        seriesIndex: 0,
        dataIndex: nodeIndex
      })
      entityGraphRef.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }
  emit('show-entity-detail', entity.id)
}

onBeforeUnmount(() => {
  if (entityChartInstance) {
    entityChartInstance.dispose()
    entityChartInstance = null
  }
})

defineExpose({ searchEntitiesLocal, fetchEntityGraphLocal, renderEntityGraph })
</script>

<style scoped>
.filter-card {
  margin-bottom: var(--space-4);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.entity-linked-view {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  margin-top: var(--space-4);
}

.entity-graph-panel,
.entity-list-panel {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  border-bottom: 1px solid var(--color-border-light);
}

.panel-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0;
}

.panel-hint,
.panel-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.entity-graph-container {
  height: 500px;
  width: 100%;
}

.graph-empty,
.list-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
}

.entity-list-scroll {
  max-height: 500px;
  overflow-y: auto;
  padding: var(--space-3);
}

.entity-list-scroll::-webkit-scrollbar {
  width: 6px;
}

.entity-list-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.entity-list-scroll::-webkit-scrollbar-thumb {
  background: var(--color-text-placeholder);
  border-radius: 3px;
}

.entity-card {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
  margin-bottom: var(--space-2);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.entity-card:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}

.entity-card-active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  box-shadow: 0 0 0 2px var(--color-primary-border);
}

.entity-triple {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  flex-wrap: wrap;
}

.entity-subject {
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}

.entity-predicate {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  padding: 2px 8px;
  background: var(--color-info-bg);
  border-radius: var(--radius-full);
}

.entity-object {
  color: var(--color-accent);
}

.entity-condition-text {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.entity-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.meta-confidence {
  margin-left: auto;
}

.entity-pagination {
  padding: var(--space-3);
  border-top: 1px solid var(--color-border-light);
}

.entity-triple-large {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--font-size-lg);
  margin-bottom: var(--space-4);
}

.entity-detail-section h4 {
  margin: 0 0 var(--space-3) 0;
  color: var(--color-text-primary);
}

.source-item {
  padding: var(--space-2) var(--space-3);
  background: var(--color-info-bg);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-2);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.source-item:hover {
  background: var(--color-primary-bg);
}

.clickable {
  cursor: pointer;
}
</style>

<style>
/* v77 P2.6-E.3: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
[data-theme="dark"] .entity-graph-panel,
[data-theme="dark"] .entity-list-panel {
  background: var(--color-bg-card);
}
[data-theme="dark"] .panel-header {
  border-bottom-color: var(--color-border-light);
}
[data-theme="dark"] .entity-card {
  border-color: var(--color-border-light);
}
[data-theme="dark"] .entity-pagination {
  border-top-color: var(--color-border-light);
}
[data-theme="dark"] .entity-list-scroll::-webkit-scrollbar-thumb {
  background: var(--color-text-placeholder);
}
[data-theme="dark"] .entity-card-active {
  background: var(--color-primary-bg);
  box-shadow: 0 0 0 2px var(--color-primary-border);
}
[data-theme="dark"] .el-empty__image svg,
[data-theme="dark"] .el-empty__image img {
  filter: invert(0.9) hue-rotate(180deg);
}
[data-theme="dark"] .el-empty__description p {
  color: var(--color-text-secondary);
}
</style>