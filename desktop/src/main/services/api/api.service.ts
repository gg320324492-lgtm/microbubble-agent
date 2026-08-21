// 主进程 API Service —— 鉴权业务 endpoint 统一入口。
//
// 设计原则（详见 docs/desktop-conversion/security.md §API Gateway）：
// - 所有需要鉴权的业务请求都走 request() 入口
// - 自动注入 Bearer access_token（主进程内存，不暴露 renderer）
// - 单飞 refresh: 多请求并发 401 → 只一个 POST /auth/refresh → 排队 waiters 重试
// - refresh 失败 → 强制清场 → 整个 session 失效 → renderer 跳 /login
// - 错误归一化为 ApiError, 业务 code 与 auth 共享 AUTH_ERROR_CODES
//
// 调用方（main 内）：
//   import { apiService } from './services/api'
//   const r = await apiService.request({ method:'GET', path:'/tasks' })
//   if (r.ok) { r.data ... } else { r.error ... }
//
// 调用方（renderer, via IPC）：
//   window.api.api.request({ method:'GET', path:'/tasks' })
//
// 单飞算法：
//   incoming request N (auth required)
//   ├─ has access_token + not expired? → 直接发
//   ├─ token missing/expired → 走 refresh 路径
//   └─ on 401 received:
//        ├─ refreshing 还在 in-flight → 等它 + 用新 token 重试
//        └─ refreshing 不在 → 创建 refreshing promise
//             ├─ POST /auth/refresh
//             ├─ 成功 → 更新 token, resolve waiters, 重试原 request
//             └─ 失败 → 强制清场, reject waiters, 原 request 返回 NO_ACTIVE_SESSION

import { BrowserWindow } from 'electron'
import { APP_CONFIG } from '@shared/config'
import { AUTH_ERROR_CODES } from '@shared/auth-types'
import { IPC_CHANNELS } from '@shared/ipc-types'
import type { ApiError, ApiRequestPayload, ApiResult } from '@shared/preload-api'
import { authService } from '../auth.service'
import { vaultLoadRefreshToken } from '../token-vault'

const DEFAULT_TIMEOUT_MS = 15000

/**
 * 主进程 → renderer broadcast: session 失效。
 * 任何 webContents (含 future 多个窗口) 都推一次。
 * 不抛异常 —— 即便无窗口也安全。
 */
export function broadcastSessionExpired(): void {
  try {
    const wins = BrowserWindow.getAllWindows()
    for (const w of wins) {
      if (!w.isDestroyed()) {
        w.webContents.send(IPC_CHANNELS.AUTH_SESSION_EXPIRED)
      }
    }
  } catch (_err) {
    // ipc 通道异常时不抛 (e.g. app quitting 期间)
  }
}

function buildApiError(code: ApiError['code'], message: string, status?: number): ApiError {
  const err: ApiError = { code, message }
  if (status !== undefined) err.status = status
  return err
}

function extractFastApiDetail(body: unknown): string | undefined {
  if (typeof body === 'object' && body !== null) {
    const detail = (body as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string }
      if (typeof first?.msg === 'string') return first.msg
    }
  }
  return undefined
}

function buildQueryString(query?: Record<string, string | number | boolean>): string {
  if (!query || Object.keys(query).length === 0) return ''
  const entries = Object.entries(query)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => [encodeURIComponent(k), encodeURIComponent(String(v))].join('='))
  return entries.length === 0 ? '' : '?' + entries.join('&')
}

function normalizeHttpError(status: number, body: unknown): ApiError {
  const detail = extractFastApiDetail(body)
  let code: ApiError['code']
  let message: string
  if (status === 401) code = AUTH_ERROR_CODES.TOKEN_EXPIRED
  else if (status === 403) code = AUTH_ERROR_CODES.FORBIDDEN
  else if (status === 404) code = AUTH_ERROR_CODES.NOT_FOUND
  else if (status === 429) code = AUTH_ERROR_CODES.RATE_LIMITED
  else if (status >= 500) code = AUTH_ERROR_CODES.SERVER_ERROR
  else code = AUTH_ERROR_CODES.UNKNOWN_ERROR

  if (status === 401) message = detail ?? '认证失败，请重新登录'
  else if (status === 403) message = detail ?? '无权限访问此资源'
  else if (status === 404) message = detail ?? '资源不存在'
  else if (status === 429) message = detail ?? '请求过于频繁，请稍后重试'
  else if (status >= 500) message = detail ?? `服务端异常 (${status})`
  else message = detail ?? `请求失败 (${status})`

  return buildApiError(code, message, status)
}

// ============ 单飞 refresh 实现 ============

