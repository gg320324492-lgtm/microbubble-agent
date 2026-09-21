// M2-3a 云端 API 客户端 —— 全部离线，HTTP 注入式（契约来自 app/api/v1/auth.py 只读调研）
import { describe, expect, it, vi } from 'vitest'
import {
  CloudApiClient,
  DEFAULT_CLOUD_BASE_URL,
  cloudStatusLabel,
  initialBindingState,
  isCloudUsable,
  isRetryable,
  normalizeBaseUrl,
  normalizeCloudError,
  type CloudHttpFn,
  type CloudHttpRequest,
  type CloudHttpResponse
} from '@main/services/cloud/api-client'

function res(status: number, json: unknown, headers: Record<string, string> = {}): CloudHttpResponse {
  return { status, headers, text: typeof json === 'string' ? json : JSON.stringify(json) }
}

/** 记录请求并按脚本回应的注入式 HTTP */
function httpScript(script: ((req: CloudHttpRequest) => CloudHttpResponse | Promise<CloudHttpResponse>)[]): {
  http: CloudHttpFn
  requests: CloudHttpRequest[]
} {
  const requests: CloudHttpRequest[] = []
  let i = 0
  const http: CloudHttpFn = async (req) => {
    requests.push(req)
    const step = script[Math.min(i, script.length - 1)]!
    i += 1
    return step(req)
  }
  return { http, requests }
}

const loginOk = () => res(200, { access_token: 'AT1', refresh_token: 'RT1', token_type: 'bearer' })
const meOk = () => res(200, { id: 7, name: '王天志', grade: '博士', email: 'a@b.c' })

function client(script: Parameters<typeof httpScript>[0], baseUrl = 'https://agent.mnb-lab.cn'): { c: CloudApiClient; requests: CloudHttpRequest[] } {
  const { http, requests } = httpScript(script)
  return { c: new CloudApiClient({ http, baseUrl }), requests }
}

// ---------------------------------------------------------------- 1 绑定流程（≥3）

describe('绑定流程', () => {
  it('成功：POST /api/v1/auth/login，取回 access+refresh 令牌，且请求形状符合父级契约', async () => {
    const { c, requests } = client([loginOk])
    const r = await c.login('wangtianzhi', 'secret')
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toEqual({ accessToken: 'AT1', refreshToken: 'RT1' })
    expect(requests).toHaveLength(1)
    expect(requests[0]!.method).toBe('POST')
    expect(requests[0]!.url).toBe('https://agent.mnb-lab.cn/api/v1/auth/login')
    expect(JSON.parse(requests[0]!.body!)).toEqual({ username: 'wangtianzhi', password: 'secret' })
    expect(requests[0]!.headers['content-type']).toBe('application/json')
  })

  it('密码错：401 → auth 分类 + 中性中文文案（原始报错只进日志）', async () => {
    const logs: string[] = []
    const { http } = httpScript([() => res(401, { detail: 'Invalid credentials (traceback...)' })])
    const c = new CloudApiClient({ http, log: (m) => logs.push(m) })
    const r = await c.login('u', 'wrong')
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.error.kind).toBe('auth')
      expect(r.error.message).toBe('云端账号或密码不正确，或登录状态已过期。')
      expect(r.error.message).not.toMatch(/traceback|Invalid|401/)
    }
    expect(logs.some((l) => l.includes('401'))).toBe(true) // 原始信息进日志
  })

  it('网络失败：连接类错误 → network 分类 + 可重试判定', async () => {
    const { http } = httpScript([
      () => {
        throw new Error('getaddrinfo ENOTFOUND mnb-lab.cn')
      }
    ])
    const c = new CloudApiClient({ http })
    const r = await c.login('u', 'p')
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.error.kind).toBe('network')
      expect(r.error.message).toContain('无法连接云端服务器')
      expect(isRetryable(r.error.kind)).toBe(true)
    }
  })

  it('登录成功但响应缺令牌字段 → malformed（不静默当成功）', async () => {
    const { http } = httpScript([() => res(200, { token_type: 'bearer' })])
    const c = new CloudApiClient({ http })
    const r = await c.login('u', 'p')
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.kind).toBe('malformed')
  })
})

// ---------------------------------------------------------------- 2 续期（≥2）

