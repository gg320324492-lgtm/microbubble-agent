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
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import { autoLinkContent } from '@/utils/paperAdapter'
import { formatChemicalText } from '@/utils/chemFormat'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  block: { type: Object, required: true },
  isChinese: { type: Boolean, default: false },
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
  color: #1F2937;
  margin: 0 0 14px;
  word-break: break-word;
  overflow-wrap: break-word;
  text-indent: 0;
}

.block-paragraph.block-chinese {
  line-height: 1.85;
  text-indent: 2em;
}

.block-paragraph :deep(.auto-link) {
  color: #2563EB;
  text-decoration: none;
  transition: color 0.15s;
}

.block-paragraph :deep(.auto-link:hover) {
  color: #1D4ED8;
  text-decoration: underline;
}

/* 化学式 / 离子 / 自由基样式（v26 回归修复：改为 Unicode 字符）
   formatChemicalText 现已返回纯 Unicode 上下标字符，不再输出 <span> 标签。
   浏览器原生渲染 O₃ / H₂O₂ / OH⁻ / mg·L⁻¹，无需特殊样式。
   如需视觉强调（如 ·OH 自由基），用 CSS 标记包裹：见下面 ::first-letter 等。 */

.block-heading {
  font-size: 16px;
  font-weight: 600;
  color: #1F2937;
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
  background: #fff;
}
.block-table-wrapper :deep(.paper-md-table th) {
  background: #F9FAFB;
  font-weight: 600;
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border-light, #E5E7EB);
  color: #1F2937;
}
.block-table-wrapper :deep(.paper-md-table td) {
  padding: 8px 12px;
  border-bottom: 1px solid #F3F4F6;
  color: #374151;
  vertical-align: top;
}
.block-table-wrapper :deep(.paper-md-table tr:last-child td) {
  border-bottom: none;
}
.block-table-wrapper :deep(.paper-md-table tr:hover) {
  background: #FAFAFA;
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
  color: #9CA3AF;
  background: #F3F4F6;
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
  color: #B45309;
  font-weight: 500;
  scroll-margin-top: 80px;
}

.figure-label {
  font-weight: 600;
}

.figure-page {
  color: #9CA3AF;
  font-size: 11px;
  margin-left: 4px;
}
</style>
