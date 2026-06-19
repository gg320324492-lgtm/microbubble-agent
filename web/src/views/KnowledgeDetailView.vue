<template>
  <div class="knowledge-detail-page">
    <!-- 顶部导航 -->
    <div class="detail-topbar">
      <el-button text @click="$router.push('/knowledge')">
        <el-icon><ArrowLeft /></el-icon> 返回知识库
      </el-button>
      <el-button
        v-if="knowledge && knowledge.analysis_status === 'failed'"
        size="small"
        type="danger"
        plain
        :loading="reanalyzing"
        @click="handleReanalyze"
      >重新分析</el-button>
    </div>

    <div v-if="loading" class="detail-loading">
      <el-skeleton :rows="10" animated />
    </div>

    <template v-else-if="knowledge">
      <!-- 标题 -->
      <h1 class="detail-title">{{ knowledge.title }}</h1>

      <!-- 元信息 -->
      <div class="detail-meta">
        <span class="category-badge">{{ knowledge.category || '未分类' }}</span>
        <span v-if="knowledge.knowledge_type" class="type-badge">{{ knowledge.knowledge_type }}</span>
        <span class="detail-date">{{ formatDate(knowledge.created_at) }}</span>
        <el-tag v-if="knowledge.analysis_status === 'analyzing'" size="small" type="warning">分析中</el-tag>
        <el-tag v-if="knowledge.auto_researched" size="small" type="success">自主研究</el-tag>
      </div>

      <!-- 标签 -->
      <div v-if="knowledge.tags?.length" class="detail-tags">
        <span v-for="tag in knowledge.tags" :key="tag" class="tag-chip">{{ tag }}</span>
      </div>

      <!-- 审阅提醒 -->
      <div v-if="knowledge.needs_review" class="detail-review-warning">
        <span>该条目与其他知识存在矛盾，待人工审阅</span>
      </div>

      <!-- 核心概念 -->
      <div v-if="knowledge.key_concepts?.length || knowledge.related_topics?.length" class="detail-analysis">
        <div v-if="knowledge.key_concepts?.length" class="analysis-section">
          <span class="analysis-label">核心概念</span>
          <div class="analysis-items">
            <span v-for="c in knowledge.key_concepts" :key="c" class="concept-chip">{{ c }}</span>
          </div>
        </div>
        <div v-if="knowledge.related_topics?.length" class="analysis-section">
          <span class="analysis-label">关联主题</span>
          <div class="analysis-items">
            <span v-for="t in knowledge.related_topics" :key="t" class="topic-chip">{{ t }}</span>
          </div>
        </div>
      </div>

      <!-- 知识三元组 -->
      <div v-if="knowledge.entities?.length" class="detail-entities">
        <div class="entities-label">知识三元组</div>
        <div class="entities-grid">
          <div v-for="(e, i) in knowledge.entities" :key="i" class="entity-card">
            <div class="entity-triple">
              <span class="entity-subject">{{ e.subject }}</span>
              <span class="entity-predicate">→ {{ e.predicate }} →</span>
              <span class="entity-object">{{ e.object }}</span>
            </div>
            <div v-if="e.condition" class="entity-condition">条件: {{ e.condition }}</div>
            <div class="entity-confidence">
              <el-progress :percentage="(e.confidence * 100).toFixed(0)" :stroke-width="4" :show-text="false" />
            </div>
          </div>
        </div>
      </div>

      <!-- AI 摘要 -->
      <div v-if="knowledge.summary" class="detail-summary">
        <div class="summary-label">AI 摘要</div>
        <div class="summary-text">{{ knowledge.summary }}</div>
      </div>

      <!-- 正文 -->
      <div class="detail-body">
        <div
          v-if="knowledge.formatted_content"
          class="detail-content markdown-body"
          v-html="renderMarkdown(knowledge.formatted_content)"
        ></div>
        <div v-else class="detail-content">{{ knowledge.content }}</div>
      </div>

      <!-- 2026-06-19 Phase 7: 多模态提取区（图片 / 公式 / 表格 / 图表） -->
      <div v-if="knowledge.file_path" class="detail-multimodal">
        <div class="multimodal-header">
          <h2 class="multimodal-title">🖼️ 多模态提取</h2>
          <el-button
            v-if="!hasMultimodal"
            size="small"
            type="primary"
            plain
            :loading="extracting"
            @click="handleExtractMultimodal"
          >
            <el-icon><MagicStick /></el-icon> 触发图片/公式/表格提取
          </el-button>
        </div>
        <el-tabs v-if="hasMultimodal" v-model="activeMultimodalTab" class="multimodal-tabs">
          <el-tab-pane name="images" :label="`图片 (${imageStats.total})`" lazy>
            <KnowledgeImageGallery
              :knowledge-id="knowledge.id"
              :show-trigger="false"
              empty-text="该知识条目暂无提取图片"
              @updated="onGalleryUpdated"
            />
          </el-tab-pane>
          <el-tab-pane name="extractions" :label="`公式/表格/图表 (${extractionTotal})`" lazy>
            <KnowledgeExtractionsPanel
              :knowledge-id="knowledge.id"
              :show-trigger="false"
              empty-text="该知识条目暂无公式/表格/图表提取"
              @updated="onExtractionsUpdated"
            />
          </el-tab-pane>
        </el-tabs>
        <div v-else class="multimodal-empty">
          <el-empty
            description="该知识条目尚未触发多模态提取（仅 PDF/PPTX 文件可提取）"
            :image-size="80"
          />
        </div>
      </div>

      <!-- 来源 -->
      <div v-if="knowledge.source || knowledge.file_name" class="detail-source">
        <div v-if="knowledge.source">来源：{{ knowledge.source }}</div>
        <div v-if="knowledge.file_name">文件：{{ knowledge.file_name }}</div>
      </div>

      <!-- 相关知识 -->
      <div v-if="relatedKnowledge.length > 0" class="detail-related">
        <div class="related-title">相关知识</div>
        <div
          v-for="rel in relatedKnowledge"
          :key="rel.id"
          class="related-item"
          @click="$router.push('/knowledge/' + rel.id)"
        >
          <div class="related-header">
            <span class="related-item-title">{{ rel.title }}</span>
            <el-tag size="small" :type="relationTagType(rel.relation_type)">
              {{ rel.relation_type }} {{ (rel.score * 100).toFixed(0) }}%
            </el-tag>
          </div>
          <div v-if="rel.reason" class="related-reason">{{ rel.reason }}</div>
        </div>
      </div>

      <!-- 知识图谱 -->
      <div v-if="graphData.nodes?.length > 0" class="detail-graph">
        <div class="graph-title">知识图谱</div>
        <div ref="graphRef" class="graph-container"></div>
      </div>
    </template>

    <div v-else class="detail-empty">
      <el-empty description="知识条目不存在" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, MagicStick } from '@element-plus/icons-vue'
