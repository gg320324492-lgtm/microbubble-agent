// 会话级上下文裁切（工单 M8-2 §2）— 纯函数，零 Electron / 零依赖 / 离线可穷举。
//
// 要解决的问题：M8-1 只管「单条」工具结果的预算，**多轮累积**仍会撑爆上下文
// （长会话 + 多工具轮次 + 多次大文件读取叠加）。
//
// 本模块的语义（工单硬要求）：
//   ① 触发线：估算总量超过「窗口 × 70%」才动手，裁到「窗口 × 50%」为止
//   ② 保留近端：最近 K 轮（默认 3）与 system 永不裁切；**最早的用户目标消息**保留
//   ③ **工具组原子裁切**：一轮的 tool_use 与对应 tool_result 必须同切同留 ——
//      绝不允许出现孤儿 tool_result（协议会直接报错）或悬空 tool_use
//   ④ 裁切顺序：最老的「可裁轮次」先动；单轮内先裁**工具结果正文**（复用 M8-1 头尾语义），
//      仍不够再整组裁掉
//   ⑤ 裁切记录（轮次/字节/token/时间）产出给会话元数据，供日志与 UI 查询

import type { AgentContentBlock, AgentTurn } from '@shared/types'
import { estimateContext, utf8Bytes, type EstimateMessage, type EstimateSegment } from './estimate'
import { fitUtf8Prefix, fitUtf8Suffix } from '../tools/output-limit'

export interface PruneConfig {
  /** 模型上下文窗口假设（token）—— 可配置，默认 131072 */
  windowTokens: number
  /** 触发线比例：超过「窗口 × 此值」才裁（默认 0.7） */
  triggerRatio: number
  /** 目标比例：裁到「窗口 × 此值」为止（默认 0.5） */
  targetRatio: number
  /** 保留近端轮次数（默认 3） */
  keepRecentRounds: number
  /** 单条工具结果正文裁剪预算（字节）；复用 M8-1 的头尾语义 */
  toolResultTrimBytes: number
  /**
   * 轮次开始的**预算预留**（token，M8-3 §8）：按「预计本轮工具结果」预留额度，
   * 让触发线判定前移，减少「刚裁完又被一轮大结果顶爆」。0 = 不预留。
   */
  reserveTokens: number
}

export const DEFAULT_PRUNE_CONFIG: PruneConfig = {
  windowTokens: 131072,
  triggerRatio: 0.7,
  targetRatio: 0.5,
  keepRecentRounds: 3,
  toolResultTrimBytes: 8 * 1024,
  // 预留 ≈ 24KB 工具结果（≈6k tokens）再留一点余量 —— 与 read_file 的 24KB 预算同量级
  reserveTokens: 6 * 1024
}

/** 可配置项的合法范围（越界即回退默认，避免坏配置把预算算歪） */
export const PRUNE_CONFIG_RANGES = {
  windowTokens: { min: 4096, max: 4 * 1024 * 1024 },
  triggerRatio: { min: 0.1, max: 0.95 },
  targetRatio: { min: 0.05, max: 0.9 },
  keepRecentRounds: { min: 0, max: 50 },
  toolResultTrimBytes: { min: 256, max: 256 * 1024 },
  reserveTokens: { min: 0, max: 64 * 1024 }
} as const

/**
 * 归一化用户配置（纯函数）：逐项做范围校验，越界/非法一律回退默认。
 * 约束：targetRatio 必须 < triggerRatio（否则会「裁到比触发线还高」而永不生效）——
 * 不满足时 targetRatio 回退默认（默认 0.5 < 0.7 ✓）。
 */
