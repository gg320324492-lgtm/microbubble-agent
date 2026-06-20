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

        <!-- 阅读器工具栏（v28 step 15: 仅保留字号/行距/回顶） -->
        <ReadingToolbar
          :paper="paper"
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

        <!-- 知识三元组（v28 step 50: 兼容两种字段格式）
             老格式: { subject, predicate, object, condition, confidence }
             新格式（LLM 实际输出）: { name, type, description, aliases }
             模板用 entityField() 统一取值 -->
        <section v-if="paper.entities?.length" class="paper-entities">
          <h3 class="entities-label">知识三元组（{{ paper.entities.length }}）</h3>
          <div class="entities-list">
            <div v-for="(e, i) in paper.entities" :key="i" class="entity-card">
              <div class="entity-triple">
                <span class="entity-subject">{{ entityField(e, 'subject') }}</span>
                <span class="entity-predicate">→ {{ entityField(e, 'predicate') }} →</span>
                <span class="entity-object">{{ entityField(e, 'object') }}</span>
              </div>
              <div v-if="entityField(e, 'condition')" class="entity-condition">条件: {{ entityField(e, 'condition') }}</div>
              <div v-if="e.description && !entityField(e, 'object')" class="entity-description">
                {{ e.description }}
              </div>
              <div class="entity-meta">
                <span v-if="e.type" class="entity-type">{{ e.type }}</span>
                <span v-if="e.confidence" class="entity-confidence">
                  <el-progress
                    :percentage="Math.round((e.confidence || 0) * 100)"
                    :stroke-width="3"
                    :show-text="false"
                  />
                  <span class="confidence-text">{{ Math.round((e.confidence || 0) * 100) }}%</span>
                </span>
                <span v-else class="entity-na">N/A</span>
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
            v-for="section in displaySections"
            :key="section.id"
            :section="section"
            :is-chinese="paper.isChineseHeavy"
            :inline-figures="getInlineFiguresFor(section)"
            :inline-figure-anchors="paper.inlineFigureAnchors || {}"
            :show-inline-figures="showInlineFigures"
            :show-high-confidence-only="showHighConfidenceOnly"
            :figure-registry="paper.figureRegistry || []"
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

        <!-- 知识图谱三态：success / empty / failed -->
        <section v-if="graphStatus === 'success' && graphRendered" class="paper-graph">
          <h2 class="graph-title">🕸️ 知识图谱</h2>
          <div ref="graphRef" class="graph-container"></div>
        </section>
        <section v-else-if="graphStatus === 'failed'" class="paper-graph paper-graph-empty paper-graph-failed">
          <div class="graph-empty-content">
            <el-icon class="graph-empty-icon"><CircleClose /></el-icon>
            <span class="graph-empty-text">知识图谱生成失败</span>
            <span class="graph-empty-hint">图谱数据加载异常，请稍后刷新重试</span>
          </div>
        </section>
        <section v-else class="paper-graph paper-graph-empty">
          <div class="graph-empty-content">
            <el-icon class="graph-empty-icon"><Share /></el-icon>
            <span class="graph-empty-text">该论文尚未完成知识图谱构建</span>
            <span class="graph-empty-hint">暂无实体关系数据 / not_generated</span>
          </div>
        </section>

        <!-- 相关知识 -->
        <RelatedKnowledgeList :related="paper.relatedKnowledge" />
      </main>

      <!-- 右侧导航（sticky） -->
      <div class="paper-right-column">
        <RightAnchorNav
          v-if="hasAnchors"
          :sections="anchorSections"
          :modules="anchorModules"
        />
        <!-- v28 step 10: 移除右侧本节图表栏 — 正文已内嵌图片，无需重复 -->
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Share, CircleClose } from '@element-plus/icons-vue'
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
// v28 step 10: 移除 RightImageRail（正文已自动内嵌图片，右侧重复展示已无用）
import ReadingToolbar from '@/components/paper/ReadingToolbar.vue'

import {
  normalizePaperData,
  buildAnchorTree,
  extractFigureMarkers,
  normalizeGraphData,
} from '@/utils/paperAdapter'

