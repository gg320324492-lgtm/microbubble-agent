<!--
  KnowledgeEntityTab.vue — 实体图谱 tab · 2026-09-13 档案墨线风重做

  重做要点 (用户报告: 图谱混乱/标签裁剪/列表难翻/风格不齐):
  - 墨线档案头部行 (mono eyebrow + 衬线标题 + 刷新) 取代 el-card 过滤条
  - 过滤行: 关键字宽框 + 主体/关系窄框 + 常用关系快速戳, 回车即搜
  - 左 2fr 图谱 / 右 1.2fr 实体列表, 面板高度对齐 (min-height 640)
  - 列表行: predicate 改 mono 戳 + 置信度细条, 墨线虚线分隔
  - 配色全部走 var(--color-*) — 自动继承 .knowledge-view 页面配色④青灰水墨 + 深色主题

  契约不变:
  Props: entityList / entityTotal / entityPage / entityGraphData (来自 useKnowledge)
  Emits: refresh / page-change / show-entity-detail
  Expose: searchEntitiesLocal / fetchEntityGraphLocal (父级 watch(activeTab) 调用)
-->
<template>
  <div class="entity-tab">
    <!-- 头部行 -->
    <div class="et-head">
      <div>
        <div class="et-eyebrow">ENTITY GRAPH · 关系网络</div>
        <div class="et-title">实体关系图谱</div>
      </div>
      <button class="et-refresh" :disabled="entityGraphLoading" @click="fetchEntityGraphLocal">
        <span class="et-refresh-glyph" :class="{ spin: entityGraphLoading }">⟳</span>
        刷新图谱
      </button>
    </div>

    <!-- 过滤行 -->
    <div class="et-filters">
      <input
        v-model="entitySearch.keyword"
        class="et-input et-input-wide"
        placeholder="搜索主体、关系、客体、条件…"
        @keyup.enter="searchEntitiesLocal"
      />
      <input
        v-model="entitySearch.subject"
        class="et-input"
        placeholder="主体 (精确)"
        @keyup.enter="searchEntitiesLocal"
      />
      <input
        v-model="entitySearch.predicate"
        class="et-input"
        placeholder="关系 (精确)"
        @keyup.enter="searchEntitiesLocal"
      />
      <button class="et-btn et-btn-pri" @click="searchEntitiesLocal">搜索实体</button>
    </div>

    <!-- 常用关系快速过滤 -->
    <div class="et-quick">
      <span class="et-quick-label">常用关系</span>
      <button
        v-for="p in QUICK_PREDICATES"
        :key="p"
        class="et-quick-chip"
        :class="{ on: entitySearch.predicate === p }"
        @click="quickPredicate(p)"
      >{{ p }}</button>
      <button
        v-if="entitySearch.predicate"
        class="et-quick-clear"
        @click="quickPredicate('')"
      >✕ 清除</button>
    </div>

    <!-- 主体双栏 -->
    <div class="et-body">
      <!-- 图谱面板 -->
      <div class="et-graph-panel">
        <div class="et-panel-header">
          <span class="et-panel-title"><span class="et-link-glyph">🔗</span> 关系网络</span>
          <span class="et-panel-hint">点击节点查看详情 · 滚轮缩放 · 拖拽平移</span>
        </div>

        <div v-if="entityGraphLoading" class="et-skel">
          <div class="et-skel-line" style="width: 42%"></div>
          <div class="et-skel-line" style="width: 68%"></div>
          <div class="et-skel-line" style="width: 55%"></div>
          <div class="et-skel-line" style="width: 74%"></div>
        </div>
        <KnowledgeGraphExplorer
          v-else-if="entityGraphData?.nodes?.length"
          :nodes="entityGraphData.nodes"
          :edges="entityGraphData.edges"
          :loading="entityGraphLoading"
          @node-click="handleGraphNodeClick"
        />
        <div v-else class="et-empty">
          <div class="et-empty-mark">∅</div>
          <div class="et-empty-t">暂无图谱数据</div>
          <div class="et-empty-s">添加知识条目并触发深度研究后, 这里会自动生成关系网络</div>
          <button class="et-btn" @click="fetchEntityGraphLocal">重新加载</button>
        </div>
      </div>

      <!-- 列表面板 -->
      <div class="et-list-panel">
        <div class="et-panel-header">
          <span class="et-panel-title"><span class="et-link-glyph">📋</span> 实体列表</span>
          <span class="et-panel-hint">{{ entityTotal }} 条</span>
        </div>

        <div v-if="entityList.length === 0" class="et-empty">
          <div class="et-empty-mark">∅</div>
          <div class="et-empty-t">暂无实体数据</div>
          <div class="et-empty-s">调整搜索条件后重试</div>
        </div>

        <div v-else class="et-list-scroll">
          <div
            v-for="e in entityList"
            :key="e.id"
            class="et-row"
            :class="{ 'et-row-on': selectedEntityId === e.id }"
            @click="handleEntityClick(e)"
          >
            <div class="et-triple">
              <span class="et-subject">{{ e.subject }}</span>
              <span class="et-pred">{{ e.predicate }}</span>
              <span class="et-object">{{ e.object }}</span>
            </div>
            <div v-if="e.condition" class="et-cond">条件 · {{ e.condition }}</div>
            <div class="et-meta">
              <span>{{ e.source_count }} 篇文档</span>
              <span>{{ e.occurrence_count }} 次出现</span>
              <span class="et-conf" :title="`置信度 ${Math.round(e.confidence * 100)}%`">
                <i :style="{ width: Math.round(e.confidence * 100) + '%' }"></i>
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
 * KnowledgeEntityTab.vue — 实体图谱 tab (v77 P2.6-E.3 拆分; 2026-09-13 墨线重做)
 *
 * 数据流契约不变:
 * - Props: entityList / entityTotal / entityPage / entityGraphData (来自 useKnowledge)
 * - Emits: refresh (list+graph 回传父级) / page-change / show-entity-detail
 * - Expose: searchEntitiesLocal / fetchEntityGraphLocal (父级 watch(activeTab) 调用)
 * - 取数: axios 直连 /api/v1/knowledge/entities(+ /graph), request.js 拦截器注入鉴权
 */
