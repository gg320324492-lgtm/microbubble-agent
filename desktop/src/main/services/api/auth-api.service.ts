// auth-api service —— auth 业务 endpoint 高层封装（不走 login/logout/restore, 走鉴权业务）。
//
// login/logout/restore 在 auth.service.ts (vault + token 主权)。
// 这里只封装 post-login 的用户档案操作: GET /auth/me, PUT /auth/profile,
// POST /auth/change-password, POST /auth/reset-password 等。
//
// 全部走 api.service.request —— 主进程自动注入 Bearer + 单飞 refresh。

import type {
  UserInfo,
  ProfileUpdateRequest,
  ChangePasswordRequest,
  ResetPasswordRequest
} from '@shared/auth-types'
import type { ApiResult } from '@shared/preload-api'
import { apiService } from './api.service'

export async function getMe(): Promise<ApiResult<UserInfo>> {
  return apiService.request<UserInfo>({
    method: 'GET',
    path: '/auth/me'
  })
}

export async function updateProfile(req: ProfileUpdateRequest): Promise<ApiResult<UserInfo>> {
  return apiService.request<UserInfo>({
    method: 'PUT',
    path: '/auth/profile',
    body: req
  })
}

export async function changePassword(req: ChangePasswordRequest): Promise<ApiResult<{ message: string }>> {
  return apiService.request<{ message: string }>({
    method: 'POST',
    path: '/auth/change-password',
    body: req
  })
}

export async function resetPassword(req: ResetPasswordRequest): Promise<ApiResult<{ message: string }>> {
  return apiService.request<{ message: string }>({
    method: 'POST',
    path: '/auth/reset-password',
    body: req
  })
}

export async function initPassword(req: ChangePasswordRequest): Promise<ApiResult<{ message: string }>> {
  return apiService.request<{ message: string }>({
    method: 'POST',
    path: '/auth/init-password',
    body: req
  })
}

export const authApiService = {
  getMe,
  updateProfile,
  changePassword,
  resetPassword,
  initPassword
}