const route = useRoute()
const rawKnowledge = ref(null)
const paper = ref(null)

// v28 step 50: 兼容 entities 两种字段格式
//   老格式: { subject, predicate, object, condition, confidence }
//   新格式（LLM 实际输出）: { name, type, description, aliases }
//   entityField() 统一取值，老数据用 subject/predicate/object，
//   新数据用 name 替代 subject、type 替代 predicate、description 替代 object
function entityField(e, field) {
  if (!e) return ''
  if (field === 'subject') return e.subject || e.name || ''
  if (field === 'predicate') return e.predicate || e.type || ''
  if (field === 'object') return e.object || e.description || ''
  if (field === 'condition') return e.condition || ''
  return e[field] || ''
}
const relatedKnowledge = ref([])
const graphData = ref({ nodes: [], edges: [] })
const graphStatus = ref('loading')  // 'loading' | 'success' | 'empty' | 'failed'
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
  return displaySections.value.length > 0
})

/**
 * 用于正文区显示的 sections：
 * - 过滤掉 preamble / highlights / graphical_abstract / article_info / keywords
 *   （这些已经在 AbstractCard / 元信息区显示）
 * - 保留 introduction / methods / results / conclusion / references / normal / etc.
 */
const displaySections = computed(() => {
  if (!paper.value?.sections) return []
  const skipTypes = new Set(['preamble', 'highlights', 'graphical_abstract', 'article_info', 'keywords', 'abstract'])
  return paper.value.sections.filter(s => !skipTypes.has(s.type))
})

const hasAnchors = computed(() => anchorSections.value.length > 0)

const anchorSections = computed(() => {
  if (!paper.value) return []
  // 导航也用过滤后的 sections（保持与正文一致）
  const { sections } = buildAnchorTree(displaySections.value, {
    moduleCounts: moduleCounts.value,
  })
  return sections
})

const anchorModules = computed(() => {
  if (!paper.value) return []
  const { modules } = buildAnchorTree(paper.value.sections || [], {
    moduleCounts: moduleCounts.value,
  })
  return modules
})

/**
 * 当前激活 section id（v28 step 5）— 用 IntersectionObserver 检测
 *
 * 历史教训：v27.2 留了 ref 但没接 IO，实际永远是 ''。
 * v28 独立接 IO（不依赖 RightAnchorNav emit），监听所有 <section id="section-XXX"> 元素。
 */
const activeSectionId = ref('')
let sectionObserver = null

/**
 * 去除章节标题中的编号前缀（"1. Introduction" → "Introduction"）
 * 与 RightAnchorNav 保持一致
 */
function _stripNumberPrefix(title) {
  if (!title) return ''
  return String(title).replace(/^(\d+(?:\.\d+)*)\.?\s+/, '').trim() || title
}

/**
 * v28 step 5: 当前 section 相关图表（RightImageRail 数据源）
 *
 * 算法（按优先级）：
 * 1. 过滤 publisher/logo/cover（这些不进 rail）
 * 2. 如果有 activeSectionId 且该 section 有 title：
 *    - 找该 section title 与图 figure.sectionHint 的关键词匹配
 *    - 双向包含匹配（title 含 hint OR hint 含 title）
 *    - 匹配数 >= 1 → 返回这些图
 * 3. fallback：按 page 排序前 8 个（v27.2 行为）
 *
 * 优势：滚动到 "Results and Discussion" 时自动显示该 section 的图；
 * 滚动到 "Conclusion" 时切换到 Conclusion 相关图。
 */
