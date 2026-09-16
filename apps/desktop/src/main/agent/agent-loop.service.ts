// Agent ReAct 循环（工单 C-2 核心）— 多轮「思考→调工具→看结果→再回答」。
// 健壮性契约：未注册工具 catch 后回喂 ok:false tool_result；15 轮上限优雅终止；
// 用户停止可中断流式与循环任意环节（已产生内容保留）；无工作区降级为纯对话。
// streamTurn 注入式设计：离线测试用假网关驱动，不 import 任何 Electron ABI 模块。
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import type {
  AgentContentBlock,
  AgentTurn,
  AnthropicToolDef,
  MessageMeta,
  StreamTurnEvent,
  StreamTurnFn,
  StreamTurnResult,
  ToolCallRecord
} from '@shared/types'
import type { ChatTurn } from '../services/model-gateway.service'
import type { ToolRegistry } from './tool-registry'
import type { WorkspaceService } from '../services/workspace/workspace.service'

/** 单次任务最大 LLM 请求轮数 */
export const MAX_AGENT_ROUNDS = 15

/** 回喂模型的单条 tool_result 序列化上限（保护上下文窗口） */
const TOOL_RESULT_MAX_CHARS = 8000

/** AGENT.md 注入 system 的截断长度 */
const AGENT_MD_MAX_CHARS = 4000

/** Agent system 提示词 — 含工作区根路径与相对路径约定；AGENT.md 存在时节选注入 */
export function buildAgentSystemPrompt(workspaceRoot: string | null): string {
  if (!workspaceRoot) {
    return '你是「小气 · 科研工作台」的研究助理。当前未设置工作区，文件工具不可用，请直接以对话回答用户的科研问题。'
  }
  const lines = [
    '你是「小气 · 科研工作台」的研究助理 Agent，可以调用工作区只读工具（list_dir / read_file / glob / grep）查看文件后再回答。',
    `工作区根目录：${workspaceRoot}`,
    '铁律：',
    '- 工具路径参数一律为相对工作区根的相对路径；.git 目录为禁区，绝不访问。',
    '- 涉及文件内容的问题先动手查（调工具），不要凭空猜测。',
    '- 回答用中文；引用文件时给出相对路径。'
  ]
  try {
    const agentMd = readFileSync(join(workspaceRoot, 'AGENT.md'), 'utf8')
    lines.push('', '—— 以下是工作区 AGENT.md 行为守则（节选）——', agentMd.slice(0, AGENT_MD_MAX_CHARS))
  } catch {
    /* 无守则文件则跳过注入 */
  }
  return lines.join('\n')
}

/** 循环过程事件 — ipc 层转成 ChatStreamEvent 推给渲染进程 */
export type LoopEvent =
  | { kind: 'text'; delta: string }
  | { kind: 'thinking'; delta: string }
  | { kind: 'round'; round: number; label: string }
  | { kind: 'tool'; call: ToolCallRecord }

export interface AgentRunParams {
  userId: string
  sessionId: string
  /** 基础上下文（最近历史 + 本条新消息，content 均为纯文本） */
  baseTurns: ChatTurn[]
  system: string
  /** 流事件出口（text/thinking 增量、轮次、工具卡片状态流转） */
  emit: (e: LoopEvent) => void
}

export interface AgentRunResult {
  content: string
  meta: MessageMeta
}

export class AgentLoopService {
  /** 已请求停止的会话（CHAT_ABORT 置位，run 结束清除） */
  private readonly stopped = new Set<string>()

  constructor(
    private readonly streamTurn: StreamTurnFn,
    private readonly registry: ToolRegistry,
    private readonly workspace: WorkspaceService
  ) {}

  /** 用户请求停止（与网关 HTTP abort 并联：一个杀在途流，一个杀轮间空隙） */
  stop(sessionId: string): void {
    this.stopped.add(sessionId)
  }

  /** registry.list() → Anthropic tools 格式（parameters 已是 JSON Schema，改名 input_schema） */
  buildToolDefs(): AnthropicToolDef[] {
    if (!this.workspace.getRoot()) return [] // 无工作区 → 不提供任何工具
    return this.registry.list().map((t) => ({
      name: t.name,
      description: t.description,
      input_schema: t.parameters as Record<string, unknown>
    }))
  }