import axios from 'axios'
import { formatDate } from '@/utils/format'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import * as echarts from 'echarts'
import KnowledgeImageGallery from '@/components/knowledge/KnowledgeImageGallery.vue'
import KnowledgeExtractionsPanel from '@/components/knowledge/KnowledgeExtractionsPanel.vue'

const route = useRoute()
const knowledge = ref(null)
const relatedKnowledge = ref([])
const graphData = ref({ nodes: [], edges: [] })
const loading = ref(true)
const reanalyzing = ref(false)
const graphRef = ref(null)
let chartInstance = null

// Phase 7: 多模态提取
const hasMultimodal = ref(false)
const imageStats = ref({ total: 0, done: 0, failed: 0, pending: 0 })
const extractionTotal = ref(0)
const extracting = ref(false)
const activeMultimodalTab = ref('images')

const handleExtractMultimodal = async () => {
  if (!knowledge.value) return
  extracting.value = true
  try {
    const { data } = await axios.post(`/api/v1/knowledge/${knowledge.value.id}/extract-multimodal`)
    if (data.ok) {
      const msg = data.skipped
        ? `未提取：${data.reason}`
        : `提取完成（${data.images_total} 张图 / ${(data.extractions?.formula || 0)} 公式 / ${(data.extractions?.table || 0)} 表格）`
      ElMessage.success(msg)
      hasMultimodal.value = !data.skipped
      // 切换到对应 tab 让用户立刻看到结果
      if (!data.skipped && (data.extractions?.formula || data.extractions?.table || data.extractions?.chart)) {
        activeMultimodalTab.value = 'extractions'
      }
    } else {
      ElMessage.warning(data.error || data.reason || '提取失败')
    }
  } catch (e) {
    ElMessage.error('触发提取失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    extracting.value = false
  }
}

const onGalleryUpdated = (stats) => {
  if (stats) imageStats.value = stats
}

const onExtractionsUpdated = (info) => {
  if (info?.total != null) extractionTotal.value = info.total
}

// 检测知识是否已有多模态提取
const checkMultimodalStatus = async () => {
  if (!knowledge.value?.file_path) return
  try {
    const [imgRes, extRes] = await Promise.all([
      axios.get(`/api/v1/knowledge/${knowledge.value.id}/images`),
      axios.get(`/api/v1/knowledge/${knowledge.value.id}/extractions`, { params: { page: 1, page_size: 1 } }),
    ])
    const imgs = imgRes.data?.items || []
    imageStats.value = {
      total: imgs.length,
      done: imgs.filter((i) => i.ocr_status === 'done').length,
      failed: imgs.filter((i) => i.ocr_status === 'failed').length,
      pending: imgs.filter((i) => i.ocr_status === 'pending' || i.ocr_status === 'skipped').length,
    }
    extractionTotal.value = extRes.data?.total || 0
    hasMultimodal.value = imgs.length > 0 || extractionTotal.value > 0
  } catch (e) {
    // 静默 — 多模态状态是辅助信息，不影响主流程
  }
}

const renderMarkdown = (text) => {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text))
}

