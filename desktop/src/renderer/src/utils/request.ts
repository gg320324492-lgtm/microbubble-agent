// 统一请求封装（仅非鉴权 endpoint 用）。
//
// 鉴权 endpoint 必须走 window.api.api.request（主进程 API Gateway）。
// 本文件保留给 renderer 调公开 endpoint 时的便利方法。
//
// 严禁：
// - 在任何地方写入 / 读取 Authorization header
// - 持有 access_token / refresh_token

import client from '../api/client'
import { AxiosError } from 'axios'
import type { AxiosResponse } from 'axios'

export class HttpError extends Error {
  readonly code: string
  readonly status: number
  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'HttpError'
    this.code = code
    this.status = status
  }
}

function normalizeError(err: unknown): never {
  if (err instanceof AxiosError) {
    const status = err.response?.status ?? 0
    const body = err.response?.data
    const detail =
      typeof body === 'object' && body !== null && 'detail' in body
        ? (body as { detail?: string | unknown[] }).detail
        : undefined
    const message = typeof detail === 'string' ? detail : err.message
    let code: string
    if (status === 401) code = 'UNAUTHORIZED'
    else if (status === 403) code = 'FORBIDDEN'
    else if (status === 404) code = 'NOT_FOUND'
    else if (status === 429) code = 'RATE_LIMITED'
    else if (status >= 500) code = 'SERVER_ERROR'
    else if (status === 0) code = 'NETWORK_ERROR'
    else code = 'HTTP_ERROR'
    throw new HttpError(status, code, message ?? err.message)
  }
  throw new HttpError(0, 'UNKNOWN_ERROR', String(err))
}

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  try {
    const res: AxiosResponse<T> = await client.get(url, { params })
    return res.data
  } catch (err) {
    return normalizeError(err)
  }
}

export async function post<T>(url: string, body?: unknown): Promise<T> {
  try {
    const res: AxiosResponse<T> = await client.post(url, body)
    return res.data
  } catch (err) {
    return normalizeError(err)
  }
}

export async function patch<T>(url: string, body?: unknown): Promise<T> {
  try {
    const res: AxiosResponse<T> = await client.patch(url, body)
    return res.data
  } catch (err) {
    return normalizeError(err)
  }
}

export async function del<T>(url: string): Promise<T> {
  try {
    const res: AxiosResponse<T> = await client.delete(url)
    return res.data
  } catch (err) {
    return normalizeError(err)
  }
}
