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
import type { AgentTool } from './tool-registry'
import type { WorkspaceService } from '../services/workspace/workspace.service'
import type { AuditService } from '../services/workspace/audit.service'
import { ZERO_USAGE, addUsage } from '../services/model/usage'
import { fitUtf8Prefix, fitUtf8Suffix, utf8ByteLength } from './tools/output-limit'
import {
  DEFAULT_PRUNE_CONFIG,
  applySummaries,
  estimateTurns,
  planPrune,
  targetTokens,
  triggerTokens,
  type PruneConfig,
  type PruneRecord
} from './context/prune'
import { summarizeRounds } from './context/summarize'
import {
  categoryOfPermissionLevel,
  denyMessage,
  resolvePermission,
  ruleFromChoice,
  type PermissionValue,
  type RememberChoice,
  type ResolvedPermission,
  type ToolCategory
} from './permissions/policy'
import { callSignature, evaluateRunaway, type RunawayVerdict } from './guards'
import { AbortRegistry, SteeringBuffer } from './abort'
import type { TokenUsage } from '@shared/types'

/** 单次任务最大 LLM 请求轮数 */
export const MAX_AGENT_ROUNDS = 15

/** 单个写操作确认等待上限（超时按拒绝处理 — 安全默认） */
export const CONFIRM_TIMEOUT_MS = 5 * 60 * 1000

/**
 * 回喂模型的单条 tool_result 序列化上限（保护上下文窗口）。
 *
 * M8-1 修正：原实现是「8000 **字符** 头部硬切」—— 有两个问题：
 *   ① 字符 ≠ 字节，中文场景实际能塞进去的内容远少于预期；
 *   ② **只留头部**会把工具写在尾部的「续读提示 / 错误原因」直接切掉，
 *      导致模型看不到「怎么继续读」——真机实测模型原话「没有看到截断提示」。
 * 现改为「字节预算 + 头尾保留」，预算取 32KB（大于 read_file 的 24KB 工具预算，
 * 留出 JSON 包装余量），确保工具侧的输出与提示能完整抵达模型。
 */
const TOOL_RESULT_MAX_BYTES = 32 * 1024
/** 超限时头尾分配（尾部必须保住续读提示/错误信息） */
const TOOL_RESULT_HEAD_RATIO = 0.6

/** 用户确认决定 */
export type ConfirmDecision = 'approve' | 'reject' | 'stop'

/** M8-3：确认结果（decision + 用户是否选择记住到某作用域） */
export interface ConfirmOutcome {
  decision: ConfirmDecision
  /** 'once' 或缺省 = 仅本次（不落库）；workspace/global = 记住 */
  remember?: RememberChoice
}

/**
 * 工作区守则（AGENTS.md / AGENT.md）注入 system 的预算 —— **按字节** 8KB（M8-3 §6）。
 * 原实现按「字符」截 4000，中文场景实际可达 12KB，与工单「预算 ≤8KB」不符。
 */
const AGENT_MD_MAX_BYTES = 8 * 1024

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
  // M8-3 §6：工作区守则注入。AGENTS.md（复数，对标惯例）优先，回退既有 AGENT.md。
  // 预算 ≤8KB：超限截断并附一行提示（让模型知道还有内容没看到）。
  for (const fileName of ['AGENTS.md', 'AGENT.md']) {
    try {
      const raw = readFileSync(join(workspaceRoot, fileName), 'utf8')
      const clipped = fitUtf8Prefix(raw, AGENT_MD_MAX_BYTES)
      const truncated = clipped.length < raw.length
      lines.push('', `—— 以下是工作区 ${fileName} 行为守则${truncated ? '（已按 8KB 预算节选）' : ''} ——`, clipped)
      if (truncated) lines.push(`（${fileName} 内容超过 8KB 已截断，如需完整守则请直接读取该文件）`)
      break
    } catch {
      /* 该文件不存在则试下一个 */
    }
  }
  return lines.join('\n')
}

/** 循环过程事件 — ipc 层转成 ChatStreamEvent 推给渲染进程 */
export type LoopEvent =
  | { kind: 'text'; delta: string }
  | { kind: 'thinking'; delta: string }
  | { kind: 'round'; round: number; label: string }
  | { kind: 'tool'; call: ToolCallRecord }
  /** M8-2 可观测性：上下文估算与裁切事件（设置页调试区/日志可见） */
  | {
      kind: 'context'
      estimatedTokens: number
      triggerTokens: number
      pruned: boolean
      afterTokens: number
      /** 本次裁切的轮次与动作摘要 */
      actions: { round: number; action: 'trim_tool_result' | 'drop_group'; summarized: boolean }[]
    }

