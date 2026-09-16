// Agent 工具注册表（工单 C-1 §2）— C-2 的 ReAct 循环经此统一调工具。
// invoke 统一入口：未注册报错 → 路径参数围栏校验 → 审计(前) → 执行 → 审计(后)。
// 约定：parameters.properties 里名为 `path` 的参数视为工作区相对路径，
//       invoke 前先过 WorkspaceService 围栏并替换为绝对路径再交给工具。
import type { AuditService } from '../services/workspace/audit.service'
import type { WorkspaceService } from '../services/workspace/workspace.service'

export type ToolPermissionLevel = 'auto' | 'confirm' // 本单只实现 'auto'；'confirm' 留给 C-3

export interface ToolContext {
  userId: string
  workspaceRoot: string
}

export interface ToolResult {
  ok: boolean
  summary: string
  data?: unknown
  error?: string
}

export interface AgentTool {
  name: string
  /** 给模型看的说明 */
  description: string
  permission: ToolPermissionLevel
  parameters: { type: 'object'; properties: Record<string, unknown>; required: string[] }
  execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult>
}

const INPUT_SUMMARY_MAX = 500

function summarize(value: unknown): string {
  let text: string
  try {
    text = JSON.stringify(value) ?? String(value)
  } catch {
    text = String(value)
  }
  return text.length > INPUT_SUMMARY_MAX ? `${text.slice(0, INPUT_SUMMARY_MAX)}…` : text
}

export class ToolRegistry {
  private readonly tools = new Map<string, AgentTool>()

  constructor(
    private readonly workspace: WorkspaceService,
    private readonly audit: AuditService
  ) {}

  register(tool: AgentTool): void {
    if (this.tools.has(tool.name)) throw new Error(`工具已注册: ${tool.name}`)
    this.tools.set(tool.name, tool)
  }

  get(name: string): AgentTool | undefined {
    return this.tools.get(name)
  }

  list(): AgentTool[] {
    return [...this.tools.values()]
  }

  async invoke(name: string, input: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult> {
    const tool = this.tools.get(name)
    if (!tool) throw new Error(`未注册的工具: ${name}`)

    // 围栏校验在审计之前 — 越界尝试不产生审计噪音，直接拒绝
    const prepared: Record<string, unknown> = { ...input }
    if (tool.parameters.properties['path'] && typeof prepared['path'] === 'string') {
      prepared['path'] = this.workspace.resolveInWorkspace(prepared['path'])
    }

    this.audit.record(ctx.userId, name, summarize(input), true)
    try {
      const result = await tool.execute(prepared, ctx)
      this.audit.record(ctx.userId, name, result.summary, result.ok)
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      this.audit.record(ctx.userId, name, `执行异常: ${message}`, false)
      return { ok: false, summary: `工具 ${name} 执行异常`, error: message }
    }
  }
}
