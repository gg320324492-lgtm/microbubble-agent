<template>
  <div class="paper-detail-page">
    <!-- 加载状态 -->
    <div v-if="loading" class="paper-detail-loading">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 数据不存在 -->
    <div v-else-if="!paper" class="paper-detail-empty">
      <el-empty description="知识条目不存在" />
    </div>

    <!-- 主内容：三栏布局（左侧系统菜单由 MainLayout 提供） -->
    <div v-else class="paper-detail-layout">
      <!-- 中间主内容 -->
      <main class="paper-detail-main">
        <!-- 标题区 -->
        <PaperHeader
          :paper="paper"
          :reanalyzing="reanalyzing"
          @reanalyze="handleReanalyze"
        />

        <!-- 摘要卡片 -->
        <AbstractCard v-if="paper.abstract" :paper="paper" />

        <!-- 核心概念 / 关联主题（兼容老数据） -->
        <section v-if="paper.keyConcepts?.length || paper.relatedTopics?.length" class="paper-concepts">
          <div v-if="paper.keyConcepts?.length" class="concept-block">
            <h3 class="concept-label">核心概念</h3>
            <div class="concept-items">
              <el-tag
                v-for="c in paper.keyConcepts"
                :key="c"
                type="info"
                effect="plain"
                size="small"
                round
              >{{ c }}</el-tag>
            </div>
          </div>
          <div v-if="paper.relatedTopics?.length" class="concept-block">
            <h3 class="concept-label">关联主题</h3>
            <div class="concept-items">
              <el-tag
                v-for="t in paper.relatedTopics"
                :key="t"
                type="success"
                effect="plain"
                size="small"
                round
              >{{ t }}</el-tag>
            </div>
          </div>
        </section>

        <!-- 知识三元组（兼容老数据） -->
        <section v-if="paper.entities?.length" class="paper-entities">
          <h3 class="entities-label">知识三元组</h3>
          <div class="entities-list">
            <div v-for="(e, i) in paper.entities" :key="i" class="entity-card">
              <div class="entity-triple">
                <span class="entity-subject">{{ e.subject }}</span>
                <span class="entity-predicate">→ {{ e.predicate }} →</span>
                <span class="entity-object">{{ e.object }}</span>
              </div>
              <div v-if="e.condition" class="entity-condition">条件: {{ e.condition }}</div>
              <div class="entity-confidence">
                <el-progress
                  :percentage="Math.round((e.confidence || 0) * 100)"
                  :stroke-width="3"
                  :show-text="false"
                />
                <span class="confidence-text">{{ Math.round((e.confidence || 0) * 100) }}%</span>
              </div>
            </div>
          </div>
        </section>

        <!-- 论文正文（按章节渲染） -->
        <article id="paper-content" class="paper-article">
          <div v-if="!hasAnyContent" class="paper-no-content">
            <el-empty description="该条目暂无正文内容" :image-size="60" />
          </div>
          <PaperSectionRenderer
            v-for="section in paper.sections"
            :key="section.id"
            :section="section"
            :is-chinese="paper.isChineseHeavy"
            :inline-figures="getInlineFiguresFor(section)"
          />
        </article>

        <!-- 来源信息 -->
        <div v-if="paper.raw?.source || paper.fileName" class="paper-source">
          <span v-if="paper.raw?.source">来源：{{ paper.raw.source }}</span>
          <span v-if="paper.fileName">文件：{{ paper.fileName }}</span>
        </div>

        <!-- 多模态提取区（仅 PDF/PPTX 显示） -->
        <ExtractionPanel
          v-if="paper.filePath"
          :paper="paper"
          :figures="paper.figures"
          :formulas="paper.formulas"
          :tables="paper.tables"
          :charts="paper.extractions"
          :image-stats="imageStats"
          :loading="extractionLoading"
          :extracting="extracting"
          @extract="handleExtractMultimodal"
        />

        <!-- 知识图谱（兼容老数据） -->
        <section v-if="graphData?.nodes?.length" class="paper-graph">
          <h2 class="graph-title">🕸️ 知识图谱</h2>
          <div ref="graphRef" class="graph-container"></div>
        </section>

        <!-- 相关知识 -->
        <RelatedKnowledgeList :related="paper.relatedKnowledge" />
      </main>

      <!-- 右侧导航（sticky） -->
      <RightAnchorNav
        v-if="hasAnchors"
        :anchors="anchorList"
        :module-counts="moduleCounts"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import * as echarts from 'echarts'

