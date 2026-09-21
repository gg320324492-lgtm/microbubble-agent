// 云端 API 客户端（工单 M2-3a §1）— 纯逻辑 + 注入式 HTTP，零 Electron / 零依赖。
//
// 用途：打通「桌面端 ↔ 父级服务器」的账号绑定。本单只做「连接」这件事，
// 不改知识库/网盘任何 UI 与数据流（那是 M2-3b/c）。
//
// 契约来自只读调研（app/api/v1/auth.py + app/schemas/auth.py + app/core/*）：
//   POST {base}/api/v1/auth/login    body {username, password}      → {access_token, refresh_token, token_type:"bearer"}
//   POST {base}/api/v1/auth/refresh  body {refresh_token}           → {access_token, token_type}   ← 注意：不换发 refresh
//   GET  {base}/api/v1/auth/me       header Authorization: Bearer   → {id, name, grade, ...}
//   登录限流：5 分钟 5 次，触发 429 且带 Retry-After（本模块尊重该头）

/** 注入式 HTTP 函数（测试用 mock，生产用 fetch） */
export interface CloudHttpRequest {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  url: string
  headers: Record<string, string>
  body?: string
  timeoutMs: number
}

export interface CloudHttpResponse {
  status: number
  headers: Record<string, string>
  /** 响应正文（文本；调用方自行 JSON.parse） */
  text: string
}

export type CloudHttpFn = (req: CloudHttpRequest) => Promise<CloudHttpResponse>

export interface CloudTokens {
  accessToken: string
  refreshToken: string
}

export interface CloudUser {
  id: number
  name: string
  grade?: string | null
  email?: string | null
}

/** 错误分类（归一化后只暴露中性中文，原始报错进日志） */
export type CloudErrorKind = 'network' | 'timeout' | 'auth' | 'rate-limit' | 'client' | 'server' | 'malformed'

export interface CloudError {
  kind: CloudErrorKind
  /** 面向用户的中性文案 */
  message: string
  /** 原始信息（仅日志用，绝不直接展示） */
  detail?: string
  /** 429 时服务端要求的等待秒数 */
  retryAfterSec?: number
}

export type CloudResult<T> = { ok: true; data: T } | { ok: false; error: CloudError }

/**
 * 默认云端地址。
 *
 * 注意（M2-3a 真机实测纠正）：工单原写 `https://mnb-lab.cn`，但**实测该主机返回的是网页端 SPA**
 * （`/api/v1/auth/me` 返回 HTML 200、POST 返回 405），API 实际部署在 `https://agent.mnb-lab.cn`：
 *   GET  /health           → 200
 *   GET  /api/v1/auth/me   → 401（JSON，缺令牌）
 *   POST /api/v1/auth/login（错密码）→ 401 {"error":{"code":"AUTH_ERROR","message":"用户名或密码错误"}}
 * 故默认值按证据取真实 API 主机；地址在设置页可改（含自建/局域网部署）。
 */
export const DEFAULT_CLOUD_BASE_URL = 'https://agent.mnb-lab.cn'
export const DEFAULT_TIMEOUT_MS = 15_000

/** 归一化 base url（去掉尾部斜杠；非法值回退默认） */
export function normalizeBaseUrl(raw: unknown): string {
  const s = String(raw ?? '').trim()
  if (!s) return DEFAULT_CLOUD_BASE_URL
  const trimmed = s.replace(/\/+$/, '')
  if (!/^https?:\/\/[^\s/]+/i.test(trimmed)) return DEFAULT_CLOUD_BASE_URL
  return trimmed
}

/** 错误归一化（纯函数）：状态码/异常 → 分类 + 中性中文 */
export function normalizeCloudError(input: {
  status?: number
  headers?: Record<string, string>
  detail?: string
  exceptionName?: string
}): CloudError {
  const { status, headers, detail, exceptionName } = input
  const retryAfter = headers?.['retry-after']
  const retryAfterSec = retryAfter && /^\d+$/.test(retryAfter) ? Number(retryAfter) : undefined

  if (status === undefined) {
    if (exceptionName === 'AbortError' || exceptionName === 'TimeoutError') {
      return { kind: 'timeout', message: '连接云端超时，请检查网络后重试。', detail }
    }
    return { kind: 'network', message: '无法连接云端服务器，请检查网络或服务器地址。', detail }
  }
  if (status === 401 || status === 403) {
    return { kind: 'auth', message: '云端账号或密码不正确，或登录状态已过期。', detail }
  }
  if (status === 429) {
    return {
      kind: 'rate-limit',
      message: retryAfterSec
        ? `尝试过于频繁，请在 ${Math.ceil(retryAfterSec / 60)} 分钟后重试。`
        : '尝试过于频繁，请稍后重试。',
      detail,
      ...(retryAfterSec === undefined ? {} : { retryAfterSec })
    }
  }
  if (status >= 500) {
    return { kind: 'server', message: '云端服务暂时不可用，请稍后重试。', detail }
  }
  if (status >= 400) {
    return { kind: 'client', message: '请求被云端拒绝，请检查填写的信息。', detail }
  }
  return { kind: 'malformed', message: '云端返回了无法识别的响应。', detail }
}

