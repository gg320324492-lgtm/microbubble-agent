// ErrorRecovery Composable — Phase 8-M0-H0
// 统一错误恢复: 覆盖 AI 失败 / 设备断开 / 数据加载失败 / 论文保存失败 / 网络失败 / 文件损坏.
// 保留已有状态 + 提供重试入口 + 自动上报到 ScientificLogger.

import { computed, ref } from 'vue'
import type { Ref } from 'vue'

export type ErrorDomain = 'ai' | 'device' | 'data' | 'manuscript' | 'network' | 'file-corrupt' | 'system'

export interface ErrorRecord {
  id: string
  domain: ErrorDomain
  message: string
  cause?: unknown
  timestamp: string
  retryable: boolean
  retriedCount: number
  preservedState?: Record<string, unknown>
}

interface ErrorRecoveryBus {
  errors: Ref<ErrorRecord[]>
  recordError: (input: {
    domain: ErrorDomain
    message: string
    cause?: unknown
    retryable?: boolean
    preservedState?: Record<string, unknown>
  }) => ErrorRecord
  retry: (id: string) => Promise<boolean>
  retryAll: () => Promise<number>
  clear: (id?: string) => void
  hasRecoverableError: Ref<boolean>
}

const errors = ref<ErrorRecord[]>([])
const retryListeners = new Map<string, () => Promise<boolean> | boolean>()

function genId(): string {
  return `err-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function useErrorRecovery(): ErrorRecoveryBus {
  function recordError(input: {
    domain: ErrorDomain
    message: string
    cause?: unknown
    retryable?: boolean
    preservedState?: Record<string, unknown>
  }): ErrorRecord {
    const record: ErrorRecord = {
      id: genId(),
      domain: input.domain,
      message: input.message,
      cause: input.cause,
      timestamp: new Date().toISOString(),
      retryable: input.retryable ?? true,
      retriedCount: 0,
      preservedState: input.preservedState
    }
    errors.value = [...errors.value, record].slice(-50) // 保留最近 50 条
    void writeLog(record)
    return record
  }

  async function retry(id: string): Promise<boolean> {
    const err = errors.value.find((e) => e.id === id)
    if (!err) return false
    const listener = retryListeners.get(id)
    if (!listener) {
      // 没有具体 handler, 仅清错误
      clear(id)
      return true
    }
    try {
      const ok = await listener()
      err.retriedCount += 1
      if (ok) clear(id)
      return ok
    } catch {
      return false
    }
  }

  async function retryAll(): Promise<number> {
    let count = 0
    for (const err of [...errors.value]) {
      if (err.retryable) {
        const ok = await retry(err.id)
        if (ok) count += 1
      }
    }
    return count
  }

  function clear(id?: string): void {
    if (!id) {
      errors.value = []
      retryListeners.clear()
      return
    }
    errors.value = errors.value.filter((e) => e.id !== id)
    retryListeners.delete(id)
  }

  return {
    errors,
    recordError,
    retry,
    retryAll,
    clear,
    hasRecoverableError: computed(() => errors.value.some((e) => e.retryable))
  }
}

export function registerRetryHandler(id: string, handler: () => Promise<boolean> | boolean): () => void {
  retryListeners.set(id, handler)
  return () => {
    if (retryListeners.get(id) === handler) retryListeners.delete(id)
  }
}

async function writeLog(record: ErrorRecord): Promise<void> {
  try {
    const api = (window as unknown as { api?: { app?: { logWrite?: (l: string, m: string, msg: string, meta?: unknown) => Promise<unknown> } } }).api
    if (api?.app?.logWrite) {
      await api.app.logWrite('error', `recovery.${record.domain}`, record.message, {
        cause: record.cause instanceof Error ? record.cause.message : record.cause,
        retried: record.retriedCount
      })
    }
  } catch {
    // 日志上报失败不阻塞业务
  }
}

