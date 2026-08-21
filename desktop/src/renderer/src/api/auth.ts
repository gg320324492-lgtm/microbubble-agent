// auth API 入口（renderer 端统一封装）。
//
// 设计原则：
// - 全部走 IPC 委托主进程 auth.service，避免 access_token 漂移到 renderer 内存
//   （login/restore 由 main 调后端拿，renderer 仅看 success/failure + profile）
// - 业务模块未来需要的"取 access_token 调普通 API"由 Phase 2+ 提供
//   window.api.auth.getAccessToken()，本文件不重复实现
//
// 注意：本文件不直接 import axios，因为不走 renderer->backend 直接调用。

import type { LoginRequest, UserProfile, AuthRestoreResult } from '@shared/auth-types'

/**
 * 调 window.api.auth.login 返回结构化结果。
 * 主进程已吃掉所有 token——renderer 拿不到 refresh_token，只能拿到 expiresIn + profile。
 *
 * 返回类型与 main 一致：success / error 二分。
 */
export async function login(
  payload: LoginRequest
): Promise<
  | { success: true; data: { expiresIn: number; profile: UserProfile } }
  | { success: false; error: { code: string; message: string; status?: number } }
> {
  return window.api.auth.login(payload) as Promise<
    | { success: true; data: { expiresIn: number; profile: UserProfile } }
    | { success: false; error: { code: string; message: string; status?: number } }
  >
}

/**
 * 登出。仅返回 success。
 */
export async function logout(): Promise<{ success: true }> {
  return window.api.auth.logout()
}

/**
 * 应用启动时尝试恢复 session。
 * 任何失败均返回 null，由调用方清空 state。
 */
export async function restore(): Promise<AuthRestoreResult | null> {
  return window.api.auth.restore()
}

/**
 * 拿到当前后端 baseURL（调试 / 设置页可见）。
 */
export async function getBackendUrl(): Promise<string> {
  return window.api.auth.getBackendUrl()
}
