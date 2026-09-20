// LLM 提交边界重试（工单 M8-1 §2）— 纯逻辑：零 Electron / 零网络 / 零依赖，时序全部注入。
//
// 语义（工单硬要求）：
//   · **提交边界**：流事件先缓冲。出现**首个可见 delta**（text / thinking / toolcall）= 已提交
//     → 之后任何失败都不重试（错误并入文继续，保持既有行为），因为重试会让用户看到重复内容。
//   · 未提交前的失败（429 / 5xx / 网络 / 空响应）→ 丢弃缓冲、静默重试，用户无感。
//   · 策略：最多 5 次重试；1s 起步指数退避 + 抖动；单次等待 30s 封顶；重试总时长 120s 封顶；
//     **尊重 Retry-After / Retry-After-Ms 响应头**（服务端说等多久就等多久，但不超过单次上限）。
//   · **错误归一化**：原始报错只进日志；对用户/模型只给中性中文文案（不泄漏 URL、密钥、堆栈）。
//
// 对标出处（报告 §7）：模式借鉴 minimax-code `packages/agent-core/src/pi-turn-runner/llm-retry.ts`
// （MIT）。本实现为独立编写：不引入其 symbol 身份机制 / metric 观察者 / 多 scope 体系，
// 只保留「策略常量 + 退避 + 提交边界 + 错误归一化」四项，命名与文案按本项目约定重写。

/** 重试策略（数值与参考实现一致：5 次 / 1s 起步 / 单次 30s / 总 120s） */
export interface RetryPolicy {
  maxRetries: number
  baseDelayMs: number
  maxDelayMs: number
  maxRetryElapsedMs: number
}

export const DEFAULT_RETRY_POLICY: Readonly<RetryPolicy> = {
  maxRetries: 5,
  baseDelayMs: 1_000,
  maxDelayMs: 30_000,
  maxRetryElapsedMs: 120_000
}

/** 错误分类枚举 */
export type LlmErrorKind =
  | 'rate_limited'
  | 'overloaded'
  | 'network'
  | 'timeout'
  | 'empty_response'
  | 'invalid_request'
  | 'auth'
  | 'server'
  | 'aborted'
  | 'unknown'

/** 可重试的错误类别（提交前才生效） */
export const RETRYABLE_KINDS: readonly LlmErrorKind[] = [
  'rate_limited',
  'overloaded',
  'network',
  'timeout',
  'empty_response',
  'server'
]

export interface LlmErrorInput {
  /** HTTP 状态码（如 429 / 500 / 401） */
  status?: number
  /** 错误码字符串（如 ETIMEDOUT / ECONNRESET） */
  code?: string
  /** 原始报错文本（仅用于分类，**不会**直接给用户） */
  message?: string
  /** 调用方已判定为中止（用户点停止 / 应用退出） */
  aborted?: boolean
  /** 流正常结束但没有任何内容 */
  emptyResponse?: boolean
}

/** 错误分类（纯函数）。顺序敏感：先看显式中止，再看空响应，再看状态码/错误码。 */
export function classifyLlmError(input: LlmErrorInput): LlmErrorKind {
  if (input.aborted) return 'aborted'
  if (input.emptyResponse) return 'empty_response'

  const status = input.status
  if (status !== undefined) {
    if (status === 401 || status === 403) return 'auth'
    if (status === 400 || status === 422) return 'invalid_request'
    if (status === 408 || status === 504) return 'timeout'
    if (status === 429) return 'rate_limited'
    if (status === 503 || status === 529) return 'overloaded'
    if (status >= 500) return 'server'
    if (status >= 400) return 'invalid_request'
  }

  const code = (input.code ?? '').toUpperCase()
  if (code === 'ETIMEDOUT' || code === 'UND_ERR_CONNECT_TIMEOUT' || code === 'ABORT_ERR') return 'timeout'
  if (code === 'ECONNRESET' || code === 'ECONNREFUSED' || code === 'ENOTFOUND' || code === 'EAI_AGAIN' || code === 'UND_ERR_SOCKET')
    return 'network'

  const msg = (input.message ?? '').toLowerCase()
  if (msg.includes('rate limit') || msg.includes('too many requests')) return 'rate_limited'
  if (msg.includes('overload') || msg.includes('capacity')) return 'overloaded'
  if (msg.includes('timeout') || msg.includes('timed out')) return 'timeout'
  if (msg.includes('fetch failed') || msg.includes('socket') || msg.includes('network')) return 'network'
  if (msg.includes('unauthorized') || msg.includes('invalid api key') || msg.includes('api key')) return 'auth'
  if (msg.includes('aborted') || msg.includes('cancel')) return 'aborted'
  return 'unknown'
}