/** 该错误是否值得「连接类重试 1 次」（幂等 GET only —— 由调用方保证方法幂等） */
export function isRetryable(kind: CloudErrorKind): boolean {
  return kind === 'network' || kind === 'timeout'
}

export interface CloudApiDeps {
  http: CloudHttpFn
  baseUrl?: string
  timeoutMs?: number
  log?: (message: string) => void
}

/**
 * 云端 API 客户端。
 *
 * 令牌管理：access 附于后续请求；401 → 用 refresh 静默续期**一次**并重放原请求；
 * refresh 也失效 → 返回 auth 错误（上层据此把状态置「凭据失效」并提示重新绑定）。
 */
export class CloudApiClient {
  private readonly http: CloudHttpFn
  private readonly timeoutMs: number
  private readonly log: (m: string) => void
  private baseUrl: string

  constructor(deps: CloudApiDeps) {
    this.http = deps.http
    this.baseUrl = normalizeBaseUrl(deps.baseUrl)
    this.timeoutMs = deps.timeoutMs ?? DEFAULT_TIMEOUT_MS
    this.log = deps.log ?? ((): void => undefined)
  }

  getBaseUrl(): string {
    return this.baseUrl
  }

  setBaseUrl(raw: unknown): string {
    this.baseUrl = normalizeBaseUrl(raw)
    return this.baseUrl
  }

  private url(path: string): string {
    return `${this.baseUrl}${path.startsWith('/') ? path : `/${path}`}`
  }

  /** 单次请求（不发重试）；异常已归一化 */
  private async request(
    method: CloudHttpRequest['method'],
    path: string,
    opts: { body?: unknown; accessToken?: string; idempotent?: boolean } = {}
  ): Promise<CloudResult<{ status: number; json: unknown }>> {
    const headers: Record<string, string> = { 'content-type': 'application/json' }
    if (opts.accessToken) headers['authorization'] = `Bearer ${opts.accessToken}`
    const req: CloudHttpRequest = {
      method,
      url: this.url(path),
      headers,
      timeoutMs: this.timeoutMs,
      ...(opts.body === undefined ? {} : { body: JSON.stringify(opts.body) })
    }

    const attempt = async (): Promise<CloudResult<{ status: number; json: unknown }>> => {
      try {
        const res = await this.http(req)
        if (res.status < 200 || res.status >= 300) {
          const err = normalizeCloudError({ status: res.status, headers: res.headers, detail: res.text.slice(0, 300) })
          this.log(`[cloud] ${method} ${path} → HTTP ${res.status}（${err.kind}）`)
          return { ok: false, error: err }
        }
        try {
          return { ok: true, data: { status: res.status, json: res.text ? JSON.parse(res.text) : {} } }
        } catch (e) {
          const err = normalizeCloudError({ detail: e instanceof Error ? e.message : String(e) })
          err.kind = 'malformed'
          err.message = '云端返回了无法识别的响应。'
          this.log(`[cloud] ${method} ${path} → 响应非 JSON`)
          return { ok: false, error: err }
        }
      } catch (e) {
        const err = normalizeCloudError({
          detail: e instanceof Error ? e.message : String(e),
          exceptionName: e instanceof Error ? e.name : undefined
        })
        this.log(`[cloud] ${method} ${path} → ${err.kind}：${err.detail ?? ''}`)
        return { ok: false, error: err }
      }
    }

    const first = await attempt()
    // 连接类错误且调用方声明幂等 → 重试 1 次（不做激进重试）
    if (!first.ok && opts.idempotent && isRetryable(first.error.kind)) {
      this.log(`[cloud] ${method} ${path} 连接类错误，重试 1 次`)
      return attempt()
    }
    return first
  }

  /** 登录（换令牌） */
  async login(username: string, password: string): Promise<CloudResult<CloudTokens>> {
    const res = await this.request('POST', '/api/v1/auth/login', { body: { username, password } })
    if (!res.ok) return res
    const j = res.data.json as { access_token?: unknown; refresh_token?: unknown }
    if (typeof j.access_token !== 'string' || typeof j.refresh_token !== 'string') {
      return {
        ok: false,
        error: { kind: 'malformed', message: '云端返回了无法识别的登录响应。', detail: JSON.stringify(j).slice(0, 200) }
      }
    }
    return { ok: true, data: { accessToken: j.access_token, refreshToken: j.refresh_token } }
  }

