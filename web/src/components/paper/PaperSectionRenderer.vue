<template>
  <section
    :id="`section-${section.id}`"
    class="paper-section"
    :class="[`section-level-${section.level || 1}`, `section-type-${section.type || 'normal'}`]"
    :data-section-type="section.type"
  >
    <!-- 章节标题 -->
    <header v-if="shouldShowTitle" class="section-header">
      <div class="section-title-bar"></div>
      <div class="section-title-content">
        <span v-if="sectionNumber" class="section-number">{{ sectionNumber }}</span>
        <h2 class="section-title">{{ displayTitle }}</h2>
      </div>
      <span v-if="sectionBlocksHasPage" class="section-meta">
        {{ pageRangeText }}
      </span>
    </header>

    <!-- 章节正文（References section 跳过，由下方折叠卡片渲染） -->
    <!-- v27 段落级 inline figure 锚定：在每个 paragraph block 后插入锚定的图 -->
    <div v-if="!isReferences" class="section-body">
      <template v-for="(block, i) in section.blocks" :key="i">
        <PaperBlockRenderer
          :block="block"
          :is-chinese="isChinese"
        />
        <!-- 段落级 inline figure 锚定: 在 paragraph block 后插入 -->
        <div
          v-if="block.type === 'paragraph' && getAnchoredFigures(i).length"
          class="paragraph-inline-figures"
        >
          <FigureCard
            v-for="fig in getAnchoredFigures(i)"
            :key="`fig-${fig.id}`"
            :figure="fig"
            :figure-no="fig._displayNo"
            :caption="fig.caption"
            compact
          />
        </div>
      </template>
    </div>

    <!-- 参考文献可折叠 -->
    <div v-if="isReferences" class="section-references">
      <div class="references-header">
        <span class="references-label">参考文献（共 {{ references.length }} 条）</span>
        <button class="references-toggle" @click="referencesExpanded = !referencesExpanded">
          {{ referencesExpanded ? '收起 ▴' : '展开全部 ▾' }}
        </button>
      </div>
      <ol v-if="referencesExpanded || references.length <= 5" class="references-list">
        <li v-for="(ref, i) in references" :key="i" class="reference-item">
          {{ ref }}
        </li>
      </ol>
      <ol v-else class="references-list references-list-collapsed">
        <li v-for="(ref, i) in references.slice(0, 5)" :key="i" class="reference-item">
          {{ ref }}
        </li>
      </ol>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import PaperBlockRenderer from './PaperBlockRenderer.vue'
import FigureCard from './FigureCard.vue'
import { splitReferences } from '@/utils/paperAdapter'

const props = defineProps({
  section: { type: Object, required: true },
  isChinese: { type: Boolean, default: false },
  // 兼容旧 API: section 级 inline figures（已废弃，建议用 inlineFigureAnchors）
  inlineFigures: { type: Array, default: () => [] },
  // v27 新 API: paragraph 级锚定 { paragraphId → [figures] }
  // paragraphId 格式: `${section.id}__p${paragraphIndex}`
  inlineFigureAnchors: { type: Object, default: () => ({}) },
  // v27.2: 是否显示正文内嵌图（默认 false — 推荐使用右侧图表栏）
  showInlineFigures: { type: Boolean, default: false },
  // v28 step 6 + 15: 内嵌图永远显示（不再有开关）
  // 保留 prop 是为了父组件传值，v28 step 15 后父组件永远传 true
  showInlineFigures: { type: Boolean, default: true },
  // v28 step 6: 仅显示高置信度图（confidence >= HIGH_CONFIDENCE_THRESHOLD）
  // 默认 true — vision_confidence 0.85+ 才在正文显示，避免低质量图污染阅读
  showHighConfidenceOnly: { type: Boolean, default: true },
  // v28 step 15: paper 内所有 figure registry（用于按 page 顺序算 displayNo）
  figureRegistry: { type: Array, default: () => [] },
})

// v28 step 6: confidence 阈值常量（vision model 输出 >=0.85 视为高置信度）
const HIGH_CONFIDENCE_THRESHOLD = 0.85

