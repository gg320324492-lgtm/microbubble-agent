<script setup lang="ts">
/**
 * Markdown Safe Viewer —— 自写小型 markdown 解析 + Vue 模板渲染。
 *
 * 设计铁律:
 * 1. 永远不在 source 中执行 v-html (CSP 锁死 unsafe-inline, 也不允许)
 * 2. 全部解析为 AST, 模板 v-for 渲染, Vue 自动 escape 文本
 * 3. Inline token 输出 HTML 字符串时严格二次 escape
 * 4. link URL 仅允许 http(s) 与相对路径 / 开头的 scheme, 其他丢弃
 * 5. 不引入第三方 markdown 库 (Phase 2-Impl-2B 范围内); Phase 3+ 可选 highlight.js
 *
 * 支持 markdown 子集 (详见 docs/desktop-conversion/knowledge-detail-contract.md §3.3)
 */
import { computed } from 'vue'

interface Props {
  source: string
  /** 自定义类名, 用于在页面中调整 markdown 渲染区样式 */
  bodyClass?: string
}
const props = withDefaults(defineProps<Props>(), {
  bodyClass: ''
})

// ===================== HTML 实体 escape =====================
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/**
 * URL sanitizer: 仅 http(s) / 锚点 / 邮件 / 相对路径允许。
 * 其他 (javascript:, data:, vbscript:, ...) 一律返回空字符串 (链接整段 token 被吞掉)。
 */
function sanitizeHref(raw: string): string | null {
  const trimmed = (raw ?? '').trim()
  if (trimmed.length === 0) return null
  if (trimmed.startsWith('/') || trimmed.startsWith('#') || trimmed.startsWith('./') || trimmed.startsWith('../')) {
    return trimmed
  }
  if (/^mailto:[^\s]+$/.test(trimmed)) return trimmed
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return null
}

// ===================== Inline AST =====================
interface InlineToken {
  text: string
  bold?: boolean
  italic?: boolean
  code?: boolean
  href?: string
}

function buildInlineFromScratch(input: string): InlineToken[] {
  const out: InlineToken[] = []
  let i = 0
  const n = input.length

  while (i < n) {
    // 1. inline code `xxx`
    if (input[i] === '`') {
      const j = input.indexOf('`', i + 1)
      if (j > i) {
        out.push({ text: input.slice(i + 1, j), code: true })
        i = j + 1
        continue
      }
    }
    // 2. link [text](url)
    if (input[i] === '[') {
      const closeBracket = input.indexOf(']', i + 1)
      if (closeBracket > i && input[closeBracket + 1] === '(') {
        const closeParen = input.indexOf(')', closeBracket + 2)
        if (closeParen > closeBracket) {
          const text = input.slice(i + 1, closeBracket)
          const url = input.slice(closeBracket + 2, closeParen)
          const sanitized = sanitizeHref(url)
          if (sanitized !== null) {
            out.push({ text, href: sanitized })
          } else {
            // 危险 URL 退回纯文本
            out.push({ text: `[${text}](${url})` })
          }
          i = closeParen + 1
          continue
        }
      }
    }
    // 3. bold **xx**
    if (input.startsWith('**', i)) {
      const j = input.indexOf('**', i + 2)
      if (j > i) {
        out.push({ text: input.slice(i + 2, j), bold: true })
        i = j + 2
        continue
      }
    }
    // 4. italic *x*
    if (input[i] === '*') {
      const j = input.indexOf('*', i + 1)
      if (j > i + 1) {
        out.push({ text: input.slice(i + 1, j), italic: true })
        i = j + 1
        continue
      }
    }
    // 5. 普通字符
    const next = findNextSpecial(input, i + 1)
    if (next === -1) {
      out.push({ text: input.slice(i) })
      break
    }
    out.push({ text: input.slice(i, next) })
    i = next
  }

  // 合并相邻纯 text tokens
  const merged: InlineToken[] = []
  for (const t of out) {
    const last = merged[merged.length - 1]
    const isFmt = t.bold || t.italic || t.code || t.href
    const lastIsFmt = last && (last.bold || last.italic || last.code || last.href)
    if (last && !isFmt && !lastIsFmt) {
      last.text += t.text
    } else {
      merged.push({ ...t })
    }
  }
  return merged
}