/**
 * 错误归一化：类别 → **对用户安全的中性中文文案**。
 * 原则：不出现原始 URL、不出现密钥/请求 id、不出现堆栈；只说「发生了什么 + 接下来怎么办」。
 */
export function normalizeLlmErrorMessage(kind: LlmErrorKind, opts: { attempt?: number; maxRetries?: number } = {}): string {
  const tried = opts.attempt !== undefined && opts.maxRetries !== undefined ? `（已尝试 ${opts.attempt}/${opts.maxRetries + 1} 次）` : ''
  switch (kind) {
    case 'rate_limited':
      return `模型服务当前请求过多，已稍后重试仍未成功${tried}。请稍等片刻再发送，或换一个模型服务。`
    case 'overloaded':
      return `模型服务暂时繁忙${tried}。请稍后再试，或换一个模型服务。`
    case 'network':
      return `连接模型服务失败${tried}。请检查网络与代理设置后重试。`
    case 'timeout':
      return `模型服务响应超时${tried}。请稍后重试，或缩短本次提问内容。`
    case 'empty_response':
      return `模型服务没有返回任何内容${tried}。请重试，或换一个模型服务。`
    case 'invalid_request':
      return '本次请求未被模型服务接受。请检查所选模型是否可用，或把问题拆小一些再试。'
    case 'auth':
      return '模型服务拒绝了本次请求，凭据可能已失效。请在「设置 · 模型服务」中检查密钥是否正确。'
    case 'server':
      return `模型服务出现内部错误${tried}。请稍后重试。`
    case 'aborted':
      return '本次生成已停止。'
    default:
      return `本次调用未能完成${tried}。请重试；若持续失败，请在「设置 · 模型服务」中检查配置。`
  }
}

/** 是否可重试（提交前 + 类别在白名单内 + 未中止） */
export function isRetryableKind(kind: LlmErrorKind): boolean {
  return RETRYABLE_KINDS.includes(kind)
}

/** 解析 Retry-After / Retry-After-Ms（秒数或 HTTP 日期），无则 undefined */
export function parseRetryAfterMs(headers: Record<string, string> | undefined, nowMs: number): number | undefined {
  if (!headers) return undefined
  const entries = Object.entries(headers)
  const pick = (name: string): string | undefined => entries.find(([k]) => k.toLowerCase() === name)?.[1]

  const msRaw = pick('retry-after-ms')
  if (msRaw !== undefined) {
    const ms = Number(msRaw)
    if (Number.isFinite(ms) && ms >= 0) return ms
  }
  const raw = pick('retry-after')
  if (raw === undefined) return undefined
  const secs = Number(raw)
  if (Number.isFinite(secs) && secs >= 0) return secs * 1000
  const date = Date.parse(raw)
  if (Number.isFinite(date)) return Math.max(0, date - nowMs)
  return undefined
}

/**
 * 退避计算（纯函数，random 注入）：
 *   有 Retry-After → 用它（但不超过 maxDelayMs）
 *   否则 → baseDelay * 2^(attempt-1)，加 ±25% 抖动，再取 maxDelayMs 上限
 * attempt 从 1 开始（第 1 次重试）。
 */
export function computeBackoffMs(
  policy: RetryPolicy,
  attempt: number,
  opts: { retryAfterMs?: number; random: () => number } = { random: Math.random }
): number {
  if (opts.retryAfterMs !== undefined) {
    return Math.min(policy.maxDelayMs, Math.max(0, opts.retryAfterMs))
  }
  const base = policy.baseDelayMs * 2 ** Math.max(0, attempt - 1)
  const jitter = 1 + (opts.random() * 0.5 - 0.25) // ±25%
  return Math.min(policy.maxDelayMs, Math.max(0, Math.round(base * jitter)))
}

/** 提交边界状态：一旦可见 delta 出现即置位，此后不再重试 */
export interface CommitState {
  committed: boolean
}

export function createCommitState(): CommitState {
  return { committed: false }
}

