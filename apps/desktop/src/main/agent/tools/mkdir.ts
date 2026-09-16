// mkdir 工具 — 创建目录含父目录，幂等（已存在返回 ok），无破坏性（permission: auto）
import { existsSync, mkdirSync, statSync } from 'node:fs'
import type { AgentTool, ToolResult } from '../tool-registry'
import { displayRel } from './walk'

export const mkdirTool: AgentTool = {
  name: 'mkdir',
  description: '在工作区内创建目录（自动创建父目录；已存在时幂等返回成功）。无破坏性，无需确认。path 相对工作区。',
  permission: 'auto',
  parameters: {
    type: 'object',
    properties: {
      path: { type: 'string', description: '相对工作区的目录路径' }
    },
    required: ['path']
  },
  async execute(input, ctx): Promise<ToolResult> {
    const abs = typeof input['path'] === 'string' ? input['path'] : ''
    if (!abs) return { ok: false, summary: '缺少 path 参数', error: '缺少 path 参数' }
    const rel = displayRel(abs, ctx.workspaceRoot)
    if (existsSync(abs)) {
      if (statSync(abs).isDirectory()) return { ok: true, summary: `目录已存在（幂等）: ${rel}`, data: { path: rel, existed: true } }
      return { ok: false, summary: `同名文件已存在，无法创建目录: ${rel}`, error: '同名文件已存在' }
    }
    mkdirSync(abs, { recursive: true })
    return { ok: true, summary: `已创建目录: ${rel}`, data: { path: rel, existed: false } }
  }
}