/**
 * 权限端口（M8-3 §1/§2）—— 由装配层注入三层 store 的读写，循环本身不关心存储位置。
 * 缺省实现 = 「只读放行、写类询问」= 现行为（零行为变更）。
 */
export interface PermissionPort {
  /** sessionId 用于取「本次会话」层规则 */
  resolve(category: ToolCategory, sessionId: string): ResolvedPermission
  remember(category: ToolCategory, value: 'allow' | 'deny', choice: RememberChoice, sessionId: string): void
}

export const DEFAULT_PERMISSION_PORT: PermissionPort = {
  resolve: (category) => resolvePermission({ session: {}, workspace: {}, global: {} }, category),
  remember: () => undefined
}

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
  /** V1 用量记账：本次 run 跨轮累计的 token 用量 */
  usage: TokenUsage
}

export class AgentLoopService {
  /** M8-3：统一中止源（用户停止 / 权限拒绝 / runaway / 应用退出） */
  private readonly aborts = new AbortRegistry()
  /** M8-3：steering 缓冲（轮边界注入） */
  private readonly steering = new SteeringBuffer()
  /** M8-2 上下文预算配置（默认 128k 窗口 70% 触发 / 50% 目标） */
  private contextConfig: PruneConfig = { ...DEFAULT_PRUNE_CONFIG }
  /** 最近一次裁切记录（会话元数据 / 调试区展示用） */
  private lastPruneRecords: PruneRecord[] = []
  private lastEstimate = 0

  /** 供设置页调试区读取 */
  contextSnapshot(): {
    estimatedTokens: number
    triggerTokens: number
    targetTokens: number
    config: PruneConfig
    records: PruneRecord[]
  } {
    return {
      estimatedTokens: this.lastEstimate,
      triggerTokens: triggerTokens(this.contextConfig),
      targetTokens: targetTokens(this.contextConfig),
      config: { ...this.contextConfig },
      records: this.lastPruneRecords
    }
  }

  /** 覆盖上下文预算配置（测试/设置页） */
  setContextConfig(patch: Partial<PruneConfig>): PruneConfig {
    this.contextConfig = { ...this.contextConfig, ...patch }
    return this.contextConfig
  }

  /** 进行中的写操作确认（CHAT_CONFIRM_RESOLVE / stop 唤醒） */
  private readonly pendingConfirms = new Map<string, { resolve: (o: ConfirmOutcome) => void; timer: ReturnType<typeof setTimeout> }>()

  constructor(
    private readonly streamTurn: StreamTurnFn,
    private readonly registry: ToolRegistry,
    private readonly workspace: WorkspaceService,
    private readonly audit: AuditService,
    private permissions: PermissionPort = DEFAULT_PERMISSION_PORT
  ) {}

  /** M8-3：装配层注入权限端口（三层 store） */
  setPermissionPort(port: PermissionPort): void {
    this.permissions = port
  }

  /** M8-3 steering：会话进行中用户输入即时指令（轮边界注入，不打断进行中的工具） */
  steer(sessionId: string, text: string): void {
    this.steering.push(sessionId, text)
  }

  /** M8-3：应用退出时中止全部在跑会话（并入统一中止源） */
  abortAllForShutdown(): string[] {
    return this.aborts.abortAll('shutdown')
  }

  /** M8-3：最近一次 runaway 判定（可观测/测试用） */
  lastRunaway: RunawayVerdict | null = null

  /** 用户请求停止（杀在途等待 + HTTP 流 + 轮间空隙） */
  stop(sessionId: string): void {
    this.aborts.for(sessionId).abort('user')
    for (const [key, pending] of this.pendingConfirms) {
      if (key.startsWith(`${sessionId}::`)) {
        this.pendingConfirms.delete(key)
        pending.resolve({ decision: 'stop' })
      }
    }
  }

