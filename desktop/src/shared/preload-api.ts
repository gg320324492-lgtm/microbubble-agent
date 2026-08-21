// 暴露给渲染进程的桌面 API 类型契约（单一源）。

import type {
  LoginRequest,
  UserProfile,
  AuthRestoreResult,
  AuthErrorPayload
} from './auth-types'

export interface PingRequest {
  message?: string
}

export interface PongResponse {
  success: boolean
  message: 'pong'
  timestamp: number
  echo?: string
}

/**
 * auth namespace —— Phase 1 实施；Phase 2+ 业务模块按需加。
 * 任何 channel 新增 / 重命名 / 删除，必须同步修改：
 *   - src/preload/index.ts  (实际实现 + contextBridge 暴露)
 *   - src/main/ipc.ts       (ipcMain.handle 注册)
 *   - src/shared/ipc-types.ts (channel 名)
 *   - 本文件                  (类型形状)
 */
export interface DesktopAuthApi {
  /**
   * 用户名/邮箱 + 密码登录。
   * 成功：返回 { expiresIn, profile }，access_token 进内存，refresh_token 进 safeStorage。
   *   - 注意：refresh_token 永不出主进程，renderer 不应也不需要拿到
   * 失败：返回 AuthErrorPayload（不抛）。
   */
  login: (payload: LoginRequest) => Promise<
    { success: true; data: { expiresIn: number; profile: UserProfile } } | { success: false; error: AuthErrorPayload }
  >

  /**
   * 登出（清内存 access_token + safeStorage 中密文 + electron-store 中 profile）。
   * 永远返回 success（幂等）。
   */
  logout: () => Promise<{ success: true }>

  /**
   * 应用启动时尝试恢复 session：
   *   - 从 electron-store 取密文 → safeStorage.decryptString 还原 refresh_token
   *   - 调后端 /api/v1/auth/me 验 refresh_token 有效性
   *   - 有效：返回 tokenPair + profile；无效：返回 null
   * 任何异常都返回 null，renderer 清空 Pinia state。
   */
  restore: () => Promise<AuthRestoreResult | null>

  /**
   * 方便前端展示"当前连哪个后端"——主要是开发/调试用。
   */
  getBackendUrl: () => Promise<string>
}

export interface DesktopApi {
  ping: (payload?: PingRequest) => Promise<PongResponse>
  auth: DesktopAuthApi
  // Phase 2+ expand here
}
