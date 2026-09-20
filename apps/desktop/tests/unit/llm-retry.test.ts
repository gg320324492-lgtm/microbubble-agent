// M8-1 §2 提交边界重试 — 退避序列 / 提交边界两侧 / Retry-After / 封顶 / 错误归一化（全部离线）
import { describe, expect, it } from 'vitest'
import {
  DEFAULT_RETRY_POLICY,
  classifyLlmError,
  computeBackoffMs,
  createCommitState,
  decideRetry,
  isRetryableKind,
  markVisible,
  normalizeLlmErrorMessage,
  parseRetryAfterMs,
  withCommitBoundaryRetry
} from '@main/agent/llm-retry'

describe('策略常量 — 与工单一致', () => {
  it('最多 5 次 / 1s 起步 / 单次 30s / 总 120s', () => {
    expect(DEFAULT_RETRY_POLICY).toEqual({ maxRetries: 5, baseDelayMs: 1_000, maxDelayMs: 30_000, maxRetryElapsedMs: 120_000 })
  })
})

describe('错误分类', () => {
  it('按状态码分类', () => {
    expect(classifyLlmError({ status: 429 })).toBe('rate_limited')
    expect(classifyLlmError({ status: 503 })).toBe('overloaded')
    expect(classifyLlmError({ status: 529 })).toBe('overloaded')
    expect(classifyLlmError({ status: 500 })).toBe('server')
    expect(classifyLlmError({ status: 401 })).toBe('auth')
    expect(classifyLlmError({ status: 403 })).toBe('auth')
    expect(classifyLlmError({ status: 400 })).toBe('invalid_request')
    expect(classifyLlmError({ status: 408 })).toBe('timeout')
    expect(classifyLlmError({ status: 504 })).toBe('timeout')
  })

  it('按错误码分类（网络类）', () => {
    expect(classifyLlmError({ code: 'ETIMEDOUT' })).toBe('timeout')
    expect(classifyLlmError({ code: 'ECONNRESET' })).toBe('network')
    expect(classifyLlmError({ code: 'ENOTFOUND' })).toBe('network')
    expect(classifyLlmError({ code: 'EAI_AGAIN' })).toBe('network')
  })

  it('显式中止与空响应优先于其它信号', () => {
    expect(classifyLlmError({ aborted: true, status: 500 })).toBe('aborted')
    expect(classifyLlmError({ emptyResponse: true })).toBe('empty_response')
    expect(classifyLlmError({})).toBe('unknown')
  })

  it('可重试白名单：中止/鉴权/参数错误不可重试', () => {
    expect(isRetryableKind('rate_limited')).toBe(true)
    expect(isRetryableKind('overloaded')).toBe(true)
    expect(isRetryableKind('network')).toBe(true)
    expect(isRetryableKind('timeout')).toBe(true)
    expect(isRetryableKind('empty_response')).toBe(true)
    expect(isRetryableKind('server')).toBe(true)
    expect(isRetryableKind('aborted')).toBe(false)
    expect(isRetryableKind('auth')).toBe(false)
    expect(isRetryableKind('invalid_request')).toBe(false)
    expect(isRetryableKind('unknown')).toBe(false)
  })
})

