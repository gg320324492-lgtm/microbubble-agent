// 主进程 Auth 服务。
//
// 职责：
// - login: 调用后端 /auth/login，拿 access + refresh + user，
//          access 进内存，refresh 进 safeStorage
// - logout: 清内存 + 清 vault（幂等）
// - restore: 启动时用 refresh_token 重签 access，调 /auth/me 取 user
//
// 错误规范（详见 shared/auth-types.ts §AuthErrorPayload）：
// - 任何失败返回 { success: false, error: { code, message, status? } }
// - 不抛异常到 renderer（避免 IPC 通道传递 Error 对象本身）
//
// 字段对齐: 严格按 docs/desktop-conversion/auth-api-contract.md §3。

import { APP_CONFIG } from '@shared/config'
import type {
  LoginRequest,
  UserInfo,
  AuthRestoreResult,
  AuthErrorPayload
} from '@shared/auth-types'
import { AUTH_ERROR_CODES, isAdminRole } from '@shared/auth-types'
import {
  vaultStoreRefreshToken,
  vaultLoadRefreshToken,
  vaultClear
} from './token-vault'

// 仅活在 main 进程的 access_token（Renderer 永远不应拿到）
let currentAccessToken: string | null = null
let currentAccessExpiresAt = 0  // epoch ms; 来自 JWT exp claim

// ============ util ============

function buildError(status: number, code: string, message: string): AuthErrorPayload {
  return { code, message, status }
}

/** fastapi 风格错误：{ detail: '...' } 或 { detail: [...] }。 */
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

/**
 * 解析 JWT payload 取 `exp` claim。
 * base64url decode JSON 段；不校验签名（仅本地算 expiry 时间）。
 */
function parseJwtExp(token: string): number {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return 0
    // base64url → base64
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
    const payload = JSON.parse(Buffer.from(padded, 'base64').toString('utf-8')) as {
      exp?: number
    }
    if (typeof payload.exp === 'number') return payload.exp * 1000
  } catch (_err) {
    // 忽略
  }
  return 0
}

/** 把后端 UserInfo json 转成 TS 类型（窄化 + 保 null）。 */
function parseUserInfo(json: unknown): UserInfo | null {
  if (typeof json !== 'object' || json === null) return null
  const o = json as Record<string, unknown>
  return {
    id: typeof o.id === 'number' ? o.id : Number(o.id) || 0,
    name: typeof o.name === 'string' ? o.name : '',
    role: typeof o.role === 'string' ? o.role : '',
    grade: typeof o.grade === 'string' ? o.grade : null,
    research_area: typeof o.research_area === 'string' ? o.research_area : null,
    email: typeof o.email === 'string' ? o.email : null,
    phone: typeof o.phone === 'string' ? o.phone : null,
    bio: typeof o.bio === 'string' ? o.bio : null,
    avatar: typeof o.avatar === 'string' ? o.avatar : null,
    is_active: o.is_active !== false
  }
}

// ============ Public API ============

/**
 * 用户登录。
 * 主进程拿 token, refresh 进 vault。renderer 只看到 user + expiresAt。
 */
export async function login(
  payload: LoginRequest
): Promise<
  { success: true; data: { expiresAt: number; user: UserInfo } } | { success: false; error: AuthErrorPayload }
> {
  if (!payload?.username || !payload?.password) {
    return {
      success: false,
      error: buildError(400, AUTH_ERROR_CODES.INVALID_INPUT, 'username 和 password 都必填')
    }
  }

  try {
    const url = `${APP_CONFIG.backendUrl}/auth/login`
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: payload.username, password: payload.password })
    })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      const detail = extractFastApiDetail(body)
      let code: string
      let message: string
      if (response.status === 401) {
        code = AUTH_ERROR_CODES.INVALID_CREDENTIALS
        message = detail ?? '用户名或密码错误'
      } else if (response.status === 429) {
        code = AUTH_ERROR_CODES.RATE_LIMITED
        message = detail ?? '登录请求过于频繁，请稍后重试'
      } else if (response.status === 403) {
        code = AUTH_ERROR_CODES.USER_DISABLED
        message = detail ?? '账号已被禁用'
      } else if (response.status >= 500) {
        code = AUTH_ERROR_CODES.SERVER_ERROR
        message = detail ?? `服务端异常 (${response.status})`
      } else {
        code = AUTH_ERROR_CODES.UNKNOWN_ERROR
        message = detail ?? `登录失败 (${response.status})`
      }
      return { success: false, error: buildError(response.status, code, message) }
    }

    const json = (await response.json()) as {
      access_token?: string
      refresh_token?: string
      token_type?: string
      user?: unknown
    }

    if (!json.access_token || !json.refresh_token || !json.user) {
      return {
        success: false,
        error: buildError(502, AUTH_ERROR_CODES.INVALID_RESPONSE, '后端返回格式不正确')
      }
    }

    const user = parseUserInfo(json.user)
    if (!user) {
      return {
        success: false,
        error: buildError(502, AUTH_ERROR_CODES.INVALID_RESPONSE, '后端 user 字段格式不正确')
      }
    }

    // 安全姿态：
    // - refresh_token 仅在此处入 vault, 永不出 main 进程
    // - access_token 进 currentAccessToken 内存 + 计算 expiresAt
    vaultStoreRefreshToken(json.refresh_token)
    currentAccessToken = json.access_token
    currentAccessExpiresAt = parseJwtExp(json.access_token)

    return {
      success: true,
      data: {
        expiresAt: currentAccessExpiresAt,
        user
      }
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return {
      success: false,
      error: buildError(0, AUTH_ERROR_CODES.NETWORK_ERROR, `网络异常: ${message}`)
    }
  }
}