const currentSectionFigures = computed(() => {
  if (!paper.value?.figures) return []

  // 1. 过滤核心图
  const coreFigures = (paper.value.figures || []).filter(f => {
    if (f.isPublisherImage) return false
    if (f.kind === 'cover' || f.kind === 'logo') return false
    return true
  })

  // 2. 找当前激活 section
  const activeSection = (paper.value.sections || []).find(s => s.id === activeSectionId.value)
  if (activeSection && activeSection.title) {
    const sectionTitle = _stripNumberPrefix(activeSection.title).toLowerCase()
    if (sectionTitle && sectionTitle.length > 2) {
      // 3. sectionHint 关键词匹配
      //    算法：sectionTitle 的核心词（>=4 字符）与 hint 的核心词取交集，>=1 个即匹配
      //    容忍 vision model 输出 "Results and Discussion - Oxidation Efficiency"
      //    这种完整句子（hint 不会等于 sectionTitle）
      const sectionTitleWords = sectionTitle.split(/\s+/).filter(w => w.length >= 4)
      const matched = coreFigures.filter(f => {
        const hint = (f.sectionHint || '').toLowerCase()
        if (!hint || hint.length < 3) return false
        const hintWords = hint.split(/[\s/\-,;|()]+/).filter(w => w.length >= 4)
        // 核心词重叠（任一方向都行）
        const overlap = sectionTitleWords.filter(w => hintWords.includes(w))
        if (overlap.length >= 1) return true
        // 极端情况：hint 是简短关键词（如 "Mechanism"），且 sectionTitle 也短
        if (hint.length <= 30 && sectionTitle.includes(hint)) return true
        if (sectionTitle.length <= 30 && hint.includes(sectionTitle)) return true
        return false
      })
      if (matched.length >= 1) {
        return matched.slice(0, 8)
      }
    }
  }

  // 4. fallback：按 page 排序（v27.2 行为）
  return coreFigures
    .slice()
    .sort((a, b) => (a.page || 0) - (b.page || 0))
    .slice(0, 8)
})

/**
 * v28 step 5 + 8: 独立 IO 监听 sections
 *
 * 优化（v28 step 8）：
 * 1. Hysteresis 滞后防跳变：当前 active 保持到 ratio < HYSTERESIS_LOWEST，
 *    切换新 section 需要 ratio >= ACTIVATE_THRESHOLD
 * 2. visibilityMap 随 setup 清空（旧 section id 不残留）
 * 3. rAF 节流：IO 回调高频时合并到下一帧执行
 * 4. fetchDetail 完成后强制 reconnect（route 切换时 section 元素可能未挂载）
 */
const ACTIVATE_THRESHOLD = 0.35  // 新 section 比例 >= 35% 才切到
const HYSTERESIS_LOWEST = 0.15    // 当前 active 比例 < 15% 才让位
let visibilityMap = new Map()
let rafPending = false

function setupSectionObserver() {
  if (typeof IntersectionObserver === 'undefined') return
  if (sectionObserver) {
    sectionObserver.disconnect()
    sectionObserver = null
  }
  // v28 step 8: 清空旧 map（route 切换时 section id 会变化）
  visibilityMap = new Map()
  sectionObserver = new IntersectionObserver((entries) => {
    // 先记录所有 entries 的最新 ratio
    for (const entry of entries) {
      const rawId = entry.target.id || ''
      const id = rawId.replace(/^section-/, '')
      if (!id) continue
      visibilityMap.set(id, entry.intersectionRatio)
    }
    // v28 step 8: rAF 节流（防连续触发性能浪费）
    if (rafPending) return
    rafPending = true
    requestAnimationFrame(() => {
      rafPending = false
      _recomputeActiveSection()
    })
  }, {
    rootMargin: '-80px 0px -60% 0px',
    threshold: [0, 0.1, 0.25, 0.5, 0.75, 1],
  })

  // 观察所有 section 元素
  const elements = document.querySelectorAll('[id^="section-"]')
  elements.forEach(el => sectionObserver.observe(el))
}

/**
 * v28 step 8: Hysteresis 算法的 active section 选择
 *
 * 规则：
 * - 当前 active 仍可见（ratio >= HYSTERESIS_LOWEST）→ 保持不变（防快速滚动跳变）
 * - 否则找 ratio 最高的 section，且 ratio >= ACTIVATE_THRESHOLD → 切换
 * - 没 section 满足阈值（页面顶/底部）→ 清空 activeSectionId
 */
