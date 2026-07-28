<template>
  <!--
    KnowledgeGraphView.vue
    Phase 9 batch 1 (W85 B-1) — 课题组知识图谱可视化主视图
    路由: /knowledge/graph
    集成 KnowledgeGraphExplorer + 工具栏 + 节点详情侧栏
  -->
  <div class="kg-view">
    <div class="kg-toolbar">
      <h2 class="kg-title">课题组知识图谱</h2>
      <div class="kg-actions">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索节点标题"
          clearable
          style="width: 240px"
          @keyup.enter="onSearch"
        />
        <el-button type="primary" :icon="Search" @click="onSearch">搜索</el-button>
        <el-button :icon="Refresh" @click="onResetGraph" :loading="loading">重置</el-button>
      </div>
    </div>

    <div class="kg-layout">
      <div class="kg-explorer-wrap">
        <KnowledgeGraphExplorer
          ref="explorerRef"
          :nodes="filteredNodes"
          :edges="filteredEdges"
          :loading="loading"
          @node-click="onNodeClick"
        />
      </div>
      <aside class="kg-side">
        <div class="kg-side-card">
          <h3 class="kg-side-title">节点详情</h3>
          <div v-if="!selectedNode" class="kg-empty">点击图谱中任意节点查看详情</div>
          <div v-else class="kg-node-detail">
            <div class="kg-node-title">{{ selectedNode.title }}</div>
            <el-tag size="small" :type="categoryTagType(selectedNode.category)">
              {{ selectedNode.category || '未分类' }}
            </el-tag>
            <div class="kg-node-actions">
              <el-button size="small" type="primary" plain @click="onExpandNeighbors">
                展开邻居
              </el-button>
              <el-button size="small" plain @click="onFetchSubgraph" :loading="subgraphLoading">
                钻取子图
              </el-button>
            </div>
            <div v-if="neighbors.length" class="kg-neighbor-list">
              <h4 class="kg-section-title">邻居 ({{ neighbors.length }})</h4>
              <ul>
                <li v-for="n in neighbors" :key="n.id" @click="onNeighborClick(n.id)">
                  {{ n.title }}
                  <span class="kg-relation-count">×{{ n.relation_count }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div class="kg-side-card">
          <h3 class="kg-side-title">图谱统计</h3>
          <div class="kg-stat">
            <div class="kg-stat-num">{{ stats.nodes }}</div>
            <div class="kg-stat-label">节点</div>
          </div>
          <div class="kg-stat">
            <div class="kg-stat-num">{{ stats.edges }}</div>
            <div class="kg-stat-label">关系</div>
          </div>
          <div class="kg-stat">
            <div class="kg-stat-num">{{ stats.categories }}</div>
            <div class="kg-stat-label">分类</div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import KnowledgeGraphExplorer from '@/components/knowledge/KnowledgeGraphExplorer.vue'

const explorerRef = ref(null)
const searchKeyword = ref('')
const loading = ref(false)
const subgraphLoading = ref(false)
const selectedNode = ref(null)
const neighbors = ref([])
const allNodes = ref([])
const allEdges = ref([])

const filteredNodes = computed(() => {
  if (!searchKeyword.value) return allNodes.value
  const kw = searchKeyword.value.toLowerCase()
  return allNodes.value.filter(n => String(n.title || '').toLowerCase().includes(kw))
})

const filteredEdges = computed(() => {
  if (!searchKeyword.value) return allEdges.value
  const ids = new Set(filteredNodes.value.map(n => n.id))
  return allEdges.value.filter(e => ids.has(e.source) && ids.has(e.target))
})

const stats = computed(() => {
  const cats = new Set(filteredNodes.value.map(n => n.category).filter(Boolean))
  return {
    nodes: filteredNodes.value.length,
    edges: filteredEdges.value.length,
    categories: cats.size,
  }
})

const fetchGlobalGraph = async () => {
  loading.value = true
  try {
    // Phase 9 batch 1: 全局图谱复用现有 /knowledge/graph 端点 (W68 已落地)
    const res = await axios.get('/api/v1/knowledge/graph', {
      params: { depth: 2, limit: 80 }
    })
    allNodes.value = res.data?.nodes || []
    allEdges.value = res.data?.edges || []
  } catch (e) {
    console.error('[KnowledgeGraphView] 全局图谱加载失败', e)
    ElMessage.warning('图谱加载失败，已降级为空状态')
    allNodes.value = []
    allEdges.value = []
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  // computed filteredNodes/Edges 自动重算
}

const onResetGraph = () => {
  searchKeyword.value = ''
  selectedNode.value = null
  neighbors.value = []
  fetchGlobalGraph()
}

const onNodeClick = (node) => {
  selectedNode.value = node
  neighbors.value = []
}

const onNeighborClick = (nodeId) => {
  const node = allNodes.value.find(n => n.id === nodeId)
  if (node) selectedNode.value = node
}

const onExpandNeighbors = async () => {
  if (!selectedNode.value) return
  try {
    // Phase 9 batch 1 新端点: /knowledge-graph/neighbors
    const res = await axios.get('/api/v1/knowledge-graph/neighbors', {
      params: { node: selectedNode.value.id, limit: 30 }
    })
    neighbors.value = res.data?.neighbors || []
    // 合并到全局图谱（去重）
    mergeIntoGraph({ nodes: res.data?.neighbors || [], edges: res.data?.edges || [] })
    ElMessage.success(`展开 ${neighbors.value.length} 个邻居`)
  } catch (e) {
    console.error('[KnowledgeGraphView] 邻居展开失败', e)
    ElMessage.error('邻居展开失败')
  }
}

const onFetchSubgraph = async () => {
  if (!selectedNode.value) return
  subgraphLoading.value = true
  try {
    // Phase 9 batch 1 新端点: /knowledge-graph/subgraph
    const res = await axios.get('/api/v1/knowledge-graph/subgraph', {
      params: { concepts: selectedNode.value.id, depth: 2 }
    })
    mergeIntoGraph({ nodes: res.data?.nodes || [], edges: res.data?.edges || [] })
    ElMessage.success(`钻取子图完成，新增 ${res.data?.nodes?.length || 0} 个节点`)
  } catch (e) {
    console.error('[KnowledgeGraphView] 子图钻取失败', e)
    ElMessage.error('子图钻取失败')
  } finally {
    subgraphLoading.value = false
  }
}

const mergeIntoGraph = ({ nodes, edges }) => {
  const nodeMap = new Map(allNodes.value.map(n => [n.id, n]))
  nodes.forEach(n => { if (!nodeMap.has(n.id)) nodeMap.set(n.id, n) })
  allNodes.value = [...nodeMap.values()]

  const edgeKeys = new Set(allEdges.value.map(e => `${e.source}-${e.target}-${e.type}`))
  edges.forEach(e => {
    const k = `${e.source}-${e.target}-${e.type}`
    if (!edgeKeys.has(k)) {
      allEdges.value.push(e)
      edgeKeys.add(k)
    }
  })
}

const categoryTagType = (cat) => {
  const map = {
    '论文': '', '会议': 'success', '项目': 'warning',
    '公式': 'info', '假设': 'danger'
  }
  return map[cat] || ''
}

onMounted(() => {
  fetchGlobalGraph()
})
</script>

<style scoped>
.kg-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-page, #fafafa);
}
.kg-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: var(--color-bg-card, #fff);
  border-bottom: 1px solid var(--color-border, #e4e7ed);
}
.kg-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.kg-actions {
  display: flex;
  gap: 8px;
}
.kg-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 16px;
  padding: 16px 24px;
  min-height: 0;
}
@media (max-width: 1024px) {
  .kg-layout {
    grid-template-columns: 1fr;
  }
}
.kg-explorer-wrap {
  background: var(--color-bg-card, #fff);
  border-radius: 8px;
  overflow: hidden;
  min-height: 480px;
}
.kg-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.kg-side-card {
  background: var(--color-bg-card, #fff);
  border-radius: 8px;
  padding: 16px;
}
.kg-side-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
}
.kg-empty {
  color: var(--color-text-secondary, #909399);
  font-size: 13px;
  text-align: center;
  padding: 24px 0;
}
.kg-node-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.kg-node-title {
  font-size: 14px;
  font-weight: 600;
  word-break: break-all;
}
.kg-node-actions {
  display: flex;
  gap: 8px;
}
.kg-section-title {
  margin: 8px 0 4px 0;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}
.kg-neighbor-list ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.kg-neighbor-list li {
  padding: 6px 8px;
  font-size: 13px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  justify-content: space-between;
}
.kg-neighbor-list li:hover {
  background: var(--color-bg-hover, #f5f7fa);
}
.kg-relation-count {
  color: var(--color-text-secondary, #909399);
  font-size: 12px;
}
.kg-stat {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 0;
}
.kg-stat-num {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-primary, #409eff);
}
.kg-stat-label {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}
</style>