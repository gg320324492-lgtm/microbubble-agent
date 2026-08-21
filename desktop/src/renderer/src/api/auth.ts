// auth API 入口（renderer 端统一封装）。
//
// 设计原则：
// - 所有 auth 操作走 IPC 委托主进程 auth.service
//   （token 永不出主进程：refresh_token 进 vault；access_token 仅活主进程内存）
// - 业务 API 调用走 window.api.api.request（统一鉴权 + 单飞 refresh），
//   禁止 renderer 直接 axios 调鉴权 endpoint

import type {
  LoginRequest,
  UserInfo,
  AuthRestoreResult,
  AuthErrorPayload
} from '@shared/auth-types'
import type {
  ApiRequestPayload,
  ApiResult
} from '@shared/preload-api'

/**
 * 调 window.api.auth.login。
 * 主进程已吃掉所有 token——renderer 拿不到 refresh_token / access_token。
 */
export async function login(
  payload: LoginRequest
): Promise<
  | { success: true; data: { expiresAt: number; user: UserInfo } }
  | { success: false; error: AuthErrorPayload }
> {
  return window.api.auth.login(payload)
}

export async function logout(): Promise<{ success: true }> {
  return window.api.auth.logout()
}

export async function restore(): Promise<AuthRestoreResult | null> {
  return window.api.auth.restore()
}

export async function getBackendUrl(): Promise<string> {
  return window.api.auth.getBackendUrl()
}

/**
 * 业务 API 统一调用入口。
 *
 * 用法:
 *   const result = await apiRequest<Task[]>({
 *     method: 'GET',
 *     path: '/tasks',
 *     query: { status: 'in_progress' }
 *   })
 *   if (result.ok) console.log(result.data)
 *   else console.error(result.error)
 *
 * 主进程负责:
 *   1. 注入 Bearer access_token（主进程内存）
 *   2. 单飞 refresh（401 → 自动 refresh 一次 → 重试）
 *   3. refresh 失败 → 强制清场 → renderer 跳 /login
 */
export async function apiRequest<T = unknown>(
  payload: ApiRequestPayload
): Promise<ApiResult<T>> {
  return window.api.api.request<T>(payload)
}