function findNextSpecial(s: string, from: number): number {
  for (let k = from; k < s.length; k++) {
    const c = s[k]
    if (c === '`' || c === '[' || c === '*') return k
  }
  return -1
}

// ===================== Block AST =====================
type BlockNode =
  | { type: 'heading'; level: 1 | 2 | 3 | 4 | 5 | 6; tokens: InlineToken[] }
  | { type: 'paragraph'; tokens: InlineToken[] }
  | { type: 'code'; lang: string; text: string }
  | { type: 'list'; ordered: boolean; items: InlineToken[][] }
  | { type: 'quote'; tokens: InlineToken[] }
  | { type: 'hr' }

function parseBlocks(src: string): BlockNode[] {
  const blocks: BlockNode[] = []
  const lines = src.replace(/\r\n?/g, '\n').split('\n')
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (line.trim() === '') {
      i++
      continue
    }

    // code fence
    const fenceMatch = line.match(/^```(\w*)\s*$/)
    if (fenceMatch) {
      const lang = fenceMatch[1] ?? ''
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].match(/^```\s*$/)) {
        codeLines.push(lines[i])
        i++
      }
      if (i < lines.length) i++
      blocks.push({ type: 'code', lang, text: codeLines.join('\n') })
      continue
    }

    // heading
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      const level = headingMatch[1].length as 1 | 2 | 3 | 4 | 5 | 6
      blocks.push({ type: 'heading', level, tokens: buildInlineFromScratch(headingMatch[2]) })
      i++
      continue
    }

    // hr
    if (/^---+\s*$/.test(line)) {
      blocks.push({ type: 'hr' })
      i++
      continue
    }

    // quote
    if (/^>\s?/.test(line)) {
      const qLines: string[] = []
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        qLines.push(lines[i].replace(/^>\s?/, ''))
        i++
      }
      blocks.push({ type: 'quote', tokens: buildInlineFromScratch(qLines.join(' ')) })
      continue
    }

    // unordered list
    if (/^(\s*)[-*]\s+/.test(line)) {
      const items: InlineToken[][] = []
      while (i < lines.length && /^(\s*)[-*]\s+/.test(lines[i])) {
        items.push(buildInlineFromScratch(lines[i].replace(/^(\s*)[-*]\s+/, '')))
        i++
      }
      blocks.push({ type: 'list', ordered: false, items })
      continue
    }

    // ordered list
    if (/^(\s*)\d+\.\s+/.test(line)) {
      const items: InlineToken[][] = []
      while (i < lines.length && /^(\s*)\d+\.\s+/.test(lines[i])) {
        items.push(buildInlineFromScratch(lines[i].replace(/^(\s*)\d+\.\s+/, '')))
        i++
      }
      blocks.push({ type: 'list', ordered: true, items })
      continue
    }

    // paragraph: 累积到下一个空行 / 特殊 block
    const pLines: string[] = [line]
    i++
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !/^#{1,6}\s/.test(lines[i]) &&
      !/^```/.test(lines[i]) &&
      !/^>\s?/.test(lines[i]) &&
      !/^---+\s*$/.test(lines[i]) &&
      !/^(\s*)[-*]\s+/.test(lines[i]) &&
      !/^(\s*)\d+\.\s+/.test(lines[i])
    ) {
      pLines.push(lines[i])
      i++
    }
    blocks.push({ type: 'paragraph', tokens: buildInlineFromScratch(pLines.join(' ')) })
  }

  return blocks
}

const blocks = computed<BlockNode[]>(() => parseBlocks(props.source))

// Vue 模板用 helper: text -> 始终 escape (避免被解释为 HTML)
function pickText(t: InlineToken): string {
  return escapeHtml(t.text)
}
</script>

<template>
  <div :class="['md-body', bodyClass]">
    <template v-for="(block, idx) in blocks" :key="idx">
      <h1 v-if="block.type === 'heading' && block.level === 1" class="md-h1">
        <template v-for="(t, j) in block.tokens" :key="`h1-${idx}-${j}`">
          <code v-if="t.code" class="md-code">{{ pickText(t) }}</code>
          <strong v-else-if="t.bold" class="md-bold">{{ pickText(t) }}</strong>
          <em v-else-if="t.italic" class="md-italic">{{ pickText(t) }}</em>
          <a v-else-if="t.href" :href="t.href" target="_blank" rel="noopener noreferrer" class="md-link">{{ pickText(t) }}</a>
          <span v-else>{{ pickText(t) }}</span>
        </template>
      </h1>
      <h2 v-else-if="block.type === 'heading' && block.level === 2" class="md-h2">
        <template v-for="(t, j) in block.tokens" :key="`h2-${idx}-${j}`">
          <code v-if="t.code" class="md-code">{{ pickText(t) }}</code>
          <strong v-else-if="t.bold" class="md-bold">{{ pickText(t) }}</strong>
          <em v-else-if="t.italic" class="md-italic">{{ pickText(t) }}</em>
          <a v-else-if="t.href" :href="t.href" target="_blank" rel="noopener noreferrer" class="md-link">{{ pickText(t) }}</a>
          <span v-else>{{ pickText(t) }}</span>
        </template>
      </h2>
      <h3 v-else-if="block.type === 'heading' && block.level === 3" class="md-h3">
        <template v-for="(t, j) in block.tokens" :key="`h3-${idx}-${j}`">
          <code v-if="t.code" class="md-code">{{ pickText(t) }}</code>
          <strong v-else-if="t.bold" class="md-bold">{{ pickText(t) }}</strong>
          <em v-else-if="t.italic" class="md-italic">{{ pickText(t) }}</em>
          <a v-else-if="t.href" :href="t.href" target="_blank" rel="noopener noreferrer" class="md-link">{{ pickText(t) }}</a>
          <span v-else>{{ pickText(t) }}</span>
        </template>
      </h3>
      <h4 v-else-if="block.type === 'heading' && block.level === 4" class="md-h4">
        <template v-for="(t, j) in block.tokens" :key="`h4-${idx}-${j}`">
          <code v-if="t.code" class="md-code">{{ pickText(t) }}</code>
          <strong v-else-if="t.bold" class="md-bold">{{ pickText(t) }}</strong>
          <em v-else-if="t.italic" class="md-italic">{{ pickText(t) }}</em>
          <a v-else-if="t.href" :href="t.href" target="_blank" rel="noopener noreferrer" class="md-link">{{ pickText(t) }}</a>
          <span v-else>{{ pickText(t) }}</span>
        </template>
      </h4>
      <h5 v-else-if="block.type === 'heading' && block.level === 5" class="md-h5">
        <template v-for="(t, j) in block.tokens" :key="`h5-${idx}-${j}`">
          <code v-if="t.code" class="md-code">{{ pickText(t) }}</code>
          <strong v-else-if="t.bold" class="md-bold">{{ pickText(t) }}</strong>
          <em v-else-if="t.italic" class="md-italic">{{ pickText(t) }}</em>
          <a v-else-if="t.href" :href="t.href" target="_blank" rel="noopener noreferrer" class="md-link">{{ pickText(t) }}</a>
          <span v-else>{{ pickText(t) }}</span>
        </template>
      </h5>
      <h6 v-else-if="block.type === 'heading' && block.level === 6" class="md-h6">
        <template v-for="(t, j) in block.tokens" :key="`h6-${idx}-${j}`">
          <code v-if="t.code" class="md-code">{{ pickText(t) }}</code>
          <strong v-else-if="t.bold" class="md-bold">{{ pickText(t) }}</strong>
          <em v-else-if="t.italic" class="md-italic">{{ pickText(t) }}</em>
          <a v-else-if="t.href" :href="t.href" target="_blank" rel="noopener noreferrer" class="md-link">{{ pickText(t) }}</a>
          <span v-else>{{ pickText(t) }}</span>
        </template>
      </h6>

      <pre v-else-if="block.type === 'code'" class="md-pre"><code>{{ block.text }}</code></pre>

      <hr v-else-if="block.type === 'hr'" class="md-hr" />

      <ul v-else-if="block.type === 'list' && !block.ordered" class="md-ul">
        <li v-for="(item, k) in block.items" :key="`ul-${idx}-${k}`">
          <template v-for="(t, j) in item" :key="`ul-${idx}-${k}-${j}`">
            <code v-if="t.code" class="md-code">{{ pickText(t) }}</code>
            <strong v-else-if="t.bold" class="md-bold">{{ pickText(t) }}</strong>
            <em v-else-if="t.italic" class="md-italic">{{ pickText(t) }}</em>
            <a v-else-if="t.href" :href="t.href" target="_blank" rel="noopener noreferrer" class="md-link">{{ pickText(t) }}</a>
            <span v-else>{{ pickText(t) }}</span>
          </template>
        </li>
      </ul>

      <ol v-else-if="block.type === 'list' && block.ordered" class="md-ol">
        <li v-for="(item, k) in block.items" :key="`ol-${idx}-${k}`">
          <template v-for="(t, j) in item" :key="`ol-${idx}-${k}-${j}`">
            <code v-if="t.code" class="md-code">{{ pickText(t) }}</code>
            <strong v-else-if="t.bold" class="md-bold">{{ pickText(t) }}</strong>
            <em v-else-if="t.italic" class="md-italic">{{ pickText(t) }}</em>
            <a v-else-if="t.href" :href="t.href" target="_blank" rel="noopener noreferrer" class="md-link">{{ pickText(t) }}</a>
            <span v-else>{{ pickText(t) }}</span>
          </template>
        </li>
      </ol>

      <blockquote v-else-if="block.type === 'quote'" class="md-quote">
        <template v-for="(t, j) in block.tokens" :key="`q-${idx}-${j}`">
          <code v-if="t.code" class="md-code">{{ pickText(t) }}</code>
          <strong v-else-if="t.bold" class="md-bold">{{ pickText(t) }}</strong>
          <em v-else-if="t.italic" class="md-italic">{{ pickText(t) }}</em>
          <a v-else-if="t.href" :href="t.href" target="_blank" rel="noopener noreferrer" class="md-link">{{ pickText(t) }}</a>
          <span v-else>{{ pickText(t) }}</span>
        </template>
      </blockquote>

      <p v-else-if="block.type === 'paragraph'" class="md-p">
        <template v-for="(t, j) in block.tokens" :key="`p-${idx}-${j}`">
          <code v-if="t.code" class="md-code">{{ pickText(t) }}</code>
          <strong v-else-if="t.bold" class="md-bold">{{ pickText(t) }}</strong>
          <em v-else-if="t.italic" class="md-italic">{{ pickText(t) }}</em>
          <a v-else-if="t.href" :href="t.href" target="_blank" rel="noopener noreferrer" class="md-link">{{ pickText(t) }}</a>
          <span v-else>{{ pickText(t) }}</span>
        </template>
      </p>
    </template>
  </div>
</template>

<style scoped>
.md-body {
  font-size: 0.92rem;
  line-height: 1.7;
  color: #cbd5e1;
  word-break: break-word;
}
.md-h1, .md-h2, .md-h3, .md-h4, .md-h5, .md-h6 {
  margin: 1.2em 0 0.5em;
  color: #f1f5f9;
  font-weight: 600;
  line-height: 1.3;
}
.md-h1 { font-size: 1.5rem; border-bottom: 1px solid #334155; padding-bottom: 0.3em; }
.md-h2 { font-size: 1.3rem; }
.md-h3 { font-size: 1.15rem; }
.md-h4 { font-size: 1.05rem; }
.md-h5 { font-size: 1rem; color: #cbd5e1; }
.md-h6 { font-size: 0.95rem; color: #94a3b8; }

.md-p { margin: 0.6em 0; }

.md-pre {
  margin: 0.8em 0;
  padding: 0.8em 1em;
  background: #0b1220;
  border: 1px solid #1e293b;
  border-radius: 5px;
  overflow-x: auto;
  font-size: 0.85rem;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  color: #e2e8f0;
}
.md-pre code {
  background: transparent;
  padding: 0;
  color: inherit;
}

.md-code {
  background: rgba(99, 102, 241, 0.12);
  color: #c7d2fe;
  padding: 0.05em 0.35em;
  border-radius: 3px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.85em;
}
.md-bold { color: #fde68a; font-weight: 600; }
.md-italic { color: #f9a8d4; font-style: italic; }
.md-link {
  color: #f97316;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.md-link:hover { color: #ea580c; }

.md-ul, .md-ol {
  margin: 0.6em 0;
  padding-left: 1.6em;
}
.md-ul li, .md-ol li {
  margin: 0.25em 0;
  list-style: revert;
}

.md-quote {
  margin: 0.8em 0;
  padding: 0.4em 0.9em;
  border-left: 3px solid #475569;
  background: #0f172a;
  color: #94a3b8;
  font-style: italic;
}

.md-hr {
  margin: 1.2em 0;
  border: 0;
  border-top: 1px dashed #334155;
}
</style>