  /** renderer 回传确认结果；返回 false 表示确认请求不存在/已过期/已超时 */
  resolveConfirm(sessionId: string, callId: string, approve: boolean, remember?: RememberChoice): boolean {
    const key = `${sessionId}::${callId}`
    const pending = this.pendingConfirms.get(key)
    if (!pending) return false
    this.pendingConfirms.delete(key)
    // M8-3：携带「记住」选择（仅本次 / 此工作区 / 全局）—— 仅本次不落库
    pending.resolve({ decision: approve ? 'approve' : 'reject', ...(remember === undefined ? {} : { remember }) })
    return true
  }

  /** 等待用户对某次写操作的决定；超时按拒绝（安全默认：不写） */
  private waitConfirm(sessionId: string, callId: string): Promise<ConfirmOutcome> {
    return new Promise((resolve) => {
      const key = `${sessionId}::${callId}`
      const timer = setTimeout(() => {
        if (this.pendingConfirms.delete(key)) resolve({ decision: 'reject' })
      }, CONFIRM_TIMEOUT_MS)
      this.pendingConfirms.set(key, {
        resolve: (o) => {
          clearTimeout(timer)
          resolve(o)
        },
        timer
      })
    })
  }

  /** confirm 预览用：与 registry.invoke 相同的 path 参数围栏预解析（invoke 仍会自行解析原始入参） */
  private preResolvePath(tool: AgentTool, input: Record<string, unknown>): Record<string, unknown> {
    if (tool.parameters.properties['path'] && typeof input['path'] === 'string') {
      return { ...input, path: this.workspace.resolveInWorkspace(input['path']) }
    }
    return input
  }

  /** registry.list() → Anthropic tools 格式（parameters 已是 JSON Schema，改名 input_schema） */
  /**
   * M8-2：上下文预算管理 —— 触发线判定 → 裁切规划 → 摘要随车 → 记录可观测事件。
   * 返回可直接喂给网关的 turns。**绝不因裁切失败而中断对话**（异常即回退原 turns）。
   */
  private async applyContextBudget(
    turns: readonly AgentTurn[],
    userId: string,
    sessionId: string,
    emit: (e: LoopEvent) => void,
    tools: readonly unknown[] = []
  ): Promise<AgentTurn[]> {
    const config = this.contextConfig
    const estimated = estimateTurns(turns)
    this.lastEstimate = estimated
    const trigger = triggerTokens(config)
    // 预留额度参与触发判定（与 planPrune 内一致）
    const reserveTokens = tools.length > 0 ? config.reserveTokens : 0
    if (estimated + reserveTokens <= trigger) return [...turns]

    try {
      // 第一遍规划：拿到「即将整组裁掉的轮次」，再决定是否生成摘要
      // M8-3 §8：有工具可用时按「预计本轮工具结果」预留额度（无工具则无产出，不预留）
      const reserveTokens = tools.length > 0 ? config.reserveTokens : 0
      const plan = planPrune(turns, config, { reserveTokens })
      let finalPlan = plan
      let summarizedRounds = new Set<number>()

      if (plan.roundsToSummarize.length > 0) {
        // 摘要请求复用注入的 streamTurn（已套 M8-1 提交边界重试），tools 为空、事件静默
        const { summaries } = await summarizeRounds(
          {
            complete: async ({ system: s, user }) => {
              const res = await this.streamTurn(userId, sessionId, {
                system: s,
                turns: [{ role: 'user', content: user }],
                tools: [],
                onEvent: () => undefined
              })
              return res.text
            },
            log: (m) => console.log(m)
          },
          plan.roundsToSummarize
        )
        if (summaries.size > 0) {
          finalPlan = applySummaries(turns, config, summaries)
          summarizedRounds = new Set(summaries.keys())
        }
      }

      this.lastPruneRecords = finalPlan.records
      emit({
        kind: 'context',
        estimatedTokens: finalPlan.beforeTokens,
        triggerTokens: trigger,
        pruned: finalPlan.pruned,
        afterTokens: finalPlan.afterTokens,
        actions: finalPlan.records.map((r) => ({
          round: r.round,
          action: r.action,
          summarized: summarizedRounds.has(r.round)
        }))
      })
      console.log(
        `[context] 触发裁切：${finalPlan.beforeTokens} → ${finalPlan.afterTokens} tokens（触发线 ${trigger}），` +
          `动作 ${finalPlan.records.length} 项，摘要 ${summarizedRounds.size} 轮`
      )
      return finalPlan.turns
    } catch (e) {
      // 上下文管理不能成为新的故障点：失败即原样继续
      console.log(`[context] 裁切失败，按原上下文继续：${e instanceof Error ? e.message : String(e)}`)
      return [...turns]
    }
  }

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
    const abortSrc = this.aborts.for(sessionId)
    const isAborted = (): boolean => abortSrc.aborted
    const tools = this.buildToolDefs()
    const root = this.workspace.getRoot()
    const toolCalls: ToolCallRecord[] = []
    // M8-3 runaway guard 状态（跨轮累计，仅本次 run 有效）
    const callSignatures: string[] = []
    const roundProgress: boolean[] = []
    let wroteThisRound = false
    const textParts: string[] = []
    const thinkingParts: string[] = []