function _recomputeActiveSection() {
  if (visibilityMap.size === 0) return
  const currentId = activeSectionId.value
  const currentRatio = currentId ? (visibilityMap.get(currentId) || 0) : 0

  // 当前 active 仍可见 → 保持
  if (currentId && currentRatio >= HYSTERESIS_LOWEST) {
    // 即便保持也要找"更好"的（处理缓慢滚动到完全可见场景）
    let bestId = currentId
    let bestRatio = currentRatio
    for (const [id, ratio] of visibilityMap.entries()) {
      if (ratio > bestRatio) {
        bestRatio = ratio
        bestId = id
      }
    }
    if (bestId !== currentId && bestRatio >= ACTIVATE_THRESHOLD) {
      activeSectionId.value = bestId
    }
    return
  }

  // 当前 active 已滚出或不存在 → 找 ratio 最高的 section
  let bestId = null
  let bestRatio = 0
  for (const [id, ratio] of visibilityMap.entries()) {
    if (ratio > bestRatio) {
      bestRatio = ratio
      bestId = id
    }
  }
  if (bestId && bestRatio >= ACTIVATE_THRESHOLD) {
    if (activeSectionId.value !== bestId) {
      activeSectionId.value = bestId
    }
  } else if (bestRatio === 0 && currentId) {
    // 所有 section 都不可见（页面顶部/底部）→ 清空
    activeSectionId.value = ''
  }
}

/**
 * watch displaySections 变化时重新 setup IO（章节数量变化）
 */
watch(displaySections, () => {
  nextTick(() => setupSectionObserver())
  // v28 step 37: 论文 sections 变化时重 typeset 数学公式
  nextTick(() => typesetMath())
}, { deep: true })

onMounted(() => {
  fetchDetail()
  // 等 sections 渲染完毕再接 IO
  nextTick(() => setupSectionObserver())
  // v28 step 37: 等 paper content 渲染完后 typeset 数学公式
  //   注意：MathJax v3 startup.typeset=true 已经处理首屏，
  //   但 SPA 路由切换到不同论文时需要重新 typeset
  nextTick(() => typesetMath())
})

// v28 step 37: typesetMath helper（懒加载 MathJax + typeset 整个 article）
async function typesetMath() {
  try {
    const { typesetMathJax } = await import('@/utils/mathFormat')
    const article = document.getElementById('paper-content')
    if (article) {
      await typesetMathJax(article)
    }
  } catch (e) {
    console.warn('[typesetMath]', e)
  }
}

onUnmounted(() => {
  if (sectionObserver) {
    sectionObserver.disconnect()
    sectionObserver = null
  }
  visibilityMap.clear()
  rafPending = false
})

const moduleCounts = computed(() => {
  if (!paper.value) return { figures: 0, extractions: 0, related: 0 }
  return {
    figures: paper.value.coreFigureCount || paper.value.figures?.length || 0,
    extractions: paper.value.extractions?.length || 0,
    related: paper.value.relatedKnowledge?.length || 0,
  }
})

/**
 * 根据章节内嵌的 figure_marker 或 inlineFigureMap 把对应图片放进章节
 *
 * v26 回归修复：过滤掉 Elsevier logo / 期刊封面 / publisher 图片，
 * 这些图不应该进正文，只保留在文末多模态总图库。
 */
/**
 * v28 step 15: 图片永远自动展示（不再有开关）
 *
 * 历史：
 * - v27.2: 默认 false，用右侧图表栏
 * - v28 step 10: 默认 true（用户 PDF 阅读器一样）
 * - v28 step 15: 永远 true，删除工具栏切换按钮
 *
 * 保留为 ref 是为了 prop 透传需要（PaperSectionRenderer 仍接收这两个 prop），
 * 实际值永远是 true，外部不能修改。
 */
const showInlineFigures = ref(true)
const showHighConfidenceOnly = ref(true)