const relationTagType = (type) => {
  const map = { similar: 'success', supplements: 'warning', extends: '', supports: '', contradicts: 'danger', method_inherits: 'primary', cites: 'info', prerequisite: 'warning', compares: 'primary' }
  return map[type] || 'info'
}

const fetchDetail = async () => {
  loading.value = true
  try {
    const id = route.params.id
    const { data } = await axios.get(`/api/v1/knowledge/${id}`)
    knowledge.value = data
    // 无排版内容时触发后台排版
    if (!data.formatted_content) {
      axios.post(`/api/v1/knowledge/${id}/reformat`).catch(() => {})
    }
    // 并行获取关联和图谱
    const [relRes, graphRes] = await Promise.all([
      axios.get(`/api/v1/knowledge/${id}/related`, { params: { limit: 8 } }),
      axios.get('/api/v1/knowledge/graph', { params: { center_id: id, depth: 1, limit: 30 } }),
    ])
    relatedKnowledge.value = relRes.data || []
    graphData.value = graphRes.data || { nodes: [], edges: [] }
    await nextTick()
    renderGraph()
    await checkMultimodalStatus()
  } catch (e) {
    ElMessage.error('获取知识详情失败')
  } finally {
    loading.value = false
  }
}

const handleReanalyze = async () => {
  reanalyzing.value = true
  try {
    await axios.post(`/api/v1/knowledge/${knowledge.value.id}/reanalyze`)
    ElMessage.success('已开始重新分析')
    knowledge.value.analysis_status = 'analyzing'
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    reanalyzing.value = false
  }
}

const renderGraph = () => {
  if (!graphRef.value || !graphData.value.nodes?.length) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(graphRef.value)
  const nodes = graphData.value.nodes.map(n => ({
    id: n.id, name: n.label || n.title, symbolSize: Math.min(40, 15 + (n.weight || 1) * 5),
    category: n.type || 0
  }))
  const edges = graphData.value.edges.map(e => ({
    source: e.source, target: e.target, label: { show: true, formatter: e.label || '' }
  }))
  chartInstance.setOption({
    tooltip: {},
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      force: { repulsion: 200, edgeLength: [100, 300] },
      data: nodes, edges: edges,
      label: { show: true, fontSize: 11 },
      lineStyle: { color: '#ccc', curveness: 0.2 }
    }]
  })
}

watch(() => route.params.id, () => {
  if (route.params.id) fetchDetail()
})

onMounted(() => fetchDetail())
onUnmounted(() => { if (chartInstance) chartInstance.dispose() })
</script>

<style scoped>
.knowledge-detail-page {
  max-width: 860px;
  margin: 0 auto;
  padding-bottom: var(--space-8);
}

.detail-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.detail-loading {
  padding: var(--space-8);
}

.detail-title {
  font-size: 1.5em;
  font-weight: 700;
  margin-bottom: var(--space-3);
  line-height: 1.4;
  color: var(--color-text-primary);
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}

.category-badge {
  background: var(--color-primary);
  color: #fff;
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
}

.type-badge {
  background: var(--color-accent);
  color: #fff;
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
}

