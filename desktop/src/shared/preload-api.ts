import type {
  LoginRequest,
  UserInfo,
  AuthRestoreResult,
  AuthErrorPayload
} from './auth-types'
import type { PingRequest, PongResponse } from './common-types'

// Re-export for renderer convenience
export type { PingRequest, PongResponse }
export type {
  LoginRequest,
  UserInfo,
  AuthRestoreResult,
  AuthErrorPayload
}

/**
 * 暴露给渲染进程的桌面 API 类型契约（单一源）。
 *
 * 任何 channel 新增 / 重命名 / 删除，必须同步修改：
 *   - src/preload/index.ts  (实际实现 + contextBridge 暴露)
 *   - src/main/ipc.ts       (ipcMain.handle 注册)
 *   - src/shared/ipc-types.ts (channel 名)
 *   - 本文件                  (类型形状)
 */
export interface DesktopPingApi {
  ping: (payload?: PingRequest) => Promise<PongResponse>
}

export interface DesktopAuthApi {
  /**
   * 用户名/邮箱 + 密码登录。
   * 成功：返回 { expiresAt, user }，access_token 进主进程内存，refresh_token 进 safeStorage。
   *   - 注意：refresh_token 永不出主进程；expiresAt 来自 JWT exp claim
   * 失败：返回 AuthErrorPayload（不抛）。
   */
  login: (payload: LoginRequest) => Promise<
    { success: true; data: { expiresAt: number; user: UserInfo } } | { success: false; error: AuthErrorPayload }
  >

  /**
   * 登出（清内存 access_token + safeStorage 中密文 + electron-store 中 user）。
   * 永远返回 success（幂等）。
   */
  logout: () => Promise<{ success: true }>

  /**
   * 应用启动时尝试恢复 session：
   *   - 从 electron-store 取密文 → safeStorage.decryptString 还原 refresh_token
   *   - 调后端 /auth/refresh 拿新 access_token
   *   - 调后端 /auth/me 拉最新 user
   *   - 成功：返回 expiresAt + user；失败：返回 null
   * 任何异常都返回 null，renderer 清空 Pinia state。
   */
  restore: () => Promise<AuthRestoreResult | null>

  /**
   * 方便前端展示"当前连哪个后端"——主要是开发/调试用。
   */
  getBackendUrl: () => Promise<string>
}

/**
 * IPC API Gateway —— 所有需要鉴权的业务请求都走这条。
 *
 * 任何 renderer 想调后端的鉴权 endpoint（如 /api/v1/tasks）都必须经此：
 *   window.api.api.request({ method, path, body, query })
 *
 * 主进程:
 *   1. 注入 Bearer access_token (主进程内存里)
 *   2. 调后端
 *   3. 收到 401 → 单飞 refresh → 用新 token 重试一次
 *      - refresh 失败 → 整个 session 强制 re-login (renderer 跳 /login)
 *   4. 响应归一化为 { ok, data, error }
 */
export interface ApiRequestPayload {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** 后端 endpoint 路径，例如 "/tasks"。不含 baseURL，baseURL 由 main 决定。 */
  path: string
  /** JSON body (POST/PUT/PATCH) 或 undefined (GET/DELETE). */
  body?: unknown
  /** query string 对象（GET 常用）。 */
  query?: Record<string, string | number | boolean>
  /** request timeout ms. 默认 15000. */
  timeoutMs?: number
}

export interface ApiError {
  code: 'INVALID_INPUT' | 'UNAUTHORIZED' | 'TOKEN_EXPIRED' | 'USER_DISABLED' | 'FORBIDDEN' | 'NOT_FOUND' | 'RATE_LIMITED' | 'SERVER_ERROR' | 'NETWORK_ERROR' | 'INVALID_RESPONSE' | 'UNKNOWN_ERROR' | 'NO_ACTIVE_SESSION' | string
  message: string
  status?: number
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError }

export interface DesktopApiGatewayApi {
  request: <T = unknown>(payload: ApiRequestPayload) => Promise<ApiResult<T>>
}

/**
 * Session 失效广播 (Phase 2-Impl-1)。
 * main 进程在以下情况向所有 renderer 广播:
 *   - 单飞 refresh 全部失败 → 强制清场 → 推 auth:session-expired
 *   - 用户禁用 / token 主动 revoke
 *
 * renderer 通过 window.api.onSessionExpired(cb) 订阅。
 * cb 内典型操作: authStore.onSessionExpired() + router.push('/login')
 */
export interface DesktopSessionApi {
  onSessionExpired: (cb: () => void) => void
}

export interface DesktopApi extends DesktopPingApi {
  auth: DesktopAuthApi
  api: DesktopApiGatewayApi
  session: DesktopSessionApi
  // Phase 2+ expand here (task / knowledge / meeting / ...)
}

// Marker module — runtime unused; only for namespace clarity.
export const PRELOAD_API_NAMESPACE = 'microbubble-desktop' as const