function getInlineFiguresFor(section) {
  if (!paper.value || !section) return []

  // v28 step 14 修复：之前用 paper.inlineFigureMap（旧 section 级 API），
  //    且要求 figureNo 存在（OCR 没识别 figureNo 的图全部被过滤掉）
  //    改为读 paper.inlineFigureAnchors（paragraph 级 API，含 L1/L2/L3 全部匹配结果），
  //    放宽过滤（只要不是 publisher/logo，figureNo 为 null 也允许）
  const isInlineEligible = (f) => {
    if (!f) return false
    if (f.isPublisherImage) return false
    if (f.kind === 'cover' || f.kind === 'logo') return false
    if (['cover', 'logo', 'publisher', 'unknown'].includes(f.figureType)) return false
    return true
  }

  // 主路径：从 inlineFigureAnchors 找该 section 的所有 paragraph figures
  // 格式: { 'sectionId__p0': [fig, ...], 'sectionId__p1': [fig, ...] }
  const anchors = paper.value.inlineFigureAnchors || {}
  const sectionFigures = []
  for (const [pid, figs] of Object.entries(anchors)) {
    if (pid.startsWith(`${section.id}__p`)) {
      for (const f of figs) {
        if (isInlineEligible(f)) sectionFigures.push(f)
      }
    }
  }
  if (sectionFigures.length) return sectionFigures

  // 兜底：figure_marker blocks（兼容旧 [FIGURE:N] 占位符）
  const figureIds = new Set()
  for (const b of (section.blocks || [])) {
    if (b.type === 'figure_marker') figureIds.add(b.content)
  }
  if (!figureIds.size) return []
  return (paper.value.figures || []).filter(f => {
    if (!isInlineEligible(f)) return false
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
      axios.get('/api/v1/knowledge/graph', { params: { center_id: id, depth: 1, limit: 30 } })
        .then(r => { graphStatus.value = 'success'; return r })
        .catch(e => { graphStatus.value = 'failed'; return { data: { nodes: [], edges: [] } } }),
    ])

    rawKnowledge.value = detailRes.data
    relatedKnowledge.value = relRes.data || []
    graphData.value = graphRes.data || { nodes: [], edges: [] }
    if (graphStatus.value !== 'failed') {
      // 用 normalizeGraphData 判断是否有可渲染的节点
      const normalized = normalizeGraphData(graphData.value)
      graphStatus.value = normalized._status === 'success' ? 'success' : 'empty'
    }

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

    // 调试钩子（开发时启用，生产时注释）
    // window.__PAPER_DEBUG__ = { ... }
    // console.log('[PaperDetail DEBUG]', window.__PAPER_DEBUG__)

    await nextTick()
    renderGraph()
    // v28 step 5: sections 渲染完成后接入 IO（监听滚动到哪个 section）
    setupSectionObserver()
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
    // 不再写 paper.value.status = 'analyzing' —— 后端 _analyze_and_embed 异步任务会
    // 设置 knowledge.analysis_status = "analyzing"，前端通过定时 fetchDetail 轮询更新状态
    // (否则 paper.value.status 永久卡在 analyzing，右上角"分析中"标签不消失)
    startReanalyzePolling()
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    reanalyzing.value = false
  }
}

// v28 step 30: reanalyze 后定时轮询 fetchDetail，等后端 analysis_status 变化
// 之前: paper.value.status = 'analyzing' 永久不更新，右上角"分析中"标签不消失
// 现在: 每 3s 拉一次 fetchDetail 直到 paper.status !== 'analyzing'
const reanalyzePollingTimer = ref(null)
const startReanalyzePolling = () => {
  if (reanalyzePollingTimer.value) clearInterval(reanalyzePollingTimer.value)
  let count = 0
  reanalyzePollingTimer.value = setInterval(async () => {
    count += 1
    await fetchDetail()
    // 最多轮询 60 次（3 分钟），超时自动停止
    if (paper.value?.status !== 'analyzing' || count > 60) {
      clearInterval(reanalyzePollingTimer.value)
      reanalyzePollingTimer.value = null
    }
  }, 3000)
}

const graphRendered = ref(false)

