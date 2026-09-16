// glob 工具 — **/* 语义模式匹配，node:fs 自实现递归，上限 200 条（工单 C-1 §2）
import type { AgentTool, ToolResult } from '../tool-registry'
import { walkTree } from './walk'

const MAX_MATCHES = 200

/**
 * glob → RegExp：支持 `**`（跨目录，可匹配零段）、`*`（段内通配）、`?`（单字符）。
 * 相对路径统一以 / 分隔参与匹配。
 */
export function globToRegExp(pattern: string): RegExp {
  let re = ''
  for (let i = 0; i < pattern.length; i++) {
    const c = pattern[i]
    if (c === '*') {
      if (pattern[i + 1] === '*') {
        let j = i + 2
        while (pattern[j] === '*') j++
        if (pattern[j] === '/') {
          re += '(?:.*/)?' // '**/' 匹配零层或多层目录
          i = j
        } else {
          re += '.*'
          i = j - 1
        }
      } else {
        re += '[^/]*'
      }
    } else if (c === '?') {
      re += '[^/]'
    } else {
      re += c.replace(/[.+^${}()|[\]\\]/g, '\\$&')
    }
  }
  return new RegExp(`^${re}$`)
}

export const globTool: AgentTool = {
  name: 'glob',
  description:
    '按模式匹配工作区内的文件/目录路径（支持 ** 跨目录、* 段内通配、? 单字符）。pattern 相对工作区根；不含 / 的模式（如 *.md）递归匹配所有层级。上限 200 条。',
  permission: 'auto',
  parameters: {
    type: 'object',
    properties: {
      pattern: { type: 'string', description: '相对工作区的 glob 模式，如 **/*.md、data/*.csv' }
    },
    required: ['pattern']
  },
  async execute(input, ctx): Promise<ToolResult> {
    const raw = typeof input['pattern'] === 'string' ? input['pattern'] : ''
    if (raw.trim() === '') return { ok: false, summary: '缺少 pattern 参数', error: '缺少 pattern 参数' }

    const pattern = raw.replaceAll('\\', '/')
    if (pattern.startsWith('/') || /^[a-zA-Z]:/.test(pattern)) {
      return { ok: false, summary: `拒绝绝对路径模式: ${raw}`, error: '拒绝绝对路径入参' }
    }
    if (pattern.split('/').some((seg) => seg === '..')) {
      return { ok: false, summary: `模式越出工作区: ${raw}`, error: '模式包含 ..' }
    }

    // 语义：**/ 开头原样用；纯文件名模式（*.md）递归匹配所有层级；其余含 / 的模式锚定根目录
    const effective = pattern.startsWith('**/') ? pattern : !pattern.includes('/') ? `**/${pattern}` : pattern
    const regex = globToRegExp(effective)

    const matches: string[] = []
    walkTree(ctx.workspaceRoot, (_abs, rel) => {
      if (!regex.test(rel)) return true
      matches.push(rel)
      return matches.length < MAX_MATCHES // 到上限即中止遍历
    })
    const truncated = matches.length >= MAX_MATCHES
    return {
      ok: true,
      summary: `模式 ${raw} 命中 ${matches.length} 条${truncated ? '（已达上限 200，仅返回前 200 条）' : ''}`,
      data: { pattern: raw, matches, truncated }
    }
  }
}
