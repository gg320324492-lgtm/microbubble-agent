// AbortSource 统一中止源（工单 M8-3 §5）— 纯逻辑，零 Electron / 零依赖。
//
// 现状：循环里只有一个 `stopped: Set<sessionId>`（用户点停止时置位），
// 权限拒绝、runaway 触发、应用退出各自另想办法 —— 中止原因无法区分，也无法事后追溯。
//
// 本模块把四类中止源收敛为**一个带原因的中止源**：
//   用户停止（user）/ 权限拒绝（permission）/ runaway 触发（runaway）/ 应用退出（shutdown）
// 语义要点：
//   · **幂等**：已中止后再触发不会改变首个原因（首个原因才是真相）
//   · **原因可查**：abortReason() 供循环收尾与证据链使用
//   · 不依赖 AbortController（主进程零 DOM 依赖），只做状态机

export type AbortReason = 'user' | 'permission' | 'runaway' | 'shutdown'

export interface AbortRecord {
  reason: AbortReason
  at: number
  /** 可选补充（如 runaway 的命中次数、被拒工具名） */
  detail?: string
}

/** 面向用户的中性文案 */
export function abortMessage(reason: AbortReason): string {
  switch (reason) {
    case 'user':
      return '已按你的要求停止本次生成。'
    case 'permission':
      return '由于权限设置拒绝了必要的工具调用，本次任务已停止。可在「设置 · 工具权限」中调整后重试。'
    case 'runaway':
      return '检测到重复空转，已自动停止本次任务。可以换个说法让它继续。'
    case 'shutdown':
      return '应用即将退出，本次任务已中止。'
  }
}

/** 单个会话的中止状态机（纯逻辑，可离线断言） */
export class AbortSource {
  private record: AbortRecord | null = null

  constructor(private readonly now: () => number = Date.now) {}

  /** 请求中止；**首个原因胜出**（幂等），返回是否为本次生效的调用 */
  abort(reason: AbortReason, detail?: string): boolean {
    if (this.record) return false
    this.record = { reason, at: this.now(), ...(detail === undefined ? {} : { detail }) }
    return true
  }

  get aborted(): boolean {
    return this.record !== null
  }

  abortReason(): AbortReason | null {
    return this.record?.reason ?? null
  }

  /** 证据链/收尾用：完整记录 */
  snapshot(): AbortRecord | null {
    return this.record ? { ...this.record } : null
  }

  /** 供下次任务复用（run 结束时重置） */
  reset(): void {
    this.record = null
  }
}

/** 多会话中止源注册表（装配层用：一个 run 一个源） */
export class AbortRegistry {
  private readonly sources = new Map<string, AbortSource>()

  constructor(private readonly now: () => number = Date.now) {}

  for(sessionId: string): AbortSource {
    let s = this.sources.get(sessionId)
    if (!s) {
      s = new AbortSource(this.now)
      this.sources.set(sessionId, s)
    }
    return s
  }

  /** 应用退出：中止全部在跑的会话 */
  abortAll(reason: AbortReason = 'shutdown'): string[] {
    const hit: string[] = []
    for (const [sid, src] of this.sources) {
      if (src.abort(reason)) hit.push(sid)
    }
    return hit
  }

  release(sessionId: string): void {
    this.sources.delete(sessionId)
  }

  size(): number {
    return this.sources.size
  }
}

// ---------------------------------------------------------------- steering（§5）

export interface SteeringMessage {
  sessionId: string
  text: string
  at: number
}

/**
 * steering 缓冲：会话进行中用户输入的即时指令**在轮边界注入下一轮**，
 * 不打断正在执行的工具（工单要求）。纯数据结构，便于离线断言。
 */
export class SteeringBuffer {
  private readonly bySession = new Map<string, SteeringMessage[]>()

  push(sessionId: string, text: string, now: number = Date.now()): void {
    const trimmed = text.trim()
    if (!trimmed) return
    const list = this.bySession.get(sessionId) ?? []
    list.push({ sessionId, text: trimmed, at: now })
    this.bySession.set(sessionId, list)
  }

  /** 取走并在下一轮注入（取走即清空，避免重复注入） */
  drain(sessionId: string): SteeringMessage[] {
    const list = this.bySession.get(sessionId)
    if (!list || list.length === 0) return []
    this.bySession.delete(sessionId)
    return list
  }

  /** 合并为一条注入文本（模型可读） */
  static format(messages: readonly SteeringMessage[]): string {
    if (messages.length === 0) return ''
    const body = messages.map((m) => m.text).join('\n')
    return `[用户在任务进行中补充了以下要求，请在本轮起遵循]\n${body}`
  }

  pending(sessionId: string): number {
    return this.bySession.get(sessionId)?.length ?? 0
  }
}
