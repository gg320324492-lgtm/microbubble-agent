// grep 工具 — 内容搜索（子串或正则 + 大小写开关），返回 文件:行号:行内容，上限 100 条（工单 C-1 §2）
import { readFileSync, statSync } from 'node:fs'
import type { AgentTool, ToolResult } from '../tool-registry'
import { displayRel, walkTree } from './walk'

const MAX_MATCHES = 100
const LINE_DISPLAY_MAX = 500

export const grepTool: AgentTool = {
  name: 'grep',
  description:
    '在工作区内按内容搜索文本文件，返回 文件:行号:行内容 列表（上限 100 条）。默认子串匹配且不区分大小写；is_regex=true 时按正则解释；case_sensitive=true 区分大小写。可用 path 限定子目录。',
  permission: 'auto',
  parameters: {
    type: 'object',
    properties: {
      pattern: { type: 'string', description: '搜索内容（子串或正则）' },
      path: { type: 'string', description: '限定搜索的子目录，相对工作区，缺省为全工作区' },
      is_regex: { type: 'boolean', description: 'true 时 pattern 按正则解释，缺省 false（子串）' },
      case_sensitive: { type: 'boolean', description: 'true 时区分大小写，缺省 false' }
    },
    required: ['pattern']
  },
  async execute(input, ctx): Promise<ToolResult> {
    const pattern = typeof input['pattern'] === 'string' ? input['pattern'] : ''
    if (pattern === '') return { ok: false, summary: '缺少 pattern 参数', error: '缺少 pattern 参数' }
    const isRegex = input['is_regex'] === true
    const caseSensitive = input['case_sensitive'] === true
    // registry 已把 path（若给）围栏解析为绝对路径；缺省为工作区根
    const scope = typeof input['path'] === 'string' && input['path'] !== '' ? input['path'] : ctx.workspaceRoot

    let isDir = true
    try {
      isDir = statSync(scope).isDirectory()
    } catch {
      const rel = displayRel(scope, ctx.workspaceRoot)
      return { ok: false, summary: `搜索范围不存在: ${rel}`, error: '目录不存在' }
    }
    if (!isDir) {
      const rel = displayRel(scope, ctx.workspaceRoot)
      return { ok: false, summary: `搜索范围不是目录: ${rel}`, error: '目标不是目录' }
    }

    let matchLine: (line: string) => boolean
    if (isRegex) {
      let regex: RegExp
      try {
        regex = new RegExp(pattern, caseSensitive ? '' : 'i')
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err)
        return { ok: false, summary: `正则无效: ${message}`, error: `正则无效: ${message}` }
      }
      matchLine = (line) => regex.test(line)
    } else {
      const needle = caseSensitive ? pattern : pattern.toLowerCase()
      matchLine = (line) => (caseSensitive ? line : line.toLowerCase()).includes(needle)
    }

    const matches: string[] = []
    walkTree(scope, (abs) => {
      let buf: Buffer
      try {
        buf = readFileSync(abs)
      } catch {
        return true // 不可读的文件跳过
      }
      if (buf.includes(0)) return true // 二进制文件跳过
      const lines = buf.toString('utf8').split(/\r?\n/)
      for (let i = 0; i < lines.length; i++) {
        if (!matchLine(lines[i])) continue
        const content = lines[i].length > LINE_DISPLAY_MAX ? `${lines[i].slice(0, LINE_DISPLAY_MAX)}…` : lines[i]
        matches.push(`${displayRel(abs, ctx.workspaceRoot)}:${i + 1}:${content}`)
        if (matches.length >= MAX_MATCHES) return false
      }
      return true
    })
    const truncated = matches.length >= MAX_MATCHES
    const scopeRel = displayRel(scope, ctx.workspaceRoot)
    return {
      ok: true,
      summary: `在 ${scopeRel} 内搜索「${pattern}」命中 ${matches.length} 条${truncated ? '（已达上限 100，仅返回前 100 条）' : ''}`,
      data: { pattern, scope: scopeRel, matches, truncated }
    }
  }
}