describe('令牌续期', () => {
  it('401 → refresh 成功 → 重放原请求一次，并回传新令牌', async () => {
    const { c, requests } = client([
      () => res(401, { detail: 'token expired' }), // 首次 me
      () => res(200, { access_token: 'AT2', token_type: 'bearer' }), // refresh
      () => meOk() // 重放 me
    ])
    const r = await c.requestWithAuth('GET', '/api/v1/auth/me', { accessToken: 'AT1', refreshToken: 'RT1' })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.refreshed).toBe(true)
      expect(r.data.tokens).toEqual({ accessToken: 'AT2', refreshToken: 'RT1' }) // refresh 不换发 → 保留旧 refresh
      expect((r.data.json as { name: string }).name).toBe('王天志')
    }
    expect(requests.map((q) => q.url)).toEqual([
      'https://agent.mnb-lab.cn/api/v1/auth/me',
      'https://agent.mnb-lab.cn/api/v1/auth/refresh',
      'https://agent.mnb-lab.cn/api/v1/auth/me'
    ])
    expect(JSON.parse(requests[1]!.body!)).toEqual({ refresh_token: 'RT1' })
    expect(requests[2]!.headers['authorization']).toBe('Bearer AT2') // 重放用新令牌
  })

  it('refresh 也失效 → auth 错误且文案提示重新绑定（不无限重试）', async () => {
    const { c, requests } = client([
      () => res(401, { detail: 'expired' }),
      () => res(401, { detail: 'refresh invalid' })
    ])
    const r = await c.requestWithAuth('GET', '/api/v1/auth/me', { accessToken: 'AT1', refreshToken: 'RT_BAD' })
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.error.kind).toBe('auth')
      expect(r.error.message).toContain('重新绑定')
    }
    expect(requests).toHaveLength(2) // 只续期一次，不循环
  })

  it('非 401 错误不触发续期（避免无谓刷新）', async () => {
    const { c, requests } = client([() => res(500, { detail: 'boom' })])
    const r = await c.requestWithAuth('GET', '/api/v1/auth/me', { accessToken: 'AT1', refreshToken: 'RT1' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.kind).toBe('server')
    expect(requests).toHaveLength(1)
  })
})

// ---------------------------------------------------------------- 3 错误归一化（≥3）

describe('REST 错误归一化', () => {
  it('超时（AbortError）→ timeout + 中文文案', () => {
    const e = normalizeCloudError({ exceptionName: 'AbortError', detail: 'The operation was aborted' })
    expect(e.kind).toBe('timeout')
    expect(e.message).toContain('超时')
  })

  it('4xx 分类：401/403 → auth，429 → rate-limit（尊重 Retry-After），其它 4xx → client', () => {
    expect(normalizeCloudError({ status: 403 }).kind).toBe('auth')
    const rl = normalizeCloudError({ status: 429, headers: { 'retry-after': '300' } })
    expect(rl.kind).toBe('rate-limit')
    expect(rl.retryAfterSec).toBe(300)
    expect(rl.message).toContain('5 分钟')
    expect(normalizeCloudError({ status: 400 }).kind).toBe('client')
  })

  it('5xx → server；文案中性且不含状态码/原始报错', () => {
    const e = normalizeCloudError({ status: 502, detail: 'upstream connect error' })
    expect(e.kind).toBe('server')
    expect(e.message).toBe('云端服务暂时不可用，请稍后重试。')
    expect(e.message).not.toMatch(/502|upstream/)
    expect(isRetryable(e.kind)).toBe(false) // 5xx 不自动重试
  })

  it('429 无 Retry-After 时也给中性文案', () => {
    const e = normalizeCloudError({ status: 429 })
    expect(e.kind).toBe('rate-limit')
    expect(e.retryAfterSec).toBeUndefined()
    expect(e.message).toContain('稍后')
  })
})

// ---------------------------------------------------------------- 4 幂等重试（≥1）

describe('连接类重试策略', () => {
  it('幂等 GET 遇连接类错误重试 1 次并成功', async () => {
    const { c, requests } = client([
      () => {
        throw new Error('ECONNRESET')
      },
      () => meOk()
    ])
    const r = await c.me('AT1')
    expect(r.ok).toBe(true)
    expect(requests).toHaveLength(2)
  })

  it('非幂等 POST（登录）遇连接类错误不自动重试', async () => {
    const { c, requests } = client([
      () => {
        throw new Error('ECONNRESET')
      }
    ])
    const r = await c.login('u', 'p')
    expect(r.ok).toBe(false)
    expect(requests).toHaveLength(1)
  })
})

// ---------------------------------------------------------------- 5 状态机（≥2）

