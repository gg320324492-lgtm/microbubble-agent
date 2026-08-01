/**
 * AssistantPhase 纯状态机 — chat 思考 UI 阶段推导（2026-08-02 W99 +12）
 *
 * 设计目标：
 * 1. 零依赖（不 import Vue / pinia / axios / sse）— 单测 0 mock
 * 2. 单调递进 + 显式重置（防御 SSE 乱序 / 并发工具 / abort race）
 * 3. 文案 / 阶段 / 推导全集中于此，桌面 + 移动 + 单测共用同源
 *
 * 阶段映射（rank 守卫）：
 *   queued(0) → thinking(1) → retrieving(2) → found(3)
 *     → synthesizing(4) → generating(5) → refining(5) [rank 同 generating]
 *   终态（显式重置）：done / aborted / error（rank=99，不可复活）
 */

export type AssistantPhase =
  | 'queued'
  | 'thinking'
  | 'retrieving'
  | 'found'
  | 'synthesizing'
  | 'generating'
  | 'refining'
  | 'done'
  | 'aborted'
  | 'error'

const PHASE_RANK: Record<AssistantPhase, number> = {
  queued: 0,
  thinking: 1,
  retrieving: 2,
  found: 3,
  synthesizing: 4,
  generating: 5,
  refining: 5,
  done: 99,
  aborted: 99,
  error: 99,
}

const TERMINAL: ReadonlySet<AssistantPhase> = new Set(['done', 'aborted', 'error'])

/** 视为"检索类"的工具名 — 触发 retrieving/found 阶段 */
export const RETRIEVAL_TOOLS = ['search_knowledge', 'web_search', 'hybrid_retrieve'] as const

export interface PhaseCtx {
  foundCount?: number
  retryCount?: number
}

/** 文案不带 emoji — 图标由 ThinkingCapsule 按 phase 渲染，便于 reduced-motion 降级 */
export const PHASE_LABELS: Record<AssistantPhase, (c?: PhaseCtx) => string> = {
  queued: () => '正在理解问题',
  thinking: () => '正在思考',
  retrieving: () => '正在检索',
  found: (c) => `找到 ${c?.foundCount ?? 0} 条相关内容`,
  synthesizing: () => '正在组织回答',
  generating: () => '正在生成',
  refining: (c) =>
    c?.retryCount ? `正在重新优化（第 ${c.retryCount} 次）` : '正在重新优化',
  done: () => '已完成',
  aborted: () => '已中断',
  error: () => '出错了',
}

export const phaseLabel = (p: AssistantPhase, c?: PhaseCtx): string =>
  (PHASE_LABELS[p] ?? PHASE_LABELS.queued)(c)

export const isTerminalPhase = (p: AssistantPhase): boolean => TERMINAL.has(p)

export const isRetrievalTool = (n?: string): boolean =>
  !!n && (RETRIEVAL_TOOLS as readonly string[]).includes(n)

/**
 * 单调递进 + 显式重置守卫
 * - 终态 next 是显式重置指令（abort/done/error 互不复活）
 * - 终态 cur 不可被任何非终态覆盖
 * - refining 是显式重置（后端已清空 content）
 * - refining → generating 允许（重试后再次生成）
 * - 其余严格按 PHASE_RANK 比较，只许前进
 */
export function advancePhase(
  current: AssistantPhase | undefined,
  next: AssistantPhase,
): AssistantPhase {
  const cur = current ?? 'queued'
  if (isTerminalPhase(next)) return next
  if (isTerminalPhase(cur)) return cur
  if (next === 'refining') return 'refining'
  if (cur === 'refining' && next === 'generating') return 'generating'
  return PHASE_RANK[next] > PHASE_RANK[cur] ? next : cur
}

/** SSE 事件 → AssistantPhase 映射（无副作用，null 表示不切换阶段） */
export function phaseFromEvent(evt: {
  type: string
  tool_name?: string
}): AssistantPhase | null {
  switch (evt.type) {
    case 'thinking':
      return 'thinking'
    case 'intent_detected':
      // 据主拍决策：并入 thinking（同 rank 1，advancePhase 自然吞掉）
      return 'thinking'
    case 'tool_use':
      return isRetrievalTool(evt.tool_name) ? 'retrieving' : 'thinking'
    case 'tool_result':
      return isRetrievalTool(evt.tool_name) ? 'found' : null
    case 'synthesis_start':
      return 'synthesizing'
    case 'text_delta':
      return 'generating'
    case 'retry':
      return 'refining'
    case 'done':
      return 'done'
    case 'error':
      return 'error'
    default:
      return null
  }
}

/**
 * 从 tool_result.output 推断结果数
 * 支持 results / items / 数组 3 种字段名 + 边界 fallback
 */
export function countResults(output: unknown): number {
  const o = (output as Record<string, unknown>) || {}
  if (Array.isArray(o.results)) return (o.results as unknown[]).length
  if (Array.isArray(o.items)) return (o.items as unknown[]).length
  return 0
}

/**
 * 僵尸 phase 净化（防御 R1 — 流式中刷新）
 * - state='streaming' 反序列化时不可能还在流式
 * - phase 非终态必收敛为 done / aborted
 * - 删 phaseStartedAt（elapsed 无意义，防显示"3721.4s"）
 */
export interface RestorableMessage {
  state?: string
  content?: string | null
  phase?: string | null
  phaseStartedAt?: number | null
  generatingDispatched?: boolean
}

export function sanitizeRestored<T extends RestorableMessage>(m: T): T {
  if (m.state === 'streaming') {
    m.state = m.content ? 'idle' : 'aborted'
  }
  if (!m.phase || !isTerminalPhase(m.phase as AssistantPhase)) {
    m.phase = m.state === 'aborted' ? 'aborted' : 'done'
  }
  delete m.phaseStartedAt
  m.generatingDispatched = undefined
  return m
}