const renderGraph = () => {
  if (!graphRef.value || !graphData.value?.nodes?.length) {
    graphRendered.value = false
    return
  }
  try {
    if (chartInstance) chartInstance.dispose()
    chartInstance = echarts.init(graphRef.value)
    // 使用 normalizeGraphData 适配多种字段名（id/node_id/label/value 等）
    const normalized = normalizeGraphData(graphData.value)
    if (import.meta.env.DEV) {
      console.debug('[KnowledgeGraph] normalized:', normalized._status, 'nodes:', normalized.nodes.length, 'links:', normalized.links.length)
    }
    if (!normalized.nodes.length) {
      graphRendered.value = false
      return
    }
    chartInstance.setOption({
      tooltip: { trigger: 'item' },
      legend: normalized.categories?.length > 1 ? { data: normalized.categories.map(c => c.name) } : undefined,
      series: [{
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        force: { repulsion: 200, edgeLength: [100, 300] },
        data: normalized.nodes,
        links: normalized.links,
        categories: normalized.categories,
        label: { show: true, fontSize: 11 },
        lineStyle: { color: '#ccc', curveness: 0.2 },
      }],
    })
    graphRendered.value = true
  } catch (e) {
    console.warn('知识图谱渲染失败，降级为空状态:', e)
    graphRendered.value = false
  }
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

// 注意: onMounted + onUnmounted 已合并到上方 v28 step 5 IO setup 处（line 363+）

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

/* 右侧栏: 章节导航 + 图表栏 stack (v27.2) */
.paper-right-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: sticky;
  top: 24px;
  align-self: start;
  max-height: calc(100vh - 48px);
  overflow-y: auto;
}

.paper-right-rail {
  /* RightImageRail 自身已有 sticky，由父级控制滚动 */
  position: relative;
  top: auto;
  max-height: none;
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

/* v28 step 50: 新格式字段 (type/description) 样式 */
.entity-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
}

.entity-type {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 8px;
  background: rgba(59, 130, 246, 0.08);
  color: #2563EB;
  font-weight: 500;
}

.entity-description {
  font-size: 12px;
  color: #6B7280;
  margin-top: 4px;
  line-height: 1.5;
}

.entity-na {
  font-size: 11px;
  color: #9CA3AF;
  background: #F3F4F6;
  padding: 1px 6px;
  border-radius: 8px;
}

/* 正文容器（v26 回归修复：去掉 820px 限制，恢复 1180-1280px 阅读宽度） */
.paper-article {
  background: #fff;
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  padding: 32px 44px;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  max-width: 100%;       /* 恢复撑满主列，不再 820px 居中挤压 */
  overflow: hidden;
}

.paper-article :deep(.block-paragraph) {
  font-size: 16px;
  line-height: 1.85;
  color: #1F2937;
  margin: 0 0 16px;
  word-break: break-word;
  overflow-wrap: break-word;
  text-indent: 0;
  max-width: 100%;
}

.paper-article :deep(.section-title) {
  margin-top: 36px;
  margin-bottom: 20px;
  scroll-margin-top: 80px;
}

.paper-article :deep(.section-title h2) {
  font-size: 22px;
  line-height: 1.4;
}

.paper-article :deep(.section-level-2 .section-title h2) {
  font-size: 18px;
}

.paper-article :deep(.section-body) {
  margin-bottom: 24px;
}

@media (max-width: 768px) {
  .paper-article {
    padding: 20px;
  }
  .paper-article :deep(.block-paragraph) {
    font-size: 15.5px;
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

/* 知识图谱无数据时的轻量空状态 */
.paper-graph-empty {
  min-height: 100px;
  max-height: 140px;
  height: auto;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #FAFAFA;
  border: 1px dashed var(--color-border-light);
}

.graph-empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 20px 16px;
}

.graph-empty-icon {
  font-size: 28px;
  color: #D1D5DB;
  margin-bottom: 4px;
}

.graph-empty-text {
  font-size: 13px;
  font-weight: 500;
  color: #6B7280;
}

.graph-empty-hint {
  font-size: 12px;
  color: #9CA3AF;
}

.paper-graph-failed {
  border-color: #fde2e2;
  background: #fef0f0;
}

.paper-graph-failed .graph-empty-icon {
  color: var(--color-danger);
}

.paper-graph-failed .graph-empty-text {
  color: var(--color-danger);
}
</style>