    // 循环内部 turns：起步于纯文本历史，之后追加块结构轮次
    const turns: AgentTurn[] = baseTurns.map((t) => ({ role: t.role === 'assistant' ? 'assistant' : 'user', content: t.content }))
    let round = 0
    let stopped = false
    // V1 用量记账：跨轮累加（每轮 res.usage 归一化后相加）
    let usageTotal: TokenUsage = ZERO_USAGE
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
        wroteThisRound = false

        emit({
          kind: 'round',
          round,
          label: tools.length > 0 ? `第 ${round}/${MAX_AGENT_ROUNDS} 轮 · 正在思考…` : '正在思考…'
        })
        let res: StreamTurnResult
        try {
          // M8-2：送模型前做一次上下文预算管理（未触线则零开销原样返回）
          const budgetedTurns = await this.applyContextBudget(turns, userId, sessionId, emit, tools)
          res = await this.streamTurn(userId, sessionId, {
            system,
            turns: budgetedTurns,
            tools,
            onEvent: (e: StreamTurnEvent) => emit(e.kind === 'text' ? { kind: 'text', delta: e.delta } : { kind: 'thinking', delta: e.delta })
          })
        } catch (err) {
          // 单轮流式失败：前面轮次已产生的内容不丢，错误并入正文说明
          const message = err instanceof Error ? err.message : String(err)
          textParts.push(`⚠️ 第 ${round} 轮生成失败：${message}`)
          break
        }

        usageTotal = addUsage(usageTotal, res.usage)
        if (res.thinking) thinkingParts.push(res.thinking)
        if (res.text) textParts.push(res.text)
        // tool_use 块必须原样回放，Anthropic 协议要求 tool_use → tool_result 相邻配对（thinking 不回传）
        turns.push({ role: 'assistant', content: res.assistantBlocks })
        if (res.stopReason === 'aborted' || isAborted()) {
          stopped = true
          break
        }
        if (res.stopReason !== 'tool_use' || res.toolUses.length === 0) break