describe('错误归一化 — 对用户安全的中性中文文案', () => {
  it('每类都有专属文案且不含技术细节', () => {
    const kinds = ['rate_limited', 'overloaded', 'network', 'timeout', 'empty_response', 'invalid_request', 'auth', 'server', 'aborted', 'unknown'] as const
    const seen = new Set<string>()
    for (const k of kinds) {
      const msg = normalizeLlmErrorMessage(k)
      expect(msg.length).toBeGreaterThan(4)
      seen.add(msg)
      // 不泄漏：不出现 URL / 密钥样式 / 堆栈
      expect(msg).not.toMatch(/https?:\/\//)
      expect(msg).not.toMatch(/sk-[A-Za-z0-9]/)
      expect(msg).not.toMatch(/\bat .+:\d+:\d+/)
      expect(msg).not.toMatch(/\bError:/)
    }
    expect(seen.size).toBe(kinds.length) // 每类文案互不相同
  })

  it('可带重试次数说明（仅在传入时出现）', () => {
    expect(normalizeLlmErrorMessage('rate_limited')).not.toContain('已尝试')
    expect(normalizeLlmErrorMessage('rate_limited', { attempt: 3, maxRetries: 5 })).toContain('已尝试 3/6 次')
  })

  it('鉴权类文案指向设置页（可操作）', () => {
    expect(normalizeLlmErrorMessage('auth')).toContain('设置')
  })
})

describe('Retry-After 解析', () => {
  it('秒数 / 毫秒 / HTTP 日期三种形态', () => {
    expect(parseRetryAfterMs({ 'retry-after': '2' }, 0)).toBe(2000)
    expect(parseRetryAfterMs({ 'Retry-After': '3' }, 0)).toBe(3000) // 大小写不敏感
    expect(parseRetryAfterMs({ 'retry-after-ms': '1500' }, 0)).toBe(1500)
    const now = Date.parse('2026-09-20T10:00:00Z')
    expect(parseRetryAfterMs({ 'retry-after': 'Sun, 20 Sep 2026 10:00:05 GMT' }, now)).toBe(5000)
    expect(parseRetryAfterMs({}, now)).toBeUndefined()
    expect(parseRetryAfterMs(undefined, now)).toBeUndefined()
    expect(parseRetryAfterMs({ 'retry-after': 'garbage' }, now)).toBeUndefined()
  })

  it('retry-after-ms 优先于 retry-after', () => {
    expect(parseRetryAfterMs({ 'retry-after': '10', 'retry-after-ms': '250' }, 0)).toBe(250)
  })
})

describe('退避计算', () => {
  const policy = DEFAULT_RETRY_POLICY

  it('指数退避序列：1s → 2s → 4s → 8s（随机固定为 0.5 时无抖动）', () => {
    const seq = [1, 2, 3, 4].map((a) => computeBackoffMs(policy, a, { random: () => 0.5 }))
    expect(seq).toEqual([1000, 2000, 4000, 8000])
  })

  it('抖动范围 ±25%（random 极值时）', () => {
    expect(computeBackoffMs(policy, 1, { random: () => 0 })).toBe(750)
    expect(computeBackoffMs(policy, 1, { random: () => 1 })).toBe(1250)
  })

  it('单次等待 30s 封顶', () => {
    expect(computeBackoffMs(policy, 20, { random: () => 0.5 })).toBe(30_000)
  })

  it('尊重 Retry-After（但仍受单次上限约束）', () => {
    expect(computeBackoffMs(policy, 1, { retryAfterMs: 7000, random: () => 0.5 })).toBe(7000)
    expect(computeBackoffMs(policy, 1, { retryAfterMs: 600_000, random: () => 0.5 })).toBe(30_000)
  })
})

describe('重试决策 — 提交边界两侧行为', () => {
  const policy = DEFAULT_RETRY_POLICY
  const base = { policy, retriesUsed: 0, elapsedMs: 0, random: () => 0.5 }

  it('未提交 + 可重试类别 → 重试并给出延迟', () => {
    const d = decideRetry({ kind: 'rate_limited', commit: createCommitState(), ...base })
    expect(d.retry).toBe(true)
    expect(d.delayMs).toBe(1000)
  })

  it('**已提交** → 绝不重试（防止用户看到重复内容）', () => {
    const commit = markVisible(createCommitState(), 'text')
    const d = decideRetry({ kind: 'rate_limited', commit, ...base })
    expect(d.retry).toBe(false)
    expect(d.reason).toBe('already-committed')
  })

  it('text / thinking / toolcall 三种可见事件都算提交', () => {
    for (const kind of ['text', 'thinking', 'toolcall'] as const) {
      const c = markVisible(createCommitState(), kind)
      expect(c.committed).toBe(true)
      expect(decideRetry({ kind: 'network', commit: c, ...base }).retry).toBe(false)
    }
  })

  it('不可重试类别（鉴权/参数/中止）不重试', () => {
    for (const kind of ['auth', 'invalid_request', 'aborted', 'unknown'] as const) {
      const d = decideRetry({ kind, commit: createCommitState(), ...base })
      expect(d.retry).toBe(false)
      expect(d.reason).toBe('non-retryable-kind')
    }
  })

  it('次数用尽（5 次）不再重试', () => {
    expect(decideRetry({ kind: 'server', commit: createCommitState(), ...base, retriesUsed: 4 }).retry).toBe(true)
    const d = decideRetry({ kind: 'server', commit: createCommitState(), ...base, retriesUsed: 5 })
    expect(d.retry).toBe(false)
    expect(d.reason).toBe('max-retries')
  })

  it('重试总时长 120s 封顶', () => {
    const d = decideRetry({ kind: 'server', commit: createCommitState(), ...base, retriesUsed: 3, elapsedMs: 119_500 })
    expect(d.retry).toBe(false)
    expect(d.reason).toBe('max-elapsed')
  })
})

describe('编排：withCommitBoundaryRetry（sleep/now/random 全注入）', () => {
  function harness(failures: Array<{ status?: number; headers?: Record<string, string> }>, opts: { commitOn?: number; policy?: typeof DEFAULT_RETRY_POLICY } = {}) {
    const slept: number[] = []
    let clock = 1_000_000
    const retries: Array<{ attempt: number; delayMs: number; kind: string }> = []
    let calls = 0
    const run = (): Promise<string> =>
      withCommitBoundaryRetry<string>({
        ...(opts.policy ? { policy: opts.policy } : {}),
        now: () => clock,
        random: () => 0.5,
        sleep: async (ms) => {
          slept.push(ms)
          clock += ms // 时间随 sleep 前进，使「总时长封顶」可断言
        },
        onRetry: (info) => retries.push(info as { attempt: number; delayMs: number; kind: string }),
        attempt: async (visible) => {
          calls += 1
          const f = failures[calls - 1]
          if (opts.commitOn === calls) visible('text') // 本轮已提交
          if (f) {
            const e = new Error('upstream said no') as Error & { status?: number; headers?: Record<string, string> }
            if (f.status !== undefined) e.status = f.status
            if (f.headers !== undefined) e.headers = f.headers
            throw e
          }
          return 'ok'
        },
        toFailure: (err) => {
          const e = err as Error & { status?: number; headers?: Record<string, string> }
          // Retry-After 由调用方（网关装配层）解析后随失败信息一起上报
          const retryAfterMs = parseRetryAfterMs(e.headers, clock)
          return {
            kind: classifyLlmError({ ...(e.status === undefined ? {} : { status: e.status }), message: e.message }),
            ...(retryAfterMs === undefined ? {} : { retryAfterMs })
          }
        }
      })
    return { run, slept, retries, calls: () => calls }
  }

  it('首次成功 → 不重试、不 sleep', async () => {
    const h = harness([])
    await expect(h.run()).resolves.toBe('ok')
    expect(h.slept).toEqual([])
    expect(h.calls()).toBe(1)
  })

  it('429 → 重试后成功，退避序列 1000/2000/4000', async () => {
    const h = harness([{ status: 429 }, { status: 429 }, { status: 429 }])
    await expect(h.run()).resolves.toBe('ok')
    expect(h.slept).toEqual([1000, 2000, 4000])
    expect(h.retries.map((r) => r.attempt)).toEqual([1, 2, 3])
    expect(h.retries.every((r) => r.kind === 'rate_limited')).toBe(true)
  })

  it('尊重 Retry-After：服务端说 7s 就等 7s（替代指数退避）', async () => {
    const h = harness([{ status: 429, headers: { 'retry-after': '7' } }])
    await expect(h.run()).resolves.toBe('ok')
    expect(h.slept).toEqual([7000])
  })

  it('提交后失败 → 不重试，抛出中性文案（且 kind 可读）', async () => {
    const h = harness([{ status: 500 }], { commitOn: 1 })
    await expect(h.run()).rejects.toThrow(/模型服务出现内部错误/)
    expect(h.calls()).toBe(1)
    expect(h.slept).toEqual([])
  })

  it('重试耗尽 → 抛出中性文案，且总等待不超 120s 封顶', async () => {
    const h = harness([{ status: 503 }, { status: 503 }, { status: 503 }, { status: 503 }, { status: 503 }, { status: 503 }])
    await expect(h.run()).rejects.toThrow(/繁忙|稍后再试/)
    // 5 次重试的退避：1000+2000+4000+8000+16000 = 31000ms（远低于 120s 封顶）
    expect(h.slept).toEqual([1000, 2000, 4000, 8000, 16000])
    expect(h.slept.reduce((a, b) => a + b, 0)).toBeLessThanOrEqual(DEFAULT_RETRY_POLICY.maxRetryElapsedMs)
  })

  it('总时长封顶生效：把 maxRetryElapsedMs 调小即可提前放弃', async () => {
    const h = harness([{ status: 503 }, { status: 503 }, { status: 503 }], {
      policy: { maxRetries: 5, baseDelayMs: 1000, maxDelayMs: 30_000, maxRetryElapsedMs: 2500 }
    })
    await expect(h.run()).rejects.toThrow()
    // 1000 → 2000 时累计 3000 > 2500，故只 sleep 了一次
    expect(h.slept).toEqual([1000])
  })

  it('不可重试类别（401）→ 立即失败，不 sleep', async () => {
    const h = harness([{ status: 401 }])
    await expect(h.run()).rejects.toThrow(/凭据可能已失效/)
    expect(h.slept).toEqual([])
    expect(h.calls()).toBe(1)
  })
})
