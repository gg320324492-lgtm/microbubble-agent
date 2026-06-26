<template>
  <div class="paper-block" :class="blockClasses">
    <!-- v28 step 13: page_marker 改为不可见（仅作 page 标记供 L3 图片插入用） -->
    <!-- 之前显示居中"Page 3"标签，PDF 阅读体验突兀；现在用最小占位 -->
    <div
      v-if="block.type === 'page_marker'"
      class="block-page-marker-hidden"
      :data-page="block.content"
      :aria-label="`page ${block.content}`"
    ></div>

    <!-- 图表占位符 -->
    <div
      v-else-if="block.type === 'figure_marker'"
      :id="`figure-marker-${block.content}`"
      class="block-figure-marker"
    >
      <el-icon><Picture /></el-icon>
      <span class="figure-label">图 {{ block.content }}</span>
      <span v-if="block.page" class="figure-page">P{{ block.page }}</span>
    </div>

    <!-- v28 step 109: image_anchor 块（vision layout 输出的 inline 图片锚点）→ 用 FigureCard 直接显示图 -->
    <div
      v-else-if="block.type === 'image_anchor'"
      class="block-image-anchor"
      :data-page="block.page"
      :data-figure-no="block.figure_no || ''"
    >
      <FigureCard
        v-if="resolvedFigure"
        :figure="resolvedFigure"
        :figure-no="resolvedFigure._displayNo || block.figure_no || ''"
        :caption="resolvedFigure._captionText || block.caption || ''"
      />
      <div v-else class="image-anchor-fallback">
        <el-icon><Picture /></el-icon>
        <span>图 {{ block.figure_no || '?' }}（P{{ block.page || '?' }}）</span>
        <small class="image-anchor-hint">图片元数据缺失，仅显示占位</small>
      </div>
    </div>

    <!-- 段落（含 auto-link） -->
    <p
      v-else-if="block.type === 'paragraph'"
      class="block-paragraph"
      :class="{ 'block-chinese': isChinese }"
      v-html="renderedContent"
    ></p>

    <!-- v28 step 38: Markdown 表格 -->
    <div
      v-else-if="block.type === 'table'"
      class="block-table-wrapper"
      v-html="renderedContent"
    ></div>

    <!-- 标题（section 内部小标题） -->
    <h4 v-else-if="block.type === 'heading'" class="block-heading">
      {{ block.content }}
    </h4>

    <!-- v28 step 71: Q&A 卡片（问题块） -->
    <div v-else-if="block.type === 'qa_question'" class="qa-question-card">
      <div class="qa-icon qa-icon-question">Q</div>
      <div class="qa-content">
        <div class="qa-label">问题</div>
        <div class="qa-text" v-html="renderedQAContent"></div>
      </div>
    </div>

    <!-- v28 step 71: Q&A 卡片（回答块，支持 markdown） -->
    <div v-else-if="block.type === 'qa_answer'" class="qa-answer-card">
      <div class="qa-icon qa-icon-answer">A</div>
      <div class="qa-content">
        <div class="qa-label">回答</div>
        <div class="qa-text" v-html="renderedQAContent"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import FigureCard from './FigureCard.vue'
import { autoLinkContent } from '@/utils/paperAdapter'
import { formatChemicalText } from '@/utils/chemFormat'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  block: { type: Object, required: true },
  isChinese: { type: Boolean, default: false },
  // v28 step 109: figureRegistry 传给 PaperBlockRenderer 查找 image_anchor 对应的图
  figureRegistry: { type: Array, default: () => [] },
})

