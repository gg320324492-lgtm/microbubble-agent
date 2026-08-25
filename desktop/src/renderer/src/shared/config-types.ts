// shared/config-types.ts — 仅类型声明, 渲染进程可引用.
// 完整实现见 src/shared/config.ts (含 electron app 引用, 仅 main 进程).
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

export const APP_DEMO_WARNING = '演示数据 · 非真实实验结果'
