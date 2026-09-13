// window.api 形状声明 — renderer 侧全局类型（与 preload/index.ts 实现严格同步）
import type { AppInfo, AuthSession, ChatMessage, ChatSession, LocalUser } from './types'

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
  chat: {
    sessionsList(): Promise<ChatSession[]>
    sessionCreate(title?: string): Promise<ChatSession>
    sessionRename(id: string, title: string): Promise<void>
    sessionDelete(id: string): Promise<void>
    messagesList(sessionId: string): Promise<ChatMessage[]>
    send(sessionId: string, content: string): Promise<{ userMessage: ChatMessage; assistantMessage: ChatMessage }>
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

export type { LocalUser, AuthSession, AppInfo, ChatSession, ChatMessage }