// v28 step 109: 根据 block.figure_no + block.page 在 figureRegistry 里找对应图
//   block 是 vision 输出的 image_anchor（page, figure_no, caption）
//   figureRegistry 里的 fig 用 figureNo / pageNumber / imageId 匹配
const resolvedFigure = computed(() => {
  if (props.block.type !== 'image_anchor') return null
  const targetPage = props.block.page
  const targetFigNo = props.block.figure_no
  const targetCaption = (props.block.caption || '').trim()
  const targetCaption50 = targetCaption.slice(0, 50)
  const targetCaption30 = targetCaption.slice(0, 30)

  // 优先级 1：figureNo + page 精确匹配
  if (targetFigNo) {
    for (const fig of props.figureRegistry) {
      if (fig.figureNo === targetFigNo && (fig.page === targetPage || fig.pageNumber === targetPage || !targetPage)) {
        return { ...fig, _displayNo: fig.figureNo, _captionText: targetCaption || fig.caption || '' }
      }
    }
  }
  // 优先级 2：caption 前 50 字符 + page 匹配
  if (targetCaption50) {
    for (const fig of props.figureRegistry) {
      const figPage = fig.page || fig.pageNumber
      const figCap = (fig.caption || '').slice(0, 50)
      if (figCap && figCap === targetCaption50 && (figPage === targetPage || !targetPage)) {
        return { ...fig, _displayNo: fig.figureNo || targetFigNo, _captionText: targetCaption || fig.caption || '' }
      }
    }
  }
  // 优先级 3：caption 前 30 字符 + page 匹配
  if (targetCaption30) {
    for (const fig of props.figureRegistry) {
      const figPage = fig.page || fig.pageNumber
      const figCap = (fig.caption || '').slice(0, 30)
      if (figCap && figCap === targetCaption30 && (figPage === targetPage || !targetPage)) {
        return { ...fig, _displayNo: fig.figureNo || targetFigNo, _captionText: targetCaption || fig.caption || '' }
      }
    }
  }
  // 优先级 4：仅 page 匹配（兜底）
  if (targetPage) {
    for (const fig of props.figureRegistry) {
      if (fig.page === targetPage || fig.pageNumber === targetPage) {
        return { ...fig, _displayNo: fig.figureNo || targetFigNo, _captionText: targetCaption || fig.caption || '' }
      }
    }
  }
  return null
})

const blockClasses = computed(() => ({
  'block-page': props.block.type === 'page_marker',
  'block-figure-marker': props.block.type === 'figure_marker',
  'block-paragraph-wrapper': props.block.type === 'paragraph',
}))

const renderedContent = computed(() => {
  const raw = props.block.content || ''
  // v28 step 38: Markdown 表格特殊处理（直接转 HTML，不用 autoLinkContent）
  if (props.block.type === 'table') {
    return renderMarkdownTable(raw)
  }
  // v28 step 61: 检测是否含 Markdown 列表结构（- / 1. / * 开头）
  //   之前完全靠 autoLinkContent（只 escape + URL/DOI 链接），列表项被压成纯文本
  //   视觉上"挤一行"，GFM task list `- [ ]` 也不会变成 checkbox
  //   修复：含 list 结构时先链接纯文本 URL/DOI，再 marked.parse 解析 list 结构
  //   marked.parse 会自动 escape < > & 字符，且保留已生成的 <a> 标签
  const hasMarkdownList = /(^|\n)\s*(?:[-*+]\s|\d+\.\s)/.test(raw)
  if (hasMarkdownList) {
    const formatted = props.isChinese ? raw : formatChemicalText(raw)
    // 第一步：链接纯文本 URL/DOI（不 escape，让 marked 处理）
    const linked = _linkPlainText(formatted)
    // 第二步：marked 解析 list + escape
    return renderMarkdown(linked)
  }
  // v28 step 41: KaTeX auto-render 自动扫描 $..$ / $$..$$，
  // 这里不需要手工包 <span class="math">，只需 escape + link 即可。
  // KaTeX typeset 由 KnowledgeDetailView.typesetMath() 在 onMounted / watch 触发。
  const formatted = props.isChinese ? raw : formatChemicalText(raw)
  return autoLinkContent(formatted)
})

// v28 step 71: QA 块专用渲染（marked 解析 markdown + 保留代码块/列表）
const renderedQAContent = computed(() => {
  const raw = props.block.content || ''
  if (props.block.type === 'qa_question') {
    // 问题直接渲染（无 markdown，保持纯文本）
    return escapeHtmlSimple(raw)
  }
  if (props.block.type === 'qa_answer') {
    // 回答走 marked.parse（支持 markdown 格式）
    return renderMarkdown(raw)
  }
  return ''
})