import { ref, onMounted, watch } from 'vue'
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

// 常用关系快速过滤 (后端 predicate 参数为精确匹配)
const QUICK_PREDICATES = ['产生', '具有', '提高', '影响', '抑制', '改善']

const quickPredicate = (p) => {
  entitySearch.value.predicate = p
  searchEntitiesLocal()
}

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
    // W86 mini-6 fix: 直接拉图谱并回传父级 (兼容老路径), 不依赖父级 watch 链路
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

onMounted(() => {
  if (!props.entityGraphData?.nodes?.length) {
    fetchEntityGraphLocal()
  }
  // W86 mini-7: entityList 为空时自动 search (覆盖 useKnowledge page_size=1 的 [1 item])
  if (props.entityList.length === 0) {
    searchEntitiesLocal()
  }
})

// 兜底: 父组件 emit('refresh') 后 entityGraphData 通过 props 变化,
// 若数据仍为空 (e.g. 接口异常), 重新拉一次.
watch(() => props.entityGraphData?.nodes?.length, (newLen, oldLen) => {
  if (oldLen !== undefined && newLen === 0 && oldLen > 0) {
    fetchEntityGraphLocal()
  }
})

const handleGraphNodeClick = (nodeData) => {
  if (!nodeData) return
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
/* ═══ 墨线档案 · 页面配色④令牌自动继承 (.knowledge-view 覆盖) ═══ */
.entity-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
  animation: fadeSlideUp var(--duration-slow, .3s) ease-out both;
}

/* 头部行 */
.et-head { display: flex; justify-content: space-between; align-items: flex-end; }
.et-eyebrow {
  font-family: Consolas, 'SFMono-Regular', monospace;
  font-size: 10px; letter-spacing: .3em; color: var(--color-text-secondary);
}
.et-title {
  font-family: 'Noto Serif SC', 'Songti SC', 'SimSun', serif;
  font-size: 21px; font-weight: 700; letter-spacing: .05em; line-height: 1.3;
  margin-top: 2px;
}
.et-refresh {
  font-size: 12.5px; padding: 7px 16px; border-radius: 3px; cursor: pointer;
  background: var(--color-bg-card); color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  display: inline-flex; align-items: center; gap: 7px;
}
.et-refresh:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); }
.et-refresh:disabled { opacity: .55; cursor: wait; }
.et-refresh-glyph { display: inline-block; }
.et-refresh-glyph.spin { animation: et-spin 1s linear infinite; }
@keyframes et-spin { to { transform: rotate(360deg); } }