/**
 * 获取指定 paragraph index 锚定的 figures
 * v27.2: 默认不返回（除非 showInlineFigures=true），让右侧图表栏承担展示职责
 * v28 step 6: 增加 confidence >= 0.85 过滤（showHighConfidenceOnly=true 时）
 *
 * fig.confidence 字段来源（paperAdapter.js v28 step 4）：
 *   img.visionConfidence ?? ext.confidence ?? 0.5
 */
/**
 * v28 step 19: figure label 统一为 "Fig. N"（按 page 顺序索引从 1 开始）
 *
 * 用户原话："正文的图片就从1数字开始吧，或者说就应该按照论文原文说的标题号来展示"
 *
 * 优先级（v28 step 19）：
 * 1. `fig.figureNo` (vision model 输出的真实图号，如 "Fig. 5" 或 "Fig. 5e") → 保留
 * 2. 没 figureNo → 按 page 升序分配 "Fig. 1" / "Fig. 2" ...（用户视角的顺序）
 *
 * 重要：label **不显示页码**（页码移到 figcaption 单独展示），
 *      **不显示描述**（描述在 figcaption 完整展开）。
 *      label 就是简短的 "Fig. N"，让用户一眼看清有几张图。
 */
const _displayNoMap = computed(() => {
  const map = new Map()  // imageId → "Fig. N" 字符串
  const allFigs = props.figureRegistry || []
  // v28 step 24: 完全重算 —— 不依赖 paperAdapter._alignFigureNosWithText
  //    原因: 之前依赖 vision model 输出的 figureNo + 后端对齐逻辑，
  //    但 vision 经常给错位（536 = "Fig. 1" 与 530 重复），paperAdapter 修正不可靠
  //    现在前端直接按 page 顺序重新编号，1 张 core fig 一个 "Fig. N"
  //    保留 vision 的"Fig. Ne"子号（如 "Fig. 5e" → "Fig. 5e"），
  //    普通 "Fig. N" 重新编号避免冲突
  const isCore = (f) => f.isCoreFigure === true
    || (f.isCoreFigure !== false
      && !f.isPublisherImage
      && !['cover', 'logo', 'publisher', 'unknown'].includes(f.figureType)
      && f.kind !== 'cover' && f.kind !== 'logo')
  // 按 page 升序排序（无 page 放最后）
  const sorted = [...allFigs]
    .filter(f => isCore(f))
    .sort((a, b) => (a.page || 9999) - (b.page || 9999))
  let idx = 0
  for (const f of sorted) {
    idx += 1
    // 检查 vision 给的 figureNo 是否有"子号"（如 Fig. 5e / Fig. 3a）
    // 子号 = 数字 + 字母 格式 → 保留（用户能看到 a/b/c/d 子图）
    const figNo = f.figureNo || ''
    const hasSubLetter = /^Fig\.\s*\d+[a-z]$/i.test(figNo)
    if (hasSubLetter) {
      // 子号图：保留 vision 值（用户视角有意义）
      map.set(f.imageId ?? f.id, figNo)
    } else {
      // 普通图：按 page 顺序重新编号 Fig. 1, Fig. 2, ...
      map.set(f.imageId ?? f.id, `Fig. ${idx}`)
    }
  }
  return map
})

function getAnchoredFigures(paragraphIdx) {
  if (!props.showInlineFigures) return []
  const pid = `${props.section.id}__p${paragraphIdx}`
  const figs = props.inlineFigureAnchors[pid] || []
  const filtered = props.showHighConfidenceOnly
    ? figs.filter(f => (f.confidence ?? 0) >= HIGH_CONFIDENCE_THRESHOLD)
    : figs
  // 给每个 fig 注入 _displayNo + _page（页码）+ _captionText（原文 caption）供 FigureCard 使用
  return filtered.map(f => ({
    ...f,
    _displayNo: _displayNoMap.value.get(f.imageId ?? f.id) || 'Fig.',
    _page: f.page,
    _captionText: f.caption || f.semanticTitle || null,
    _description: f.description || f.visualSummary || null,
  }))
}

const referencesExpanded = ref(false)

const sectionNumber = computed(() => {
  const m = /^(\d+(?:\.\d+)*)\.?\s+/.exec(props.section.title || '')
  return m ? m[1] : null
})