function escapeHtmlSimple(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

/**
 * v28 step 61: 仅做 DOI/URL/邮箱链接，不 escape HTML
 * 后续 marked.parse 会 escape < > & 字符，且保留 <a> 标签
 */
function _linkPlainText(text) {
  if (!text) return ''
  // DOI 链接
  let out = text.replace(
    /https?:\/\/(?:dx\.)?doi\.org\/(10\.\d{4,9}\/[-._;()\/:A-Z0-9]+)/gi,
    '<a class="auto-link doi-link" href="https://doi.org/$1">$1</a>'
  )
  out = out.replace(
    /(?<!doi\.org\/)(?<!href="https:\/\/doi\.org\/)\b(10\.\d{4,9}\/[-._;()\/:A-Z0-9]+)\b(?![^<]*<\/a>)/gi,
    '<a class="auto-link doi-link" href="https://doi.org/$1">$1</a>'
  )
  // 普通 URL
  out = out.replace(
    /\bhttps?:\/\/[^\s<]+\b/g,
    (m) => {
      if (/\.(png|jpg|jpeg|gif|svg|webp)$/i.test(m)) return m
      if (/\/minio\//.test(m)) return m
      if (/doi\.org/i.test(m)) return m
      return `<a class="auto-link url-link" href="${m}" target="_blank" rel="noopener">${m}</a>`
    }
  )
  // 邮箱
  out = out.replace(
    /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
    (m) => `<a class="auto-link email-link" href="mailto:${m}">${m}</a>`
  )
  return out
}

/**
 * v28 step 38: Markdown 表格转 HTML
 *
 * 输入: | col1 | col2 |\n|---|---|\n| a | b |
 * 输出: <table><thead><tr><th>col1</th>...
 *
 * 安全: 每格内容 HTML escape，但保留行内公式（MathJax 会后处理）
 */
function renderMarkdownTable(text) {
  if (!text || !text.trim()) return ''
  const lines = text.split('\n').filter(l => l.trim())
  if (lines.length < 2) return '<pre>' + text + '</pre>'

  // 解析表头
  const parseRow = (line) => {
    // 去掉首尾 | 后 split('|')
    let inner = line.trim()
    if (inner.startsWith('|')) inner = inner.slice(1)
    if (inner.endsWith('|')) inner = inner.slice(0, -1)
    return inner.split('|').map(c => c.trim())
  }

  const headers = parseRow(lines[0])
  // lines[1] 是分隔行 |---|---:|
  const rows = lines.slice(2).map(parseRow)

  const escape = (s) => String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const ths = headers.map(h => `<th>${escape(h)}</th>`).join('')
  const trs = rows.map(row => {
    const tds = row.map(c => `<td>${escape(c)}</td>`).join('')
    return `<tr>${tds}</tr>`
  }).join('')

  return `<table class="paper-md-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`
}
</script>

<style scoped>
.paper-block {
  margin: 0;
}

.block-paragraph {
  font-size: 15.5px;
  line-height: 1.85;
  color: var(--color-text-primary);
  margin: 0 0 14px;
  overflow-wrap: anywhere;
  overflow-wrap: break-word;
  text-indent: 0;
}

.block-paragraph.block-chinese {
  line-height: 1.85;
  text-indent: 2em;
}

.block-paragraph :deep(.auto-link) {
  color: var(--color-primary);
  text-decoration: none;
  transition: color 0.15s;
}

.block-paragraph :deep(.auto-link:hover) {
  color: var(--color-primary);
  text-decoration: underline;
}

/* 化学式 / 离子 / 自由基样式（v26 回归修复：改为 Unicode 字符）
   formatChemicalText 现已返回纯 Unicode 上下标字符，不再输出 <span> 标签。
   浏览器原生渲染 O₃ / H₂O₂ / OH⁻ / mg·L⁻¹，无需特殊样式。
   如需视觉强调（如 ·OH 自由基），用 CSS 标记包裹：见下面 ::first-letter 等。 */

.block-heading {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 20px 0 10px;
}

/* v28 step 38: Markdown 表格样式 */
.block-table-wrapper {
  margin: 16px 0;
  overflow-x: auto;
  border-radius: 6px;
  border: 1px solid var(--color-border-light, #E5E7EB);
}
.block-table-wrapper :deep(.paper-md-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
  background: var(--color-bg-card);
}
.block-table-wrapper :deep(.paper-md-table th) {
  background: var(--color-bg-card);
  font-weight: 600;
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border-light, #E5E7EB);
  color: var(--color-text-primary);
}
.block-table-wrapper :deep(.paper-md-table td) {
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-text-regular);
  vertical-align: top;
}
.block-table-wrapper :deep(.paper-md-table tr:last-child td) {
  border-bottom: none;
}
.block-table-wrapper :deep(.paper-md-table tr:hover) {
  background: var(--color-bg-page);
}

.block-page-marker-hidden {
  /* v28 step 13: 占位 1px 让后续 paragraph block 继承 page 字段
     视觉上完全不可见，避免突兀的"Page 3"标签打断阅读 */
  display: block;
  height: 1px;
  margin: 0;
  padding: 0;
  visibility: hidden;
}

/* v28 step 109: image_anchor 块样式（vision layout inline 图片占位） */
.block-image-anchor {
  margin: 18px 0 14px;
}
.image-anchor-fallback {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #F0F9FF, #E0F2FE);
  border-left: 4px solid #0EA5E9;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary);
}
.image-anchor-hint {
  font-size: 11px;
  color: var(--color-text-secondary);
  font-weight: 400;
  margin-left: auto;
}

.block-page-marker {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 28px 0 20px;
  user-select: none;
}

.page-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-border) 50%, transparent);
}

