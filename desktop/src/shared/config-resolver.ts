// Shared config resolver — Phase 8-M1-B
// 渲染层 + 主进程都能访问的纯函数 resolveAppConfig (不依赖 electron.app, 避免渲染进程崩溃)

import { existsSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'
import type { AppConfigShape, AppEnvironment } from './config'

const APP_FALLBACK: AppConfigShape = {
  backendUrl: 'https://agent.mnb-lab.cn/api/v1',
  appName: 'Scientific Research OS',
  appVersion: '0.1.0',
  environment: 'development',
  dataDir: '',
  logDir: '',
  cacheDir: '',
  isDemo: false,
  windowMinWidth: 1024,
  windowMinHeight: 640
}

function ensureDir(path: string): string {
  if (!existsSync(path)) mkdirSync(path, { recursive: true })
  return path
}

/**
 * 跨主进程 / 渲染进程 / 测试环境通用的解析.
 * 主进程通过 electron.app.getPath('userData') 解析, 渲染进程通过环境变量 fallback.
 */
export function resolveAppConfig(): AppConfigShape {
  let baseUserData = process.env['MICROBUBBLE_USER_DATA'] ?? ''
  if (!baseUserData) {
    try {
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
    backendUrl: 'https://agent.mnb-lab.cn/api/v1',
    appName: 'Scientific Research OS',
    appVersion: '0.1.0',
    environment: (process.env['NODE_ENV'] as AppEnvironment) || (process.env['MICROBUBBLE_PROD'] === '1' ? 'production' : 'development'),
    dataDir,
    logDir,
    cacheDir,
    isDemo: process.env['MICROBUBBLE_DEMO'] === '1',
    windowMinWidth: 1024,
    windowMinHeight: 640
  }
}

export { APP_FALLBACK }
export type { AppConfigShape, AppEnvironment }