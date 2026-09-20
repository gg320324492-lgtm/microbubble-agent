// LLM 摘要随车（工单 M8-2 §3）— 纯逻辑 + 注入式 LLM 调用，离线可断言。
//
// 语义：
//   · 整组裁切**之前**，把该轮次交给 LLM 生成 ≤200 token 的摘要，以一条注记替换原内容
//     （形如「[第 3–5 轮已摘要：…]」），把「被丢掉的信息」赎回一部分
//   · **失败/超时一律降级为纯删除 + 标记**，绝不阻塞主流程（上下文管理不能成为新的故障点）
//   · 摘要请求本身走 M8-1 的提交边界重试装配（由调用方注入 complete 函数）
//   · 摘要本身有预算上限（按 token 估算截断，避免摘要又变成新的膨胀源）

import type { AgentTurn } from '@shared/types'
import { estimateTextTokens, utf8Bytes } from './estimate'

/** 单轮摘要的 token 上限（工单要求 ≤200） */
export const DEFAULT_MAX_SUMMARY_TOKENS = 200
/** 摘要生成的默认超时（毫秒） */
export const DEFAULT_SUMMARY_TIMEOUT_MS = 20_000

export interface SummarizeDeps {
  /** 调一次 LLM 补全（调用方负责套 M8-1 重试装配）。返回纯文本 */
  complete: (input: { system: string; user: string }) => Promise<string>
  maxSummaryTokens?: number
  timeoutMs?: number
  now?: () => number
  /** 日志钩子（可选） */
  log?: (message: string) => void
}

export interface SummaryOutcome {
  round: number
  ok: boolean
  summary?: string
  /** 失败原因（中性，可入日志） */
  reason?: string
}

/** 摘要提示词（把该轮次渲染成可读文本交给模型） */
export function buildSummaryPrompt(round: number, turns: readonly AgentTurn[]): { system: string; user: string } {
  const system =
    '你是一个会话压缩器。请把给定的一轮工具交互压缩成不超过 200 token 的中文摘要，' +
    '只保留：用户在做什么、调用了什么工具、得到了什么关键结论/数据、对后续对话有用的约束。' +
    '不要复述大段原文，不要评价，直接输出摘要正文。'
  const parts: string[] = [`以下是要压缩的第 ${round} 轮内容：`]
  for (const t of turns) {
    const role = t.role === 'assistant' ? '助手' : '用户/工具'
    if (typeof t.content === 'string') {
      parts.push(`【${role}】${t.content}`)
      continue
    }
    for (const b of t.content) {
      if (b.type === 'text') parts.push(`【${role}·正文】${b.text}`)
      else if (b.type === 'tool_use') {
        let input = ''
        try {
          input = JSON.stringify(b.input ?? {})
        } catch {
          input = String(b.input)
        }
        parts.push(`【${role}·调用工具】${b.name} 参数 ${input}`)
      } else if (b.type === 'tool_result') {
        parts.push(`【工具结果】${b.content}`)
      }
    }
  }
  return { system, user: parts.join('\n') }
}

/**
 * 按 token 预算截断摘要文本（保守：宁短勿长）。
 * 用 estimateTextTokens 逐段回退，保证不切断字符。
 */
export function truncateSummary(text: string, maxTokens: number): string {
  const trimmed = text.trim()
  if (estimateTextTokens(trimmed) <= maxTokens) return trimmed
  const chars = [...trimmed]
  let out = ''
  for (const ch of chars) {
    const candidate = out + ch
    if (estimateTextTokens(candidate) > maxTokens) break
    out = candidate
  }
  return out ? `${out}…` : ''
}

/** 带超时的 Promise 包装（超时即降级，不抛出） */
async function withTimeout<T>(p: Promise<T>, ms: number): Promise<{ ok: true; value: T } | { ok: false; reason: string }> {
  let timer: ReturnType<typeof setTimeout> | null = null
  const timeout = new Promise<{ ok: false; reason: string }>((resolve) => {
    timer = setTimeout(() => resolve({ ok: false, reason: `摘要超时（>${ms}ms）` }), ms)
  })
  try {
    const raced = await Promise.race([p.then((value) => ({ ok: true as const, value })), timeout])
    return raced
  } catch (e) {
    return { ok: false, reason: e instanceof Error ? e.message : String(e) }
  } finally {
    if (timer) clearTimeout(timer)
  }
}

/**
 * 生成单轮摘要。**永不抛出** —— 失败时返回 ok:false，调用方据此降级为纯删除。
 */
export async function summarizeRound(
  deps: SummarizeDeps,
  round: number,
  turns: readonly AgentTurn[]
): Promise<SummaryOutcome> {
  const maxTokens = deps.maxSummaryTokens ?? DEFAULT_MAX_SUMMARY_TOKENS
  const timeoutMs = deps.timeoutMs ?? DEFAULT_SUMMARY_TIMEOUT_MS
  try {
    const { system, user } = buildSummaryPrompt(round, turns)
    const res = await withTimeout(deps.complete({ system, user }), timeoutMs)
    if (!res.ok) {
      deps.log?.(`[context] 第 ${round} 轮摘要降级：${res.reason}`)
      return { round, ok: false, reason: res.reason }
    }
    const summary = truncateSummary(String(res.value ?? ''), maxTokens)
    if (!summary) {
      deps.log?.(`[context] 第 ${round} 轮摘要为空，降级为纯删除`)
      return { round, ok: false, reason: '摘要为空' }
    }
    deps.log?.(`[context] 第 ${round} 轮摘要完成（${utf8Bytes(summary)} 字节）`)
    return { round, ok: true, summary }
  } catch (e) {
    const reason = e instanceof Error ? e.message : String(e)
    deps.log?.(`[context] 第 ${round} 轮摘要失败：${reason}`)
    return { round, ok: false, reason }
  }
}

/**
 * 批量生成摘要（并发；单个失败不影响其它）。
 * 返回可直接喂给 planPrune 的 summaries Map（只含成功的）。
 */
export async function summarizeRounds(
  deps: SummarizeDeps,
  rounds: readonly { round: number; turns: AgentTurn[] }[]
): Promise<{ summaries: Map<number, string>; outcomes: SummaryOutcome[] }> {
  const outcomes = await Promise.all(rounds.map((r) => summarizeRound(deps, r.round, r.turns)))
  const summaries = new Map<number, string>()
  for (const o of outcomes) if (o.ok && o.summary) summaries.set(o.round, o.summary)
  return { summaries, outcomes }
}