  /** 刷新 access（refresh 失效 → auth 错误，上层置「凭据失效」） */
  async refresh(refreshToken: string): Promise<CloudResult<{ accessToken: string }>> {
    const res = await this.request('POST', '/api/v1/auth/refresh', { body: { refresh_token: refreshToken } })
    if (!res.ok) return res
    const j = res.data.json as { access_token?: unknown }
    if (typeof j.access_token !== 'string') {
      return {
        ok: false,
        error: { kind: 'malformed', message: '云端返回了无法识别的续期响应。', detail: JSON.stringify(j).slice(0, 200) }
      }
    }
    return { ok: true, data: { accessToken: j.access_token } }
  }

  /** 取当前用户信息（幂等 GET → 允许连接类重试 1 次） */
  async me(accessToken: string): Promise<CloudResult<CloudUser>> {
    const res = await this.request('GET', '/api/v1/auth/me', { accessToken, idempotent: true })
    if (!res.ok) return res
    const j = res.data.json as { id?: unknown; name?: unknown; grade?: unknown; email?: unknown }
    if (typeof j.id !== 'number' || typeof j.name !== 'string') {
      return {
        ok: false,
        error: { kind: 'malformed', message: '云端返回了无法识别的用户信息。', detail: JSON.stringify(j).slice(0, 200) }
      }
    }
    return { ok: true, data: { id: j.id, name: j.name, grade: (j.grade as string) ?? null, email: (j.email as string) ?? null } }
  }

  /**
   * 带自动续期的请求（本单唯一对外入口，供 b/c 单复用）：
   * 401 → refresh 一次 → 重放；refresh 失效 → auth 错误。
   * 返回新的令牌（续期成功时），调用方负责持久化。
   */
  async requestWithAuth(
    method: CloudHttpRequest['method'],
    path: string,
    tokens: CloudTokens,
    opts: { body?: unknown } = {}
  ): Promise<CloudResult<{ json: unknown; tokens: CloudTokens; refreshed: boolean }>> {
    const first = await this.request(method, path, {
      ...(opts.body === undefined ? {} : { body: opts.body }),
      accessToken: tokens.accessToken,
      idempotent: method === 'GET'
    })
    if (first.ok) {
      return { ok: true, data: { json: first.data.json, tokens, refreshed: false } }
    }
    if (first.error.kind !== 'auth') return first

    // access 过期 → 静默续期一次
    this.log(`[cloud] access 失效，尝试续期一次：${method} ${path}`)
    const refreshed = await this.refresh(tokens.refreshToken)
    if (!refreshed.ok) {
      this.log(`[cloud] 续期失败（${refreshed.error.kind}）→ 置「凭据失效」`)
      return {
        ok: false,
        error: { kind: 'auth', message: '登录状态已失效，请重新绑定云端账号。', detail: refreshed.error.detail }
      }
    }
    const nextTokens: CloudTokens = { accessToken: refreshed.data.accessToken, refreshToken: tokens.refreshToken }
    const replay = await this.request(method, path, {
      ...(opts.body === undefined ? {} : { body: opts.body }),
      accessToken: nextTokens.accessToken,
      idempotent: method === 'GET'
    })
    if (!replay.ok) return replay
    return { ok: true, data: { json: replay.data.json, tokens: nextTokens, refreshed: true } }
  }
}

// ---------------------------------------------------------------- 绑定状态机（§2/§4）

export type CloudBindingStatus = 'unbound' | 'bound' | 'expired' | 'offline'

export interface CloudBindingState {
  status: CloudBindingStatus
  baseUrl: string
  /** 服务器侧用户名（绑定成功后由 /me 回填） */
  username?: string
  /** 最近一次错误（中性文案） */
  lastError?: string
  /** 最近一次状态变更时间 */
  updatedAt: number
}

export function initialBindingState(baseUrl = DEFAULT_CLOUD_BASE_URL): CloudBindingState {
  return { status: 'unbound', baseUrl: normalizeBaseUrl(baseUrl), updatedAt: 0 }
}

/** 状态是否处于「可用」态（b/c 单据此决定能否发起远程调用） */
export function isCloudUsable(state: CloudBindingState): boolean {
  return state.status === 'bound'
}

export function cloudStatusLabel(status: CloudBindingStatus): string {
  return status === 'bound'
    ? '已连接'
    : status === 'expired'
      ? '凭据失效'
      : status === 'offline'
        ? '离线'
        : '未绑定'
}

/** 面向用户的中性文案（错误只给中文，原始信息进日志） */
export function cloudErrorMessage(error: CloudError): string {
  return error.message
}
