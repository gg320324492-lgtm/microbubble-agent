// 后端 URL 等配置常量（main / preload / renderer 共享）。
// 修改本文件必须同步 verify 三方 import。

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

function ensureDir(path: string): string {
  if (!existsSync(path)) mkdirSync(path, { recursive: true })
  return path
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
    backendUrl: 'https://agent.mnb-lab.cn/api/v1',
    appName: 'MicroBubble Desktop',
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

// 进程级常量(供不需要 IO 的模块快速读取).
export const APP_CONFIG = {
  backendUrl: 'https://agent.mnb-lab.cn/api/v1',
  appName: 'MicroBubble Desktop',
  appVersion: '0.1.0',
  environment: 'development' as AppEnvironment,
  dataDir: '',
  logDir: '',
  cacheDir: '',
  isDemo: false,
  windowMinWidth: 1024,
  windowMinHeight: 640
} as const

export const APP_DEMO_WARNING = '演示数据 · 非真实实验结果'