export function normalizePruneConfig(raw: unknown): PruneConfig {
  const o = (raw ?? {}) as Record<string, unknown>
  const num = (v: unknown): number | undefined => (typeof v === 'number' && Number.isFinite(v) ? v : undefined)
  const clamp = (v: number | undefined, key: keyof typeof PRUNE_CONFIG_RANGES, fallback: number): number => {
    const r = PRUNE_CONFIG_RANGES[key]
    if (v === undefined || v < r.min || v > r.max) return fallback
    return v
  }

  const windowTokens = clamp(num(o['windowTokens']), 'windowTokens', DEFAULT_PRUNE_CONFIG.windowTokens)
  const triggerRatio = clamp(num(o['triggerRatio']), 'triggerRatio', DEFAULT_PRUNE_CONFIG.triggerRatio)
  let targetRatio = clamp(num(o['targetRatio']), 'targetRatio', DEFAULT_PRUNE_CONFIG.targetRatio)
  if (targetRatio >= triggerRatio) {
    // 不能简单回退到默认目标比例：用户把 triggerRatio 调小（如 0.3）时，默认 0.5 仍 >= 0.3，
    // 会「裁到比触发线还高」→ 永远不生效。改为按默认比例（0.5/0.7）等比缩到触发线以下。
    const keepDefaultProportion = (DEFAULT_PRUNE_CONFIG.targetRatio / DEFAULT_PRUNE_CONFIG.triggerRatio) * triggerRatio
    targetRatio = Math.max(PRUNE_CONFIG_RANGES.targetRatio.min, Math.min(keepDefaultProportion, triggerRatio * 0.9))
  }
  const keepRecentRounds = Math.floor(
    clamp(num(o['keepRecentRounds']), 'keepRecentRounds', DEFAULT_PRUNE_CONFIG.keepRecentRounds)
  )
  const toolResultTrimBytes = Math.floor(
    clamp(num(o['toolResultTrimBytes']), 'toolResultTrimBytes', DEFAULT_PRUNE_CONFIG.toolResultTrimBytes)
  )
  const reserveTokens = Math.floor(clamp(num(o['reserveTokens']), 'reserveTokens', DEFAULT_PRUNE_CONFIG.reserveTokens))

  return { windowTokens, triggerRatio, targetRatio, keepRecentRounds, toolResultTrimBytes, reserveTokens }
}

/** 触发线（token） */
export function triggerTokens(config: PruneConfig): number {
  return Math.floor(config.windowTokens * config.triggerRatio)
}

/** 目标线（token） */
export function targetTokens(config: PruneConfig): number {
  return Math.floor(config.windowTokens * config.targetRatio)
}

export interface PruneRecord {
  round: number
  /** body = 只裁了工具结果正文；group = 整组裁掉 */
  action: 'trim_tool_result' | 'drop_group'
  beforeTokens: number
  afterTokens: number
  beforeBytes: number
  afterBytes: number
  at: number
}

export interface PrunePlan {
  /** 裁切后的 turns（可直接喂给网关） */
  turns: AgentTurn[]
  pruned: boolean
  beforeTokens: number
  afterTokens: number
  records: PruneRecord[]
  /** 需要生成摘要的轮次（整组裁切前随车调用 LLM） */
  roundsToSummarize: { round: number; turns: AgentTurn[] }[]
}

/** 把循环内部的 AgentTurn 转成估算用的中性消息 */
export function toEstimateMessage(turn: AgentTurn): EstimateMessage {
  const segments: EstimateSegment[] = []
  if (typeof turn.content === 'string') {
    segments.push({ kind: 'text', text: turn.content })
  } else {
    for (const block of turn.content) {
      if (block.type === 'text') segments.push({ kind: 'text', text: block.text })
      else if (block.type === 'tool_use') segments.push({ kind: 'tool_use', name: block.name, input: block.input })
      else if (block.type === 'tool_result')
        segments.push({ kind: 'tool_result', text: block.content, ...(block.is_error ? { isError: true } : {}) })
    }
  }
  return { role: turn.role, segments }
}

export function estimateTurns(turns: readonly AgentTurn[]): number {
  return estimateContext(turns.map(toEstimateMessage)).total
}

// ---------------------------------------------------------------- 轮次切分

