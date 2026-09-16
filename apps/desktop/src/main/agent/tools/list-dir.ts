// list_dir 工具 — 列目录（名称/类型/大小/修改时间），非目录报错（工单 C-1 §2）
import { readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import type { AgentTool, ToolResult } from '../tool-registry'
import { displayRel } from './walk'

interface DirEntryDto {
  name: string
  type: 'dir' | 'file' | 'other'
  size: number
  mtimeMs: number
}

export const listDirTool: AgentTool = {
  name: 'list_dir',
  description: '列出工作区内某个目录的内容（名称/类型/大小/修改时间）。path 为相对工作区的路径，缺省为工作区根目录。',
  permission: 'auto',
  parameters: {
    type: 'object',
    properties: {
      path: { type: 'string', description: '相对工作区的目录路径，如 data 或 .（缺省为根目录）' }
    },
    required: []
  },
  async execute(input, ctx): Promise<ToolResult> {
    const dir = typeof input['path'] === 'string' && input['path'] !== '' ? input['path'] : ctx.workspaceRoot
    let st
    try {
      st = statSync(dir)
    } catch {
      return { ok: false, summary: `目录不存在: ${displayRel(dir, ctx.workspaceRoot)}`, error: '目录不存在' }
    }
    if (!st.isDirectory()) {
      return { ok: false, summary: `不是目录: ${displayRel(dir, ctx.workspaceRoot)}`, error: '目标不是目录' }
    }

    const entries: DirEntryDto[] = []
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const type = entry.isDirectory() ? 'dir' : entry.isFile() ? 'file' : 'other'
      let size = 0
      let mtimeMs = 0
      try {
        const child = statSync(join(dir, entry.name))
        size = child.size
        mtimeMs = child.mtimeMs
      } catch {
        /* 悬空链接等不可 stat 的条目保留 0 值 */
      }
      entries.push({ name: entry.name, type, size, mtimeMs })
    }
    // 目录在前，同类按名称排序 — 输出稳定便于模型阅读
    entries.sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === 'dir' ? -1 : 1))

    const rel = displayRel(dir, ctx.workspaceRoot)
    return {
      ok: true,
      summary: `目录 ${rel} 共 ${entries.length} 项（${entries.filter((e) => e.type === 'dir').length} 个子目录）`,
      data: { path: rel, entries }
    }
  }
}