/** 标记「已有可见输出」。text / thinking / toolcall 任一出现即算提交。 */
export function markVisible(state: CommitState, kind: 'text' | 'thinking' | 'toolcall'): CommitState {
  if (kind === 'text' || kind === 'thinking' || kind === 'toolcall') state.committed = true
  return state
}

export interface RetryDecision {
  retry: boolean
  delayMs?: number
  kind: LlmErrorKind
  /** 给日志的原因（不给用户） */
  reason: string
}

/**
 * 重试决策（纯函数）：结合提交边界、类别白名单、次数与总时长上限。
 * @param elapsedMs 从首次请求开始已累计的重试等待时间
 */
export function decideRetry(input: {
  kind: LlmErrorKind
  commit: CommitState
  policy: RetryPolicy
  /** 已用重试次数（第 1 次重试前为 0） */
  retriesUsed: number
  elapsedMs: number
  retryAfterMs?: number
  random?: () => number
}): RetryDecision {
  const { kind, commit, policy } = input
  if (commit.committed) {
    return { retry: false, kind, reason: 'already-committed' }
  }
  if (!isRetryableKind(kind)) {
    return { retry: false, kind, reason: 'non-retryable-kind' }
  }
  if (input.retriesUsed >= policy.maxRetries) {
    return { retry: false, kind, reason: 'max-retries' }
  }
  const delayMs = computeBackoffMs(policy, input.retriesUsed + 1, {
    ...(input.retryAfterMs === undefined ? {} : { retryAfterMs: input.retryAfterMs }),
    random: input.random ?? Math.random
  })
  if (input.elapsedMs + delayMs > policy.maxRetryElapsedMs) {
    return { retry: false, kind, reason: 'max-elapsed' }
  }
  return { retry: true, delayMs, kind, reason: 'retryable' }
}

export interface AttemptFailure {
  kind: LlmErrorKind
  retryAfterMs?: number
  headers?: Record<string, string>
}

/**
 * 提交边界重试编排（时序注入，离线可断言）：
 *   attempt 回调收到 `markVisibleDelta(kind)`，网关在**首个可见 delta** 时调用它。
 *   返回最后一次成功的值；不可重试/超限时抛出最后一次的错误信息（中性文案）。
 */
export async function withCommitBoundaryRetry<T>(opts: {
  policy?: RetryPolicy
  /** 执行一次请求。visible(kind) 由调用方在首个可见 delta 时调用 */
  attempt: (visible: (kind: 'text' | 'thinking' | 'toolcall') => void) => Promise<T>
  /** 把抛出的异常归一化为失败信息（分类 + Retry-After） */
  toFailure: (err: unknown) => AttemptFailure
  sleep: (ms: number) => Promise<void>
  now: () => number
  random?: () => number
  onRetry?: (info: { attempt: number; delayMs: number; kind: LlmErrorKind }) => void
}): Promise<T> {
  const policy = opts.policy ?? DEFAULT_RETRY_POLICY
  const random = opts.random ?? Math.random
  const commit = createCommitState()
  const startedAt = opts.now()
  let retriesUsed = 0
  let lastKind: LlmErrorKind = 'unknown'

  for (;;) {
    try {
      return await opts.attempt((kind) => markVisible(commit, kind))
    } catch (err) {
      const failure = opts.toFailure(err)
      lastKind = failure.kind
      const decision = decideRetry({
        kind: failure.kind,
        commit,
        policy,
        retriesUsed,
        elapsedMs: opts.now() - startedAt,
        ...(failure.retryAfterMs === undefined ? {} : { retryAfterMs: failure.retryAfterMs }),
        random
      })
      if (!decision.retry) {
        // 提交后失败 / 不可重试 / 超限 → 交给上层（并入文或报错），此处只抛出归一化后的类别
        const e = new Error(normalizeLlmErrorMessage(failure.kind, { attempt: retriesUsed + 1, maxRetries: policy.maxRetries }))
        ;(e as Error & { kind?: LlmErrorKind; reason?: string }).kind = failure.kind
        ;(e as Error & { kind?: LlmErrorKind; reason?: string }).reason = decision.reason
        throw e
      }
      retriesUsed += 1
      opts.onRetry?.({ attempt: retriesUsed, delayMs: decision.delayMs!, kind: failure.kind })
      await opts.sleep(decision.delayMs!)
    }
  }
  // 不可达；保留类型收窄
  throw new Error(normalizeLlmErrorMessage(lastKind))
}
