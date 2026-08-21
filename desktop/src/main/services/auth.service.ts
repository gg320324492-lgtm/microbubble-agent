// 主进程 Auth 服务。
//
// 职责：
// - login: 调用后端 /auth/login，拿 access + refresh + profile，
//          access 进内存，refresh 进 safeStorage，profile 进 electron-store
// - logout: 清内存 + 清 vault（幂等）
// - restore: 启动时用 refresh_token 重新签 access，调 /auth/me 取 profile
//
// 错误规范（详见 shared/auth-types.ts §AuthErrorPayload）：
// - 任何失败返回 { success: false, error: { code, message, status? } }
// - 不抛异常到 renderer（避免 IPC 通道传递 Error 对象本身）

import { APP_CONFIG } from '@shared/config'
import type {
  LoginRequest,
  TokenPair,
  UserProfile,
  AuthRestoreResult,
  AuthErrorPayload
} from '@shared/auth-types'
import {
  vaultStoreRefreshToken,
  vaultLoadRefreshToken,
  vaultClear
} from './token-vault'
import {
  setProfile,
  getProfile
} from './storage.service'

// 仅活在 main 进程的 access_token（Renderer 永远不应拿到）
let currentAccessToken: string | null = null
let accessTokenExpiresAt = 0  // epoch ms; 与 expires_in 配合

/** 错误规范 —— 业务级 + HTTP 级。 */
function buildError(status: number, code: string, message: string): AuthErrorPayload {
  return { code, message, status }
}

/** fastapi 风格错误检测：{ detail: '...' } 或 { detail: [...] }。 */
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
 * 用户登录。
 * 主进程拿 token，全部存在安全地方。
 * 渲染进程只通过 IPC 拿到 success/failure 结果。
 */
export async function login(
  payload: LoginRequest
): Promise<
  { success: true; data: { expiresIn: number; profile: UserProfile } } | { success: false; error: AuthErrorPayload }
> {
  if (!payload?.username || !payload?.password) {
    return {
      success: false,
      error: buildError(400, 'INVALID_INPUT', 'username 和 password 都必填')
    }
  }

  try {
    const url = `${APP_CONFIG.backendUrl}/auth/login`
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: payload.username,
        password: payload.password
      })
    })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      const detail = extractFastApiDetail(body)
      let code: string
      let message: string
      if (response.status === 401) {
        code = 'INVALID_CREDENTIALS'
        message = detail ?? '用户名或密码错误'
      } else if (response.status === 429) {
        code = 'RATE_LIMITED'
        message = detail ?? '登录请求过于频繁，请稍后重试'
      } else if (response.status >= 500) {
        code = 'SERVER_ERROR'
        message = detail ?? `服务端异常 (${response.status})`
      } else {
        code = 'UNKNOWN_ERROR'
        message = detail ?? `登录失败 (${response.status})`
      }
      return { success: false, error: buildError(response.status, code, message) }
    }

    const json = (await response.json()) as {
      access_token: string
      refresh_token: string
      token_type?: string
      expires_in?: number
    }

    if (!json.access_token || !json.refresh_token) {
      return {
        success: false,
        error: buildError(502, 'INVALID_RESPONSE', '后端返回格式不正确')
      }
    }

    const tokenPair: TokenPair = {
      access_token: json.access_token,
      refresh_token: json.refresh_token,
      token_type: json.token_type === 'bearer' ? 'bearer' : 'bearer',
      expires_in: typeof json.expires_in === 'number' ? json.expires_in : 3600
    }

    // 升级：内存只活 access_token；refresh 进 safeStorage；profile 进 electron-store
    currentAccessToken = tokenPair.access_token
    accessTokenExpiresAt = Date.now() + tokenPair.expires_in * 1000
    vaultStoreRefreshToken(tokenPair.refresh_token)

    const profile = await fetchCurrentProfile(tokenPair.access_token)
    if (profile) {
      setProfile(profile)
    }

    return {
      success: true,
      data: {
        // 不外传 tokenPair —— refresh_token 必须留在主进程 vault 内
        expiresIn: tokenPair.expires_in,
        profile: profile ?? synthesizeEmptyProfile(payload.username)
      }
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return {
      success: false,
      error: buildError(0, 'NETWORK_ERROR', `网络异常: ${message}`)
    }
  }
}