export interface TurnRound {
  /** 轮次序号（1 基，按出现顺序） */
  round: number
  /** 该轮占用的 turns 下标（assistant 及其对应 tool_result 的 user 消息） */
  indexes: number[]
  /** 该轮含 tool_use（工具组）还是纯文本 */
  hasToolGroup: boolean
  /** 该轮工具结果的 turns 下标 */
  resultIndexes: number[]
  /** 该轮内 tool_result 的 tool_use_id 集合 */
  toolUseIds: string[]
}

/**
 * 把 turns 切成「轮次」。一轮 = 一条含 tool_use 的 assistant 消息 + 紧随其后承载其
 * tool_result 的 user 消息（可能跨多条 user 消息）。纯文本消息各自成轮。
 */
export function splitRounds(turns: readonly AgentTurn[]): TurnRound[] {
  const rounds: TurnRound[] = []
  let roundNo = 0
  let i = 0
  while (i < turns.length) {
    const turn = turns[i]!
    roundNo += 1
    const ids: string[] = []
    if (turn.role === 'assistant' && Array.isArray(turn.content)) {
      for (const b of turn.content) if (b.type === 'tool_use') ids.push(b.id)
    }
    const indexes = [i]
    const resultIndexes: number[] = []
    if (ids.length > 0) {
      // 向后收拢承载这些 tool_result 的 user 消息（同轮）
      let j = i + 1
      const pending = new Set(ids)
      while (j < turns.length && pending.size > 0) {
        const next = turns[j]!
        if (next.role !== 'user' || !Array.isArray(next.content)) break
        let matched = false
        for (const b of next.content) {
          if (b.type === 'tool_result' && pending.has(b.tool_use_id)) {
            pending.delete(b.tool_use_id)
            matched = true
          }
        }
        if (!matched) break
        indexes.push(j)
        resultIndexes.push(j)
        j += 1
      }
    }
    rounds.push({ round: roundNo, indexes, hasToolGroup: ids.length > 0, resultIndexes, toolUseIds: ids })
    i = indexes[indexes.length - 1]! + 1
  }
  return rounds
}

// ---------------------------------------------------------------- 协议有效性

export interface ToolPairingIssue {
  messageIndex: number
  kind: 'orphan_tool_result' | 'dangling_tool_use'
  toolUseId: string
}

/**
 * 校验 tool_use / tool_result 配对。返回违规项：
 *   · orphan_tool_result：出现了没有对应 tool_use 的 tool_result（协议直接报错）
 *   · dangling_tool_use：tool_use 没有对应 tool_result（模型会以为工具没执行）
 * 裁切后的结果必须为空数组。
 */
export function validateToolPairing(turns: readonly AgentTurn[]): ToolPairingIssue[] {
  const issues: ToolPairingIssue[] = []
  const useIds = new Set<string>()
  const resultIds = new Set<string>()
  const useAt = new Map<string, number>()
  const resultAt = new Map<string, number>()

  turns.forEach((turn, index) => {
    if (!Array.isArray(turn.content)) return
    for (const b of turn.content) {
      if (b.type === 'tool_use') {
        useIds.add(b.id)
        useAt.set(b.id, index)
      } else if (b.type === 'tool_result') {
        resultIds.add(b.tool_use_id)
        resultAt.set(b.tool_use_id, index)
      }
    }
  })

  for (const id of resultIds) {
    if (!useIds.has(id)) issues.push({ messageIndex: resultAt.get(id) ?? -1, kind: 'orphan_tool_result', toolUseId: id })
  }
  for (const id of useIds) {
    if (!resultIds.has(id)) issues.push({ messageIndex: useAt.get(id) ?? -1, kind: 'dangling_tool_use', toolUseId: id })
  }
  return issues
}

// ---------------------------------------------------------------- 正文裁剪（复用 M8-1 头尾语义）

/** 工具结果正文裁剪：头 60% + 尾 40%，尾部保住（与 M8-1 clipToolResultText 同语义） */
export function trimToolResultText(text: string, maxBytes: number): string {
  const bytes = utf8Bytes(text)
  if (bytes <= maxBytes) return text
  const marker = `\n…（此处省略 ${bytes} 字节中的中段内容，尾部信息已保留）…\n`
  const markerBytes = utf8Bytes(marker)
  const budget = Math.max(0, maxBytes - markerBytes)
  const head = fitUtf8Prefix(text, Math.floor(budget * 0.6))
  const tail = fitUtf8Suffix(text, budget - utf8Bytes(head))
  return `${head}${marker}${tail}`
}