/* 过滤行 */
.et-filters { display: flex; gap: 10px; }
.et-input {
  background: var(--color-bg-card); color: var(--color-text-primary);
  border: 1px solid var(--color-border); border-radius: 3px;
  padding: 9px 12px; font-size: 13px; outline: none; min-width: 0;
}
.et-input::placeholder { color: var(--color-text-placeholder); }
.et-input:focus { border-color: var(--color-primary); }
.et-input-wide { flex: 1; }
.et-input:not(.et-input-wide) { width: 150px; }
.et-btn {
  font-size: 13px; padding: 9px 18px; border-radius: 3px; cursor: pointer;
  border: 1px solid var(--color-border); background: var(--color-bg-card);
  color: var(--color-text-primary); white-space: nowrap;
}
.et-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }
.et-btn-pri {
  background: var(--color-primary); border-color: var(--color-primary); color: #fff;
  font-weight: 600;
}
.et-btn-pri:hover { background: var(--color-primary-light); border-color: var(--color-primary-light); color: #fff; }

/* 常用关系快速过滤 */
.et-quick { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.et-quick-label {
  font-family: Consolas, 'SFMono-Regular', monospace;
  font-size: 10px; letter-spacing: .25em; color: var(--color-text-secondary);
}
.et-quick-chip {
  font-size: 12px; padding: 2px 13px; border-radius: 9999px; cursor: pointer;
  border: 1px dashed var(--color-border); background: transparent; color: var(--color-text-secondary);
}
.et-quick-chip:hover { border-color: var(--color-primary); color: var(--color-primary); }
.et-quick-chip.on {
  border-style: solid; border-color: var(--color-primary);
  background: var(--color-primary); color: #fff; font-weight: 600;
}
.et-quick-clear {
  font-size: 12px; border: none; background: none; cursor: pointer;
  color: var(--color-text-secondary); text-decoration: underline;
}
.et-quick-clear:hover { color: var(--color-primary); }

/* 主体双栏 */
.et-body {
  display: grid; grid-template-columns: 2fr 1.2fr; gap: 16px; align-items: stretch;
}
.et-graph-panel, .et-list-panel {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border); border-radius: 4px;
  overflow: hidden; display: flex; flex-direction: column;
}
.et-graph-panel { min-height: 640px; }
.et-panel-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 11px 16px; border-bottom: 1px dashed var(--color-border);
}
.et-panel-title { font-weight: 700; font-size: 14px; letter-spacing: .04em; }
.et-link-glyph { margin-right: 4px; }
.et-panel-hint { font-family: Consolas, monospace; font-size: 10px; letter-spacing: .12em; color: var(--color-text-secondary); }

.et-graph-panel :deep(.kg-explorer) {
  flex: 1; min-height: 0;
}

/* 加载骨架 */
.et-skel { padding: 26px; }
.et-skel-line {
  height: 12px; border-radius: 3px; margin-bottom: 14px;
  background: linear-gradient(90deg, var(--color-border) 25%, var(--color-bg-page) 50%, var(--color-border) 75%);
  background-size: 200% 100%; animation: et-shimmer 1.4s infinite;
}
@keyframes et-shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }

/* 空态 */
.et-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px; padding: 40px 20px; text-align: center;
}
.et-empty-mark { font-family: Consolas, monospace; font-size: 34px; color: var(--color-text-placeholder); }
.et-empty-t { font-weight: 700; font-size: 14px; }
.et-empty-s { font-size: 12px; color: var(--color-text-secondary); margin-bottom: 10px; }

/* 实体列表 */
.et-list-scroll {
  flex: 1; overflow-y: auto; padding: 10px 12px;
  max-height: 560px;
}
.et-list-scroll::-webkit-scrollbar { width: 5px; }
.et-list-scroll::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 3px; }

.et-row {
  padding: 10px 12px; border-radius: 3px; cursor: pointer;
  border-bottom: 1px dashed var(--color-border);
  transition: background var(--duration-fast, .15s) ease-out;
}
.et-row:hover { background: var(--color-primary-bg); }
.et-row-on {
  background: var(--color-primary-bg);
  box-shadow: inset 2px 0 0 var(--color-primary);
}
.et-triple { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 13px; }
.et-subject { font-weight: 700; }
.et-pred {
  font-family: Consolas, monospace; font-size: 10px; letter-spacing: .08em;
  border: 1px solid var(--color-primary); color: var(--color-primary);
  border-radius: 2px; padding: 0 6px;
}
.et-object { color: var(--color-text-primary); }
.et-cond { font-size: 11px; color: var(--color-text-secondary); margin-top: 3px; }
.et-meta {
  display: flex; align-items: center; gap: 12px; margin-top: 5px;
  font-family: Consolas, monospace; font-size: 10px; color: var(--color-text-secondary);
}
.et-conf {
  width: 54px; height: 3px; background: var(--color-border);
  border-radius: 2px; overflow: hidden; display: inline-block;
}
.et-conf i { display: block; height: 100%; background: var(--color-primary); }

.entity-pagination {
  display: flex; justify-content: center;
  border-top: 1px dashed var(--color-border);
  padding: 8px 12px;
}

@media (max-width: 900px) {
  .et-body { grid-template-columns: 1fr; }
  .et-filters { flex-wrap: wrap; }
  .et-input-wide { flex: 1 1 100%; }
  .et-input:not(.et-input-wide) { flex: 1; width: auto; }
  .et-graph-panel { min-height: 480px; }
}
</style>

<style>
/* 暗色主题分页可读性 (W86 修复恢复): .el-pager li 数字在暗色下继承失当 */
[data-theme="dark"] .entity-pagination .el-pager li {
  color: var(--color-text-regular) !important;
}
[data-theme="dark"] .entity-pagination .el-pager li.is-active {
  color: #fff !important;
  background-color: var(--color-primary) !important;
}
</style>
