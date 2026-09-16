// read_file 工具 — UTF-8 文本读取；256KB 上限截断；NUL 字节探测判二进制拒读（工单 C-1 §2）
import { readFileSync, statSync } from 'node:fs'
import type { AgentTool, ToolResult } from '../tool-registry'
import { displayRel } from './walk'

const MAX_BYTES = 256 * 1024

export const readFileTool: AgentTool = {
  name: 'read_file',
  description: '读取工作区内一个 UTF-8 文本文件（上限 256KB，超出截断并在结果注明）。二进制文件拒绝读取。',
  permission: 'auto',
  parameters: {
    type: 'object',
    properties: {
      path: { type: 'string', description: '相对工作区的文件路径，如 docs/notes.md' }
    },
    required: ['path']
  },
  async execute(input, ctx): Promise<ToolResult> {
    const file = typeof input['path'] === 'string' ? input['path'] : ''
    if (file === '') return { ok: false, summary: '缺少 path 参数', error: '缺少 path 参数' }

    let st
    try {
      st = statSync(file)
    } catch {
      const rel = displayRel(file, ctx.workspaceRoot)
      return { ok: false, summary: `文件不存在: ${rel}`, error: '文件不存在' }
    }
    if (st.isDirectory()) {
      const rel = displayRel(file, ctx.workspaceRoot)
      return { ok: false, summary: `目标是目录而非文件: ${rel}`, error: '目标是目录' }
    }

    const buf = readFileSync(file)
    if (buf.includes(0)) {
      const rel = displayRel(file, ctx.workspaceRoot)
      return { ok: false, summary: `二进制文件拒绝读取: ${rel}`, error: '二进制文件' }
    }

    const truncated = buf.length > MAX_BYTES
    const text = (truncated ? buf.subarray(0, MAX_BYTES) : buf).toString('utf8')
    const rel = displayRel(file, ctx.workspaceRoot)
    return {
      ok: true,
      summary: truncated
        ? `已读取 ${rel}（原始 ${buf.length} 字节，超过 256KB 上限，已截断至 ${MAX_BYTES} 字节）`
        : `已读取 ${rel}（${buf.length} 字节）`,
      data: { path: rel, size: buf.length, truncated, content: text }
    }
  }
}
