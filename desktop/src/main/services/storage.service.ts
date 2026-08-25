// Electron 持久化 storage 的统一抽象层（main 进程使用）。
//
// 设计原则：
// - 仅存密文（refresh_token）+ 非敏感 user，access_token 永不入库
// - 应用根目录 + userData 模式（不同 OS 不同路径）
// - 加密文件位于 OS 用户配置目录，Win 路径示例：
//   %APPDATA%/microbubble-desktop/config.json
//
// 详见 docs/desktop-conversion/security.md §Token 未来存储原则

import Store from 'electron-store'
import { promises as fsp, existsSync, mkdirSync, appendFileSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { APP_CONFIG, resolveAppConfig } from '@shared/config'
import type { UserInfo } from '@shared/user-info'

type StoreSchema = {
  // safeStorage 加密后的 refresh_token（base64 字符串）
  refresh_token_cipher?: string
  // 后端返回的 user（非敏感信息；access_token + refresh_token 不在这里）
  user?: UserInfo
  // 后端 URL（开发阶段可能调整，记录最后一次连的后端）
  last_backend_url?: string
}

const store = new Store<StoreSchema>({
  name: 'microbubble-desktop-config',
  defaults: {},
  encryptionKey: undefined
})

/** 存 refresh_token 密文（base64 字符串）。 */
export function setRefreshTokenCipher(cipher: string): void {
  store.set('refresh_token_cipher', cipher)
}

/** 取 refresh_token 密文；不存在时返回 undefined。 */
export function getRefreshTokenCipher(): string | undefined {
  return store.get('refresh_token_cipher')
}

/** 清所有 auth 相关 state（密文 + user + last_backend_url）。幂等。 */
export function clearAuthState(): void {
  store.delete('refresh_token_cipher')
  store.delete('user')
  store.delete('last_backend_url')
}

/** 存 user（非敏感信息）。 */
export function setUser(user: UserInfo): void {
  store.set('user', user)
}

/** 取 user；不存在时返回 undefined。 */
export function getUser(): UserInfo | undefined {
  return store.get('user')
}

/** 存最近一次连的后端 URL（仅供调试 / 设置页可见）。 */
export function setLastBackendUrl(url: string): void {
  store.set('last_backend_url', url)
}

/** 调试用：返回完整 store 路径。 */
export function getStorePath(): string {
  return store.path
}

export { APP_CONFIG }

// ============ Phase 8-M0-H0: LocalPersistenceAdapter + ScientificLogger ============

/**
 * 本地数据持久化适配器. 与 Store(view state) 解耦, 仅负责跨会话 Recovery.
 * 用途: project 元数据, workspace 视图恢复, 用户偏好 (侧栏折叠 / 主题等).
 *
 * 设计: 单一 JSON 文件 per namespace, 写入 dataDir 目录.
 */
class LocalPersistenceAdapter {
  private cache = new Map<string, Map<string, unknown>>()
  private initialized = false

  private async ensureInit(): Promise<void> {
    if (this.initialized) return
    const cfg = resolveAppConfig()
    if (!existsSync(cfg.dataDir)) mkdirSync(cfg.dataDir, { recursive: true })
    this.initialized = true
  }

  private fileFor(namespace: string): string {
    const cfg = resolveAppConfig()
    return join(cfg.dataDir, `${namespace}.json`)
  }

  async save(namespace: string, key: string, value: unknown): Promise<void> {
    await this.ensureInit()
    let bucket = this.cache.get(namespace)
    if (!bucket) {
      bucket = new Map<string, unknown>()
      this.cache.set(namespace, bucket)
    }
    bucket.set(key, value)
    const filePath = this.fileFor(namespace)
    const snapshot = Object.fromEntries(bucket.entries())
    await fsp.writeFile(filePath, JSON.stringify(snapshot, null, 2), 'utf8')
  }

  load<T = unknown>(namespace: string, key: string): T | undefined {
    if (this.cache.has(namespace)) {
      return this.cache.get(namespace)!.get(key) as T | undefined
    }
    const filePath = this.fileFor(namespace)
    if (!existsSync(filePath)) return undefined
    try {
      const raw = readFileSync(filePath, 'utf8')
      const parsed = JSON.parse(raw) as Record<string, unknown>
      const bucket = new Map<string, unknown>(Object.entries(parsed))
      this.cache.set(namespace, bucket)
      return bucket.get(key) as T | undefined
    } catch {
      return undefined
    }
  }

  async remove(namespace: string, key: string): Promise<void> {
    await this.ensureInit()
    const bucket = this.cache.get(namespace)
    if (!bucket) return
    bucket.delete(key)
    const filePath = this.fileFor(namespace)
    const snapshot = Object.fromEntries(bucket.entries())
    await fsp.writeFile(filePath, JSON.stringify(snapshot, null, 2), 'utf8')
  }
}

export const persistence = new LocalPersistenceAdapter()

/**
 * 结构化科研日志. 输出到 logDir/<date>.log (每日 rotate).
 * 格式: { timestamp, level, module, message, metadata? }
 *
 * 支持 4 个预设 stream:
 *   - ai: AI 对话/推理/工具调用
 *   - experiment: 实验变量/数据点/状态变更
 *   - device: 设备连接/数据采集/错误
 *   - error: 全局错误捕获 (UI 异常 + IPC 异常)
 */
export type LogLevel = 'info' | 'warn' | 'error' | 'debug'

export interface LogEntry {
  timestamp: string
  level: LogLevel
  module: string
  message: string
  metadata?: unknown
}

class ScientificLogger {
  private maxTail = 500

  private fileForToday(): string {
    const cfg = resolveAppConfig()
    const date = new Date().toISOString().slice(0, 10)
    return join(cfg.logDir, `${date}.log`)
  }

  write(level: LogLevel, module: string, message: string, metadata?: unknown): void {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      module,
      message,
      metadata
    }
    try {
      appendFileSync(this.fileForToday(), JSON.stringify(entry) + '\n', 'utf8')
    } catch {
      // 日志写入失败不阻塞业务; UI 层 tail() 仍可显示内存缓冲
    }
  }

  tail(lines: number = 100): LogEntry[] {
    const filePath = this.fileForToday()
    if (!existsSync(filePath)) return []
    try {
      const raw = readFileSync(filePath, 'utf8')
      const all = raw.split('\n').filter(Boolean).map((line) => {
        try { return JSON.parse(line) as LogEntry } catch { return null }
      }).filter((entry): entry is LogEntry => entry !== null)
      const slice = all.slice(-Math.min(lines, this.maxTail))
      return slice
    } catch {
      return []
    }
  }

  ai(module: string, message: string, metadata?: unknown): void { this.write('info', `ai.${module}`, message, metadata) }
  experiment(module: string, message: string, metadata?: unknown): void { this.write('info', `experiment.${module}`, message, metadata) }
  device(module: string, message: string, metadata?: unknown): void { this.write('info', `device.${module}`, message, metadata) }
  error(module: string, message: string, metadata?: unknown): void { this.write('error', `error.${module}`, message, metadata) }
  info(module: string, message: string, metadata?: unknown): void { this.write('info', module, message, metadata) }
  warn(module: string, message: string, metadata?: unknown): void { this.write('warn', module, message, metadata) }
  debug(module: string, message: string, metadata?: unknown): void { this.write('debug', module, message, metadata) }
}

export const logger = new ScientificLogger()