// ---------------------------------------------------------------- 裁切规划

export interface PlanPruneOptions {
  /** 摘要注记：整组裁切时用 system 注记替换（key = 轮次号） */
  summaries?: Map<number, string>
  /** 当前时间（注入，便于离线断言记录） */
  now?: number
  /** 覆盖预留额度（缺省取配置里的 reserveTokens） */
  reserveTokens?: number
}

/**
 * 规划裁切（纯函数）。
 *
 * 返回的 `roundsToSummarize` 表示「这些轮次即将整组裁掉，请先给摘要」——
 * 调用方（循环装配）拿到摘要后，用 `summaries` 再调一次即可得到最终 turns。
 * 这样裁切决策本身保持纯函数、可离线穷举。
 */
export function planPrune(
  turns: readonly AgentTurn[],
  config: PruneConfig = DEFAULT_PRUNE_CONFIG,
  options: PlanPruneOptions = {}
): PrunePlan {
  const now = options.now ?? Date.now()
  const beforeTokens = estimateTurns(turns)
  const trigger = triggerTokens(config)
  // M8-3 §8 预算预留：按「预计本轮还会产出多少工具结果」把判定前移
  const reserve = options.reserveTokens ?? config.reserveTokens

  // 未触线（含预留）→ 原样返回（零副作用）
  if (beforeTokens + reserve <= trigger) {
    return { turns: [...turns], pruned: false, beforeTokens, afterTokens: beforeTokens, records: [], roundsToSummarize: [] }
  }

  const rounds = splitRounds(turns)
  const target = targetTokens(config)
  // 近端保留：最后 K 轮 + 第一条用户目标消息所在的轮次
  const firstUserRound = rounds.find((r) => {
    const t = turns[r.indexes[0]!]
    return t?.role === 'user' && typeof t.content === 'string'
  })
  const protectedRounds = new Set<number>()
  for (const r of rounds.slice(-Math.max(0, config.keepRecentRounds))) protectedRounds.add(r.round)
  if (firstUserRound) protectedRounds.add(firstUserRound.round)

  const prunable = rounds.filter((r) => !protectedRounds.has(r.round))
  const records: PruneRecord[] = []
  const roundsToSummarize: { round: number; turns: AgentTurn[] }[] = []

  // 关键：所有裁切都在**原始下标**上规划，最后一次性组装输出。
  // （早先实现是「边裁边按 round.indexes 过滤 current」，一旦发生整组删除，
  //   后续轮次的原始下标就会与已缩短的数组错位 —— 会误改近端、把摘要插到错误位置。
  //   离线测试抓到了这个漂移，故改为「先规划、后组装」。）
  const trims = new Map<number, string>() // turnIndex -> 裁剪后的 tool_result 正文
  const dropped = new Set<number>() // 轮次号
  const summaryNotes = new Map<number, string>() // 轮次号 -> 摘要注记

  const projectBytes = (): number => {
    let n = 0
    turns.forEach((turn, i) => {
      if (dropped.has(roundOfIndex.get(i) ?? -1)) return
      n += utf8Bytes(typeof turn.content === 'string' ? turn.content : JSON.stringify(applyTrim(turn, i).content))
    })
    for (const [roundNo, note] of summaryNotes) {
      if (!dropped.has(roundNo)) n += utf8Bytes(note)
    }
    return n
  }

  const projectTokens = (): number => {
    const projected: AgentTurn[] = []
    turns.forEach((turn, i) => {
      if (dropped.has(roundOfIndex.get(i) ?? -1)) return
      projected.push(applyTrim(turn, i))
    })
    for (const [roundNo, note] of summaryNotes) {
      const at = rounds.find((r) => r.round === roundNo)?.indexes[0]
      if (at !== undefined && !dropped.has(roundNo)) projected.splice(Math.min(at, projected.length), 0, { role: 'user', content: note })
    }
    return estimateTurns(projected)
  }

  const roundOfIndex = new Map<number, number>()
  for (const r of rounds) for (const i of r.indexes) roundOfIndex.set(i, r.round)

  const applyTrim = (turn: AgentTurn, index: number): AgentTurn => {
    const next = trims.get(index)
    if (next === undefined || !Array.isArray(turn.content)) return turn
    return {
      ...turn,
      content: turn.content.map((b: AgentContentBlock) =>
        b.type === 'tool_result' && b.content !== next ? { ...b, content: next } : b
      )
    }
  }

  // 阶段一：只裁最老可裁轮次的「工具结果正文」（成本最低，信息保留最多）
  for (const round of prunable) {
    if (projectTokens() <= target) break
    const before = projectTokens()
    const beforeB = projectBytes()
    let changed = false
    for (const i of round.resultIndexes) {
      const turn = turns[i]!
      if (!Array.isArray(turn.content)) continue
      for (const b of turn.content) {
        if (b.type !== 'tool_result') continue
        const trimmed = trimToolResultText(b.content, config.toolResultTrimBytes)
        if (trimmed !== b.content) {
          trims.set(i, trimmed)
          changed = true
        }
      }
    }
    if (!changed) continue
    records.push({
      round: round.round,
      action: 'trim_tool_result',
      beforeTokens: before,
      afterTokens: projectTokens(),
      beforeBytes: beforeB,
      afterBytes: projectBytes(),
      at: now
    })
  }

  // 阶段二：仍超目标 → 整组裁切（tool_use + tool_result 同切），有摘要则替换为注记
  for (const round of prunable) {
    if (projectTokens() <= target) break
    const before = projectTokens()
    const beforeB = projectBytes()
    dropped.add(round.round)
    const summary = options.summaries?.get(round.round)
    if (summary) summaryNotes.set(round.round, `[第 ${round.round} 轮已摘要：${summary}]`)
    records.push({
      round: round.round,
      action: 'drop_group',
      beforeTokens: before,
      afterTokens: projectTokens(),
      beforeBytes: beforeB,
      afterBytes: projectBytes(),
      at: now
    })
    if (!summary) {
      roundsToSummarize.push({ round: round.round, turns: round.indexes.map((i) => turns[i]!).filter(Boolean) })
    }
  }

  // 一次性组装：按下标投影（丢整组 → 套正文裁剪 → 插摘要注记）
  const current: AgentTurn[] = []
  turns.forEach((turn, i) => {
    const roundNo = roundOfIndex.get(i)
    if (roundNo !== undefined && dropped.has(roundNo)) {
      // 在该组首条消息的位置插入摘要注记
      const firstIndex = rounds.find((r) => r.round === roundNo)?.indexes[0]
      if (firstIndex === i && summaryNotes.has(roundNo)) {
        current.push({ role: 'user', content: summaryNotes.get(roundNo)! })
      }
      return
    }
    current.push(applyTrim(turn, i))
  })

  // 协议自检：裁切绝不允许破坏 tool_use / tool_result 配对
  const issues = validateToolPairing(current)
  if (issues.length > 0) {
    // 宁可放弃本次裁切，也不能把非法上下文送给模型
    return {
      turns: [...turns],
      pruned: false,
      beforeTokens,
      afterTokens: beforeTokens,
      records: [],
      roundsToSummarize: []
    }
  }

  return {
    turns: current,
    pruned: records.length > 0,
    beforeTokens,
    afterTokens: estimateTurns(current),
    records,
    roundsToSummarize
  }
}

/** 把摘要注记写入 turns（供循环在拿到 LLM 摘要后二次调用） */
export function applySummaries(
  turns: readonly AgentTurn[],
  config: PruneConfig,
  summaries: Map<number, string>,
  now = Date.now()
): PrunePlan {
  return planPrune(turns, config, { summaries, now })
}