.detail-date {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.detail-tags {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}

.tag-chip {
  background: var(--color-bg-page);
  color: var(--color-text-secondary);
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  border: 1px solid var(--color-border);
}

.detail-review-warning {
  background: #fef0f0;
  border: 1px solid #fab6b6;
  color: #c45656;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
  font-size: var(--font-size-sm);
}

.detail-analysis {
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin-bottom: var(--space-4);
}

.analysis-section {
  margin-bottom: var(--space-2);
}

.analysis-label {
  font-weight: 600;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  display: block;
  margin-bottom: var(--space-1);
}

.analysis-items {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.concept-chip {
  background: #e6f7ff;
  color: #1890ff;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}

.topic-chip {
  background: #f6ffed;
  color: #52c41a;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}

.detail-entities {
  margin-bottom: var(--space-4);
}

.entities-label {
  font-weight: 600;
  margin-bottom: var(--space-2);
}

.entities-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.entity-card {
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  border: 1px solid var(--color-border);
}

.entity-triple {
  font-size: var(--font-size-sm);
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.entity-subject { color: var(--color-primary); font-weight: 600; }
.entity-predicate { color: var(--color-text-secondary); }
.entity-object { color: var(--color-text-primary); }

.entity-condition {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: var(--space-1);
}

.entity-confidence {
  margin-top: var(--space-1);
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.detail-summary {
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: var(--radius-md);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}

.summary-label {
  font-weight: 600;
  margin-bottom: var(--space-2);
  color: #d48806;
}

.summary-text {
  font-size: var(--font-size-base);
  line-height: 1.7;
}

.detail-body {
  margin-bottom: var(--space-4);
}

.detail-content {
  font-size: var(--font-size-base);
  line-height: 1.8;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  background: var(--color-bg-page);
  padding: var(--space-4);
  border-radius: var(--radius-md);
}

.markdown-body {
  font-size: var(--font-size-base);
  line-height: 1.8;
  color: var(--color-text-primary);
  background: var(--color-bg-page);
  padding: var(--space-4) var(--space-6);
  border-radius: var(--radius-md);
}

.markdown-body :deep(h1) { font-size: 1.5em; font-weight: 700; margin: 1.2em 0 0.6em; padding-bottom: 0.3em; border-bottom: 2px solid var(--color-border); }
.markdown-body :deep(h2) { font-size: 1.3em; font-weight: 600; margin: 1em 0 0.5em; }
.markdown-body :deep(h3) { font-size: 1.1em; font-weight: 600; margin: 0.8em 0 0.4em; }
.markdown-body :deep(p) { margin: 0.5em 0; text-indent: 2em; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 2em; margin: 0.4em 0; }
.markdown-body :deep(li) { margin: 0.2em 0; }
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; margin: 0.8em 0; font-size: 0.9em; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid var(--color-border); padding: 0.4em 0.6em; text-align: left; }
.markdown-body :deep(th) { background: var(--color-bg-page); font-weight: 600; }
.markdown-body :deep(blockquote) { border-left: 3px solid var(--color-primary); margin: 0.6em 0; padding: 0.3em 1em; color: var(--color-text-secondary); }
.markdown-body :deep(sub), .markdown-body :deep(sup) { font-size: 0.8em; }
.markdown-body :deep(img) { max-width: 100%; border-radius: var(--radius-md); margin: 1em 0; }

.detail-source {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.detail-related {
  margin-top: var(--space-6);
}

.related-title {
  font-weight: 600;
  font-size: 1.1em;
  margin-bottom: var(--space-3);
}

.related-item {
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-2);
  cursor: pointer;
  transition: box-shadow var(--duration-fast);
}

.related-item:hover {
  box-shadow: var(--shadow-sm);
}

.related-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.related-item-title {
  font-weight: 500;
  color: var(--color-primary);
}

.related-reason {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-top: var(--space-1);
}

.detail-graph {
  margin-top: var(--space-6);
}

.graph-title {
  font-weight: 600;
  font-size: 1.1em;
  margin-bottom: var(--space-3);
}

.graph-container {
  width: 100%;
  height: 400px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.detail-empty {
  padding: var(--space-16);
  text-align: center;
}

/* 2026-06-19 Phase 7: 多模态区样式 */
.detail-multimodal {
  margin-top: var(--space-6);
  padding: var(--space-4);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.multimodal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
  gap: var(--space-2);
}

.multimodal-title {
  font-weight: 600;
  font-size: 1.1em;
  margin: 0;
}

.multimodal-tabs {
  margin-top: var(--space-2);
}

.multimodal-empty {
  padding: var(--space-4) 0;
}
</style>