.page-label {
  font-size: 11px;
  color: var(--color-text-placeholder);
  background: var(--color-border-light);
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.block-figure-marker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 18px 0 10px;
  padding: 4px 10px;
  background: var(--color-accent-bg);
  border: 1px dashed rgba(255, 179, 71, 0.4);
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-warning);
  font-weight: 500;
  scroll-margin-top: 80px;
}

.figure-label {
  font-weight: 600;
}

.figure-page {
  color: var(--color-text-placeholder);
  font-size: 11px;
  margin-left: 4px;
}

/* v28 step 71: Q&A 卡片样式 */
.qa-question-card,
.qa-answer-card {
  display: flex;
  gap: 14px;
  margin: 14px 0;
  padding: 16px 18px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
}

.qa-question-card {
  background: linear-gradient(135deg, #FEF3C7, #FDE68A);
  border-color: #FCD34D;
}

.qa-answer-card {
  background: linear-gradient(135deg, #EFF6FF, #DBEAFE);
  border-color: #93C5FD;
}

.qa-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  color: var(--color-bg-card);
  margin-top: 2px;
}

.qa-icon-question {
  background: linear-gradient(135deg, #F59E0B, #D97706);
}

.qa-icon-answer {
  background: linear-gradient(135deg, #3B82F6, #2563EB);
}

.qa-content {
  flex: 1;
  min-width: 0;
}

.qa-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.qa-text {
  font-size: 15px;
  line-height: 1.85;
  color: var(--color-text-primary);
  overflow-wrap: anywhere;
}

.qa-text :deep(p) {
  margin: 0 0 10px;
}
.qa-text :deep(p:last-child) {
  margin-bottom: 0;
}
.qa-text :deep(h2),
.qa-text :deep(h3),
.qa-text :deep(h4) {
  margin: 14px 0 8px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.qa-text :deep(h2) { font-size: 18px; }
.qa-text :deep(h3) { font-size: 16px; }
.qa-text :deep(h4) { font-size: 15px; }
.qa-text :deep(ul),
.qa-text :deep(ol) {
  margin: 8px 0;
  padding-left: 22px;
}
.qa-text :deep(li) {
  margin: 4px 0;
}
.qa-text :deep(strong) {
  color: var(--color-text-primary);
}
.qa-text :deep(code) {
  background: var(--color-border-light);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 13px;
}
</style>
