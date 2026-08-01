/**
 * 统一 Markdown 渲染（含代码高亮）
 *
 * 性能考量：只注册常用 6 种语言（python / js / bash / json / sql / yaml）+
 * plaintext fallback（语言未指定或不支持时透传，消 console warning），
 * 避免 highlight.js 200+ 语言全量打包（gzip 后 +30KB）。
 */

import { marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import sql from 'highlight.js/lib/languages/sql'
import yaml from 'highlight.js/lib/languages/yaml'
import plaintext from 'highlight.js/lib/languages/plaintext'

// 注册 6 种常用语言 + plaintext fallback
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescriptPlaceholder)
hljs.registerLanguage('ts', typescriptPlaceholder)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('text', plaintext)
hljs.registerLanguage('txt', plaintext)

// TypeScript 简化为 JS 高亮（避免再装 typescript 包）
function typescriptPlaceholder() { return javascript }

// 注册 marked-highlight 插件
marked.use(
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code, lang) {
      const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
      try {
        return hljs.highlight(code, { language }).value
      } catch {
        return code.replace(/</g, '&lt;').replace(/>/g, '&gt;')
      }
    }
  })
)

marked.setOptions({ breaks: true, gfm: true })

// [W99 +20 派工 v10] 图片加载失败兜底：v-html 注入的 <img> 不会触发 Vue @error，
// 必须在 HTML 字符串里内联 onerror 才能兜底。占位符走内联 SVG data URL，
// 不依赖外链资源，加载失败时立即切到占位（不闪白）。
const IMG_FALLBACK_SVG =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80" viewBox="0 0 240 80">' +
      '<rect width="240" height="80" fill="#f5f5f5"/>' +
      '<text x="120" y="44" font-family="sans-serif" font-size="13" fill="#909399" text-anchor="middle">' +
        '🖼️ 图片加载失败' +
      '</text>' +
    '</svg>'
  )

const IMG_FALLBACK_HANDLER =
  `this.onerror=null;this.src='${IMG_FALLBACK_SVG}';this.alt=this.alt||'图片加载失败';` +
  `this.style.maxWidth='240px';this.style.height='auto';`

/**
 * 后处理 marked 输出的 HTML，为 <img> 注入 onerror 内联兜底。
 * v-html 派工已知问题：v-html 注入的 img 不会触发 Vue @error 监听
 * （资源加载错误不冒泡到祖先元素），必须在 HTML 字符串里 inline onerror。
 */
function injectImgOnerror(html: string): string {
  if (!html || html.indexOf('<img') === -1) return html
  // 匹配 <img ...> 标签（self-closing 或带 src/alt/...）
  return html.replace(/<img\b([^>]*?)\/?>/g, (match, attrs: string) => {
    // 已注入过跳过（防重复）
    if (/onerror\s*=/.test(attrs)) return match
    // 提取 alt 文本（如有），拼到 fallback 上保留语义
    const altMatch = /(?:^|\s)alt\s*=\s*"([^"]*)"/.exec(attrs)
    const altText = altMatch ? altMatch[1] : '图片'
    return `<img${attrs} onerror="${IMG_FALLBACK_HANDLER}" data-fallback-text="${altText} 加载失败" />`
  })
}

export function renderMarkdown(text: string): string {
  if (!text) return ''
  const raw = marked.parse(text) as string
  return injectImgOnerror(raw)
}
