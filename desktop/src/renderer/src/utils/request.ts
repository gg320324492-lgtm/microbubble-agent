// 统一请求封装：get / post / patch / delete。
//
// 业务模块统一从这里调，而不是直接 axios。
// 所有 401/429/5xx 错误归一化为普通 Error，message 由错误码转换。

import client from '../api/client'
import { AxiosError } from 'axios'
import type { AxiosResponse } from 'axios'

/** HTTP 错误归一化（与 main auth.service.ts 的 AuthErrorPayload 形状对齐）。 */
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