  async run(params: AgentRunParams): Promise<AgentRunResult> {
    const { userId, sessionId, baseTurns, system, emit } = params
    const isAborted = (): boolean => this.stopped.has(sessionId)
    const tools = this.buildToolDefs()
    const root = this.workspace.getRoot()
    const toolCalls: ToolCallRecord[] = []
    const textParts: string[] = []
    const thinkingParts: string[] = []

    // 循环内部 turns：起步于纯文本历史，之后追加块结构轮次
    const turns: AgentTurn[] = baseTurns.map((t) => ({ role: t.role === 'assistant' ? 'assistant' : 'user', content: t.content }))
    let round = 0
    let stopped = false
    let hitCap = false

    try {
      for (;;) {
        if (isAborted()) {
          stopped = true
          break
        }
        if (round >= MAX_AGENT_ROUNDS) {
          hitCap = true
          break
        }
        round++

        emit({ kind: 'round', round, label: tools.length > 0 ? `第 ${round} 轮 · 正在思考…` : '正在思考…' })
        let res: StreamTurnResult
        try {
          res = await this.streamTurn(userId, sessionId, {
            system,
            turns,
            tools,
            onEvent: (e: StreamTurnEvent) => emit(e.kind === 'text' ? { kind: 'text', delta: e.delta } : { kind: 'thinking', delta: e.delta })
          })
        } catch (err) {
          // 单轮流式失败：前面轮次已产生的内容不丢，错误并入正文说明
          const message = err instanceof Error ? err.message : String(err)
          textParts.push(`⚠️ 第 ${round} 轮生成失败：${message}`)
          break
        }

        if (res.thinking) thinkingParts.push(res.thinking)
        if (res.text) textParts.push(res.text)
        // tool_use 块必须原样回放，Anthropic 协议要求 tool_use → tool_result 相邻配对（thinking 不回传）
        turns.push({ role: 'assistant', content: res.assistantBlocks })
        if (res.stopReason === 'aborted' || isAborted()) {
          stopped = true
          break
        }
        if (res.stopReason !== 'tool_use' || res.toolUses.length === 0) break

        // 逐个执行本响应里的全部 tool_use（含未注册 catch → ok:false 回喂）
        const results: AgentContentBlock[] = []
        for (const tu of res.toolUses) {
          if (isAborted()) {
            stopped = true
            break
          }
          const call: ToolCallRecord = { id: tu.id, name: tu.name, input: tu.input, status: 'running', summary: '运行中…' }
          toolCalls.push(call)
          emit({ kind: 'tool', call: { ...call } })

          let result
          try {
            result = await this.registry.invoke(tu.name, tu.input ?? {}, { userId, workspaceRoot: root ?? '' })
          } catch (err) {
            const message = err instanceof Error ? err.message : String(err)
            result = { ok: false, summary: `工具不可用：${message}`, error: message }
          }
          call.status = result.ok ? 'ok' : 'error'
          call.summary = result.summary
          call.data = result.data
          emit({ kind: 'tool', call: { ...call } })
          results.push({
            type: 'tool_result',
            tool_use_id: tu.id,
            content: serializeToolResult(result),
            is_error: !result.ok
          })
        }
        if (stopped) break
        turns.push({ role: 'user', content: results })
      }

      if (hitCap) {
        textParts.push(`— 已连续执行 ${MAX_AGENT_ROUNDS} 轮工具调用仍未完成，为安全起见本次到此为止。可以继续对话让它接着做。`)
      }
    } finally {
      this.stopped.delete(sessionId) // 只清本次 run 的停止标记
    }

    const content = textParts.join('\n\n')
    return {
      content,
      meta: {
        thinking: thinkingParts.join('\n\n') || undefined,
        tools: toolCalls.length > 0 ? toolCalls : undefined,
        rounds: round,
        stopped: stopped || undefined,
        hitRoundCap: hitCap || undefined,
        toolsAvailable: tools.length > 0 ? undefined : false
      }
    }
  }
}

function serializeToolResult(result: { ok: boolean; summary: string; data?: unknown; error?: string }): string {
  let text: string
  try {
    text = JSON.stringify({ ok: result.ok, summary: result.summary, data: result.data })
  } catch {
    text = JSON.stringify({ ok: result.ok, summary: result.summary, data: String(result.data) })
  }
  return text.length > TOOL_RESULT_MAX_CHARS ? `${text.slice(0, TOOL_RESULT_MAX_CHARS)}…(截断)` : text
}