        // 逐个执行本响应里的全部 tool_use（含未注册 catch → ok:false 回喂；confirm 工具在循环层拦截）
        const results: AgentContentBlock[] = []
        for (const tu of res.toolUses) {
          if (isAborted()) {
            stopped = true
            break
          }
          const tool = this.registry.get(tu.name)
          const rawInput = (tu.input ?? {}) as Record<string, unknown>

          // ---- M8-3 权限三值判定（deny 直接拒绝 / allow 直接放行 / ask 走确认流）----
          // 工具类别沿用现确认流分组：confirm → write、auto → readonly
          const category: ToolCategory = tool ? categoryOfPermissionLevel(tool.permission) : 'readonly'
          const perm = tool ? this.permissions.resolve(category, sessionId) : { value: 'allow' as PermissionValue, scope: 'default' as const, isDefault: true }
          const ruleTag = `${category}@${perm.scope}=${perm.value}`

          if (tool && perm.value === 'deny') {
            // deny：不弹窗、不执行，审计留痕（含否决来源），回喂中性说明
            this.audit.record(userId, tu.name, `权限禁止: ${summarizeShort(rawInput)}`, false, {
              permissionRule: `${category}@${perm.deniedBy ?? perm.scope}=deny`,
              confirmed: false,
              userChoice: null
            })
            const denied: ToolCallRecord = {
              id: tu.id,
              name: tu.name,
              input: rawInput,
              status: 'rejected',
              summary: `已被权限设置禁止（${category}）`
            }
            upsertCall(toolCalls, denied)
            emit({ kind: 'tool', call: { ...denied } })
            results.push({
              type: 'tool_result',
              tool_use_id: tu.id,
              content: JSON.stringify({ ok: false, denied: true, summary: denyMessage(category, tu.name) }),
              is_error: true
            })
            continue
          }

          // allow 快捷路径：不弹窗，但仍写一条证据（命中规则 + 未弹确认）——
          // 工单要求「每次工具执行追加记录：命中的规则/是否弹确认/用户选择」
          if (tool && perm.value === 'allow' && tool.permission === 'confirm') {
            this.audit.record(userId, tu.name, `按规则放行: ${summarizeShort(rawInput)}`, true, {
              permissionRule: ruleTag,
              confirmed: false,
              userChoice: null
            })
          }

          // ---- confirm 拦截（invoke 保持「已授权即执行」，授权决定在这里）----
          if (tool?.permission === 'confirm' && perm.value === 'ask') {
            let previewData: unknown
            let previewSummary = `等待确认：${tu.name}`
            try {
              const resolvedInput = this.preResolvePath(tool, rawInput)
              if (tool.preview) {
                const pv = await tool.preview(resolvedInput, { userId, workspaceRoot: root ?? '' })
                previewData = pv.data
                previewSummary = pv.summary
              }
            } catch (err) {
              // 预检（围栏/参数）失败 — 与 auto 工具同语义：不执行、不审计、错误回喂
              const message = err instanceof Error ? err.message : String(err)
              const failed: ToolCallRecord = { id: tu.id, name: tu.name, input: rawInput, status: 'error', summary: message }
              upsertCall(toolCalls, failed)
              emit({ kind: 'tool', call: { ...failed } })
              results.push({ type: 'tool_result', tool_use_id: tu.id, content: JSON.stringify({ ok: false, summary: message }), is_error: true })
              continue
            }

            const awaiting: ToolCallRecord = {
              id: tu.id,
              name: tu.name,
              input: rawInput,
              status: 'awaiting_confirm',
              summary: previewSummary,
              data: previewData
            }
            upsertCall(toolCalls, awaiting)
            emit({ kind: 'tool', call: { ...awaiting } })

            const outcome = await this.waitConfirm(sessionId, tu.id)
            const decision = outcome.decision
            if (decision === 'stop') {
              abortSrc.abort('user')
              stopped = true
              break
            }
            if (decision === 'reject') {
              // 记住拒绝（仅本次则不落库）；审计留痕含命中规则与用户选择
              if (outcome.remember && outcome.remember !== 'once') {
                const rule = ruleFromChoice(category, 'deny', outcome.remember)
                if (rule) this.permissions.remember(category, 'deny', outcome.remember, sessionId)
              }
              this.audit.record(userId, tu.name, `用户拒绝: ${summarizeShort(rawInput)}`, false, {
                permissionRule: ruleTag,
                confirmed: true,
                userChoice: 'reject'
              })
              const rejected: ToolCallRecord = { ...awaiting, status: 'rejected', summary: '用户拒绝执行' }
              upsertCall(toolCalls, rejected)
              emit({ kind: 'tool', call: { ...rejected } })
              results.push({
                type: 'tool_result',
                tool_use_id: tu.id,
                content: JSON.stringify({
                  ok: false,
                  denied: true,
                  summary: `用户拒绝了 ${tu.name} 操作，未执行。请调整方案或直接询问用户。`
                }),
                is_error: true
              })
              continue
            }
            // approve → 记住选择（仅本次不落库），随后落入下方正常执行
            if (outcome.remember && outcome.remember !== 'once') {
              this.permissions.remember(category, 'allow', outcome.remember, sessionId)
            }
            this.audit.record(userId, tu.name, `用户允许: ${summarizeShort(rawInput)}`, true, {
              permissionRule: ruleTag,
              confirmed: true,
              userChoice: 'approve'
            })
          }

          const call: ToolCallRecord = { id: tu.id, name: tu.name, input: tu.input, status: 'running', summary: '运行中…' }
          upsertCall(toolCalls, call)
          emit({ kind: 'tool', call: { ...call } })

          let result
          try {
            // sessionId 供 todowrite 等会话级工具使用（M8-3 §7）
            result = await this.registry.invoke(tu.name, rawInput, { userId, workspaceRoot: root ?? '', sessionId })
          } catch (err) {
            const message = err instanceof Error ? err.message : String(err)
            result = { ok: false, summary: `工具不可用：${message}`, error: message }
          }
          call.status = result.ok ? 'ok' : 'error'
          call.summary = result.summary
          call.data = result.cardData ?? result.data
          emit({ kind: 'tool', call: { ...call } })
          results.push({
            type: 'tool_result',
            tool_use_id: tu.id,
            content: serializeToolResult(result),
            is_error: !result.ok
          })

          // ---- M8-3 runaway guard：同工具同参数连击 / 本轮是否有落盘 ----
          callSignatures.push(callSignature(tu.name, rawInput))
          if (result.ok && category === 'write') wroteThisRound = true
          const verdict = evaluateRunaway({ callSignatures, roundProgress })
          this.lastRunaway = verdict
          if (verdict.action === 'abort') {
            abortSrc.abort('runaway', `repeat=${verdict.count ?? 0}`)
            stopped = true
            textParts.push(`— ${verdict.message ?? '检测到重复空转，已自动停止。'}`)
            break
          }
          if (verdict.action === 'warn') {
            textParts.push(`— ${verdict.message ?? ''}`)
          }
        }
        if (stopped) break
        // 每轮结束记录「本轮是否有落盘」，供无进展检测（M8-3 §4 规则②）
        roundProgress.push(wroteThisRound)
        if (roundProgress.length > 20) roundProgress.shift()
        if (callSignatures.length > 20) callSignatures.shift()
        turns.push({ role: 'user', content: results })

