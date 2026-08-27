// 后端 URL 等配置常量（main / preload / renderer 共享）。
// 修改本文件必须同步 verify 三方 import。
//
// [类 20.191] 2026-08-27:
// - backendUrl 加 MICROBUBBLE_BACKEND_URL env 覆盖路径 (默认仍是 agent.mnb-lab.cn/api/v1)
// - 删重复文件 config-resolver.ts 的 resolveAppConfig 副本 (已合并到本文件)

import { existsSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'

export type AppEnvironment = 'development' | 'staging' | 'production'

export interface AppConfigShape {
  backendUrl: string
  appName: string
  appVersion: string
  environment: AppEnvironment
  dataDir: string
  logDir: string
  isDemo: boolean
  cacheDir: string
  windowMinWidth: number
  windowMinHeight: number
}

/** [类 20.191] 默认 backend URL. 可通过 MICROBUBBLE_BACKEND_URL env 覆盖 (staging/dev 部署用). */
const DEFAULT_BACKEND_URL = 'https://agent.mnb-lab.cn/api/v1'
const APP_NAME = 'MicroBubble Desktop'
const APP_VERSION = '0.1.0'
const WINDOW_MIN_WIDTH = 1024
const WINDOW_MIN_HEIGHT = 640

function ensureDir(path: string): string {
  if (!existsSync(path)) mkdirSync(path, { recursive: true })
  return path
}

function resolveBackendUrl(): string {
  return process.env['MICROBUBBLE_BACKEND_URL']?.trim() || DEFAULT_BACKEND_URL
}

function resolveEnvironment(): AppEnvironment {
  const env = process.env['NODE_ENV'] as AppEnvironment | undefined
  if (env === 'development' || env === 'staging' || env === 'production') return env
  return process.env['MICROBUBBLE_PROD'] === '1' ? 'production' : 'development'
}

/**
 * 计算 Electron userData 子目录, 并保证目录存在.
 * 必须在 app.whenReady() 之后调用以访问 app.getPath('userData').
 * 渲染进程使用默认值即可 (主进程通过 IPC 注入真实路径).
 */
export function resolveAppConfig(): AppConfigShape {
  let baseUserData = process.env['MICROBUBBLE_USER_DATA'] ?? ''
  if (!baseUserData) {
    try {
      // 仅 main 进程能 require('electron').app
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const { app } = require('electron') as typeof import('electron')
      baseUserData = app.getPath('userData')
    } catch {
      baseUserData = join(process.cwd(), '.microbubble-data')
    }
  }
  const dataDir = ensureDir(join(baseUserData, 'data'))
  const logDir = ensureDir(join(baseUserData, 'logs'))
  const cacheDir = ensureDir(join(baseUserData, 'cache'))
  return {
    backendUrl: resolveBackendUrl(),
    appName: APP_NAME,
    appVersion: APP_VERSION,
    environment: resolveEnvironment(),
    dataDir,
    logDir,
    cacheDir,
    isDemo: process.env['MICROBUBBLE_DEMO'] === '1',
    windowMinWidth: WINDOW_MIN_WIDTH,
    windowMinHeight: WINDOW_MIN_HEIGHT
  }
}

// 进程级常量(供不需要 IO 的模块快速读取).
// [类 20.191] backendUrl 现在用 resolveBackendUrl() 而非 hardcode.
export const APP_CONFIG = {
  backendUrl: resolveBackendUrl(),
  appName: APP_NAME,
  appVersion: APP_VERSION,
  environment: resolveEnvironment(),
  dataDir: '',
  logDir: '',
  cacheDir: '',
  isDemo: process.env['MICROBUBBLE_DEMO'] === '1',
  windowMinWidth: WINDOW_MIN_WIDTH,
  windowMinHeight: WINDOW_MIN_HEIGHT
} as const

export const APP_DEMO_WARNING = '演示数据 · 非真实实验结果'
