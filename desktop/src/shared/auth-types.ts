// 跨 main / preload / renderer 共享的 auth 类型契约。
// 一切 IPC + Pinia + 后端响应都用本文件类型，避免漂移。

/**
 * 登录请求（与 FastAPI /api/v1/auth/login 一致）。
 * 后端确认 username (用户名 / 邮箱) + password。
 */
export interface LoginRequest {
  username: string
  password: string
}

/**
 * 后端返回的 token 对。
 * 与现有 web 端（auth.py schema）保持同名，方便未来 web 退役后共享 schema。
 */
export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number  // 秒; 用作 Pinia 中 access_token 过期标记
}

/**
 * 当前登录用户档案。
 * 后端 /api/v1/auth/me 返回 schema 的最小可用 subset; Phase 2+ 业务模块按需扩张。
 */
export interface UserProfile {
  id: string
  username: string
  email?: string
  full_name?: string
  is_active: boolean
  is_admin: boolean
  avatar_url?: string
}

/**
 * auth.restore 返回值 —— 包含解密后 token + 用户档案。
 * 如果无 token / 加密失败 / 解密失败，整体返回 null，由 renderer 清空 state。
 */
export interface AuthRestoreResult {
  tokenPair: TokenPair
  profile: UserProfile
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
