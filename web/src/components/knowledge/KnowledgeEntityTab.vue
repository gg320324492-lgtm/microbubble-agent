<!-- KnowledgeEntityTab.vue — v77 P2.6-E.3 拆分自 KnowledgeView.vue
     W86 mini-4 fix: 复用 KnowledgeGraphExplorer.vue (Phase 9 W85 B-1), 现代化 ECharts 渲染
     + loading state 骨架屏 + 保留搜索/过滤/侧栏实体详情
-->
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
        <!-- W86 mini-4 fix: 复用 Phase 9 KnowledgeGraphExplorer 现代化 ECharts -->
        <KnowledgeGraphExplorer
          :nodes="entityGraphData.nodes"
          :edges="entityGraphData.edges"
          :loading="entityGraphLoading"
          @node-click="handleGraphNodeClick"
        />
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
 * W86 mini-4 fix: 复用 KnowledgeGraphExplorer (Phase 9) 取代自维护 ECharts
 *
 * 父组件: KnowledgeView.vue (lazy-loaded tab-pane)
 * Props: entityList / entityTotal / entityPage / entityGraphData（来自 useKnowledge composable）
 *
 * 关键点:
 * - ECharts instance 由 KnowledgeGraphExplorer 内部 lifecycle 管理
 * - 父组件不再持有 entityChartInstance 引用（v60-v67 教训：避免跨组件状态共享）
 * - 父组件只管 search/filter/list, 图谱渲染委派给 Explorer
 */
import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import KnowledgeGraphExplorer from './KnowledgeGraphExplorer.vue'

const props = defineProps({
  entityList: { type: Array, required: true },
  entityTotal: { type: Number, required: true },
  entityPage: { type: Number, required: true },
  entityGraphData: { type: Object, required: true },
})

const emit = defineEmits(['refresh', 'show-entity-detail', 'page-change'])

const entitySearch = ref({ subject: '', predicate: '', keyword: '' })
const selectedEntityId = ref(null)
const entityGraphLoading = ref(false)

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
  } catch (e) {
    console.error('实体图谱加载失败:', e)
    ElMessage.error('实体图谱加载失败')
  } finally {
    entityGraphLoading.value = false
  }
}

const handleGraphNodeClick = (nodeData) => {
  if (!nodeData) return
  // nodeData.id 是 string (KnowledgeGraphExplorer 内部 normalize 后的 id)
  // 找到原始 entity 并高亮 + emit
  const entityId = Number(nodeData.id || nodeData.entityId)
  if (!entityId) return
  selectedEntityId.value = entityId
  const card = document.querySelector(`.entity-card-active`)
  if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' })
  emit('show-entity-detail', entityId)
}

const handleEntityClick = (entity) => {
  selectedEntityId.value = entity.id
  emit('show-entity-detail', entity.id)
}

defineExpose({ searchEntitiesLocal, fetchEntityGraphLocal })
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

/* W86 mini-5 fix: 老代码 .entity-graph-panel 无 height/flex, 子组件
   KnowledgeGraphExplorer 的 height:100% 没有可解析的父高度 → 图谱塌到
   min-height 480px 且不随面板拉伸, 用户看到"小框显示不全".
   面板改 flex column + 600px 下限, 图谱区 flex:1 吃掉 header 以外的剩余空间. */
.entity-graph-panel {
  display: flex;
  flex-direction: column;
  min-height: 600px;
}

.entity-graph-panel :deep(.kg-explorer) {
  flex: 1;
  min-height: 0; /* flex 子项默认 min-height:auto 会撑破容器 */
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