import PaperHeader from '@/components/paper/PaperHeader.vue'
import AbstractCard from '@/components/paper/AbstractCard.vue'
import PaperSectionRenderer from '@/components/paper/PaperSectionRenderer.vue'
import PaperBlockRenderer from '@/components/paper/PaperBlockRenderer.vue'
import FigureCard from '@/components/paper/FigureCard.vue'
import FormulaBlock from '@/components/paper/FormulaBlock.vue'
import TableCard from '@/components/paper/TableCard.vue'
import ExtractionPanel from '@/components/paper/ExtractionPanel.vue'
import RelatedKnowledgeList from '@/components/paper/RelatedKnowledgeList.vue'
import RightAnchorNav from '@/components/paper/RightAnchorNav.vue'

import {
  normalizePaperData,
  buildAnchorTree,
  extractFigureMarkers,
} from '@/utils/paperAdapter'

const route = useRoute()
const rawKnowledge = ref(null)
const paper = ref(null)
const relatedKnowledge = ref([])
const graphData = ref({ nodes: [], edges: [] })
const loading = ref(true)
const reanalyzing = ref(false)
const graphRef = ref(null)
let chartInstance = null

// 多模态提取状态
const imageStats = ref(null)
const extracting = ref(false)
const extractionLoading = ref(false)

const hasAnyContent = computed(() => {
  if (!paper.value) return false
  return paper.value.sections?.length > 0
})

const hasAnchors = computed(() => anchorList.value.length > 0)

const anchorList = computed(() => {
  if (!paper.value) return []
  return buildAnchorTree(paper.value.sections || [])
})

const moduleCounts = computed(() => {
  if (!paper.value) return { figures: 0, extractions: 0, related: 0 }
  return {
    figures: paper.value.figures?.length || 0,
    extractions: paper.value.extractions?.length || 0,
    related: paper.value.relatedKnowledge?.length || 0,
  }
})

/**
 * 根据章节内嵌的 figure_marker 把对应图片放进章节
 */
function getInlineFiguresFor(section) {
  if (!paper.value || !section?.blocks) return []
  const figureIds = new Set()
  for (const b of section.blocks) {
    if (b.type === 'figure_marker') figureIds.add(b.content)
  }
  if (!figureIds.size) return []
  return (paper.value.figures || []).filter(f => {
    return figureIds.has(String(f.imageId)) || figureIds.has(String(f.id))
  })
}

// ============================================================
// API
// ============================================================

const fetchDetail = async () => {
  loading.value = true
  try {
    const id = route.params.id

    // 主数据 + 关联 + 多模态状态 全部并发
    const [detailRes, relRes, graphRes] = await Promise.all([
      axios.get(`/api/v1/knowledge/${id}`),
      axios.get(`/api/v1/knowledge/${id}/related`, { params: { limit: 12 } }).catch(() => ({ data: [] })),
      axios.get('/api/v1/knowledge/graph', { params: { center_id: id, depth: 1, limit: 30 } }).catch(() => ({ data: { nodes: [], edges: [] } })),
    ])

    rawKnowledge.value = detailRes.data
    relatedKnowledge.value = relRes.data || []
    graphData.value = graphRes.data || { nodes: [], edges: [] }

    // 后台异步：触发 reformat（如果还没排版过）
    if (!detailRes.data.formatted_content) {
      axios.post(`/api/v1/knowledge/${id}/reformat`).catch(() => {})
    }

    // 并行拉多模态数据
    await fetchMultimodalData(id)

    // 适配成 PaperDetail
    paper.value = normalizePaperData(detailRes.data, {
      images: imageStats.value ? window.__paperImagesCache : [],
      extractions: window.__paperExtractionsCache || [],
      related: relatedKnowledge.value,
    })

    await nextTick()
    renderGraph()
  } catch (e) {
    console.error('获取知识详情失败', e)
    ElMessage.error('获取知识详情失败')
    paper.value = null
  } finally {
    loading.value = false
  }
}

const fetchMultimodalData = async (id) => {
  extractionLoading.value = true
  try {
    const [imgRes, extRes] = await Promise.all([
      axios.get(`/api/v1/knowledge/${id}/images`).catch(() => ({ data: { items: [], total: 0, ocr_done: 0, ocr_failed: 0, ocr_pending: 0 } })),
      axios.get(`/api/v1/knowledge/${id}/extractions`, { params: { page: 1, page_size: 200 } }).catch(() => ({ data: { items: [], total: 0, by_kind: {} } })),
    ])

    const imgs = imgRes.data?.items || []
    const exts = extRes.data?.items || []

    imageStats.value = {
      total: imgs.length,
      done: imgs.filter(i => i.ocr_status === 'done').length,
      failed: imgs.filter(i => i.ocr_status === 'failed').length,
      pending: imgs.filter(i => i.ocr_status === 'pending' || i.ocr_status === 'skipped').length,
    }

    // 缓存到 window 供 normalize 使用
    window.__paperImagesCache = imgs
    window.__paperExtractionsCache = exts
  } finally {
    extractionLoading.value = false
  }
}

