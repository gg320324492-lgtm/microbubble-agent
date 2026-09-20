// runaway guard（工单 M8-3 §4）— 纯函数，零 Electron / 零依赖，离线可穷举。
//
// 两条规则（工单硬要求）：
//   ① 连续 ≥3 次**同工具同参数**调用 → 判定 runaway → 经 AbortSource 中止 + 中性提示
//   ② 连续 ≥3 轮**无写入类进展**（没有任何落盘）→ **不硬中止**，出提示交用户决定
//
// 为什么阈值是 3：模型在正常工作中也可能重复读同一文件两次（先读再确认），
// 但连续 3 次同参调用几乎只能是卡循环 —— 且硬中止代价可控（用户可继续对话）。

/** 同工具同参数连击阈值 */
export const REPEAT_THRESHOLD = 3
/** 无进展轮次阈值 */
export const NO_PROGRESS_THRESHOLD = 3

export type RunawayAction = 'none' | 'warn' | 'abort'
export type RunawayKind = 'repeat-calls' | 'no-progress' | null

export interface RunawayVerdict {
  action: RunawayAction
  kind: RunawayKind
  /** 面向用户/模型的中性文案（action !== 'none' 时有值） */
  message?: string
  /** 诊断用：命中的次数 */
  count?: number
}

/**
 * 调用签名：工具名 + **稳定序列化**的参数。
 * 参数键排序后 JSON 化，避免 `{a,b}` 与 `{b,a}` 被当成不同调用而漏检。
 */
export function callSignature(name: string, input: unknown): string {
  let argsKey = ''
  try {
    argsKey = JSON.stringify(sortDeep(input ?? {}))
  } catch {
    argsKey = String(input)
  }
  return `${name}(${argsKey})`
}

function sortDeep(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortDeep)
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {}
    for (const k of Object.keys(value as Record<string, unknown>).sort()) {
      out[k] = sortDeep((value as Record<string, unknown>)[k])
    }
    return out
  }
  return value
}

/** 末尾连续相同签名的最长长度（从尾部往前数） */
export function trailingRepeatCount(signatures: readonly string[]): number {
  if (signatures.length === 0) return 0
  const last = signatures[signatures.length - 1]
  let n = 1
  for (let i = signatures.length - 2; i >= 0; i -= 1) {
    if (signatures[i] !== last) break
    n += 1
  }
  return n
}

/** 末尾连续「无进展」轮数 */
export function trailingNoProgressRounds(progress: readonly boolean[]): number {
  let n = 0
  for (let i = progress.length - 1; i >= 0; i -= 1) {
    if (progress[i] === true) break
    n += 1
  }
  return n
}

export interface RunawayState {
  /** 按时间顺序的调用签名（最新的在末尾） */
  callSignatures: readonly string[]
  /** 按轮次顺序的「本轮是否有写入类落盘」 */
  roundProgress: readonly boolean[]
}

/**
 * 评估是否 runaway（纯函数）。
 * 优先级：同参连击（硬中止）> 无进展（软提示）。
 * 已处于中止态时由调用方负责不再重复触发（AbortSource 幂等）。
 */
export function evaluateRunaway(
  state: RunawayState,
  opts: { repeatThreshold?: number; noProgressThreshold?: number } = {}
): RunawayVerdict {
  const repeatThreshold = opts.repeatThreshold ?? REPEAT_THRESHOLD
  const noProgressThreshold = opts.noProgressThreshold ?? NO_PROGRESS_THRESHOLD

  const repeat = trailingRepeatCount(state.callSignatures)
  if (repeat >= repeatThreshold) {
    const sig = state.callSignatures[state.callSignatures.length - 1] ?? ''
    const tool = sig.slice(0, sig.indexOf('('))
    return {
      action: 'abort',
      kind: 'repeat-calls',
      count: repeat,
      message: `检测到连续 ${repeat} 次以完全相同参数调用「${tool}」，为避免空转已自动停止本次任务。你可以换个说法让它继续，或直接说明期望的结果。`
    }
  }

  const idle = trailingNoProgressRounds(state.roundProgress)
  if (idle >= noProgressThreshold) {
    return {
      action: 'warn',
      kind: 'no-progress',
      count: idle,
      message: `已连续 ${idle} 轮没有产生任何文件改动。如果它一直只读不写，可以直接说明你想要落地的文件或结论。`
    }
  }

  return { action: 'none', kind: null }
}