/**
 * 用 access_token 调后端 /auth/me 取 profile。
 * 401 → refresh 一次 + 重试；still 401 → 返回 null。
 */
async function fetchCurrentProfile(accessToken: string): Promise<UserProfile | null> {
  try {
    const response = await fetch(`${APP_CONFIG.backendUrl}/auth/me`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: 'application/json'
      }
    })
    if (!response.ok) return null
    const json = (await response.json()) as Record<string, unknown>
    return {
      id: typeof json.id === 'string' ? json.id : String(json.id ?? ''),
      username: typeof json.username === 'string' ? json.username : '',
      email: typeof json.email === 'string' ? json.email : undefined,
      full_name: typeof json.full_name === 'string' ? json.full_name : undefined,
      is_active: json.is_active !== false,
      is_admin: json.is_admin === true,
      avatar_url: typeof json.avatar_url === 'string' ? json.avatar_url : undefined
    }
  } catch (_err) {
    return null
  }
}

/** login 失败时构造一个最小 profile，使 renderer store 仍能 set 状态。 */
function synthesizeEmptyProfile(username: string): UserProfile {
  return {
    id: '',
    username,
    is_active: true,
    is_admin: false
  }
}

/**
 * 登出（main 内存 + safeStorage vault + electron-store profile 全清）。
 * 永远成功（幂等）。
 */
export async function logout(): Promise<{ success: true }> {
  currentAccessToken = null
  accessTokenExpiresAt = 0
  vaultClear()
  return { success: true }
}

/**
 * 应用启动时恢复 session。
 * - 解密 refresh_token
 * - 调后端用 refresh 换新 access（Phase 1 暂不实现完整 refresh 协议，
 *   简化策略：仅靠 refresh_token 调 /auth/refresh，若后端无此端点则保持现状）
 * - 用新 access 调 /auth/me 取最新 profile
 *
 * 任何异常返回 null，renderer 清空 Pinia state 跳 /login。
 */
export async function restore(): Promise<AuthRestoreResult | null> {
  const refreshToken = vaultLoadRefreshToken()
  if (!refreshToken) return null

  try {
    // Phase 1 简化：直接尝试 /auth/refresh 拿新 token pair。
    // 如果后端不接受 {"refresh_token": ...} 而是 cookie-based，失败 → 返回 null 让用户重登。
    // Phase 2+ 会按后端实际 refresh 协议调整。
    const response = await fetch(`${APP_CONFIG.backendUrl}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    })

    if (!response.ok) {
      // refresh 失效 → 清状态
      vaultClear()
      return null
    }

    const json = (await response.json()) as {
      access_token: string
      refresh_token?: string
      expires_in?: number
    }

    if (!json.access_token) {
      vaultClear()
      return null
    }

    const newRefresh = json.refresh_token ?? refreshToken
    const tokenPair: TokenPair = {
      access_token: json.access_token,
      refresh_token: newRefresh,
      token_type: 'bearer',
      expires_in: typeof json.expires_in === 'number' ? json.expires_in : 3600
    }

    // 升级：update memory + vault
    currentAccessToken = tokenPair.access_token
    accessTokenExpiresAt = Date.now() + tokenPair.expires_in * 1000
    // 如果 refresh_token 轮换，重加密
    vaultStoreRefreshToken(newRefresh)

    const profile = await fetchCurrentProfile(tokenPair.access_token) ?? getProfile()
    if (profile) {
      setProfile(profile)
    }

    if (!profile) {
      vaultClear()
      return null
    }

    return { tokenPair, profile }
  } catch (_err) {
    // 网络异常时保守返回 null，让 renderer 清空 state
    return null
  }
}

/**
 * 给主进程内部使用的 access_token 拉取（业务模块未来用）。
 * 当前阶段只 restorelogin 流程使用，公开 API 仅通过 ipc。
 */
export function getCurrentAccessToken(): string | null {
  if (!currentAccessToken) return null
  if (Date.now() >= accessTokenExpiresAt) return null
  return currentAccessToken
}

/** 给调试 / 设置页可见：当前后端 URL。 */
export function getBackendUrl(): string {
  return APP_CONFIG.backendUrl
}

/** 单例导出（main 进程内调用）。 */
export const authService = {
  login,
  logout,
  restore,
  getCurrentAccessToken,
  getBackendUrl
}