/**
 * 登出（main 内存 + safeStorage vault 全清）。
 * 永远成功（幂等）。
 */
export async function logout(): Promise<{ success: true }> {
  currentAccessToken = null
  currentAccessExpiresAt = 0
  vaultClear()
  return { success: true }
}

/**
 * 应用启动时恢复 session。
 * - 解密 refresh_token
 * - 调 /auth/refresh 拿新 access_token（refresh 不轮换）
 * - 调 /auth/me 取最新 user
 *
 * 任何异常返回 null，renderer 清空 Pinia state 跳 /login。
 */
export async function restore(): Promise<AuthRestoreResult | null> {
  const refreshToken = vaultLoadRefreshToken()
  if (!refreshToken) return null

  try {
    const refreshResp = await fetch(`${APP_CONFIG.backendUrl}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    })
    if (!refreshResp.ok) {
      vaultClear()
      return null
    }

    const refreshJson = (await refreshResp.json()) as { access_token?: string }
    if (!refreshJson.access_token) {
      vaultClear()
      return null
    }

    currentAccessToken = refreshJson.access_token
    currentAccessExpiresAt = parseJwtExp(refreshJson.access_token)
    // refresh_token 不轮换 → vault 不用更新

    // 用新 access 拉 user
    const meResp = await fetch(`${APP_CONFIG.backendUrl}/auth/me`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${refreshJson.access_token}` }
    })
    if (!meResp.ok) {
      vaultClear()
      return null
    }
    const meJson = await meResp.json()
    const user = parseUserInfo(meJson)
    if (!user) {
      vaultClear()
      return null
    }

    return {
      expiresAt: currentAccessExpiresAt,
      user
    }
  } catch (_err) {
    return null
  }
}

/**
 * 给主进程内部业务模块使用 —— 拿到当前 access_token (已校验未过期)。
 * Renderer 永远走 window.api.request(), 不直接调此函数。
 *
 * 若 access_token 过期（currentAccessExpiresAt 已过），返回 null。
 * 调用方应通过 api.service 的单飞 refresh 重签后再重试。
 */
export function getCurrentAccessToken(): string | null {
  if (!currentAccessToken) return null
  if (Date.now() >= currentAccessExpiresAt) return null
  return currentAccessToken
}

/**
 * 内部使用: 用 refresh_token 重签 access（被 api.service 的单飞 refresh 调用）。
 * 成功: 写入 currentAccessToken + 解析 expiresAt; 失败: 返回 false。
 *
 * 关键不变量: refresh_token 由调用方传入（api.service 持有），不在此函数内保管。
 */
export async function performRefresh(refreshToken: string): Promise<boolean> {
  try {
    const resp = await fetch(`${APP_CONFIG.backendUrl}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    })
    if (!resp.ok) return false
    const json = (await resp.json()) as { access_token?: string }
    if (!json.access_token) return false
    currentAccessToken = json.access_token
    currentAccessExpiresAt = parseJwtExp(json.access_token)
    return true
  } catch (_err) {
    return false
  }
}

/** 强制清场 (refresh 失败 / 用户被禁用时由 api.service 触发)。 */
export function forceClearOnRefreshFail(): void {
  currentAccessToken = null
  currentAccessExpiresAt = 0
  vaultClear()
}

/** 调试 / 设置页可见：当前后端 URL。 */
export function getBackendUrl(): string {
  return APP_CONFIG.backendUrl
}

/**
 * 判断 user 是否管理员（基于 role 字段）。
 * 重导出以便 main 业务模块使用。
 */
export { isAdminRole }

/** 单例导出（main 进程内调用）。 */
export const authService = {
  login,
  logout,
  restore,
  getCurrentAccessToken,
  performRefresh,
  forceClearOnRefreshFail,
  getBackendUrl,
  isAdminRole
}
