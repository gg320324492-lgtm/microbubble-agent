// delete_file 工具 — 删除单个文件，走系统回收站，绝不物理删除（AGENT.md 守则承诺）。
// shell.trashItem 以注入函数传入（ipc.ts 装配时注入 shell.trashItem；工具与测试不 import Electron）。
import { existsSync, statSync } from 'node:fs'
import type { AgentTool, ToolContext, ToolResult } from '../tool-registry'
import { displayRel } from './walk'

export interface TrashDeps {
  trashItem(absPath: string): Promise<void>
}

export function createDeleteFileTool(deps: TrashDeps): AgentTool {
  return {
    name: 'delete_file',
    description:
      '删除工作区内的单个文件（移入系统回收站，可恢复，绝不物理删除）。仅支持文件，不支持目录。需要用户确认。path 相对工作区。',
    permission: 'confirm',
    parameters: {
      type: 'object',
      properties: {
        path: { type: 'string', description: '相对工作区的待删除文件路径' }
      },
      required: ['path']
    },
    /** 确认前预览（无副作用）：展示文件信息 */
    async preview(resolvedInput: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult> {
      const abs = typeof resolvedInput['path'] === 'string' ? resolvedInput['path'] : ''
      if (!abs) return { ok: false, summary: '缺少 path 参数', error: '缺少 path 参数' }
      const rel = displayRel(abs, ctx.workspaceRoot)
      if (!existsSync(abs)) return { ok: false, summary: `文件不存在: ${rel}`, error: '文件不存在' }
      const st = statSync(abs)
      if (!st.isFile()) return { ok: false, summary: `不是文件（目录请逐文件处理）: ${rel}`, error: '目标是目录' }
      return { ok: true, summary: `将删除 ${rel}（${st.size} 字节，移入系统回收站）`, data: { path: rel, size: st.size } }
    },
    async execute(input, ctx) {
      const abs = typeof input['path'] === 'string' ? input['path'] : ''
      if (!abs) return { ok: false, summary: '缺少 path 参数', error: '缺少 path 参数' }
      const rel = displayRel(abs, ctx.workspaceRoot)
      if (!existsSync(abs)) return { ok: false, summary: `文件不存在: ${rel}`, error: '文件不存在' }
      const st = statSync(abs)
      if (!st.isFile()) return { ok: false, summary: `不是文件（目录请逐文件处理）: ${rel}`, error: '目标是目录' }
      try {
        await deps.trashItem(abs)
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err)
        return { ok: false, summary: `移入回收站失败: ${message}`, error: message }
      }
      return { ok: true, summary: `已移入回收站: ${rel}`, data: { path: rel, size: st.size, trashed: true } }
    }
  }
}