        // M8-3 steering：轮边界注入用户在进行中补充的要求。
        // **必须放在工具结果之后** —— 若插在 tool_use 与 tool_result 之间，
        // 会破坏「tool_result 紧随其 tool_use」的协议要求（集成测试抓到过）。
        const pendingSteering = this.steering.drain(sessionId)
        if (pendingSteering.length > 0) {
          turns.push({ role: 'user', content: SteeringBuffer.format(pendingSteering) })
          emit({ kind: 'round', round, label: `已采纳你在进行中补充的 ${pendingSteering.length} 条要求` })
        }
      }

      if (hitCap) {
        textParts.push(`— 已连续执行 ${MAX_AGENT_ROUNDS} 轮工具调用仍未完成，为安全起见本次到此为止。可以继续对话让它接着做。`)
      }
    } finally {
      this.aborts.release(sessionId) // 本次 run 结束：释放中止源（下次任务从干净状态开始）
    }

    const content = textParts.join('\n\n')
    return {
      content,
      usage: usageTotal,
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

function upsertCall(list: ToolCallRecord[], call: ToolCallRecord): void {
  const i = list.findIndex((t) => t.id === call.id)
  if (i >= 0) list[i] = call
  else list.push(call)
}

function summarizeShort(value: unknown): string {
  let text: string
  try {
    text = JSON.stringify(value) ?? String(value)
  } catch {
    text = String(value)
  }
  return text.length > 200 ? `${text.slice(0, 200)}…` : text
}

function serializeToolResult(result: { ok: boolean; summary: string; data?: unknown; error?: string }): string {
  let text: string
  try {
    text = JSON.stringify({ ok: result.ok, summary: result.summary, data: result.data })
  } catch {
    text = JSON.stringify({ ok: result.ok, summary: result.summary, data: String(result.data) })
  }
  return clipToolResultText(text)
}

/**
 * 工具结果回喂裁剪（纯函数，便于离线断言）：超预算时保留头 60% + 尾 40%，
 * 中间以省略标记连接 —— **尾部一定要留住**（续读提示、错误原因都在尾部）。
 */
export function clipToolResultText(text: string, maxBytes = TOOL_RESULT_MAX_BYTES): string {
  const bytes = utf8ByteLength(text)
  if (bytes <= maxBytes) return text
  const marker = `\n…（此处省略 ${bytes} 字节中的中段内容，尾部信息已保留）…\n`
  const markerBytes = utf8ByteLength(marker)
  const budget = Math.max(0, maxBytes - markerBytes)
  const head = fitUtf8Prefix(text, Math.floor(budget * TOOL_RESULT_HEAD_RATIO))
  const tail = fitUtf8Suffix(text, budget - utf8ByteLength(head))
  return `${head}${marker}${tail}`
}