// 如果有 sectionNumber badge，标题只显示编号后的文字（避免重复显示 2.1）
const displayTitle = computed(() => {
  const title = props.section.title || '未命名章节'
  if (sectionNumber.value) {
    // 去掉编号前缀："2.1. Experimental system" → "Experimental system"
    const stripped = title.replace(/^(\d+(?:\.\d+)*)\.?\s+/, '').trim()
    return stripped || title
  }
  return title
})

const isReferences = computed(() => props.section.type === 'references')

const references = computed(() => {
  if (!isReferences.value) return []
  const text = props.section.blocks
    .filter(b => b.type === 'paragraph')
    .map(b => b.content)
    .join('\n')
  return splitReferences(text)
})

const shouldShowTitle = computed(() => {
  // preamble 类型（开头前言）不显示 title
  return props.section.type !== 'preamble'
})

const sectionBlocksHasPage = computed(() => {
  return props.section.blocks?.some(b => b.type === 'page_marker')
})

const pageRangeText = computed(() => {
  const pages = []
  for (const b of (props.section.blocks || [])) {
    if (b.type === 'page_marker') pages.push(b.content)
  }
  if (pages.length === 0) return ''
  if (pages.length === 1) return `P${pages[0]}`
  return `P${pages[0]}-${pages[pages.length - 1]}`
})
</script>

<style scoped>
.paper-section {
  margin: 0 0 32px;
  scroll-margin-top: 80px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 18px;
  padding: 14px 0 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.section-title-bar {
  width: 4px;
  height: 22px;
  background: linear-gradient(180deg, var(--color-primary), var(--color-accent));
  border-radius: 2px;
  flex-shrink: 0;
}

.section-title-content {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex: 1;
}

.section-number {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary);
  background: var(--color-primary-bg);
  padding: 2px 10px;
  border-radius: 4px;
  flex-shrink: 0;
}

.section-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #1F2937;
  line-height: 1.4;
  word-break: break-word;
}

.section-meta {
  font-size: 12px;
  color: #9CA3AF;
  background: #F3F4F6;
  padding: 2px 8px;
  border-radius: 8px;
  white-space: nowrap;
  flex-shrink: 0;
}

.section-level-2 .section-title {
  font-size: 18px;
}

.section-level-3 .section-title {
  font-size: 16px;
}

.section-level-4 .section-title {
  font-size: 15px;
}

.section-body {
  padding: 0;
}

/* 段落级 inline figure: 在 paragraph 下方插入锚定的图 */
.paragraph-inline-figures {
  margin: 12px 0 16px;
  padding: 12px 16px;
  background: #FAFAFA;
  border: 1px solid var(--color-border-light);
  border-left: 3px solid var(--color-primary);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.paragraph-inline-figures :deep(.figure-card) {
  background: #fff;
  border-radius: 4px;
}

/* 参考文献样式 */
.section-references {
  margin-top: 16px;
  padding: 16px 20px;
  background: #FAFAFA;
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
}

.references-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.references-label {
  font-weight: 600;
  color: #1F2937;
  font-size: 14px;
}

.references-toggle {
  background: none;
  border: none;
  color: var(--color-primary);
  cursor: pointer;
  font-size: 12px;
  padding: 0;
}

.references-toggle:hover {
  text-decoration: underline;
}

.references-list {
  margin: 0;
  padding: 0 0 0 20px;
  list-style: decimal;
}

.references-list-collapsed {
  position: relative;
}

.reference-item {
  font-size: 13px;
  line-height: 1.7;
  color: #4B5563;
  margin-bottom: 8px;
  word-break: break-word;
}

/* 章节类型特殊样式 */
.section-type-abstract .section-title {
  color: var(--color-primary);
}

.section-type-conclusion {
  background: linear-gradient(135deg, #F0F9EB 0%, #FAFFF7 100%);
  border: 1px solid #C6E8B0;
  border-radius: 10px;
  padding: 16px 20px;
}

.section-type-conclusion .section-header {
  border-bottom-color: rgba(103, 194, 58, 0.2);
}

.section-type-conclusion .section-title-bar {
  background: var(--color-success);
}

.section-type-references {
  background: #FAFAFA;
  border-radius: 10px;
  padding: 16px 20px;
}
</style>
