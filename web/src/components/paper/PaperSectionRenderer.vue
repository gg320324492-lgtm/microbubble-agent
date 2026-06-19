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
            :figure-no="`图 ${fig.figureNo || fig.id}`"
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
})

/**
 * 获取指定 paragraph index 锚定的 figures
 * v27.2: 默认不返回（除非 showInlineFigures=true），让右侧图表栏承担展示职责
 */
function getAnchoredFigures(paragraphIdx) {
  if (!props.showInlineFigures) return []
  const pid = `${props.section.id}__p${paragraphIdx}`
  return props.inlineFigureAnchors[pid] || []
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