let refreshingPromise: Promise<boolean> | null = null

/**
 * 单飞 refresh：先到的请求触发 refresh, 后续并发请求等其完成。
 */
async function singleFlightRefresh(): Promise<boolean> {
  if (refreshingPromise) return refreshingPromise

  // 新建 refresh promise, 跨并发合并
  refreshingPromise = (async (): Promise<boolean> => {
    // 从 vault 拿 refresh_token
    const refreshToken = vaultLoadRefreshToken()
    if (!refreshToken) {
      authService.forceClearOnRefreshFail()
      return false
    }
    const ok = await authService.performRefresh(refreshToken)
    if (!ok) {
      authService.forceClearOnRefreshFail()
    }
    return ok
  })().finally(() => {
    // 释放单飞锁 (下个 401 才会重新触发)
    refreshingPromise = null
  })

  return refreshingPromise
}

// ============ request 主体 ============

async function fetchOnce(
  method: string,
  fullUrl: string,
  body: unknown | undefined,
  timeoutMs: number
): Promise<{ response: Response; bodyText: string; bodyJson: unknown | undefined }> {
  const headers: Record<string, string> = {
    Accept: 'application/json'
  }

  const accessToken = authService.getCurrentAccessToken()
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`
  }

  let bodyToSend: string | undefined
  if (body !== undefined && body !== null) {
    headers['Content-Type'] = 'application/json'
    bodyToSend = JSON.stringify(body)
  }

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(fullUrl, {
      method,
      headers,
      body: bodyToSend,
      signal: controller.signal
    })
    const bodyText = await response.text()
    let bodyJson: unknown
    try {
      bodyJson = bodyText.length === 0 ? undefined : JSON.parse(bodyText)
    } catch (_err) {
      bodyJson = undefined
    }
    return { response, bodyText, bodyJson }
  } finally {
    clearTimeout(timer)
  }
}

/**
 * 主入口: 一次带自动 refresh 的请求
 */
async function request<T = unknown>(payload: ApiRequestPayload): Promise<ApiResult<T>> {
  const { method, path, body, query, timeoutMs = DEFAULT_TIMEOUT_MS } = payload

  if (!path || typeof path !== 'string') {
    return {
      ok: false,
      error: buildApiError(AUTH_ERROR_CODES.INVALID_INPUT, 'path 必填且为字符串')
    }
  }
  if (!path.startsWith('/')) {
    return {
      ok: false,
      error: buildApiError(AUTH_ERROR_CODES.INVALID_INPUT, 'path 必须以 / 开头（不含 baseURL）')
    }
  }

  const queryStr = buildQueryString(query)
  const fullUrl = `${APP_CONFIG.backendUrl}${path}${queryStr}`

  // 第一次发送
  const first = await fetchOnce(method, fullUrl, body, timeoutMs)

  // 非 401 → 直接返回归一化结果
  if (first.response.status !== 401) {
    return finalizeResponse<T>(first.response, first.bodyJson, first.bodyText)
  }

  // 401 → 单飞 refresh 后重试一次
  const refreshed = await singleFlightRefresh()
  if (!refreshed) {
    broadcastSessionExpired()
    return {
      ok: false,
      error: buildApiError(AUTH_ERROR_CODES.NO_ACTIVE_SESSION, '会话已过期，请重新登录')
    }
  }

  // 第二次尝试（new access_token 已就位）
  const second = await fetchOnce(method, fullUrl, body, timeoutMs)
  if (second.response.status === 401) {
    // refresh 后仍 401 → 强制清场
    authService.forceClearOnRefreshFail()
    broadcastSessionExpired()
    return {
      ok: false,
      error: buildApiError(AUTH_ERROR_CODES.NO_ACTIVE_SESSION, '会话已过期，请重新登录')
    }
  }

  return finalizeResponse<T>(second.response, second.bodyJson, second.bodyText)
}

function finalizeResponse<T>(
  response: Response,
  bodyJson: unknown | undefined,
  bodyText: string
): ApiResult<T> {
  if (response.ok) {
    if (response.status === 204 || bodyText.length === 0) {
      return { ok: true, data: undefined as T }
    }
    if (bodyJson === undefined) {
      return {
        ok: false,
        error: buildApiError(AUTH_ERROR_CODES.INVALID_RESPONSE, '后端返回非 JSON', response.status)
      }
    }
    return { ok: true, data: bodyJson as T }
  }

  return {
    ok: false,
    error: normalizeHttpError(response.status, bodyJson)
  }
}

export const apiService = {
  request,
  singleFlightRefresh,
  broadcastSessionExpired
}