const handleExtractMultimodal = async () => {
  if (!paper.value) return
  extracting.value = true
  try {
    const { data } = await axios.post(`/api/v1/knowledge/${paper.value.id}/extract-multimodal`)
    if (data.ok) {
      const msg = data.skipped
        ? `未提取：${data.reason}`
        : `提取完成（${data.images_total} 张图 / ${(data.extractions?.formula || 0)} 公式 / ${(data.extractions?.table || 0)} 表格）`
      ElMessage.success(msg)
      // 重新拉数据
      await fetchMultimodalData(paper.value.id)
      paper.value = normalizePaperData(rawKnowledge.value, {
        images: window.__paperImagesCache || [],
        extractions: window.__paperExtractionsCache || [],
        related: relatedKnowledge.value,
      })
    } else {
      ElMessage.warning(data.error || data.reason || '提取失败')
    }
  } catch (e) {
    ElMessage.error('触发提取失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    extracting.value = false
  }
}

const handleReanalyze = async () => {
  reanalyzing.value = true
  try {
    await axios.post(`/api/v1/knowledge/${paper.value.id}/reanalyze`)
    ElMessage.success('已开始重新分析')
    paper.value.status = 'analyzing'
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    reanalyzing.value = false
  }
}

const renderGraph = () => {
  if (!graphRef.value || !graphData.value?.nodes?.length) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(graphRef.value)
  const nodes = graphData.value.nodes.map(n => ({
    id: n.id,
    name: n.label || n.title,
    symbolSize: Math.min(40, 15 + (n.weight || 1) * 5),
    category: n.type || 0,
  }))
  const edges = graphData.value.edges.map(e => ({
    source: e.source,
    target: e.target,
    label: { show: true, formatter: e.label || '' },
  }))
  chartInstance.setOption({
    tooltip: {},
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      force: { repulsion: 200, edgeLength: [100, 300] },
      data: nodes,
      edges: edges,
      label: { show: true, fontSize: 11 },
      lineStyle: { color: '#ccc', curveness: 0.2 },
    }],
  })
}

// 路由 id 变化时重新加载
watch(() => route.params.id, (newId) => {
  if (newId) {
    // 清空缓存
    window.__paperImagesCache = []
    window.__paperExtractionsCache = []
    fetchDetail()
  }
})

onMounted(() => fetchDetail())

onUnmounted(() => {
  if (chartInstance) chartInstance.dispose()
})
</script>

<style scoped>
.paper-detail-page {
  width: 100%;
  min-height: 100%;
  background: #F5F7FA;
  padding: 0;
  box-sizing: border-box;
}

.paper-detail-loading {
  padding: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.paper-detail-empty {
  padding: 80px 20px;
  text-align: center;
}

.paper-detail-layout {
  display: grid;
  grid-template-columns: 1fr 240px;
  gap: 24px;
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
  align-items: start;
}

@media (max-width: 1280px) {
  .paper-detail-layout {
    grid-template-columns: 1fr;
  }
}

.paper-detail-main {
  min-width: 0;
}

/* 核心概念 */
.paper-concepts {
  background: #fff;
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.concept-block {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.concept-label {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #6B7280;
  flex-shrink: 0;
  min-width: 70px;
}

.concept-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* 三元组 */
.paper-entities {
  background: #fff;
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
}

.entities-label {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: #1F2937;
}

.entities-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.entity-card {
  background: #FAFAFA;
  border-radius: 8px;
  padding: 10px 14px;
}

.entity-triple {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  font-size: 13px;
}

.entity-subject {
  color: var(--color-primary);
  font-weight: 600;
}

.entity-predicate {
  color: #6B7280;
  font-size: 12px;
}

.entity-object {
  color: #1F2937;
}

.entity-condition {
  font-size: 12px;
  color: #6B7280;
  margin-top: 4px;
}

.entity-confidence {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-text {
  font-size: 11px;
  color: #9CA3AF;
}

/* 正文容器 */
.paper-article {
  background: #fff;
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  padding: 24px 32px;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  max-width: 100%;
  overflow: hidden;
}

@media (max-width: 768px) {
  .paper-article {
    padding: 16px 20px;
  }
}

.paper-no-content {
  padding: 40px 0;
}

/* 来源信息 */
.paper-source {
  margin: 16px 0;
  padding: 10px 16px;
  background: #fff;
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  font-size: 12px;
  color: #6B7280;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

/* 知识图谱 */
.paper-graph {
  background: #fff;
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
}

.graph-title {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 700;
  color: #1F2937;
}

.graph-container {
  width: 100%;
  height: 380px;
  border-radius: 8px;
}
</style>
