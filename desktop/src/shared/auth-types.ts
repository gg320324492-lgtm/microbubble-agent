// 跨 main / preload / renderer 共享的 auth 类型契约。
// 一律对照 app/schemas/auth.py (Pydantic) 真实 schema, 任何后端字段改动
// 必须先改 docs/desktop-conversion/auth-api-contract.md 再改本文件。
//
// 严禁保存 refresh_token / access_token 到 renderer 任何持久化层。
// login 响应拿到 refresh_token 后立即入主进程 vault, renderer 只看 user + expiresAt。

import type { UserInfo } from './user-info'

// UserInfo 从 user-info.ts 单一源导出，本文件 re-export 以便业务模块
// 一律通过 @shared/auth-types 引用。
export type { UserInfo }
export { isAdminRole } from './user-info'

/**
 * LoginRequest (来自 app/schemas/auth.py LoginRequest)。
 * 字段: username + password（用户名或邮箱均可登录；后端按 username 字段匹配）。
 */
export interface LoginRequest {
  username: string
  password: string
}

/**
 * 后端 LoginResponse 完整形状。
 * 注意：refresh_token 在响应里 —— 这是新登录时的"新" refresh_token，
 * 旧 refresh_token 被此 token 取代（用户重新登录时整体替换）。
 *
 * desktop 不直接消费整个 LoginResponse —— main 进程解析后只把 user + expiresAt
 * 暴露给 renderer（refresh_token 仅入 vault，永不漂到 renderer）。
 */
export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  user: UserInfo
}

/**
 * RefreshTokenRequest — 与 app/schemas/auth.py 一致。
 */
export interface RefreshTokenRequest {
  refresh_token: string
}

/**
 * RefreshTokenResponse — 注意：refresh_token 不轮换。
 * 续签只返新 access_token，旧 refresh_token 继续有效（直到 /auth/login 重新登录）。
 */
export interface RefreshTokenResponse {
  access_token: string
  token_type: 'bearer'
}

/**
 * ProfileUpdateRequest — 部分更新字段，任一字段为 null 表示不更新。
 */
export interface ProfileUpdateRequest {
  name?: string
  email?: string
  phone?: string
  bio?: string
  avatar?: string
}

/**
 * ChangePasswordRequest — 自己改自己密码。
 */
export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}

/**
 * ResetPasswordRequest — admin 重置他人密码。
 */
export interface ResetPasswordRequest {
  user_id: number
  new_password: string
}

/**
 * AuthRestoreResult —— restore() 成功时返回。
 * expiresAt 为 epoch 毫秒，由 main 从 JWT `exp` claim 解析计算。
 */
export interface AuthRestoreResult {
  expiresAt: number
  user: UserInfo
}

/**
 * 跨 IPC 传递的错误。
 * 不传 Error 对象本身（不可序列化），传扁平的字段。
 */
export interface AuthErrorPayload {
  code: string
  message: string
  status?: number
}

/**
 * 业务 code 归一化（main 模块导出供 api.service 复用）。
 */
export const AUTH_ERROR_CODES = {
  INVALID_INPUT: 'INVALID_INPUT',
  INVALID_CREDENTIALS: 'INVALID_CREDENTIALS',
  TOKEN_EXPIRED: 'TOKEN_EXPIRED',
  USER_DISABLED: 'USER_DISABLED',
  FORBIDDEN: 'FORBIDDEN',
  NOT_FOUND: 'NOT_FOUND',
  RATE_LIMITED: 'RATE_LIMITED',
  SERVER_ERROR: 'SERVER_ERROR',
  NETWORK_ERROR: 'NETWORK_ERROR',
  INVALID_RESPONSE: 'INVALID_RESPONSE',
  NO_ACTIVE_SESSION: 'NO_ACTIVE_SESSION',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR'
} as const

export type AuthErrorCode = (typeof AUTH_ERROR_CODES)[keyof typeof AUTH_ERROR_CODES]
