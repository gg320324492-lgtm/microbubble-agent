// window.api 形状声明 — renderer 侧全局类型（与 preload/index.ts 实现严格同步）
import type { AppInfo, AuthSession, LocalUser } from './types'

export interface PreloadApi {
  app: {
    info(): Promise<AppInfo>
  }
  auth: {
    status(): Promise<{ userCount: number }>
    registerAdmin(p: { username: string; displayName?: string; password: string }): Promise<AuthSession>
    login(p: { username: string; password: string }): Promise<AuthSession>
    restore(): Promise<AuthSession | null>
    logout(): Promise<void>
  }
  settings: {
    get(key: string): Promise<unknown>
    set(key: string, value: unknown): Promise<void>
  }
  window: {
    minimize(): Promise<void>
    toggleMaximize(): Promise<void>
    close(): Promise<void>
  }
}

declare global {
  interface Window {
    api: PreloadApi
  }
}

export interface WindowWithApi extends Window {
  api: PreloadApi
}

export type { LocalUser, AuthSession, AppInfo }
