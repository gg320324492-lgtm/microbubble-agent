/**
 * 统一 Markdown 渲染（含代码高亮）
 *
 * 性能考量：只注册常用 6 种语言（python / js / bash / json / sql / yaml），
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

// 注册 6 种常用语言
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

export function renderMarkdown(text: string): string {
  if (!text) return ''
  return marked.parse(text) as string
}
