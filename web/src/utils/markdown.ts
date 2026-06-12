/**
 * 统一 Markdown 渲染
 *
 * 基础方案：marked + 代码块样式增强（无 highlight.js 依赖）
 * 如需代码高亮后续可加 highlight.js（npm i highlight.js）
 */

import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true,
})

export function renderMarkdown(text: string): string {
  if (!text) return ''
  return marked.parse(text) as string
}