describe('绑定状态机', () => {
  it('未绑定 → 已绑定 → 失效 → 重绑（isCloudUsable 只在 bound 为真）', () => {
    const s0 = initialBindingState()
    expect(s0.status).toBe('unbound')
    expect(isCloudUsable(s0)).toBe(false)
    expect(cloudStatusLabel(s0.status)).toBe('未绑定')

    const bound = { ...s0, status: 'bound' as const, username: '王天志', updatedAt: 1 }
    expect(isCloudUsable(bound)).toBe(true)
    expect(cloudStatusLabel(bound.status)).toBe('已连接')

    const expired = { ...bound, status: 'expired' as const, lastError: '登录状态已失效，请重新绑定云端账号。' }
    expect(isCloudUsable(expired)).toBe(false)
    expect(cloudStatusLabel(expired.status)).toBe('凭据失效')

    const offline = { ...bound, status: 'offline' as const }
    expect(cloudStatusLabel(offline.status)).toBe('离线')

    const rebound = { ...expired, status: 'bound' as const, lastError: undefined }
    expect(isCloudUsable(rebound)).toBe(true)
  })

  it('服务器地址归一化：去尾斜杠、非法值回退默认、可切换（测试指向 localhost）', () => {
    expect(normalizeBaseUrl('https://agent.mnb-lab.cn/')).toBe('https://agent.mnb-lab.cn')
    expect(normalizeBaseUrl('  http://127.0.0.1:8000/// ')).toBe('http://127.0.0.1:8000')
    expect(normalizeBaseUrl('')).toBe(DEFAULT_CLOUD_BASE_URL)
    expect(normalizeBaseUrl('not-a-url')).toBe(DEFAULT_CLOUD_BASE_URL)
    expect(normalizeBaseUrl(undefined)).toBe(DEFAULT_CLOUD_BASE_URL)

    const { c, requests } = client([meOk], 'http://127.0.0.1:8000/')
    expect(c.getBaseUrl()).toBe('http://127.0.0.1:8000')
    void c.me('AT')
    expect(requests[0]!.url).toBe('http://127.0.0.1:8000/api/v1/auth/me')
  })
})

// ---------------------------------------------------------------- 6 解绑语义（≥1）

describe('解绑语义（客户端侧）', () => {
  it('解绑后不再持有令牌 → 用空令牌调用只会得到 auth 错误（不会误判成功）', async () => {
    const { c } = client([() => res(401, { detail: 'no token' })])
    const r = await c.me('')
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.kind).toBe('auth')
    // 客户端不缓存任何令牌（令牌由装配层持久化，解绑即清除）
    expect(Object.keys(c as unknown as Record<string, unknown>)).not.toContain('tokens')
  })
})

// ---------------------------------------------------------------- 7 超时参数传递（≥1）

describe('超时与请求头', () => {
  it('超时参数随请求下发；access 令牌以 Bearer 头携带', async () => {
    const { http, requests } = httpScript([meOk])
    const c = new CloudApiClient({ http, timeoutMs: 4321 })
    await c.me('AT9')
    expect(requests[0]!.timeoutMs).toBe(4321)
    expect(requests[0]!.headers['authorization']).toBe('Bearer AT9')
  })

  it('日志钩子收到请求结果（可观测性）', async () => {
    const logs: string[] = []
    const { http } = httpScript([() => res(500, { detail: 'x' })])
    const c = new CloudApiClient({ http, log: (m) => logs.push(m) })
    await c.me('AT')
    expect(logs.some((l) => l.includes('HTTP 500'))).toBe(true)
  })

  it('未使用注入的 fetch 全局（纯注入式，单测不触网）', async () => {
    const spy = vi.fn()
    vi.stubGlobal('fetch', spy)
    const { c } = client([meOk])
    await c.me('AT')
    expect(spy).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})

// ---------------------------------------------------------------- 8 真实服务器形状回放（M2-3a 实测）

describe('真实服务器响应形状回放（agent.mnb-lab.cn 实测）', () => {
  it('错密码：真实返回 401 + {"error":{"code":"AUTH_ERROR",...}} → 归一化为 auth + 中性文案', async () => {
    // 形状取自 2026-09-21 对 https://agent.mnb-lab.cn/api/v1/auth/login 的真实请求
    const { http } = httpScript([
      () => res(401, { error: { code: 'AUTH_ERROR', message: '用户名或密码错误', details: {} } })
    ])
    const c = new CloudApiClient({ http })
    const r = await c.login('someone', 'wrong')
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.error.kind).toBe('auth')
      // 不给用户看服务端原文，用本地中性文案
      expect(r.error.message).toBe('云端账号或密码不正确，或登录状态已过期。')
      expect(r.error.detail).toContain('AUTH_ERROR') // 原始信息仍留在 detail 供日志
    }
  })

  it('缺令牌访问 /auth/me：真实返回 401（JSON）→ 触发续期而不是当成服务端故障', async () => {
    const { c, requests } = client([
      () => res(401, { error: { code: 'AUTH_ERROR', message: '未认证' } }),
      () => res(200, { access_token: 'AT2', token_type: 'bearer' }),
      () => res(200, { id: 1, name: '某同学' })
    ])
    const r = await c.requestWithAuth('GET', '/api/v1/auth/me', { accessToken: 'AT_OLD', refreshToken: 'RT' })
    expect(r.ok).toBe(true)
    expect(requests).toHaveLength(3) // 401 → refresh → 重放
  })

  it('默认地址为真实 API 主机（网页端同源地址会返回 SPA，实测不可用）', () => {
    expect(DEFAULT_CLOUD_BASE_URL).toBe('https://agent.mnb-lab.cn')
  })
})
